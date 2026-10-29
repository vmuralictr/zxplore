#!/usr/bin/env node
/**
 * generate_data.js
 * Pre-processes registrations_2025.json + registrations_2026.json → dashboard_data.json
 * Run: node generate_data.js
 *
 * Drop-in JavaScript replacement for generate_data.py — produces identical output.
 */

'use strict';

const fs = require('fs');

// ── Load ──────────────────────────────────────────────────────────────────────
const data25 = JSON.parse(fs.readFileSync('registrations_2025.json', 'utf8'));
const data26 = JSON.parse(fs.readFileSync('registrations_2026.json', 'utf8'));
const data   = [...data25, ...data26].sort((a, b) => Number(a.regTime) - Number(b.regTime));

const APPROVED = new Set(['success', 'expired', 'waitforactive']);

function utc(r) { return new Date(Number(r.regTime)); }
function ym(r)  { const d = utc(r); return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`; }
function yr(r)  { return utc(r).getUTCFullYear(); }
function isAppr(r) { return APPROVED.has(r.status); }

// ── Check-result parser ───────────────────────────────────────────────────────
const CK_ZERO = { name: null, status: null, message: '' };
function parseChecks(r) {
  const map = {};
  for (const c of (r.checkResult || [])) map[c.name] = c;
  return name => map[name] || CK_ZERO;
}

function fraudScore(msg) {
  if (!msg) return null;
  const m = msg.match(/fraud_?[sS]core(?:\s*is\s*|\s*=\s*)(\d+)/);
  return m ? parseInt(m[1], 10) : null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// CATEGORIES — first-match-wins classifier
// ═══════════════════════════════════════════════════════════════════════════════
const CATEGORIES = [
  ['IBM Z Xplore / LNX Program',
   /ibm\s*z\s*xplore|z\s*xplore|zxplore|lnx\s*[123]|linuxone\s*community\s*cloud|z\s*student\s*program|ibm\s*gsap|ibmzxplore|ibmzexplore/i],
  ['Hackathon / Datathon',
   /hackathon|datathon|ssf[\s_]?2025|ssf2025|\bcompetition\b|\bcontest\b|ideathon|codeathon|ibm\s*z\s*datathon|ibm\s*datathon|smart\s*india\s*hackathon/i],
  ['AI / Machine Learning',
   /\b(artificial\s+intelligence|machine\s+learning|deep\s+learning|neural\s+net|large\s+language\s+model|\bllm\b|natural\s+language\s+processing|\bnlp\b|computer\s+vision|generative\s+ai|\bgen[\s\-]?ai\b|ai[\s\-]powered|ai[\s\-]based|ai[\s\-]driven|ai[\s\-]model|ai[\s\-]agent|ai\s+platform|transformer\s+model|convolutional|reinforcement\s+learning|random\s+forest|gradient\s+boost|\byolo\b|object\s+detection|image\s+(recognition|classification)|chatbot|recommendation\s+system|sentiment\s+analysis|predictive\s+(model|analytics)|predict\s+(disease|accident|flood|crop|stock|price|weather|churn|risk)|classification\s+model|data\s+scien)\b/i],
  ['Web Development / Hosting',
   /\b(host\s+(a\s+)?(website|web[\s\-]?app|blog|site)|personal\s+(website|site|blog|portfolio)|build\s+(a\s+)?(website|web[\s\-]?app|web\s*site|site|blog)|setup\s+(a\s+)?(website|web\s*site|site)|set\s+up\s+(a\s+)?(website|web\s*site|site)|deploy\s+(a\s+)?web|wordpress|nginx|apache|e[\-\s]?commerce|web\s+server|web\s+hosting|website\s+hosting|web\s+portfolio|portfolio\s+website|website\s+development|web\s+development|develop\s+(a\s+)?(website|web[\s\-]?app|web\s*site|site)|create\s+(a\s+)?(website|web[\s\-]?app|web\s*site|site|blog)|build\s+web\b|develop\s+web\b|building\s+(a\s+)?(website|web|blog|site)|web\s+application)\b/i],
  ['DevOps / Cloud / Infrastructure',
   /\b(kubernetes|\bk8s\b|docker|ci[\s\/]?cd|devops|terraform|ansible|\bhelm\b|microservice|containeriz|orchestrat|cloud\s+native|cloud[\s\-]native|infrastructure\s+as\s+code|\biac\b|service\s+mesh|jenkins|github\s+actions|gitlab\s+ci|continuous\s+integration|continuous\s+deployment|\berp\b)\b/i],
  ['Security / Networking / VPN',
   /\b(vpn|wireguard|openvpn|firewall|penetration\s+test|pen\s+test|cybersecur|network\s+secur|encrypt|zero[\s\-]trust|\bddos\b|proxy\s+server|reverse\s+proxy|tunneling|privac|anonymi|\bctf\b|capture\s+the\s+flag|key\s+management)\b/i],
  ['Database / Data Engineering',
   /\b(postgresql|mysql|mongodb|sqlite|\bredis\b|cassandra|elasticsearch|data\s+warehouse|\betl\b|data\s+pipeline|data\s+engineer|apache\s+spark|hadoop|kafka|\bdb2\b|sql\s+server|mariadb|data\s+analytic|data\s+visual|big\s+data|analytics\s+platform)\b/i],
  ['Blockchain / Web3',
   /\b(blockchain|crypto(?:currency)?|\bnft\b|\bdefi\b|\bweb3\b|smart\s+contract|ethereum|bitcoin|solidity|decentrali[sz])\b/i],
  ['IoT / Embedded Systems',
   /\b(iot\b|internet\s+of\s+things|embedded\s+system|raspberry\s+pi|arduino|sensor\s+data|smart\s+home|edge\s+computing|firmware)\b/i],
  ['App / Software Development',
   /\b(mobile\s+app|android\s+app|ios\s+app|flutter|react\s+native|discord\s+bot|telegram\s+bot|api\s+server|rest\s+api|backend\s+serv|full[\s\-]stack|develop\s+(an?\s+)?(app|application|platform|system|tool|service|software)|build\s+(an?\s+)?(app|application|platform|system|tool|service|software)|create\s+(an?\s+)?(app|application|platform|system|tool)|game\s+server|minecraft|building\s+(an?\s+)?(app|application|platform)|developing\s+(an?\s+)?(app|application|platform|system|software))\b/i],
  ['Testing / Development Sandbox',
   /\b(test(ing)?\s+(my|this|the|a|an?)\s+\w+|for\s+test(ing)?\s+(purposes?|only|and)|development\s+and\s+test|sandbox|staging\s+environment|dev(elopment)?\s+environment|testing\s+environment|proof\s+of\s+concept|\bpoc\b|prototype|stress\s+test|load\s+test|testing.*validation)\b/i],
  ['Research / Academic',
   /\b(research|thesis|dissertation|\bphd\b|masters?\s+degree|academic|university\s+project|capstone|graduate\s+studi|undergraduate|faculty|laboratory|scientific\s+comput|paper\s+submission|publication)\b/i],
  ['IBM LinuxONE / s390x Exploration',
   /\b(linuxone|linux\s*one|s390x|ibm\s+z\b|mainframe|ibm\s+linuxone|z\s+architecture|\bzos\b|z\/os)\b/i],
  ['Learning Linux / Sysadmin',
   /\b(learn\s+(linux|bash|shell|cli|command[\s\-]line|unix|ubuntu|centos|fedora)|study\s+linux|linux\s+(course|training|skill|fundament|command|admin|practice|operation|basic|knowledge)|system\s+administ|shell\s+script|bash\s+script|linux\s+certif|lfcs|lpic|rhcsa|linux\s+basics|linux\s+mastery|linux\s+skill|linux\s+knowledge|linux\s+environment|linux\s+experience|command\s+line\s+skill)\b/i],
  ['Learning Programming / Technology',
   /\b(learn(ing)?\s+(python|java|javascript|golang|rust|c\+\+|c#|ruby|php|html|css|react|node\.?js|programming|coding|software|cloud|networking|computer\s+science|technology|\btech\b)|study(ing)?\s+(python|java|javascript|programming|coding|software|cloud|computer\s+science|technology)|improve\s+(my\s+)?(coding|programming|technical|dev|software)\s+skill|learn\s+to\s+(code|program|develop)|learning\s+to\s+(build|develop|deploy))\b/i],
  ['Marketing Spam / Template',
   /\b(seo\s+rank|search\s+engine\s+optim|keyword\s+rank|backlink|please\s+provide\s+a\s+more\s+detailed|your\s+input\s+must\s+be\s+at\s+least\s+75\s+characters)\b|\bselling\s+your\s+products\s+or\s+services\s+and\s+driving\s+revenue\b|\bfix\s+site\s+issues.*find\s+profitable\b/i],
  ['Filler / Spam',
   /^[\s\W\d]{0,5}$|^\s*(test|hello|hi|ok|yes|no|none|n\/a|education|learning|study|learn|learn linux|i want to learn|i want to learn linux|service|web|vps|server|work|project|purpose|study linux|linux|build web|build a web|develop website|develop web|build website|build a website|judge|fder|be honest|i want to build a web)\s*[.!]?\s*$/i],
];

const LEARN_GENERIC = /\b(learn|study|education|training|practice|improve\s+skill|course|tutorial)\b/i;

function classify(purpose) {
  const p = purpose.trim();
  if (p.length < 4) return 'Filler / Spam';
  const words = p.match(/[a-zA-Z]{2,}/g) || [];
  if (p.length > 8 && words.length === 0) return 'Filler / Spam';
  if (p.length >= 10 && new Set(p.replace(/ /g, '').toLowerCase()).size <= 3) return 'Filler / Spam';
  for (const [name, pat] of CATEGORIES) {
    if (pat.test(p)) return name;
  }
  if (LEARN_GENERIC.test(p) && p.length < 150) return 'General Learning (Unspecified)';
  if (/\blinux\b/i.test(p)) return 'Learning Linux / Sysadmin';
  return 'Other / Unclassified';
}

const ORDERED_CATS = [
  'Web Development / Hosting', 'Learning Linux / Sysadmin', 'Filler / Spam',
  'General Learning (Unspecified)', 'AI / Machine Learning',
  'IBM Z Xplore / LNX Program', 'IBM LinuxONE / s390x Exploration',
  'Testing / Development Sandbox', 'DevOps / Cloud / Infrastructure',
  'Research / Academic', 'App / Software Development',
  'Learning Programming / Technology', 'Marketing Spam / Template',
  'Security / Networking / VPN', 'Hackathon / Datathon',
  'Database / Data Engineering', 'Blockchain / Web3',
  'IoT / Embedded Systems', 'Other / Unclassified',
];

const SPAM_CATS    = new Set(['Filler / Spam', 'Marketing Spam / Template']);
const EDU_CATS     = new Set(['Learning Linux / Sysadmin', 'Learning Programming / Technology', 'General Learning (Unspecified)', 'Research / Academic']);
const ZXPLORE_CATS = new Set(['IBM Z Xplore / LNX Program']);

// Classify all records once
for (const r of data) r._cat = classify(r.purpose || '');

// ── Counter helpers ───────────────────────────────────────────────────────────
function counter(arr, keyFn) {
  const m = new Map();
  for (const x of arr) {
    const k = keyFn(x);
    m.set(k, (m.get(k) || 0) + 1);
  }
  return m;
}

function mostCommon(map, n) {
  return [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
}

// ═══════════════════════════════════════════════════════════════════════════════
// MONTHS list
// ═══════════════════════════════════════════════════════════════════════════════
const allMonthsSet = new Set(data.map(ym));
const months = [...allMonthsSet].sort();

function monthlyCounts(recs, keyFn) {
  const c = counter(recs, keyFn);
  return months.map(m => c.get(m) || 0);
}

// ═══════════════════════════════════════════════════════════════════════════════
// 1. CATEGORIES — all users and approved-only, both years
// ═══════════════════════════════════════════════════════════════════════════════
function catTable(records) {
  const c  = counter(records, r => r._cat);
  const c5 = counter(records.filter(r => yr(r) === 2025), r => r._cat);
  const c6 = counter(records.filter(r => yr(r) === 2026), r => r._cat);
  const total25 = records.filter(r => yr(r) === 2025).length;
  const total26 = records.filter(r => yr(r) === 2026).length;
  return {
    labels:      ORDERED_CATS,
    counts:      ORDERED_CATS.map(cat => c.get(cat)  || 0),
    counts_2025: ORDERED_CATS.map(cat => c5.get(cat) || 0),
    counts_2026: ORDERED_CATS.map(cat => c6.get(cat) || 0),
    total:       records.length,
    total_2025:  total25,
    total_2026:  total26,
  };
}

const approvedRecs = data.filter(r => isAppr(r));
const categoriesAll      = catTable(data);
const categoriesApproved = catTable(approvedRecs);

// ═══════════════════════════════════════════════════════════════════════════════
// 2. 75-CHAR LIMIT IMPACT
// ═══════════════════════════════════════════════════════════════════════════════
const CUTOVER_MS = new Date('2025-07-10T06:00:00Z').getTime();
const preRecs  = data.filter(r => Number(r.regTime) <  CUTOVER_MS);
const postRecs = data.filter(r => Number(r.regTime) >= CUTOVER_MS);

function catPct(records) {
  const total = records.length || 1;
  const c = counter(records, r => r._cat);
  const out = {};
  for (const cat of ORDERED_CATS) out[cat] = Math.round(1000 * (c.get(cat) || 0) / total) / 10;
  return out;
}

const purposeCounts = counter(data, r => (r.purpose || '').trim().toLowerCase());
const MASS_DUP = 50;
const preDedup  = preRecs.filter(r  => (purposeCounts.get((r.purpose||'').trim().toLowerCase()) || 0) < MASS_DUP);
const postDedup = postRecs.filter(r => (purposeCounts.get((r.purpose||'').trim().toLowerCase()) || 0) < MASS_DUP);

const preC  = counter(preRecs,  r => r._cat);
const postC = counter(postRecs, r => r._cat);
const prePct   = catPct(preRecs);
const postPct  = catPct(postRecs);
const preDedupPct  = catPct(preDedup);
const postDedupPct = catPct(postDedup);

const massDupTop = mostCommon(purposeCounts, 20)
  .filter(([, n]) => n >= MASS_DUP)
  .slice(0, 6)
  .map(([t, n]) => [t.slice(0, 60), n]);

const limitImpact = {
  labels:             ORDERED_CATS,
  pre_total:          preRecs.length,
  post_total:         postRecs.length,
  pre_pct:            ORDERED_CATS.map(c => prePct[c]),
  post_pct:           ORDERED_CATS.map(c => postPct[c]),
  pre_count:          ORDERED_CATS.map(c => preC.get(c) || 0),
  post_count:         ORDERED_CATS.map(c => postC.get(c) || 0),
  mass_dup_threshold: MASS_DUP,
  pre_total_dedup:    preDedup.length,
  post_total_dedup:   postDedup.length,
  pre_pct_dedup:      ORDERED_CATS.map(c => preDedupPct[c]),
  post_pct_dedup:     ORDERED_CATS.map(c => postDedupPct[c]),
  mass_dup_regs:      [...purposeCounts.values()].filter(n => n >= MASS_DUP).reduce((a, b) => a + b, 0),
  mass_dup_top:       massDupTop,
};

// ═══════════════════════════════════════════════════════════════════════════════
// 3. MONTHLY REGISTRATIONS — total, ZXplore, Education
// ═══════════════════════════════════════════════════════════════════════════════
const monthlyTotal    = monthlyCounts(data, ym);
const zxEvent         = data.filter(r => r.eventCode === 'IBMZXPLORE');
const zxPurpose       = data.filter(r => r.eventCode !== 'IBMZXPLORE' && ZXPLORE_CATS.has(r._cat));
const monthlyZxEvent   = monthlyCounts(zxEvent,   ym);
const monthlyZxPurpose = monthlyCounts(zxPurpose, ym);
const monthlyZxplore   = monthlyZxEvent.map((v, i) => v + monthlyZxPurpose[i]);
const monthlyEdu       = monthlyCounts(data.filter(r => EDU_CATS.has(r._cat)), ym);
const monthlyApproved  = monthlyCounts(approvedRecs, ym);

// ═══════════════════════════════════════════════════════════════════════════════
// 4. SPAM BY COUNTRY PER MONTH
// ═══════════════════════════════════════════════════════════════════════════════
const spamRecs = data.filter(r => SPAM_CATS.has(r._cat));
const spamCountryCount = counter(spamRecs, r => r.country || '');
const topSpamCountries = mostCommon(spamCountryCount, 20)
  .map(([cc]) => cc)
  .filter(cc => cc && cc !== 'N/A')
  .slice(0, 12);

const spamByCountry = {};
for (const cc of topSpamCountries) {
  const recs = spamRecs.filter(r => r.country === cc);
  spamByCountry[cc] = monthlyCounts(recs, ym);
}

// ═══════════════════════════════════════════════════════════════════════════════
// 5. EVENTS
// ═══════════════════════════════════════════════════════════════════════════════
const eventCounter = counter(data, r => r.eventCode);
const topEvents = mostCommon(eventCounter, 20)
  .map(([ec]) => ec)
  .filter(ec => ec && ec !== 'bgtest')
  .slice(0, 15);

const events = topEvents.map(ec => {
  const recs  = data.filter(r => r.eventCode === ec);
  const appr  = recs.filter(r => isAppr(r));
  const ipF   = recs.filter(r => parseChecks(r)('IPCheck').status === 'failed').length;
  const emF   = recs.filter(r => parseChecks(r)('EmailCheck').status === 'failed').length;
  const catCt = counter(recs, r => r._cat);
  return {
    code:        ec,
    total:       recs.length,
    approved:    appr.length,
    appr_pct:    Math.round(1000 * appr.length / recs.length) / 10,
    ip_fail_pct: Math.round(1000 * ipF / recs.length) / 10,
    em_fail_pct: Math.round(1000 * emF / recs.length) / 10,
    monthly:     monthlyCounts(recs, ym),
    no_checks:   recs.filter(r => !(r.checkResult && r.checkResult.length)).length,
    first:       ym(recs[0]),
    last:        ym(recs[recs.length - 1]),
    top_cats:    mostCommon(catCt, 5),
  };
});

// ═══════════════════════════════════════════════════════════════════════════════
// 6. EMAIL / IP FRAUD SCORES & APPROVAL OUTCOMES
// ═══════════════════════════════════════════════════════════════════════════════
function scoreBucket(s) {
  if (s === null || s === undefined) return 'No score';
  if (s === 0)   return '0';
  if (s < 50)    return '1\u201349';
  if (s <= 75)   return '50\u201375';
  if (s < 85)    return '76\u201384';
  if (s < 100)   return '85\u201399';
  return '100';
}

const SCORE_BUCKETS = ['0', '1\u201349', '50\u201375', '76\u201384', '85\u201399', '100', 'No score'];

function scoreRows(records, checkName) {
  const rows = {};
  for (const b of SCORE_BUCKETS) rows[b] = [0, 0];
  for (const r of records) {
    const ck  = parseChecks(r)(checkName);
    const s   = fraudScore(ck.message);
    const bkt = scoreBucket(s);
    rows[bkt][0]++;
    if (isAppr(r)) rows[bkt][1]++;
  }
  return {
    buckets:  SCORE_BUCKETS,
    total:    SCORE_BUCKETS.map(b => rows[b][0]),
    approved: SCORE_BUCKETS.map(b => rows[b][1]),
    denied:   SCORE_BUCKETS.map(b => rows[b][0] - rows[b][1]),
    appr_pct: SCORE_BUCKETS.map(b => rows[b][0] ? Math.round(1000 * rows[b][1] / rows[b][0]) / 10 : 0),
  };
}

const defaultRecs = data.filter(r => r.eventCode === 'default');
const eventRecs   = data.filter(r => r.eventCode !== 'default');

const ipScores    = scoreRows(defaultRecs, 'IPCheck');
const emailScores = scoreRows(defaultRecs, 'EmailCheck');

function hasReview(r) { return (r.history || []).some(h => h.event === 'Review'); }

const manualRej = data.filter(r => r.status === 'rejected' && hasReview(r)).length;
const autoRej   = data.filter(r => r.status === 'rejected' && !hasReview(r)).length;

function rejCheckFailCounts() {
  const names = ['IPCheck', 'EmailCheck', 'EvsCheck', 'ReviewCheck'];
  const auto  = data.filter(r => r.status === 'rejected' && !hasReview(r));
  const total = auto.length || 1;
  const out   = {};
  for (const n of names)
    out[n] = Math.round(1000 * auto.filter(r => parseChecks(r)(n).status === 'failed').length / total) / 10;
  return out;
}

const autoRejReasons = rejCheckFailCounts();

const whitelistAppr = data.filter(r =>
  isAppr(r) && (r.checkResult || []).some(c => c.name === 'WhiteListCheck' && c.status === 'success')
).length;

// time-to-review (hours)
const reviewTimes = [];
for (const r of data) {
  const t0s = (r.history || []).filter(h => h.event === 'Registration pending').map(h => h.time);
  const t1s = (r.history || []).filter(h => h.event === 'Review').map(h => h.time);
  if (t0s.length && t1s.length)
    reviewTimes.push((Math.min(...t1s) - Math.min(...t0s)) / 3_600_000);
}
reviewTimes.sort((a, b) => a - b);
const p50 = reviewTimes.length ? reviewTimes[Math.floor(reviewTimes.length / 2)]           : 0;
const p90 = reviewTimes.length ? reviewTimes[Math.floor(reviewTimes.length * 0.9)]          : 0;

// EVS embargo failures
const evsEmbargo = data.filter(r =>
  (r.checkResult || []).some(c => c.name === 'EvsCheck' && (c.message || '').includes('Embargoed'))
).length;

// Score-gate summary
function ckSt(r, name) { return parseChecks(r)(name).status; }
const bothPass = defaultRecs.filter(r => ckSt(r, 'IPCheck') === 'success' && ckSt(r, 'EmailCheck') === 'success');
const anyFail  = defaultRecs.filter(r => ckSt(r, 'IPCheck') === 'failed'  || ckSt(r, 'EmailCheck') === 'failed');

const scoreGate = {
  default_total:          defaultRecs.length,
  default_approved:       defaultRecs.filter(isAppr).length,
  both_pass:              bothPass.length,
  both_pass_approved:     bothPass.filter(isAppr).length,
  any_fail:               anyFail.length,
  any_fail_approved:      anyFail.filter(isAppr).length,
  any_fail_auto_denied:   anyFail.filter(r => r.status === 'rejected' && !hasReview(r)).length,
  any_fail_manual_denied: anyFail.filter(r => r.status === 'rejected' && hasReview(r)).length,
  event_total:            eventRecs.length,
  event_approved:         eventRecs.filter(isAppr).length,
  event_approved_with_failed_score: eventRecs.filter(r =>
    isAppr(r) && (ckSt(r, 'IPCheck') === 'failed' || ckSt(r, 'EmailCheck') === 'failed')).length,
  any_fail_reviewed_approved: anyFail.filter(r => isAppr(r) && hasReview(r)).length,
  any_fail_whitelist_approved: anyFail.filter(r =>
    isAppr(r) && ckSt(r, 'WhiteListCheck') === 'success').length,
  event_no_checks:        eventRecs.filter(r => !(r.checkResult && r.checkResult.length)).length,
  pending:                data.filter(r => r.status === 'pending').length,
  leaked_total:           data.filter(r => (parseChecks(r)('EmailCheck').message || '').includes('leaked')).length,
  leaked_approved:        data.filter(r => (parseChecks(r)('EmailCheck').message || '').includes('leaked') && isAppr(r)).length,
};

const fraudSection = {
  ip_scores:          ipScores,
  email_scores:       emailScores,
  manual_rejected:    manualRej,
  auto_rejected:      autoRej,
  auto_rej_reasons:   autoRejReasons,
  whitelist_approved: whitelistAppr,
  review_median_h:    Math.round(p50 * 10) / 10,
  review_p90_h:       Math.round(p90 * 10) / 10,
  evs_embargo:        evsEmbargo,
  score_gate:         scoreGate,
  total:              data.length,
  approved:           approvedRecs.length,
};

// ═══════════════════════════════════════════════════════════════════════════════
// 7. COUNTRY CORRELATIONS (top-15)
// ═══════════════════════════════════════════════════════════════════════════════
const TOPICS = {
  'IBM Z / LinuxONE':      /ibm\s*z|linuxone|linux\s*one|z\s*xplore|lnx1|s390x|mainframe|zxplore/i,
  'Learning / Education':  /\b(learn|study|student|education|course|university|college|thesis|academic)\b/i,
  'Web / Hosting':         /\b(website|web\s*host|blog|wordpress|vps|hosting|nginx|apache|domain)\b/i,
  'AI / ML':               /\b(ai|machine\s*learning|deep\s*learning|neural|llm|gpt|chatbot|nlp|artificial\s*intelligence|data\s*scien)\b/i,
  'Security / VPN':        /\b(security|encrypt|vpn|wireguard|firewall|cybersec|ssl|tls|blockchain|quantum)\b/i,
  'DevOps / Cloud':        /\b(kubernetes|docker|ci[\s\/]?cd|devops|cloud|deploy|container|microservice)\b/i,
};

const countryCountMap = counter(data, r => r.country || '');
const topCountries = mostCommon(countryCountMap, 20)
  .map(([cc]) => cc)
  .filter(cc => cc && cc !== 'N/A')
  .slice(0, 15);

const fillerPat = /^[x.\-\s?_ !]{10,}$|^(test|education|learning|study|learn|learn linux|i want to learn)\s*$/i;
const countryAvgLen = {}, countryDupePct = {}, fillerPct = {}, topicMatrix = {};

for (const cc of topCountries) {
  const recs    = data.filter(r => r.country === cc);
  const lengths = recs.map(r => (r.purpose || '').length);
  countryAvgLen[cc] = Math.round(lengths.reduce((a, b) => a + b, 0) / lengths.length * 10) / 10;

  const purposes = recs.map(r => (r.purpose || '').trim()).filter(p => p.length > 20);
  const dupMap   = counter(purposes, p => p);
  const dupeCount = [...dupMap.values()].filter(c => c > 1).reduce((a, c) => a + (c - 1), 0);
  countryDupePct[cc] = purposes.length ? Math.round(1000 * dupeCount / purposes.length) / 10 : 0;

  fillerPct[cc] = Math.round(1000 * recs.filter(r => fillerPat.test((r.purpose || '').trim())).length / recs.length) / 10;

  topicMatrix[cc] = Object.entries(TOPICS).map(([, pat]) =>
    Math.round(1000 * recs.filter(r => pat.test(r.purpose || '')).length / recs.length) / 10
  );
}

const correlations = {
  countries:            topCountries,
  registration_counts:  topCountries.map(cc => countryCountMap.get(cc) || 0),
  avg_purpose_len:      topCountries.map(cc => countryAvgLen[cc]),
  dupe_pct:             topCountries.map(cc => countryDupePct[cc]),
  filler_pct:           topCountries.map(cc => fillerPct[cc]),
  topics:               Object.keys(TOPICS),
  topic_matrix:         Object.fromEntries(topCountries.map(cc => [cc, topicMatrix[cc]])),
};

// ── IP repeat ─────────────────────────────────────────────────────────────────
const ipCount = counter(data.filter(r => r.ip), r => r.ip);
const ipRepeat = {
  threshold:           20,
  ips_over_threshold:  [...ipCount.values()].filter(n => n > 20).length,
  regs_from_those_ips: [...ipCount.values()].filter(n => n > 20).reduce((a, b) => a + b, 0),
  max_regs_one_ip:     ipCount.size ? Math.max(...ipCount.values()) : 0,
};

// ═══════════════════════════════════════════════════════════════════════════════
// 7b. APPROVAL BY COUNTRY (countries with >=300 registrations)
// ═══════════════════════════════════════════════════════════════════════════════
const ccStats = new Map();
for (const r of data) {
  const cc = r.country || '';
  if (!cc || cc === 'N/A') continue;
  if (!ccStats.has(cc)) ccStats.set(cc, [0, 0]);
  const s = ccStats.get(cc);
  s[0]++;
  if (isAppr(r)) s[1]++;
}
const approvalByCountry = [...ccStats.entries()]
  .filter(([, v]) => v[0] >= 300)
  .map(([cc, v]) => ({ country: cc, total: v[0], approved: v[1], appr_pct: Math.round(1000 * v[1] / v[0]) / 10 }))
  .sort((a, b) => a.appr_pct - b.appr_pct);

// ═══════════════════════════════════════════════════════════════════════════════
// 7c. 75-CHAR LIMIT FACTS
// ═══════════════════════════════════════════════════════════════════════════════
const preLens  = preRecs.map(r  => (r.purpose || '').length);
const postLens = postRecs.map(r => (r.purpose || '').length);
const templatePat = /your input must be at least 75 characters/i;

function median(arr) { const s = [...arr].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; }

const limitFacts = {
  cutover_utc:              '2025-07-10 06:00',
  pre_max_len:              Math.max(...preLens),
  post_max_len:             Math.max(...postLens),
  pre_median_len:           median(preLens),
  post_median_len:          median(postLens),
  pre_under75:              preLens.filter(l => l < 75).length,
  post_under75:             postLens.filter(l => l < 75).length,
  post_exact75:             postLens.filter(l => l === 75).length,
  pre_exact75:              preLens.filter(l => l === 75).length,
  post_form_msg:            postRecs.filter(r => templatePat.test(r.purpose || '')).length,
  post_under75_ma_education: postRecs.filter(r =>
    (r.purpose || '').length < 75 &&
    (r.purpose || '').trim().toLowerCase() === 'education' &&
    r.country === 'MA').length,
};

// ═══════════════════════════════════════════════════════════════════════════════
// 7d. SINGLE-DAY SPIKES
// ═══════════════════════════════════════════════════════════════════════════════
const dayMap = new Map();
for (const r of data) {
  const d   = utc(r);
  const key = `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;
  if (!dayMap.has(key)) dayMap.set(key, []);
  dayMap.get(key).push(r);
}
const avgPerDay = data.length / dayMap.size;
const topDays = [...dayMap.entries()]
  .sort((a, b) => b[1].length - a[1].length)
  .slice(0, 8)
  .map(([dkey, recs]) => {
    const ccTop = mostCommon(counter(recs, r => r.country || ''), 1)[0];
    return {
      day:            dkey,
      total:          recs.length,
      top_country:    ccTop[0],
      top_country_n:  ccTop[1],
      appr_pct:       Math.round(1000 * recs.filter(isAppr).length / recs.length) / 10,
      default_pct:    Math.round(1000 * recs.filter(r => r.eventCode === 'default').length / recs.length) / 10,
    };
  });
const spikes = { avg_per_day: Math.round(avgPerDay * 10) / 10, top_days: topDays };

// ═══════════════════════════════════════════════════════════════════════════════
// 8. 75-CHAR WEEKLY TIMELINE
// ═══════════════════════════════════════════════════════════════════════════════
/** ISO 8601 week string (YYYY-WNN) matching Python's %G-W%V */
function isoWeek(date) {
  // Thursday in the current week determines the year (ISO 8601)
  const d   = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = d.getUTCDay() || 7;           // Mon=1 … Sun=7
  d.setUTCDate(d.getUTCDate() + 4 - day);   // nearest Thursday
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d - yearStart) / 86_400_000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

const weeklyMap = new Map();
for (const r of data) {
  const wk   = isoWeek(utc(r));
  const plen = (r.purpose || '').length;
  if (!weeklyMap.has(wk)) weeklyMap.set(wk, { total: 0, short: 0, long: 0, exact75: 0 });
  const w = weeklyMap.get(wk);
  w.total++;
  if (plen < 75) w.short++; else w.long++;
  if (plen === 75) w.exact75++;
}
const timelineWeeks = [...weeklyMap.keys()].sort();
const timeline = {
  weeks:    timelineWeeks,
  short:    timelineWeeks.map(w => weeklyMap.get(w).short),
  long:     timelineWeeks.map(w => weeklyMap.get(w).long),
  exact75:  timelineWeeks.map(w => weeklyMap.get(w).exact75),
  pct_long: timelineWeeks.map(w => {
    const wk = weeklyMap.get(w);
    return wk.total ? Math.round(1000 * wk.long / wk.total) / 10 : 0;
  }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// 9. SUMMARY KPIs
// ═══════════════════════════════════════════════════════════════════════════════
const MONTHS_EN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fmtDate(d) {
  return `${String(d.getUTCDate()).padStart(2,'0')} ${MONTHS_EN[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

const summary = {
  total_records:    data.length,
  total_2025:       data.filter(r => yr(r) === 2025).length,
  total_2026:       data.filter(r => yr(r) === 2026).length,
  files_2025:       data25.length,
  files_2026:       data26.length,
  total_approved:   approvedRecs.length,
  total_countries:  new Set(data.map(r => r.country || '').filter(c => c && c !== 'N/A')).size,
  date_range_start: fmtDate(utc(data[0])),
  date_range_end:   fmtDate(utc(data[data.length - 1])),
  transition_week:  '2025-W28',
  transition_note:  'A 75\u2013500 character limit on the purpose field is enforced from 10 Jul 2025.',
};

// ═══════════════════════════════════════════════════════════════════════════════
// WRITE
// ═══════════════════════════════════════════════════════════════════════════════
const output = {
  summary,
  months,
  monthly_total:           monthlyTotal,
  monthly_approved:        monthlyApproved,
  monthly_zxplore:         monthlyZxplore,
  monthly_zxplore_event:   monthlyZxEvent,
  monthly_zxplore_purpose: monthlyZxPurpose,
  monthly_edu:             monthlyEdu,
  categories_all:          categoriesAll,
  categories_approved:     categoriesApproved,
  limit_impact:            limitImpact,
  spam_countries:          topSpamCountries,
  spam_by_country:         spamByCountry,
  events,
  fraud:                   fraudSection,
  correlations,
  approval_by_country:     approvalByCountry,
  limit_facts:             limitFacts,
  ip_repeat:               ipRepeat,
  spikes,
  timeline,
};

fs.writeFileSync('dashboard_data.json', JSON.stringify(output), 'utf8');

console.log('✓ dashboard_data.json written');
console.log(`  ${data.length.toLocaleString()} total records (${data25.length.toLocaleString()} 2025 + ${data26.length.toLocaleString()} 2026)`);
console.log(`  ${approvedRecs.length.toLocaleString()} approved  |  ${(data.length - approvedRecs.length).toLocaleString()} not approved`);
console.log(`  ${months.length} months  |  ${topCountries.length} countries  |  ${events.length} events`);
