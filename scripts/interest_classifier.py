#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"


def load_agent_profile(agent_id: str, agents_dir: Path) -> dict:
    for f in agents_dir.glob("*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if data.get("id") == agent_id:
            return data
    raise FileNotFoundError(f"agent id not found: {agent_id}")


def keyword_classify(profile: dict, text: str):
    txt = text.lower()
    interests = profile.get("interests", {})
    scores = {"high": 0, "mid": 0, "low": 0}

    for lvl in ("high", "mid", "low"):
        for kw in (interests.get(lvl, []) or []):
            kw_l = str(kw).lower().strip()
            if not kw_l:
                continue
            # basic contains + word-boundary for ascii words
            if re.search(rf"\b{re.escape(kw_l)}\b", txt) or kw_l in txt:
                scores[lvl] += 1

    if scores["high"] > 0:
        level = "high"
    elif scores["mid"] > 0:
        level = "mid"
    else:
        level = "low"

    max_hits = max(scores.values())
    conf = 0.55 if max_hits == 0 else min(0.95, 0.6 + max_hits * 0.1)
    return {
        "level": level,
        "confidence": round(conf, 3),
        "method": "keyword",
        "scores": scores,
    }


def classify(agent_id: str, text: str, mode: str, agents_dir: Path):
    profile = load_agent_profile(agent_id, agents_dir)
    kw = keyword_classify(profile, text)

    if mode == "keyword":
        return kw

    # Placeholder for future LLM classifier
    # Current behavior for llm/hybrid: return keyword with method tag,
    # enabling integration without breaking deterministic tests.
    if mode == "llm":
        kw["method"] = "llm_stub"
        return kw

    if mode == "hybrid":
        if kw["confidence"] >= 0.75:
            kw["method"] = "hybrid_keyword"
            return kw
        kw["method"] = "hybrid_llm_fallback_stub"
        return kw

    raise ValueError(f"unsupported mode: {mode}")


def main():
    ap = argparse.ArgumentParser(description="Interest classifier")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--mode", choices=["keyword", "llm", "hybrid"], default="hybrid")
    ap.add_argument("--agents-dir", default=str(AGENTS_DIR))
    args = ap.parse_args()

    out = classify(args.agent, args.text, args.mode, Path(args.agents_dir))
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
