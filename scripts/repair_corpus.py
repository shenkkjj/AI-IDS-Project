"""Repair JSONL corpus files: escape stray ASCII double quotes inside string values."""
import json
import re
from pathlib import Path

corpus_dir = Path("server/tests/security/llm_guardrails/corpus")
files = list(corpus_dir.glob("*.jsonl"))

for path in files:
    lines = list(path.read_text(encoding="utf-8").splitlines())
    fixed_lines = []
    for line_no, line in enumerate(lines, 1):
        line = line.rstrip()
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            fixed_lines.append(json.dumps(obj, ensure_ascii=False))
            continue
        except json.JSONDecodeError:
            pass
        # crude repair: replace ASCII " between Chinese chars or after Chinese punctuation with full-width
        repaired = line
        repaired = re.sub(
            r'([一-鿿　-〿＀-￯,!?;:])"',
            r"\1”",
            repaired,
        )
        repaired = re.sub(
            r'"([一-鿿])',
            r"“\1",
            repaired,
        )
        repaired = re.sub(r'\)"', r"\)”", repaired)
        try:
            obj = json.loads(repaired)
            fixed_lines.append(json.dumps(obj, ensure_ascii=False))
            print(f"  fixed {path.name}:{line_no}")
        except json.JSONDecodeError as e:
            print(f"  still broken {path.name}:{line_no}: {e.msg} at {e.pos}")
            print(f"    line: {repaired}")
            fixed_lines.append(line)
    path.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")

print("done")
