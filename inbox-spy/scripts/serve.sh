#!/bin/bash
# Open the Inbox Spy app: starts scripts/server.py on 127.0.0.1:8791 (app + Sync now / Create Figma board)
# if needed, then opens the app in its own window with no address bar (Chrome-family app window).
cd "$(dirname "$0")/.." || exit 1
PORT=${PORT:-8791}
URL="http://127.0.0.1:$PORT/app/index.html"
running=$(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null)
if [ -n "$running" ] && ! curl -s -m 2 "http://127.0.0.1:$PORT/api/sync" | grep -q '"running"'; then
  # Something else (an old plain file server) is on the port: replace it.
  kill $running 2>/dev/null; sleep 1; running=""
fi
if [ -z "$running" ]; then
  nohup python3 -I scripts/server.py "$PORT" >/dev/null 2>&1 &
  for _ in $(seq 1 25); do curl -s -m 1 -o /dev/null "$URL" && break; sleep 0.2; done
fi
for b in "Google Chrome" "Chromium" "Brave Browser" "Microsoft Edge"; do
  if [ -d "/Applications/$b.app" ] || [ -d "$HOME/Applications/$b.app" ]; then
    open -na "$b" --args --app="$URL" --window-size=1440,900
    exit 0
  fi
done
open "$URL"
