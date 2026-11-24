#!/usr/bin/env python3
"""Bundle config + every brand's emails.json into app/data.js so app/index.html opens straight from disk.

Usage: python3 -I build_app.py [skill_dir]
"""
import datetime, json, os, sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = json.load(open(os.path.join(root, "config.json")))
brands = []
for b in cfg["brands"]:
    p = os.path.join(root, "data", b["slug"], "emails.json")
    emails = json.load(open(p)) if os.path.exists(p) else []
    for e in emails:
        shot = os.path.join(root, "data", b["slug"], "shots", e["id"] + ".jpg")
        e["shot"] = f"../data/{b['slug']}/shots/{e['id']}.jpg" if os.path.exists(shot) else None
    brands.append({**b, "emails": emails})
payload = {
    "generated": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
    "schedule": cfg["schedule"],
    "inbox": cfg.get("gmail_address"),
    "timezone": cfg.get("timezone"),
    "brands": brands,
}
os.makedirs(os.path.join(root, "app"), exist_ok=True)
with open(os.path.join(root, "app", "data.js"), "w") as f:
    f.write("window.SPY = " + json.dumps(payload, ensure_ascii=False) + ";\n")
print("app/data.js:", sum(len(b["emails"]) for b in brands), "emails across", len(brands), "brand(s)")
