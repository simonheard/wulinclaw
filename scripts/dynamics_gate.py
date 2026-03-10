#!/usr/bin/env python3
import argparse
import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Dict, Tuple

import yaml


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "state" / "dynamics.db"
GLOBAL_CFG_PATH = ROOT / "chat_dynamics.default.json"
AGENTS_DIR = ROOT / "agents"


def ensure_db(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_state (
          agent_id TEXT PRIMARY KEY,
          desire REAL NOT NULL,
          updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_seen (
          event_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          PRIMARY KEY (event_id, agent_id, kind)
        )
        """
    )
    conn.commit()


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_global_cfg(global_cfg: Path) -> dict:
    return json.loads(global_cfg.read_text(encoding="utf-8"))


def load_agent_profile(agent_id: str, agents_dir: Path) -> dict:
    files = list(agents_dir.glob("*.yaml"))
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if data.get("id") == agent_id:
            return data
    raise FileNotFoundError(f"agent id not found: {agent_id}")


def effective_cfg(global_cfg: dict, agent_profile: dict) -> dict:
    return deep_merge(global_cfg, agent_profile.get("dynamics_override", {}))


def match_interest(agent_profile: dict, text: str) -> str:
    text_l = text.lower()
    interests = agent_profile.get("interests", {})
    for lvl in ("high", "mid", "low"):
        kws = interests.get(lvl, []) or []
        for kw in kws:
            if str(kw).lower() in text_l:
                return lvl
    return "low"


def get_desire(conn: sqlite3.Connection, agent_id: str) -> float:
    row = conn.execute("SELECT desire FROM agent_state WHERE agent_id = ?", (agent_id,)).fetchone()
    if not row:
        now = time.time()
        conn.execute(
            "INSERT INTO agent_state(agent_id, desire, updated_at) VALUES(?,?,?)",
            (agent_id, 0.05, now),
        )
        return 0.05
    return float(row[0])


def set_desire(conn: sqlite3.Connection, agent_id: str, desire: float):
    now = time.time()
    conn.execute(
        """
        INSERT INTO agent_state(agent_id, desire, updated_at)
        VALUES(?,?,?)
        ON CONFLICT(agent_id) DO UPDATE SET desire=excluded.desire, updated_at=excluded.updated_at
        """,
        (agent_id, desire, now),
    )


def get_all_desires(conn: sqlite3.Connection) -> Dict[str, float]:
    rows = conn.execute("SELECT agent_id, desire FROM agent_state").fetchall()
    return {r[0]: float(r[1]) for r in rows}


def mark_seen(conn: sqlite3.Connection, event_id: str, agent_id: str, kind: str):
    conn.execute(
        "INSERT OR IGNORE INTO event_seen(event_id, agent_id, kind) VALUES(?,?,?)",
        (event_id, agent_id, kind),
    )


def is_seen(conn: sqlite3.Connection, event_id: str, agent_id: str, kind: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM event_seen WHERE event_id=? AND agent_id=? AND kind=?",
        (event_id, agent_id, kind),
    ).fetchone()
    return row is not None


def decide(args):
    global_cfg = load_global_cfg(Path(args.global_cfg))
    profile = load_agent_profile(args.agent, Path(args.agents_dir))
    cfg = effective_cfg(global_cfg, profile)

    dbp = Path(args.db)
    dbp.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(dbp), timeout=5)
    conn.isolation_level = None
    ensure_db(conn)

    clamp_min = cfg.get("clamp", {}).get("min", 0)
    clamp_max = cfg.get("clamp", {}).get("max", 1)

    interest = args.interest_level or match_interest(profile, args.text)

    conn.execute("BEGIN IMMEDIATE")
    desire_before = get_desire(conn, args.agent)
    desire = desire_before
    reasons = []

    if args.speaker_type == "user":
        if args.event_id and not is_seen(conn, args.event_id, args.agent, "user_recover"):
            # cold start
            cold = cfg.get("cold_start", {})
            if cold.get("enabled", True):
                all_des = get_all_desires(conn)
                if not all_des:
                    all_des = {args.agent: desire}
                low_th = float(cold.get("group_low_threshold", 0.18))
                low_ratio_need = float(cold.get("group_low_ratio", 0.66))
                low_ratio = sum(1 for v in all_des.values() if v < low_th) / max(1, len(all_des))
                if low_ratio >= low_ratio_need:
                    desire += float(cold.get("boost_value", 0.35))
                    reasons.append("cold_start_boost")

            rec_map = cfg.get("recover_by_user", {})
            desire += float(rec_map.get(f"{interest}_interest", 0.06))
            reasons.append(f"recover_user:{interest}")
            mark_seen(conn, args.event_id, args.agent, "user_recover")

    elif args.speaker_type == "bot":
        if args.speaker_agent and args.speaker_agent == args.agent:
            # self-ignore
            conn.execute("COMMIT")
            print(json.dumps({
                "allow": False,
                "reason": "self_ignore",
                "interest": interest,
                "desire_before": desire_before,
                "desire_after": desire_before,
                "p": 0.0,
            }, ensure_ascii=False))
            return

        if args.event_id and not is_seen(conn, args.event_id, args.agent, "bot_passive_drop"):
            drop_other = cfg.get("drop_other_speak", {})
            desire -= float(drop_other.get(f"{interest}_interest", 0.04))
            reasons.append(f"drop_other:{interest}")
            mark_seen(conn, args.event_id, args.agent, "bot_passive_drop")

    desire = clamp(desire, clamp_min, clamp_max)
    p = float(cfg.get("global_pace", 0.62)) * desire
    p = clamp(p, 0.0, 1.0)

    allow = False
    if desire >= float(cfg.get("desire_min_to_speak", 0.12)):
        rng = random.Random(args.seed) if args.seed is not None else random
        allow = rng.random() < p

    set_desire(conn, args.agent, desire)
    conn.execute("COMMIT")

    print(json.dumps({
        "allow": allow,
        "reason": ",".join(reasons) if reasons else "none",
        "interest": interest,
        "desire_before": round(desire_before, 4),
        "desire_after": round(desire, 4),
        "p": round(p, 4),
    }, ensure_ascii=False))


def apply_speak(args):
    global_cfg = load_global_cfg(Path(args.global_cfg))
    profile = load_agent_profile(args.agent, Path(args.agents_dir))
    cfg = effective_cfg(global_cfg, profile)

    dbp = Path(args.db)
    dbp.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(dbp), timeout=5)
    conn.isolation_level = None
    ensure_db(conn)

    clamp_min = cfg.get("clamp", {}).get("min", 0)
    clamp_max = cfg.get("clamp", {}).get("max", 1)

    interest = args.interest_level or "mid"

    conn.execute("BEGIN IMMEDIATE")
    if args.event_id and is_seen(conn, args.event_id, args.agent, "self_speak_drop"):
        desire = get_desire(conn, args.agent)
        conn.execute("COMMIT")
        print(json.dumps({"ok": True, "dedup": True, "desire": round(desire, 4)}, ensure_ascii=False))
        return

    desire_before = get_desire(conn, args.agent)
    drop_self = cfg.get("drop_self_speak", {})
    desire = desire_before - float(drop_self.get(f"{interest}_interest", 0.11))
    desire = clamp(desire, clamp_min, clamp_max)
    set_desire(conn, args.agent, desire)

    if args.event_id:
        mark_seen(conn, args.event_id, args.agent, "self_speak_drop")

    conn.execute("COMMIT")
    print(json.dumps({
        "ok": True,
        "desire_before": round(desire_before, 4),
        "desire_after": round(desire, 4),
        "interest": interest,
    }, ensure_ascii=False))


def status(args):
    conn = sqlite3.connect(str(args.db), timeout=5)
    ensure_db(conn)
    rows = conn.execute("SELECT agent_id, desire, updated_at FROM agent_state ORDER BY agent_id").fetchall()
    data = [{"agent": r[0], "desire": round(float(r[1]), 4), "updated_at": r[2]} for r in rows]
    print(json.dumps({"agents": data}, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Wulin chat dynamics gate")
    p.add_argument("--db", default=str(DB_PATH))
    p.add_argument("--global-cfg", default=str(GLOBAL_CFG_PATH))
    p.add_argument("--agents-dir", default=str(AGENTS_DIR))

    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decide")
    d.add_argument("--agent", required=True)
    d.add_argument("--speaker-type", choices=["user", "bot"], required=True)
    d.add_argument("--speaker-agent", default="")
    d.add_argument("--event-id", default="")
    d.add_argument("--text", default="")
    d.add_argument("--interest-level", choices=["high", "mid", "low"], default="")
    d.add_argument("--seed", type=int)

    s = sub.add_parser("speak")
    s.add_argument("--agent", required=True)
    s.add_argument("--interest-level", choices=["high", "mid", "low"], default="mid")
    s.add_argument("--event-id", default="")

    st = sub.add_parser("status")

    args = p.parse_args()
    if args.cmd == "decide":
        decide(args)
    elif args.cmd == "speak":
        apply_speak(args)
    else:
        status(args)


if __name__ == "__main__":
    main()
