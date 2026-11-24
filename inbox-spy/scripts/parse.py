#!/usr/bin/env python3
"""Inbox Spy: parse a brand's raw .eml files into emails.json.

Usage: python3 -I parse.py <brand_dir> [--no-resolve]

<brand_dir> holds raw/<gmail_message_id>.eml (fetched by the skill via Composio Gmail).
Writes:
  <brand_dir>/emails.json        one record per email, newest first
  <brand_dir>/html/<id>.html     sanitised email HTML (no scripts, no open-pixel)
  <brand_dir>/link_cache.json    click-tracker -> destination URL cache

Flow vs campaign is decided in this order (the reason is stored in `detected_via`):
  1. UTM on the email's links: utm_medium=flow|campaign (or utm_campaign with a Klaviyo "(ID)" suffix)
  2. ESP headers: Klaviyo X-Kmail-Flow (present only on flow sends)
  3. Subject-line heuristics (welcome, cart, checkout, order, review ...)
"""
import email, glob, html as htmlmod, json, os, re, sys, urllib.parse, urllib.request
from email import policy
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

def _tz():
    if os.environ.get("INBOX_SPY_TZ"):
        return os.environ["INBOX_SPY_TZ"]
    try:  # config.json sits two levels above data/<slug>/, next to scripts/
        cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        return json.load(open(cfg)).get("timezone") or "UTC"
    except (OSError, ValueError):
        return "UTC"


LOCAL_TZ = ZoneInfo(_tz())
TRACKER = re.compile(r"https?://(ctrk\.klclick\d*\.com|trk\.klclick\d*\.com|click\.[^/\"]+|[^/\"]*\.list-manage\.com|links\.[^/\"]+)/[^\"'\s>]+", re.I)
SKIP_LINK = re.compile(r"unsubscribe|manage\.kmail-lists|subscriptions/|preferences|view.?in.?browser|mailto:", re.I)

FLOW_RULES = [
    ("Welcome Series", r"welcome|first order|your discount|your code|confidence you"),
    ("Abandoned Checkout", r"checkout|complete your order|still deciding"),
    ("Abandoned Cart", r"cart|left (something|behind)|forget"),
    ("Browse Abandonment", r"still looking|caught your eye|saw you|browsing"),
    ("Post Purchase", r"thank(s| you) for (your )?order|on its way|shipped|how (are|is) your|review"),
    ("Winback", r"miss you|been a while|come back"),
]
FLOW_SUBJECT_HINT = re.compile(r"\byour (cart|order|basket|checkout)\b|welcome to|thanks for (your )?order|left in your", re.I)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def resolve(url, cache):
    if url in cache:
        return cache[url]
    dest = None
    try:
        opener = urllib.request.build_opener(NoRedirect)
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
        opener.open(req, timeout=10)
    except urllib.error.HTTPError as e:
        dest = e.headers.get("Location")
    except Exception:
        dest = None
    cache[url] = dest
    return dest


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    t = htmlmod.unescape(t)
    t = re.sub(r"[​-‏͏­ ﻿ ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def preheader(html, plain):
    for m in re.finditer(r"<(div|span|td)[^>]*style=\"[^\"]*display\s*:\s*none[^\"]*\"[^>]*>(.*?)</\1>", html, re.I | re.S):
        t = text_of(m.group(2))
        if len(t) > 3:
            return t[:180]
    if plain:
        plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
        plain = re.sub(r"https?://\S+", "", plain)
        plain = re.sub(r"\s+", " ", plain).strip()
    src = plain or text_of(re.sub(r"<(style|head)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S))
    return src[:140]


def short(t, n=110):
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def sanitise(html):
    html = re.sub(r"<script.*?</script>", "", html, flags=re.I | re.S)
    # drop open-tracking pixels so viewing the archive never registers an open
    html = re.sub(r"<img[^>]+(width=\"?1\"?[^>]+height=\"?1\"?|/o/|/open\b|trk\.klclick)[^>]*>", "", html, flags=re.I)
    return html


def utm_from(url):
    if not url:
        return {}
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return {k: v[0] for k, v in q.items() if k.startswith("utm_")}


def classify(rec, headers, utm):
    med = (utm.get("utm_medium") or "").lower()
    camp = utm.get("utm_campaign") or ""
    if med in ("flow", "campaign"):
        rec["type"] = med
        rec["detected_via"] = "UTM"
        if camp:
            rec["utm_name"] = re.sub(r"\s*\([A-Za-z0-9]{6}\)\s*$", "", camp)
        return
    if camp and re.search(r"\([A-Za-z0-9]{6}\)\s*$", camp):
        rec["type"] = "campaign"
        rec["detected_via"] = "UTM"
        rec["utm_name"] = re.sub(r"\s*\([A-Za-z0-9]{6}\)\s*$", "", camp)
        return
    if headers.get("X-Kmail-Account"):
        flow = headers.get("X-Kmail-Flow")
        rec["type"] = "flow" if flow else "campaign"
        rec["flow_id"] = flow
        rec["detected_via"] = "Klaviyo header"
        return
    rec["type"] = "flow" if FLOW_SUBJECT_HINT.search(rec["subject"]) else "campaign"
    rec["detected_via"] = "Subject heuristic"


def name_flows(recs):
    groups = {}
    for r in recs:
        if r["type"] == "flow":
            groups.setdefault(r.get("utm_name") or r.get("flow_id") or "_" + r["subject"], []).append(r)
    for key, items in groups.items():
        items.sort(key=lambda r: r["sent_utc"])
        name = items[0].get("utm_name")
        if not name:
            subjects = " ".join(i["subject"] for i in items[:2]).lower()
            name = next((n for n, pat in FLOW_RULES if re.search(pat, subjects)), None) or f"Flow {key[:8]}"
        for n, i in enumerate(items, 1):
            i["flow_name"] = name
            i["flow_step"] = n


def fmt_kind(html, words):
    imgs = [m for m in re.findall(r"<img[^>]+>", html, re.I) if not re.search(r"width=\"?([1-9]|[1-4]\d)\"?[ >]", m)]
    if len(imgs) <= 1 and words > 25:
        return "Plain text"
    if len(imgs) <= 3 and words > 80:
        return "Branded text"
    return "Designed"


def main():
    brand_dir = sys.argv[1]
    resolve_links = "--no-resolve" not in sys.argv
    os.makedirs(os.path.join(brand_dir, "html"), exist_ok=True)
    cache_p = os.path.join(brand_dir, "link_cache.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    recs = []
    for path in sorted(glob.glob(os.path.join(brand_dir, "raw", "*.eml"))):
        mid = os.path.basename(path)[:-4]
        m = email.message_from_binary_file(open(path, "rb"), policy=policy.default)
        hb = m.get_body(("html",))
        pb = m.get_body(("plain",))
        html = hb.get_content() if hb else "<pre>" + htmlmod.escape(pb.get_content() if pb else "") + "</pre>"
        plain = text_of(pb.get_content()) if pb else ""
        sent = parsedate_to_datetime(m["Date"])
        local = sent.astimezone(LOCAL_TZ)
        name, addr = email.utils.parseaddr(str(m["From"]))
        body_text = text_of(re.sub(r"<(style|head)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S))
        words = len(body_text.split())
        rec = {
            "id": mid,
            "sent_utc": sent.isoformat(),
            "sent_local": local.strftime("%Y-%m-%d %H:%M"),
            "month": local.strftime("%Y-%m"),
            "weekday": local.strftime("%a"),
            "time": local.strftime("%H:%M"),
            "sender_name": name,
            "sender_email": addr,
            "subject": str(m["Subject"] or "").strip(),
            "preview": short(preheader(html, plain).replace(email.utils.parseaddr(str(m["To"]))[1], "{email}")),
            "words": words,
            "format": fmt_kind(html, words),
            "has_offer": bool(re.search(r"\d+\s?% off|free|buy \d|get \d|credit|£\d+ off|code", body_text, re.I)),
            "gmail_url": f"https://mail.google.com/mail/u/0/#all/{mid}",
        }
        hrefs = [htmlmod.unescape(h) for h in re.findall(r"href=\"(https?://[^\"]+)\"", html)]
        links = [l for l in dict.fromkeys(hrefs) if not SKIP_LINK.search(l)]
        direct = [l for l in links if "utm_" in l]
        dest = direct[0] if direct else None
        if not dest and resolve_links:
            for l in links[:2]:
                if TRACKER.match(l):
                    dest = resolve(htmlmod.unescape(l), cache)
                    if dest:
                        break
        rec["landing"] = re.sub(r"[?&]_kx=[^&]+", "", dest or "") or None
        utm = utm_from(dest)
        rec["utm"] = utm
        classify(rec, m, utm)
        open(os.path.join(brand_dir, "html", mid + ".html"), "w").write(sanitise(html))
        recs.append(rec)
    name_flows(recs)
    recs.sort(key=lambda r: r["sent_utc"], reverse=True)
    json.dump(cache, open(cache_p, "w"), indent=1)
    json.dump(recs, open(os.path.join(brand_dir, "emails.json"), "w"), indent=1, ensure_ascii=False)
    f = sum(r["type"] == "flow" for r in recs)
    print(f"{len(recs)} emails: {f} flow, {len(recs) - f} campaign")


if __name__ == "__main__":
    main()
