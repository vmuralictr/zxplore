"""Repair registrations_2026.json into a valid JSON array.

Fixes: missing outer array / trailing commas, and unescaped quotes, raw
newlines, tabs and control characters inside "purpose"/"organization".
Writes a new file; the original is never modified.
"""
import json
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "registrations_2026.json"
DST = sys.argv[2] if len(sys.argv) > 2 else "registrations_2026_clean.json"

# Free-text fields end at the next known key.
FIELD_RES = [
    re.compile(r'("organization":\s*")(.*?)("\s*,\s*"country"\s*:)', re.DOTALL),
    re.compile(r'("purpose":\s*")(.*?)("\s*,\s*"eventCode"\s*:)', re.DOTALL),
]
CTRL = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def escape_field(match):
    raw = match.group(2)
    raw = re.sub(r'(?<!\\)"', '\\\\"', raw)  # unescaped quotes
    raw = "".join(CTRL.get(c, f"\\u{ord(c):04x}" if ord(c) < 0x20 else c) for c in raw)
    return match.group(1) + raw + match.group(3)


with open(SRC, encoding="utf-8") as fh:
    text = fh.read().strip()

# Tolerate an existing outer array (and a trailing comma before the closing bracket).
if text.startswith("["):
    text = text[1:].lstrip()
if text.endswith("]"):
    text = text[:-1].rstrip()

# Each record starts at the beginning of a line with `{ "_id"`.
chunks = re.split(r'(?m)^(?=\{\s*"_id")', text)
records, failed = [], []
for chunk in chunks:
    chunk = chunk.strip().rstrip(",").strip()
    if not chunk:
        continue
    fixed = chunk
    for field_re in FIELD_RES:
        fixed = field_re.sub(escape_field, fixed)
    try:
        records.append(json.loads(fixed))
    except ValueError as exc:
        failed.append((chunk[:80], str(exc)))

with open(DST, "w", encoding="utf-8") as fh:
    json.dump(records, fh, ensure_ascii=False, indent=1)

print(f"recovered={len(records)} failed={len(failed)} -> {DST}")
for head, err in failed:
    print("FAILED:", head, "|", err)
