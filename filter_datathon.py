"""Filter registrations_2026.json down to Datathon-related records.

A record counts as Datathon-related if its eventCode is SSF2026 (the Datathon
event code) OR its purpose/organization mentions "datathon" / "data-thon".
"""
import json
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "registrations_2026.json"
DST = sys.argv[2] if len(sys.argv) > 2 else "registrations_2026_datathon.json"

EVENT_CODES = {"SSF2026"}
TEXT_RE = re.compile(r"data[\s\-]?thon", re.IGNORECASE)

with open(SRC, encoding="utf-8") as fh:
    records = json.load(fh)

matched = [
    r for r in records
    if r.get("eventCode") in EVENT_CODES
    or TEXT_RE.search(r.get("purpose", ""))
    or TEXT_RE.search(r.get("organization", ""))
]

with open(DST, "w", encoding="utf-8") as fh:
    json.dump(matched, fh, ensure_ascii=False, indent=1)

print(f"{len(matched)} of {len(records)} records -> {DST}")
