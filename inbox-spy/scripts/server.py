#!/usr/bin/env python3
"""Inbox Spy local server: serves the app and runs Claude jobs for its Sync now and Create Figma board buttons.

Usage: python3 -I scripts/server.py [port]   (bound to 127.0.0.1 only)

GET  /api/sync               -> status of the current or last sync
POST /api/sync {"slug": ...} -> starts `claude -p "/inbox-spy sync <slug>"` in the background
POST /api/sync {"slug": ..., "action": "figma"} -> builds a new Figma board for a brand that has none,
     then saves the board link (printed by Claude as `FIGMA_FILE: <url>`) to config.json

Only same-origin requests from this app are accepted (Host + Origin checked, JSON body required),
so other websites open in the browser cannot trigger a sync.
"""
import datetime, json, os, re, shutil, subprocess, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8791))
HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ORIGINS = {f"http://{h}" for h in HOSTS}
LOGS = os.path.join(ROOT, "logs")
CLAUDE = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
TIMEOUT = 45 * 60

def allowed_tools():
    # Connector tool names depend on how Composio and Figma are connected; setup records them in config.json.
    with open(os.path.join(ROOT, "config.json")) as f:
        tools = json.load(f).get("tools") or {}
    composio = tools.get("composio") or "mcp__claude_ai_Composio"
    figma = tools.get("figma") or "mcp__claude_ai_Figma"
    return [
        "Read", "Edit", "Write", "Glob", "Grep",
        "Bash(python3 -I:*)", "Bash(curl -sL:*)", "Bash(tar:*)", "Bash(ls:*)", "Bash(cd:*)",
        "Bash(mkdir:*)", "Bash(rm new.tar.gz)", "Bash(rm data/*/new.tar.gz)", "Bash(rm -f new.tar.gz)",
        f"{composio}__COMPOSIO_SEARCH_TOOLS", f"{composio}__COMPOSIO_REMOTE_WORKBENCH", figma,
    ]

PROMPT = (
    "/inbox-spy sync {target}\n\n"
    "This was started from the Sync now button in the Inbox Spy app, so nobody is watching: do not ask questions. "
    "Skip updating last_sync in config.json; the app server records it after you finish. "
    "Use the Composio Gmail account named in config.json (the burner inbox, read-only). Never send, reply to, delete "
    "or label any email, and never click anything in an email beyond the one link lookup parse.py does. "
    "Finish with a short plain-text report: per brand, how many new emails, each one's date, subject line and "
    "whether it is a flow or campaign, plus anything that failed."
)

FIGMA_PROMPT = (
    "/inbox-spy figma {slug}\n\n"
    "This was started from the Create Figma board button in the Inbox Spy app, so nobody is watching: do not ask "
    "questions. {name} has no Figma board yet. Create a new Figma design file named \"Inbox Spy | {name}\" in the "
    "Figma team named in config.json (figma.team / figma.plan_key) and build the whole board from data/{slug}/emails.json (every month, every email), "
    "following the Board spec in SKILL.md exactly. Upload each screenshot by POSTing it with "
    "`curl -sL -F \"file=@data/{slug}/shots/<id>.jpg;type=image/jpeg\" <submitUrl>`. Take one screenshot of the "
    "finished board to check it. You cannot edit config.json; the app server saves the link. The last line of your "
    "reply must be exactly `FIGMA_FILE: <the new file's https://www.figma.com/design/... URL>`."
)

lock = threading.Lock()
state = {"running": False, "action": None, "slug": None, "started": None, "finished": None, "ok": None, "report": "", "log": None}


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def brands():
    with open(os.path.join(ROOT, "config.json")) as f:
        return {b["slug"]: b for b in json.load(f)["brands"]}


def save_config(update):
    cfg_path = os.path.join(ROOT, "config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)
    for b in cfg["brands"]:
        update(b)
    tmp = cfg_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, cfg_path)


def run_job(action, slug):
    os.makedirs(LOGS, exist_ok=True)
    log = os.path.join(LOGS, f"{action}-{datetime.datetime.now():%Y%m%d-%H%M%S}-{slug or 'all'}.log")
    if action == "figma":
        prompt = FIGMA_PROMPT.format(slug=slug, name=brands()[slug]["name"])
    else:
        prompt = PROMPT.format(target=slug or "")
    cmd = [CLAUDE, "-p", prompt, "--output-format", "text", "--allowedTools", *allowed_tools()]
    ok, report = False, ""
    try:
        with open(log, "w") as out:
            p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=out, stdin=subprocess.DEVNULL,
                               text=True, timeout=TIMEOUT)
            report = p.stdout.strip()
            out.write("\n--- report ---\n" + report + "\n")
        ok = p.returncode == 0
        # Background Claude runs can't edit files under ~/.claude, so the server records results in config.json.
        if ok and action == "figma":
            m = re.findall(r"FIGMA_FILE:\s*(https://www\.figma\.com/design/[A-Za-z0-9]{22,128})", report)
            if m:
                save_config(lambda b: b.update(figma_file=m[-1]) if b["slug"] == slug else None)
                report = re.sub(r"\n?FIGMA_FILE:.*$", "", report).strip()
            else:
                ok, report = False, report + "\n\nNo board link came back, so nothing was saved."
        elif ok:
            stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
            save_config(lambda b: b.update(last_sync=stamp) if not slug or b["slug"] == slug else None)
        if ok:  # make sure the app shows whatever landed, even if the run skipped the rebuild
            subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "build_app.py")], cwd=ROOT,
                           capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        report = f"Stopped after {TIMEOUT // 60} minutes."
    except Exception as e:  # noqa: BLE001 - surface anything to the page
        report = f"Could not start Claude: {e}"
    with lock:
        state.update(running=False, finished=now(), ok=ok, report=report[-4000:], log=os.path.relpath(log, ROOT))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        if self.path.split("?")[0].endswith((".js", ".html", ".json")) or self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _trusted(self):
        if self.headers.get("Host") not in HOSTS:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in ORIGINS

    def do_GET(self):
        if self.path.split("?")[0] == "/api/sync":
            if not self._trusted():
                return self._json(403, {"error": "forbidden"})
            with lock:
                return self._json(200, dict(state))
        if self.path.startswith(("/logs/", "/scripts/")) or "/raw/" in self.path:
            return self._json(404, {"error": "not found"})
        if self.headers.get("Host") not in HOSTS:
            return self._json(403, {"error": "forbidden"})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/sync":
            return self._json(404, {"error": "not found"})
        if not self._trusted() or self.headers.get("Origin") is None:
            return self._json(403, {"error": "forbidden"})
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._json(415, {"error": "json only"})
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 10_000)
            body = json.loads(self.rfile.read(n) or b"{}")
            slug = (body.get("slug") or "").strip()
            action = body.get("action") or "sync"
        except (ValueError, AttributeError):
            return self._json(400, {"error": "bad request"})
        known = brands()
        if action not in ("sync", "figma"):
            return self._json(400, {"error": "unknown action"})
        if slug and (not re.fullmatch(r"[a-z0-9-]+", slug) or slug not in known):
            return self._json(400, {"error": "unknown brand"})
        if action == "figma":
            if not slug:
                return self._json(400, {"error": "pick a brand"})
            if known[slug].get("figma_file"):
                return self._json(400, {"error": "this brand already has a Figma board"})
            if not os.path.exists(os.path.join(ROOT, "data", slug, "emails.json")):
                return self._json(400, {"error": "no emails yet, so there is nothing to put on a board"})
        if not os.path.exists(CLAUDE):
            return self._json(500, {"error": "Claude CLI not found"})
        with lock:
            if state["running"]:
                return self._json(409, {"error": "Claude is already working on something", **state})
            state.update(running=True, action=action, slug=slug or None, started=now(), finished=None, ok=None, report="", log=None)
            snap = dict(state)
        threading.Thread(target=run_job, args=(action, slug), daemon=True).start()
        return self._json(202, snap)


if __name__ == "__main__":
    print(f"Inbox Spy on http://127.0.0.1:{PORT}/app/index.html")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
