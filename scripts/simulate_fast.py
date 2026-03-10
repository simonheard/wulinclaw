#!/usr/bin/env python3
import hashlib
import json
import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "chat_dynamics.default.json").read_text(encoding="utf-8"))

AGENT_FILES = list((ROOT / "agents").glob("*.yaml"))
AGENTS = []
for f in AGENT_FILES:
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    AGENTS.append(data)


def deep_merge(a, b):
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def classify_interest(agent, text):
    t = text.lower()
    interests = agent.get("interests", {})
    for lvl in ("high", "mid", "low"):
        for kw in interests.get(lvl, []) or []:
            if str(kw).lower() in t:
                return lvl
    return "low"


def run_once(user_msgs, max_hops=80, max_total_bot=400):
    states = {a["id"]: 0.05 for a in AGENTS}
    seen = set()
    user_hops = []
    total_bot = 0
    event = 0

    user_turn = 0
    for um in user_msgs:
        user_turn += 1
        event += 1
        eid = f"u-{event}"
        queue = []

        # user event for each agent
        for a in AGENTS:
            aid = a["id"]
            eff = deep_merge(CFG, a.get("dynamics_override", {}))
            interest = classify_interest(a, um)

            key = (eid, aid, "user_recover")
            if key not in seen:
                phase = eff.get("user_phase", {})
                cold_turn_index = int(phase.get("cold_turn_index", 1))
                phase_mul = float(phase.get("cold_start_multiplier", 1.0)) if user_turn == cold_turn_index else float(phase.get("maintenance_multiplier", 1.0))

                # cold start
                cold = eff.get("cold_start", {})
                if cold.get("enabled", True):
                    low_th = float(cold.get("group_low_threshold", 0.18))
                    low_ratio_need = float(cold.get("group_low_ratio", 0.66))
                    low_ratio = sum(1 for v in states.values() if v < low_th) / max(1, len(states))
                    if low_ratio >= low_ratio_need:
                        states[aid] += float(cold.get("boost_value", 0.35)) * phase_mul
                rec = eff.get("recover_by_user", {})
                states[aid] += float(rec.get(f"{interest}_interest", 0.06)) * phase_mul
                seen.add(key)

            states[aid] = max(0, min(1, states[aid]))
            p = max(0, min(1, float(eff.get("global_pace", 0.6)) * states[aid]))
            if states[aid] >= float(eff.get("desire_min_to_speak", 0.12)):
                seed = int(hashlib.sha256(f"{aid}|user||{eid}".encode()).hexdigest()[:8], 16)
                if random.Random(seed).random() < p:
                    queue.append((aid, interest))

        hop = 0
        while queue and hop < max_hops and total_bot < max_total_bot:
            hop += 1
            spk, spk_interest = queue.pop(0)
            event += 1
            bid = f"b-{event}"

            # self speak drop
            a = next(x for x in AGENTS if x["id"] == spk)
            eff = deep_merge(CFG, a.get("dynamics_override", {}))
            dself = eff.get("drop_self_speak", {})
            states[spk] -= float(dself.get(f"{spk_interest}_interest", 0.11))
            states[spk] = max(0, min(1, states[spk]))
            total_bot += 1

            # bot triggers others
            for a2 in AGENTS:
                aid = a2["id"]
                if aid == spk:
                    continue
                eff2 = deep_merge(CFG, a2.get("dynamics_override", {}))
                interest2 = classify_interest(a2, f"{spk} said something")

                k = (bid, aid, "bot_passive_drop")
                if k not in seen:
                    dother = eff2.get("drop_other_speak", {})
                    states[aid] -= float(dother.get(f"{interest2}_interest", 0.04))
                    seen.add(k)
                states[aid] = max(0, min(1, states[aid]))
                p = max(0, min(1, float(eff2.get("global_pace", 0.6)) * states[aid]))
                if states[aid] >= float(eff2.get("desire_min_to_speak", 0.12)):
                    seed = int(hashlib.sha256(f"{aid}|bot|{spk}|{bid}".encode()).hexdigest()[:8], 16)
                    if random.Random(seed).random() < p:
                        queue.append((aid, interest2))

        user_hops.append(hop)

    return {
        "user_hops": user_hops,
        "total_bot": total_bot,
        "avg_per_user": round(total_bot / len(user_msgs), 2),
        "desires": {k: round(v, 3) for k, v in states.items()},
    }


if __name__ == "__main__":
    msgs = [
        "今天客栈来新人了，江湖消息很多",
        "中午吃什么，谁会做饭",
        "你们别吵，聊点轻松的",
        "最近读书效率咋样",
        "来个整活收尾",
    ]
    out = run_once(msgs)
    print(json.dumps(out, ensure_ascii=False, indent=2))
