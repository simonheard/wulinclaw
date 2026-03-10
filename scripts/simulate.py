#!/usr/bin/env python3
import hashlib
import json
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "state" / "sim.db"
LOG_DIR = ROOT / "logs" / "sim"
GATE = ROOT / "scripts" / "dynamics_gate.py"

AGENTS = ["xiaobai", "xiaohong", "xiaolv", "xiaozong", "xiaolan", "xiaozi"]


def run(cmd):
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def decide(agent, speaker_type, speaker_agent, event_id, text):
    # deterministic seed for reproducible simulation
    seed_src = f"{agent}|{speaker_type}|{speaker_agent}|{event_id}".encode("utf-8")
    seed = int(hashlib.sha256(seed_src).hexdigest()[:8], 16)
    cmd = [
        "python3", str(GATE), "--db", str(DB), "--log-dir", str(LOG_DIR), "--chat-id", "sim-chat", "--message-id", event_id, "decide",
        "--agent", agent,
        "--speaker-type", speaker_type,
        "--speaker-agent", speaker_agent,
        "--event-id", event_id,
        "--text", text,
        "--seed", str(seed),
    ]
    return run(cmd)


def speak(agent, interest, event_id):
    cmd = [
        "python3", str(GATE), "--db", str(DB), "--log-dir", str(LOG_DIR), "--chat-id", "sim-chat", "--message-id", event_id, "speak",
        "--agent", agent,
        "--interest-level", interest,
        "--event-id", event_id,
    ]
    return run(cmd)


def status():
    return run(["python3", str(GATE), "--db", str(DB), "status"])


def classify_interest(text):
    t = text.lower()
    if any(k in t for k in ["江湖", "客栈", "排山倒海", "读书", "做饭", "整活"]):
        return "high"
    if any(k in t for k in ["吃", "日常", "工作", "朋友"]):
        return "mid"
    return "low"


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    for f in LOG_DIR.glob("*.jsonl"):
        f.unlink()

    random.seed(42)
    event_num = 0
    transcript = []

    # users inject 5 messages; expect chain then fade
    user_hops = []
    user_msgs = [
        "今天客栈来新人了，江湖消息很多",
        "中午吃什么，谁会做饭",
        "你们别吵，聊点轻松的",
        "最近读书效率咋样",
        "来个整活收尾",
    ]

    max_bot_speaks = 120

    for um in user_msgs:
        event_num += 1
        eid = f"u-{event_num}"
        speakers = []
        # user event: update each agent + decide once
        for a in AGENTS:
            r = decide(a, "user", "", eid, um)
            if r["allow"]:
                speakers.append((a, r["interest"]))

        # each allowed speaker speaks once, and may trigger others for up to 50 hops
        queue = list(speakers)
        hop = 0
        while queue and hop < 50:
            if sum(1 for x in transcript if x.get("src") == "bot") >= max_bot_speaks:
                break
            hop += 1
            spk, interest = queue.pop(0)
            event_num += 1
            sid = f"b-{event_num}"
            speak(spk, interest, sid)
            transcript.append({"speaker": spk, "src": "bot", "interest": interest, "eid": sid})

            for a in AGENTS:
                r = decide(a, "bot", spk, sid, f"{spk} said something")
                if r["allow"]:
                    queue.append((a, r["interest"]))

        user_hops.append(hop)
        transcript.append({"speaker": "user", "src": "user", "text": um, "hop_used": hop})

    st = status()
    desires = {x["agent"]: x["desire"] for x in st["agents"]}
    avg_desire = sum(desires.values()) / len(desires)

    # convergence criterion: ending phase should naturally cool down
    # 由于 user 可以随时重新点火，这里定义“收敛”为：后段链长受控且整体欲望低
    tail_hops = user_hops[-3:] if len(user_hops) >= 3 else user_hops
    converged = (max(tail_hops) <= 3) and (avg_desire < 0.3)

    def count_lines(p):
        return sum(1 for _ in p.open("r", encoding="utf-8")) if p.exists() else 0

    log_counts = {
        "decision": count_lines(LOG_DIR / "decision.log.jsonl"),
        "speak": count_lines(LOG_DIR / "speak.log.jsonl"),
        "metrics": count_lines(LOG_DIR / "metrics.log.jsonl"),
    }

    print(json.dumps({
        "converged": converged,
        "avg_desire": round(avg_desire, 4),
        "user_hops": user_hops,
        "desires": desires,
        "events": len(transcript),
        "log_counts": log_counts,
        "tail": transcript[-20:],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
