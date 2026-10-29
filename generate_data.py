"""
Pre-processes registrations_2025.json + registrations_2026.json → dashboard_data.json
Run: python3 generate_data.py
"""
import json, re
from collections import Counter, defaultdict
from datetime import datetime, timezone

APPROVED = {"success", "expired", "waitforactive"}

# ── Load ──────────────────────────────────────────────────────────────────────
data25 = json.load(open("registrations_2025.json", encoding="utf-8"))
data26 = json.load(open("registrations_2026.json", encoding="utf-8"))
data   = data25 + data26
data.sort(key=lambda r: int(r.get("regTime", 0)))

def utc(r):
    return datetime.fromtimestamp(int(r["regTime"]) / 1000, tz=timezone.utc)

def ym(r):   return utc(r).strftime("%Y-%m")
def year(r): return utc(r).year


# ── Check-result parser ───────────────────────────────────────────────────────
_CK_ZERO = {"name": None, "status": None, "message": ""}
def parse_checks(r):
    out = {}
    for c in r.get("checkResult", []):
        out[c["name"]] = c
    def get(name):
        return out.get(name, _CK_ZERO)
    return get

def fraud_score(msg):
    m = re.search(r"(?:fraud_?[sS]core(?:\s*is\s*|\s*=\s*))(\d+)", msg)
    return int(m.group(1)) if m else None

# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORIES (same first-match-wins classifier as before)
# ═══════════════════════════════════════════════════════════════════════════════
CATEGORIES = [
    ("IBM Z Xplore / LNX Program",
     r"ibm\s*z\s*xplore|z\s*xplore|zxplore|lnx\s*[123]|linuxone\s*community\s*cloud|z\s*student\s*program|ibm\s*gsap|ibmzxplore|ibmzexplore"),
    ("Hackathon / Datathon",
     r"hackathon|datathon|ssf[\s_]?2025|ssf2025|\bcompetition\b|\bcontest\b|ideathon|codeathon|ibm\s*z\s*datathon|ibm\s*datathon|smart\s*india\s*hackathon"),
    ("AI / Machine Learning",
     r"\b(artificial\s+intelligence|machine\s+learning|deep\s+learning|neural\s+net|large\s+language\s+model|\bllm\b|natural\s+language\s+processing|\bnlp\b|computer\s+vision|generative\s+ai|\bgen[\s\-]?ai\b|ai[\s\-]powered|ai[\s\-]based|ai[\s\-]driven|ai[\s\-]model|ai[\s\-]agent|ai\s+platform|transformer\s+model|convolutional|reinforcement\s+learning|random\s+forest|gradient\s+boost|\byolo\b|object\s+detection|image\s+(recognition|classification)|chatbot|recommendation\s+system|sentiment\s+analysis|predictive\s+(model|analytics)|predict\s+(disease|accident|flood|crop|stock|price|weather|churn|risk)|classification\s+model|data\s+scien)\b"),
    ("Web Development / Hosting",
     r"\b(host\s+(a\s+)?(website|web[\s\-]?app|blog|site)|personal\s+(website|site|blog|portfolio)|build\s+(a\s+)?(website|web[\s\-]?app|web\s*site|site|blog)|setup\s+(a\s+)?(website|web\s*site|site)|set\s+up\s+(a\s+)?(website|web\s*site|site)|deploy\s+(a\s+)?web|wordpress|nginx|apache|e[\-\s]?commerce|web\s+server|web\s+hosting|website\s+hosting|web\s+portfolio|portfolio\s+website|website\s+development|web\s+development|develop\s+(a\s+)?(website|web[\s\-]?app|web\s*site|site)|create\s+(a\s+)?(website|web[\s\-]?app|web\s*site|site|blog)|build\s+web\b|develop\s+web\b|building\s+(a\s+)?(website|web|blog|site)|web\s+application)\b"),
    ("DevOps / Cloud / Infrastructure",
     r"\b(kubernetes|\bk8s\b|docker|ci[\s/]?cd|devops|terraform|ansible|\bhelm\b|microservice|containeriz|orchestrat|cloud\s+native|cloud[\s\-]native|infrastructure\s+as\s+code|\biac\b|service\s+mesh|jenkins|github\s+actions|gitlab\s+ci|continuous\s+integration|continuous\s+deployment|\berp\b)\b"),
    ("Security / Networking / VPN",
     r"\b(vpn|wireguard|openvpn|firewall|penetration\s+test|pen\s+test|cybersecur|network\s+secur|encrypt|zero[\s\-]trust|\bddos\b|proxy\s+server|reverse\s+proxy|tunneling|privac|anonymi|\bctf\b|capture\s+the\s+flag|key\s+management)\b"),
    ("Database / Data Engineering",
     r"\b(postgresql|mysql|mongodb|sqlite|\bredis\b|cassandra|elasticsearch|data\s+warehouse|\betl\b|data\s+pipeline|data\s+engineer|apache\s+spark|hadoop|kafka|\bdb2\b|sql\s+server|mariadb|data\s+analytic|data\s+visual|big\s+data|analytics\s+platform)\b"),
    ("Blockchain / Web3",
     r"\b(blockchain|crypto(?:currency)?|\bnft\b|\bdefi\b|\bweb3\b|smart\s+contract|ethereum|bitcoin|solidity|decentrali[sz])\b"),
    ("IoT / Embedded Systems",
     r"\b(iot\b|internet\s+of\s+things|embedded\s+system|raspberry\s+pi|arduino|sensor\s+data|smart\s+home|edge\s+computing|firmware)\b"),
    ("App / Software Development",
     r"\b(mobile\s+app|android\s+app|ios\s+app|flutter|react\s+native|discord\s+bot|telegram\s+bot|api\s+server|rest\s+api|backend\s+serv|full[\s\-]stack|develop\s+(an?\s+)?(app|application|platform|system|tool|service|software)|build\s+(an?\s+)?(app|application|platform|system|tool|service|software)|create\s+(an?\s+)?(app|application|platform|system|tool)|game\s+server|minecraft|building\s+(an?\s+)?(app|application|platform)|developing\s+(an?\s+)?(app|application|platform|system|software))\b"),
    ("Testing / Development Sandbox",
     r"\b(test(ing)?\s+(my|this|the|a|an?)\s+\w+|for\s+test(ing)?\s+(purposes?|only|and)|development\s+and\s+test|sandbox|staging\s+environment|dev(elopment)?\s+environment|testing\s+environment|proof\s+of\s+concept|\bpoc\b|prototype|stress\s+test|load\s+test|testing.*validation)\b"),
    ("Research / Academic",
     r"\b(research|thesis|dissertation|\bphd\b|masters?\s+degree|academic|university\s+project|capstone|graduate\s+studi|undergraduate|faculty|laboratory|scientific\s+comput|paper\s+submission|publication)\b"),
    ("IBM LinuxONE / s390x Exploration",
     r"\b(linuxone|linux\s*one|s390x|ibm\s+z\b|mainframe|ibm\s+linuxone|z\s+architecture|\bzos\b|z\/os)\b"),
    ("Learning Linux / Sysadmin",
     r"\b(learn\s+(linux|bash|shell|cli|command[\s\-]line|unix|ubuntu|centos|fedora)|study\s+linux|linux\s+(course|training|skill|fundament|command|admin|practice|operation|basic|knowledge)|system\s+administ|shell\s+script|bash\s+script|linux\s+certif|lfcs|lpic|rhcsa|linux\s+basics|linux\s+mastery|linux\s+skill|linux\s+knowledge|linux\s+environment|linux\s+experience|command\s+line\s+skill)\b"),
    ("Learning Programming / Technology",
     r"\b(learn(ing)?\s+(python|java|javascript|golang|rust|c\+\+|c#|ruby|php|html|css|react|node\.?js|programming|coding|software|cloud|networking|computer\s+science|technology|\btech\b)|study(ing)?\s+(python|java|javascript|programming|coding|software|cloud|computer\s+science|technology)|improve\s+(my\s+)?(coding|programming|technical|dev|software)\s+skill|learn\s+to\s+(code|program|develop)|learning\s+to\s+(build|develop|deploy))\b"),
    ("Marketing Spam / Template",
     r"\b(seo\s+rank|search\s+engine\s+optim|keyword\s+rank|backlink|please\s+provide\s+a\s+more\s+detailed|your\s+input\s+must\s+be\s+at\s+least\s+75\s+characters)\b|\bselling\s+your\s+products\s+or\s+services\s+and\s+driving\s+revenue\b|\bfix\s+site\s+issues.*find\s+profitable\b"),
    ("Filler / Spam",
     r"^[\s\W\d]{0,5}$|^\s*(test|hello|hi|ok|yes|no|none|n\/a|education|learning|study|learn|learn linux|i want to learn|i want to learn linux|service|web|vps|server|work|project|purpose|study linux|linux|build web|build a web|develop website|develop web|build website|build a website|judge|fder|be honest|i want to build a web)\s*[.!]?\s*$"),
]

def classify(purpose):
    p = purpose.strip()
    if len(p) < 4:
        return "Filler / Spam"
    words = re.findall(r"[a-zA-Z]{2,}", p)
    if len(p) > 8 and not words:
        return "Filler / Spam"
    if len(p) >= 10 and len(set(p.replace(" ", "").lower())) <= 3:
        return "Filler / Spam"
    for cat_name, pattern in CATEGORIES:
        if re.search(pattern, p, re.IGNORECASE):
            return cat_name
    learn_generic = r"\b(learn|study|education|training|practice|improve\s+skill|course|tutorial)\b"
    if re.search(learn_generic, p, re.IGNORECASE) and len(p) < 150:
        return "General Learning (Unspecified)"
    if re.search(r"\blinux\b", p, re.IGNORECASE):
        return "Learning Linux / Sysadmin"
    return "Other / Unclassified"

ORDERED_CATS = [
    "Web Development / Hosting", "Learning Linux / Sysadmin", "Filler / Spam",
    "General Learning (Unspecified)", "AI / Machine Learning",
    "IBM Z Xplore / LNX Program", "IBM LinuxONE / s390x Exploration",
    "Testing / Development Sandbox", "DevOps / Cloud / Infrastructure",
    "Research / Academic", "App / Software Development",
    "Learning Programming / Technology", "Marketing Spam / Template",
    "Security / Networking / VPN", "Hackathon / Datathon",
    "Database / Data Engineering", "Blockchain / Web3",
    "IoT / Embedded Systems", "Other / Unclassified",
]

SPAM_CATS = {"Filler / Spam", "Marketing Spam / Template"}
EDU_CATS  = {
    "Learning Linux / Sysadmin", "Learning Programming / Technology",
    "General Learning (Unspecified)", "Research / Academic",
}
ZXPLORE_CATS = {"IBM Z Xplore / LNX Program"}

# Classify all records once
for r in data:
    r["_cat"] = classify(r.get("purpose", ""))


# ═══════════════════════════════════════════════════════════════════════════════
# MONTHS list (2025-01 … last record)
# ═══════════════════════════════════════════════════════════════════════════════
all_months = sorted({ym(r) for r in data})

def monthly_counts(recs, key_fn):
    c = Counter(key_fn(r) for r in recs)
    return [c.get(m, 0) for m in all_months]

months = all_months  # label list for every monthly chart

# ═══════════════════════════════════════════════════════════════════════════════
# 1. CATEGORIES — all users and approved-only, both years
# ═══════════════════════════════════════════════════════════════════════════════
def cat_table(records):
    c  = Counter(r["_cat"] for r in records)
    c5 = Counter(r["_cat"] for r in records if year(r) == 2025)
    c6 = Counter(r["_cat"] for r in records if year(r) == 2026)
    return {
        "labels":      ORDERED_CATS,
        "counts":      [c.get(cat, 0)  for cat in ORDERED_CATS],
        "counts_2025": [c5.get(cat, 0) for cat in ORDERED_CATS],
        "counts_2026": [c6.get(cat, 0) for cat in ORDERED_CATS],
        "total":       len(records),
        "total_2025":  sum(c5.values()),
        "total_2026":  sum(c6.values()),
    }

approved_recs = [r for r in data if r.get("status") in APPROVED]

categories_all      = cat_table(data)
categories_approved = cat_table(approved_recs)

# ═══════════════════════════════════════════════════════════════════════════════
# 2. 75-CHAR LIMIT IMPACT: share of each category before and after cutover
# ═══════════════════════════════════════════════════════════════════════════════
CUTOVER_MS = int(datetime(2025, 7, 10, 6, 0, tzinfo=timezone.utc).timestamp() * 1000)
pre_recs  = [r for r in data if int(r["regTime"]) <  CUTOVER_MS]
post_recs = [r for r in data if int(r["regTime"]) >= CUTOVER_MS]

def cat_pct(records):
    total = len(records) or 1
    c = Counter(r["_cat"] for r in records)
    return {cat: round(100 * c.get(cat, 0) / total, 1) for cat in ORDERED_CATS}

_pc = Counter(r.get("purpose", "").strip().lower() for r in data)
MASS_DUP = 50   # a purpose text used by >= this many registrations is a template/campaign
pre_dedup  = [r for r in pre_recs  if _pc[r.get("purpose", "").strip().lower()] < MASS_DUP]
post_dedup = [r for r in post_recs if _pc[r.get("purpose", "").strip().lower()] < MASS_DUP]

_pre_c, _post_c = Counter(r["_cat"] for r in pre_recs), Counter(r["_cat"] for r in post_recs)
_pre_p, _post_p = cat_pct(pre_recs), cat_pct(post_recs)
_pre_dp, _post_dp = cat_pct(pre_dedup), cat_pct(post_dedup)
limit_impact = {
    "labels":     ORDERED_CATS,
    "pre_total":  len(pre_recs),
    "post_total": len(post_recs),
    "pre_pct":    [_pre_p[c]  for c in ORDERED_CATS],
    "post_pct":   [_post_p[c] for c in ORDERED_CATS],
    "pre_count":  [_pre_c.get(c, 0)  for c in ORDERED_CATS],
    "post_count": [_post_c.get(c, 0) for c in ORDERED_CATS],
    "mass_dup_threshold": MASS_DUP,
    "pre_total_dedup":  len(pre_dedup),
    "post_total_dedup": len(post_dedup),
    "pre_pct_dedup":    [_pre_dp[c]  for c in ORDERED_CATS],
    "post_pct_dedup":   [_post_dp[c] for c in ORDERED_CATS],
    "mass_dup_regs": sum(n for n in _pc.values() if n >= MASS_DUP),
    "mass_dup_top": [[t[:60], n] for t, n in _pc.most_common(6) if n >= MASS_DUP],
}

# ═══════════════════════════════════════════════════════════════════════════════
# 3. MONTHLY REGISTRATIONS — total, ZXplore, Education (both years)
# ═══════════════════════════════════════════════════════════════════════════════
monthly_total   = monthly_counts(data, ym)
_zx_event   = [r for r in data if r["eventCode"] == "IBMZXPLORE"]
_zx_purpose = [r for r in data if r["eventCode"] != "IBMZXPLORE" and r["_cat"] in ZXPLORE_CATS]
monthly_zxplore_event   = monthly_counts(_zx_event, ym)
monthly_zxplore_purpose = monthly_counts(_zx_purpose, ym)
monthly_zxplore = [a + b for a, b in zip(monthly_zxplore_event, monthly_zxplore_purpose)]
monthly_edu     = monthly_counts([r for r in data if r["_cat"] in EDU_CATS], ym)
monthly_approved = monthly_counts(approved_recs, ym)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. SPAM / GARBAGE BY COUNTRY PER MONTH
# ═══════════════════════════════════════════════════════════════════════════════
spam_recs = [r for r in data if r["_cat"] in SPAM_CATS]
# top spam countries overall
top_spam_countries = [cc for cc, _ in Counter(r.get("country", "") for r in spam_recs).most_common(12) if cc and cc != "N/A"]

spam_by_country_month = {}
for cc in top_spam_countries:
    recs = [r for r in spam_recs if r.get("country") == cc]
    spam_by_country_month[cc] = monthly_counts(recs, ym)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. EVENTS
# ═══════════════════════════════════════════════════════════════════════════════
event_counter = Counter(r["eventCode"] for r in data)
top_events = [ec for ec, _ in event_counter.most_common(15) if ec and ec != "bgtest"]

events = []
for ec in top_events:
    recs = [r for r in data if r["eventCode"] == ec]
    appr = [r for r in recs if r.get("status") in APPROVED]
    ip_f  = sum(parse_checks(r)("IPCheck")["status"] == "failed" for r in recs)
    em_f  = sum(parse_checks(r)("EmailCheck")["status"] == "failed" for r in recs)
    events.append({
        "code":        ec,
        "total":       len(recs),
        "approved":    len(appr),
        "appr_pct":    round(100 * len(appr) / len(recs), 1),
        "ip_fail_pct": round(100 * ip_f / len(recs), 1),
        "em_fail_pct": round(100 * em_f / len(recs), 1),
        "monthly":     monthly_counts(recs, ym),
        "no_checks":   sum(1 for r in recs if not r.get("checkResult")),
        "first":       ym(recs[0]),
        "last":        ym(recs[-1]),
        "top_cats":    Counter(r["_cat"] for r in recs).most_common(5),
    })

# ═══════════════════════════════════════════════════════════════════════════════
# 6. EMAIL / IP FRAUD SCORES & APPROVAL OUTCOMES
# ═══════════════════════════════════════════════════════════════════════════════
def score_bucket(s):
    if s is None:  return "No score"
    if s == 0:     return "0"
    if s < 50:     return "1–49"
    if s <= 75:    return "50–75"
    if s < 85:     return "76–84"
    if s < 100:    return "85–99"
    return "100"

SCORE_BUCKETS = ["0", "1–49", "50–75", "76–84", "85–99", "100", "No score"]

def score_rows(records, check_name):
    rows = defaultdict(lambda: [0, 0])   # [total, approved]
    for r in records:
        ck  = parse_checks(r)(check_name)
        s   = fraud_score(ck["message"]) if ck["message"] else None
        bkt = score_bucket(s)
        rows[bkt][0] += 1
        rows[bkt][1] += r.get("status") in APPROVED
    return {
        "buckets": SCORE_BUCKETS,
        "total":   [rows[b][0] for b in SCORE_BUCKETS],
        "approved":[rows[b][1] for b in SCORE_BUCKETS],
        "denied":  [rows[b][0] - rows[b][1] for b in SCORE_BUCKETS],
        "appr_pct":[round(100 * rows[b][1] / rows[b][0], 1) if rows[b][0] else 0 for b in SCORE_BUCKETS],
    }

# Scores only gate the default (non-event) path, so charts use that population.
default_recs = [r for r in data if r.get("eventCode") == "default"]
event_recs   = [r for r in data if r.get("eventCode") != "default"]

ip_scores    = score_rows(default_recs, "IPCheck")
email_scores = score_rows(default_recs, "EmailCheck")

# Rejection reasons breakdown (auto vs manual, and failing checks for auto-rejects)
manual_rej = sum(
    1 for r in data
    if r.get("status") == "rejected" and any(h["event"] == "Review" for h in r.get("history", []))
)
auto_rej = sum(
    1 for r in data
    if r.get("status") == "rejected" and not any(h["event"] == "Review" for h in r.get("history", []))
)

# For auto-rejected records, which check(s) failed?
def rej_check_fail_counts():
    names = ["IPCheck", "EmailCheck", "EvsCheck", "ReviewCheck"]
    auto = [r for r in data if r.get("status") == "rejected"
            and not any(h["event"] == "Review" for h in r.get("history", []))]
    total = len(auto) or 1
    return {n: round(100 * sum(parse_checks(r)(n)["status"] == "failed" for r in auto) / total, 1) for n in names}

auto_rej_reasons = rej_check_fail_counts()

# Whitelisted (event code) bypass stats
whitelist_appr = sum(
    1 for r in data
    if r.get("status") in APPROVED and any(
        c["name"] == "WhiteListCheck" and c["status"] == "success"
        for c in r.get("checkResult", [])
    )
)

# time-to-review (hours)
review_times = []
for r in data:
    t0 = [h["time"] for h in r.get("history", []) if h["event"] == "Registration pending"]
    t1 = [h["time"] for h in r.get("history", []) if h["event"] == "Review"]
    if t0 and t1:
        review_times.append((min(t1) - min(t0)) / 3_600_000)
review_times.sort()
p50 = review_times[len(review_times) // 2] if review_times else 0
p90 = review_times[int(len(review_times) * 0.9)] if review_times else 0

# EVS (export control) failures
evs_embargo = sum(
    1 for r in data
    if any(c["name"] == "EvsCheck" and "Embargoed" in c.get("message", "")
           for c in r.get("checkResult", []))
)


# ── Score-gate summary (default-event path) ───────────────────────────────────
def _st(r, name): return parse_checks(r)(name)["status"]
def _appr(r):     return r.get("status") in APPROVED
def _manual(r):   return any(h["event"] == "Review" for h in r.get("history", []))

both_pass = [r for r in default_recs if _st(r, "IPCheck") == "success" and _st(r, "EmailCheck") == "success"]
any_fail  = [r for r in default_recs if _st(r, "IPCheck") == "failed"  or  _st(r, "EmailCheck") == "failed"]
score_gate = {
    "default_total":        len(default_recs),
    "default_approved":     sum(map(_appr, default_recs)),
    "both_pass":            len(both_pass),
    "both_pass_approved":   sum(map(_appr, both_pass)),
    "any_fail":             len(any_fail),
    "any_fail_approved":    sum(map(_appr, any_fail)),
    "any_fail_auto_denied": sum(1 for r in any_fail if r.get("status") == "rejected" and not _manual(r)),
    "any_fail_manual_denied": sum(1 for r in any_fail if r.get("status") == "rejected" and _manual(r)),
    "event_total":          len(event_recs),
    "event_approved":       sum(map(_appr, event_recs)),
    "event_approved_with_failed_score": sum(
        1 for r in event_recs if _appr(r) and (_st(r, "IPCheck") == "failed" or _st(r, "EmailCheck") == "failed")),
    "any_fail_reviewed_approved": sum(1 for r in any_fail if _appr(r) and _manual(r)),
    "any_fail_whitelist_approved": sum(1 for r in any_fail if _appr(r) and _st(r, "WhiteListCheck") == "success"),
    "event_no_checks":      sum(1 for r in event_recs if not r.get("checkResult")),
    "pending":              sum(1 for r in data if r.get("status") in ("pending",)),
    "leaked_total":         sum(1 for r in data if "leaked" in parse_checks(r)("EmailCheck")["message"]),
    "leaked_approved":      sum(1 for r in data if "leaked" in parse_checks(r)("EmailCheck")["message"] and _appr(r)),
}

fraud_section = {
    "ip_scores":     ip_scores,
    "email_scores":  email_scores,
    "manual_rejected": manual_rej,
    "auto_rejected":   auto_rej,
    "auto_rej_reasons": auto_rej_reasons,
    "whitelist_approved": whitelist_appr,
    "review_median_h": round(p50, 1),
    "review_p90_h":    round(p90, 1),
    "evs_embargo":     evs_embargo,
    "score_gate":      score_gate,
    "total": len(data),
    "approved": len(approved_recs),
}

# ═══════════════════════════════════════════════════════════════════════════════
# 7. COUNTRY CORRELATIONS (top-15, same as before but both years)
# ═══════════════════════════════════════════════════════════════════════════════
TOPICS = {
    "IBM Z / LinuxONE": r"ibm\s*z|linuxone|linux\s*one|z\s*xplore|lnx1|s390x|mainframe|zxplore",
    "Learning / Education": r"\b(learn|study|student|education|course|university|college|thesis|academic)\b",
    "Web / Hosting": r"\b(website|web\s*host|blog|wordpress|vps|hosting|nginx|apache|domain)\b",
    "AI / ML": r"\b(ai|machine\s*learning|deep\s*learning|neural|llm|gpt|chatbot|nlp|artificial\s*intelligence|data\s*scien)\b",
    "Security / VPN": r"\b(security|encrypt|vpn|wireguard|firewall|cybersec|ssl|tls|blockchain|quantum)\b",
    "DevOps / Cloud": r"\b(kubernetes|docker|ci[\s/]?cd|devops|cloud|deploy|container|microservice)\b",
}

country_counts = Counter(r.get("country", "") for r in data)
top_countries = [cc for cc, _ in country_counts.most_common(15) if cc and cc != "N/A"]

filler_pat = r"^[x\.\-\s\?\_ !]{10,}$|^(test|education|learning|study|learn|learn linux|i want to learn)\s*$"
country_avg_len, country_dupe_pct, filler_pct = {}, {}, {}
topic_matrix = {}

for cc in top_countries:
    recs = [r for r in data if r.get("country") == cc]
    lengths = [len(r.get("purpose", "")) for r in recs]
    country_avg_len[cc] = round(sum(lengths) / len(lengths), 1)
    purposes = [r.get("purpose", "").strip() for r in recs if len(r.get("purpose", "").strip()) > 20]
    dupes = Counter(purposes)
    dupe_count = sum(c - 1 for c in dupes.values() if c > 1)
    country_dupe_pct[cc] = round(100 * dupe_count / len(purposes), 1) if purposes else 0
    fillers = sum(1 for r in recs if re.match(filler_pat, r.get("purpose", "").strip(), re.IGNORECASE))
    filler_pct[cc] = round(100 * fillers / len(recs), 1)
    row = {}
    for topic, pat in TOPICS.items():
        matches = sum(1 for r in recs if re.search(pat, r.get("purpose", ""), re.IGNORECASE))
        row[topic] = round(100 * matches / len(recs), 1)
    topic_matrix[cc] = row

correlations = {
    "countries": top_countries,
    "registration_counts": [country_counts[cc] for cc in top_countries],
    "avg_purpose_len": [country_avg_len[cc] for cc in top_countries],
    "dupe_pct": [country_dupe_pct[cc] for cc in top_countries],
    "filler_pct": [filler_pct[cc] for cc in top_countries],
    "topics": list(TOPICS.keys()),
    "topic_matrix": {cc: [topic_matrix[cc][t] for t in TOPICS] for cc in top_countries},
}


_ipc = Counter(r.get("ip", "") for r in data if r.get("ip"))
ip_repeat = {
    "threshold": 20,
    "ips_over_threshold":  sum(1 for n in _ipc.values() if n > 20),
    "regs_from_those_ips": sum(n for n in _ipc.values() if n > 20),
    "max_regs_one_ip":     max(_ipc.values()) if _ipc else 0,
}

# ═══════════════════════════════════════════════════════════════════════════════
# 7b. APPROVAL BY COUNTRY (countries with >=300 registrations)
# ═══════════════════════════════════════════════════════════════════════════════
_cc = defaultdict(lambda: [0, 0])
for r in data:
    c = r.get("country", "")
    if c and c != "N/A":
        _cc[c][0] += 1
        _cc[c][1] += _appr(r)
approval_by_country = sorted(
    [{"country": c, "total": v[0], "approved": v[1], "appr_pct": round(100 * v[1] / v[0], 1)}
     for c, v in _cc.items() if v[0] >= 300],
    key=lambda x: x["appr_pct"])

# ═══════════════════════════════════════════════════════════════════════════════
# 7c. 75-CHAR LIMIT FACTS (measured, not assumed)
# ═══════════════════════════════════════════════════════════════════════════════
_pre_len  = [len(r.get("purpose", "")) for r in pre_recs]
_post_len = [len(r.get("purpose", "")) for r in post_recs]
_template = re.compile(r"your input must be at least 75 characters", re.I)
limit_facts = {
    "cutover_utc":        "2025-07-10 06:00",
    "pre_max_len":        max(_pre_len),
    "post_max_len":       max(_post_len),
    "pre_median_len":     sorted(_pre_len)[len(_pre_len) // 2],
    "post_median_len":    sorted(_post_len)[len(_post_len) // 2],
    "pre_under75":        sum(1 for l in _pre_len if l < 75),
    "post_under75":       sum(1 for l in _post_len if l < 75),
    "post_exact75":       sum(1 for l in _post_len if l == 75),
    "pre_exact75":        sum(1 for l in _pre_len if l == 75),
    "post_form_msg":      sum(1 for r in post_recs if _template.search(r.get("purpose", ""))),
    "post_under75_ma_education": sum(
        1 for r in post_recs
        if len(r.get("purpose", "")) < 75 and r.get("purpose", "").strip().lower() == "education"
        and r.get("country") == "MA"),
}


# ═══════════════════════════════════════════════════════════════════════════════
# 7d. SINGLE-DAY SPIKES
# ═══════════════════════════════════════════════════════════════════════════════
_day = defaultdict(list)
for r in data:
    _day[utc(r).strftime("%Y-%m-%d")].append(r)
_avg_day = len(data) / len(_day)
top_days = []
for dkey, recs in sorted(_day.items(), key=lambda kv: -len(kv[1]))[:8]:
    cc = Counter(r.get("country", "") for r in recs).most_common(1)[0]
    top_days.append({
        "day": dkey, "total": len(recs),
        "top_country": cc[0], "top_country_n": cc[1],
        "appr_pct": round(100 * sum(_appr(r) for r in recs) / len(recs), 1),
        "default_pct": round(100 * sum(r["eventCode"] == "default" for r in recs) / len(recs), 1),
    })
spikes = {"avg_per_day": round(_avg_day, 1), "top_days": top_days}

# ═══════════════════════════════════════════════════════════════════════════════
# 8. 75-CHAR WEEKLY TIMELINE (kept for that tab)
# ═══════════════════════════════════════════════════════════════════════════════
weekly = defaultdict(lambda: {"total": 0, "short": 0, "long": 0, "exact75": 0})
for r in data:
    wk = utc(r).strftime("%G-W%V")
    plen = len(r.get("purpose", ""))
    weekly[wk]["total"] += 1
    if plen < 75:
        weekly[wk]["short"] += 1
    else:
        weekly[wk]["long"] += 1
    if plen == 75:
        weekly[wk]["exact75"] += 1

timeline_weeks = sorted(weekly.keys())
timeline = {
    "weeks":    timeline_weeks,
    "short":    [weekly[w]["short"]  for w in timeline_weeks],
    "long":     [weekly[w]["long"]   for w in timeline_weeks],
    "exact75":  [weekly[w]["exact75"] for w in timeline_weeks],
    "pct_long": [
        round(100 * weekly[w]["long"] / weekly[w]["total"], 1) if weekly[w]["total"] else 0
        for w in timeline_weeks
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
# 9. SUMMARY KPIs
# ═══════════════════════════════════════════════════════════════════════════════
summary = {
    "total_records":      len(data),
    "total_2025":         sum(1 for r in data if year(r) == 2025),
    "total_2026":         sum(1 for r in data if year(r) == 2026),
    "files_2025":         len(data25),
    "files_2026":         len(data26),
    "total_approved":     len(approved_recs),
    "total_countries":    len({r.get("country", "") for r in data} - {"", "N/A"}),
    "date_range_start":   utc(data[0]).strftime("%d %b %Y"),
    "date_range_end":     utc(data[-1]).strftime("%d %b %Y"),
    "transition_week":    "2025-W28",
    "transition_note":    "A 75–500 character limit on the purpose field is enforced from 10 Jul 2025.",
}

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE
# ═══════════════════════════════════════════════════════════════════════════════
output = {
    "summary":              summary,
    "months":               months,
    "monthly_total":        monthly_total,
    "monthly_approved":     monthly_approved,
    "monthly_zxplore":      monthly_zxplore,
    "monthly_zxplore_event":   monthly_zxplore_event,
    "monthly_zxplore_purpose": monthly_zxplore_purpose,
    "monthly_edu":          monthly_edu,
    "categories_all":       categories_all,
    "categories_approved":  categories_approved,
    "limit_impact":         limit_impact,
    "spam_countries":       top_spam_countries,
    "spam_by_country":      spam_by_country_month,
    "events":               events,
    "fraud":                fraud_section,
    "correlations":         correlations,
    "approval_by_country":  approval_by_country,
    "limit_facts":          limit_facts,
    "ip_repeat":            ip_repeat,
    "spikes":               spikes,
    "timeline":             timeline,
}

with open("dashboard_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

print("✓ dashboard_data.json written")
print(f"  {len(data):,} total records ({len(data25):,} 2025 + {len(data26):,} 2026)")
print(f"  {len(approved_recs):,} approved  |  {len(data)-len(approved_recs):,} not approved")
print(f"  {len(months)} months  |  {len(top_countries)} countries  |  {len(events)} events")
