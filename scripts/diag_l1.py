"""Diagnostic: which L1 pattern matches which corpus sample."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server.security.llm_guardrails.core as c
patterns = c.L1_BLOCK_PATTERNS
l1 = c._l1_check

target_ids = ["di-010", "di-014", "mt-008", "rh-005", "rh-006"]
corpora = {
    "direct": "direct_injection.jsonl",
    "multi": "multi_turn_injection.jsonl",
    "role": "role_hijack.jsonl",
    "benign": "benign.jsonl",
}

for cat, fn in corpora.items():
    path = f"server/tests/security/llm_guardrails/corpus/{fn}"
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            if obj["id"] not in target_ids:
                continue
            text = obj.get("text", "")
            history = obj.get("history", [])
            user_turns = [h.get("content", "") for h in history if h.get("role") == "user"]
            merged = "\n".join(user_turns + [text])
            matched = [p.pattern[:55] for p in patterns if p.search(merged)]
            reason = l1(merged)
            print(f"== {obj['id']} ({cat}) == l1: {bool(reason)}")
            print(f"   text: {text[:90]}")
            if matched:
                print(f"   patterns hit: {matched[:3]}")
            print()
