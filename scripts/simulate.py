#!/usr/bin/env python3
import json
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "state" / "sim.db"
GATE = ROOT / "scripts" / "dynamics_gate.py"

AGENTS = ["xiaobai", "xiaohong", "xiaolv", "xiaozong", "xiaolan", "xiaozi"]


def run(cmd):
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def decide(agent, speaker_type, speaker_agent, event_id, text):
    cmd = [
        "python3", str(GATE), "--db", str(DB), "decide",
        "--agent", agent,
        "--speaker-type", speaker_type,
        "--speaker-agent", speaker_agent,
        "--event-id", event_id,
        "--text", text,
    ]
    return run(cmd)


def speak(agent, interest, event_id):
    cmd = [
        "python3", str(GATE), "--db", str(DB), "speak",
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
    if DB.exists():
        DB.unlink()

    random.seed(42)
    event_num = 0
    transcript = []

    # users inject 5 messages; expect chain then fade
    user_msgs = [
        "今天客栈来新人了，江湖消息很多",
        "中午吃什么，谁会做饭",
        "你们别吵，聊点轻松的",
        "最近读书效率咋样",
        "来个整活收尾",
    ]

    for um in user_msgs:
        event_num += 1
        eid = f"u-{event_num}"
        speakers = []
        # user event: update each agent + decide once
        for a in AGENTS:
            r = decide(a, "user", "", eid, um)
            if r["allow"]:
                speakers.append((a, r["interest"]))

        # each allowed speaker speaks once, and may trigger others for up to 12 hops
        queue = list(speakers)
        hop = 0
        while queue and hop < 12:
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

        transcript.append({"speaker": "user", "src": "user", "text": um, "hop_used": hop})

    st = status()
    desires = {x["agent"]: x["desire"] for x in st["agents"]}
    avg_desire = sum(desires.values()) / len(desires)

    # convergence criterion
    converged = avg_desire < 0.2

    print(json.dumps({
        "converged": converged,
        "avg_desire": round(avg_desire, 4),
        "desires": desires,
        "events": len(transcript),
        "tail": transcript[-20:],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
