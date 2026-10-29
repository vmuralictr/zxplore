"""
registrations_2026_datathon.json -> datathon_data.json  (aggregates only, no PII)

Run order:
    python3 filter_datathon.py
    python3 generate_datathon_data.py
"""
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

SRC = "registrations_2026_datathon.json"
DST = "datathon_data.json"
APPROVED = {"success", "expired", "waitforactive"}

with open(SRC, encoding="utf-8") as fh:
    recs = json.load(fh)
recs.sort(key=lambda r: int(r["regTime"]))


def utc(r):
    return datetime.fromtimestamp(int(r["regTime"]) / 1000, tz=timezone.utc)


def checks(r):
    return {c["name"]: c for c in r.get("checkResult", [])}


FRAUD_RE = re.compile(r"fraud_?score\s*(?:is|=)\s*(\d+)", re.IGNORECASE)


def fraud(r, name):
    m = FRAUD_RE.search(checks(r).get(name, {}).get("message", ""))
    return int(m.group(1)) if m else None


def bucket(s):
    if s is None:
        return "No score"
    if s == 0:
        return "0"
    if s < 50:
        return "1–49"
    if s <= 75:
        return "50–75"
    if s < 85:
        return "76–84"
    if s < 100:
        return "85–99"
    return "100"


BUCKETS = ["0", "1–49", "50–75", "76–84", "85–99", "100", "No score"]


def top(counter, n):
    items = counter.most_common(n)
    return {"labels": [k for k, _ in items], "counts": [v for _, v in items]}


total = len(recs)
status = Counter(r["status"] for r in recs)

# ── Summary ──────────────────────────────────────────────────────────────────
days = Counter(utc(r).strftime("%Y-%m-%d") for r in recs)
peak_day, peak_n = days.most_common(1)[0]
countries = Counter(r["country"] for r in recs)

# ── Organizations (case/space/"the" insensitive grouping) ────────────────────
def org_key(o):
    k = re.sub(r"\s+", " ", o.strip()).casefold()
    return re.sub(r"^the ", "", k)


org_forms, org_counts = defaultdict(Counter), Counter()
for r in recs:
    k = org_key(r["organization"])
    if not k:
        continue
    org_counts[k] += 1
    org_forms[k][re.sub(r"\s+", " ", r["organization"].strip())] += 1
org_label = {k: org_forms[k].most_common(1)[0][0] for k in org_counts}
orgs_top = [
    {"name": org_label[k], "count": n,
     "approved": sum(1 for r in recs if org_key(r["organization"]) == k and r["status"] in APPROVED)}
    for k, n in org_counts.most_common(15)
]
no_org = sum(1 for r in recs if not r["organization"].strip())

# ── Email domain type ────────────────────────────────────────────────────────
def email_type(e):
    d = e.split("@")[-1].lower()
    if d == "ibm.com":
        return "IBM"
    if d in {"gmail.com", "googlemail.com"}:
        return "Gmail"
    if d.endswith(".edu") or ".edu." in d or ".ac." in d or d.endswith(".ac"):
        return "Academic (.edu / .ac)"
    if d in {"outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "live.com", "proton.me", "protonmail.com"}:
        return "Other free mail"
    return "Other / corporate"


email_types = Counter(email_type(r["email"]) for r in recs)

# ── Countries table ──────────────────────────────────────────────────────────
country_rows = []
for c, n in countries.most_common(15):
    ok = sum(1 for r in recs if r["country"] == c and r["status"] in APPROVED)
    country_rows.append({"country": c, "count": n, "approved": ok})

# ── Hourly / daily ───────────────────────────────────────────────────────────
hourly = Counter(utc(r).hour for r in recs)
day_labels = sorted(days)
day_status = {s: [sum(1 for r in recs if utc(r).strftime("%Y-%m-%d") == d and r["status"] == s)
                  for d in day_labels] for s in status}

# ── Check results ────────────────────────────────────────────────────────────
CHECKS = ["WithEventCodeCheck", "EvsCheck", "EmailCheck", "IPCheck", "WhiteListCheck", "ReviewCheck"]
check_rows = []
for n in CHECKS:
    passed = sum(1 for r in recs if checks(r).get(n, {}).get("status") == "success")
    failed = sum(1 for r in recs if checks(r).get(n, {}).get("status") == "failed")
    check_rows.append({"name": n, "passed": passed, "failed": failed})

ip_scores = Counter(bucket(fraud(r, "IPCheck")) for r in recs)
email_scores = Counter(bucket(fraud(r, "EmailCheck")) for r in recs)
leaked = sum(1 for r in recs if "leaked =true" in checks(r).get("EmailCheck", {}).get("message", ""))
review_reason = Counter()
for r in recs:
    ck = checks(r).get("ReviewCheck", {})
    if ck.get("status") == "failed":
        review_reason[re.sub(r"\s+", " ", ck["message"])] += 1
whitelist_reason = Counter(
    checks(r).get("WhiteListCheck", {}).get("message", "") for r in recs
    if checks(r).get("WhiteListCheck", {}).get("status") == "success")

# ── Approved despite a failed automated check (ManualReviewCheck always "fails": not set) ──
any_fail_approved = sum(
    1 for r in recs
    if r["status"] in APPROVED
    and any(checks(r).get(n, {}).get("status") == "failed" for n in CHECKS)
)

# ── Lifecycle ────────────────────────────────────────────────────────────────
def hist_time(r, event):
    for h in r.get("history", []):
        if h["event"] == event and h["status"].lower() == "success":
            return h["time"]
    return None


activation_secs = []
for r in recs:
    a, b = hist_time(r, "Registration completed"), hist_time(r, "Send activation success email")
    if a and b and b >= a:
        activation_secs.append((b - a) / 1000)
events = Counter((h["event"], h["status"]) for r in recs for h in r.get("history", []))
vm_failed = sum(1 for r in recs if any(h["event"] == "Activate service VM" and h["status"] == "Failed"
                                        for h in r.get("history", [])))
activated = sum(1 for r in recs if hist_time(r, "Send activation success email"))

# ── Purpose text ─────────────────────────────────────────────────────────────
lens = [len(r["purpose"].strip()) for r in recs]
LEN_B = [("<75", 0, 75), ("75–149", 75, 150), ("150–299", 150, 300), ("300–499", 300, 500), ("500+", 500, 10**9)]
len_hist = {"labels": [b[0] for b in LEN_B],
            "counts": [sum(1 for x in lens if lo <= x < hi) for _, lo, hi in LEN_B]}

THEMES = [
    ("AI / Machine Learning", r"\b(ai|a\.i\.|artificial intelligence|machine learning|ml|llm|deep learning|nlp|neural|granite|watsonx)\b"),
    ("Fraud / Security", r"\b(fraud|scam|security|cyber|threat|anomal|phishing)\w*"),
    ("Healthcare / Medical", r"\b(health|medical|medicine|patient|disease|clinical|hospital|genom|diagnos)\w*"),
    ("Finance / Banking", r"\b(bank|banking|financ|payment|credit|loan|insurance|transaction)\w*"),
    ("Climate / Energy / Environment", r"\b(climate|energy|power grid|carbon|flood|weather|environment|sustainab|agricultur|crop)\w*"),
    ("Education / Learning", r"\b(educat|student|learning platform|tutor|course)\w*"),
    ("Web / App", r"\b(web ?app|website|web application|mobile app|dashboard|frontend|backend|full[- ]stack)\b"),
    ("LinuxONE / IBM Z", r"\b(linuxone|linux one|ibm z|s390x|mainframe|z/os)\b"),
    ("Mentions \"datathon\"", r"data[\s\-]?thon"),
]
themes = {name: sum(1 for r in recs if re.search(rx, r["purpose"], re.IGNORECASE)) for name, rx in THEMES}

# ── Output ───────────────────────────────────────────────────────────────────
out = {
    "summary": {
        "total": total,
        "approved": sum(status[s] for s in APPROVED),
        "success": status["success"], "expired": status["expired"], "rejected": status["rejected"],
        "approval_rate": round(100 * sum(status[s] for s in APPROVED) / total, 1),
        "countries": len(countries),
        "organizations": len(org_counts),
        "no_org": no_org,
        "activated": activated,
        "peak_day": peak_day, "peak_day_count": peak_n,
        "first": utc(recs[0]).strftime("%d %b %Y"), "last": utc(recs[-1]).strftime("%d %b %Y"),
        "event_ssf2026": sum(1 for r in recs if r["eventCode"] == "SSF2026"),
        "text_only": sum(1 for r in recs if r["eventCode"] != "SSF2026"),
    },
    "status": dict(status),
    "event_codes": dict(Counter(r["eventCode"] for r in recs)),
    "daily": {"labels": day_labels, "status": day_status},
    "hourly": [hourly.get(h, 0) for h in range(24)],
    "countries": top(countries, 15),
    "country_rows": country_rows,
    "orgs_top": orgs_top,
    "email_types": dict(email_types),
    "checks": check_rows,
    "ip_scores": {"labels": BUCKETS, "counts": [ip_scores.get(b, 0) for b in BUCKETS]},
    "email_scores": {"labels": BUCKETS, "counts": [email_scores.get(b, 0) for b in BUCKETS]},
    "leaked_email": leaked,
    "review_reasons": dict(review_reason),
    "whitelist_reasons": dict(whitelist_reason),
    "any_fail_approved": any_fail_approved,
    "lifecycle": {
        "median_activation_s": round(statistics.median(activation_secs), 1) if activation_secs else None,
        "p90_activation_s": round(statistics.quantiles(activation_secs, n=10)[-1], 1) if len(activation_secs) > 10 else None,
        "vm_activation_failed": vm_failed,
        "expired": events[("Expiration completed", "Success")],
        "manual_reject": events[("Review", "reject")],
    },
    "purpose_len": len_hist,
    "purpose_len_avg": round(statistics.mean(lens)),
    "purpose_len_median": round(statistics.median(lens)),
    "themes": themes,
}

with open(DST, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
print(f"{total} records -> {DST}")
