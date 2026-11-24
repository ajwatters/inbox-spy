#!/usr/bin/env python3
"""Screenshot each email's HTML with headless Chrome -> <brand_dir>/shots/<id>.png (600px wide, full height).

Usage: python3 -I shoot.py <brand_dir> [--force]
Two passes per email: measure the page height with --dump-dom, then capture at that height.
"""
import glob, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
CHROME = os.environ.get("CHROME") or next((c for c in CANDIDATES if os.path.exists(c)), CANDIDATES[0])
W = 600
MEASURE = "<script>window.addEventListener('load',()=>{document.title='H='+document.documentElement.scrollHeight});</script>"
BASE = "<style>html,body{margin:0!important;padding:0!important;background:#fff}</style>"


def run(args):
    return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                           "--virtual-time-budget=8000", "--no-first-run", "--mute-audio"] + args,
                          capture_output=True, text=True, timeout=90)


def shoot(src, out):
    html = open(src, encoding="utf-8", errors="ignore").read()
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as t:
        t.write(BASE + html + MEASURE)
        tmp = t.name
    try:
        dom = run([f"--window-size={W},1000", "--dump-dom", "file://" + tmp]).stdout
        m = re.search(r"<title>H=(\d+)</title>", dom)
        h = min(int(m.group(1)) if m else 2400, 12000)
        png = out[:-4] + ".png"
        run([f"--window-size={W},{h}", f"--screenshot={png}", "file://" + tmp])
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72", png, "--out", out], capture_output=True)
        os.path.exists(png) and os.unlink(png)
        return h
    finally:
        os.unlink(tmp)


def main():
    d = sys.argv[1]
    force = "--force" in sys.argv
    os.makedirs(os.path.join(d, "shots"), exist_ok=True)
    jobs = []
    for src in glob.glob(os.path.join(d, "html", "*.html")):
        out = os.path.join(d, "shots", os.path.basename(src)[:-5] + ".jpg")
        if force or not os.path.exists(out):
            jobs.append((src, out))
    with ThreadPoolExecutor(4) as ex:
        heights = list(ex.map(lambda j: shoot(*j), jobs))
    print(f"shot {len(jobs)} emails", (min(heights), max(heights)) if heights else "")


if __name__ == "__main__":
    main()
