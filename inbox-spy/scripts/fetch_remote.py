# Paste-ready cell for COMPOSIO_REMOTE_WORKBENCH (runs in Composio's sandbox, not locally).
# Before running, set the four variables at the top. The cell lists matching Gmail messages,
# downloads each as raw MIME, tars the new ones and prints an S3 URL to `curl -L` locally.
ACCOUNT = ""                           # config.json -> gmail_account (the burner)
QUERY   = "from:example.com"           # add after:YYYY/MM/DD before:YYYY/MM/DD for a period pull
SLUG    = "example"
SKIP    = []                           # Gmail ids already on disk (filenames in data/<slug>/raw)

import os, base64, tarfile
from concurrent.futures import ThreadPoolExecutor
ids, tok = [], None
while True:
    a = {"query": QUERY, "max_results": 500, "ids_only": True, "include_spam_trash": True}
    if tok: a["page_token"] = tok
    r, e = run_composio_tool("GMAIL_FETCH_EMAILS", a, account=ACCOUNT)
    if e: raise SystemExit(e)
    d = r.get("data", r)
    ids += [m.get("messageId") or m.get("id") for m in d.get("messages", [])]
    tok = d.get("nextPageToken")
    if not tok: break
new = [i for i in dict.fromkeys(ids) if i not in set(SKIP)]
out = f"/mnt/files/spy/{SLUG}/raw"; os.makedirs(out, exist_ok=True)

def get(i):
    p = f"{out}/{i}.eml"
    if os.path.exists(p): return None
    r, e = run_composio_tool("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": i, "format": "raw"}, account=ACCOUNT)
    if e: return f"{i}: {e}"
    raw = r.get("data", r).get("raw")
    if not raw: return f"{i}: no raw"
    open(p, "wb").write(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))

with ThreadPoolExecutor(8) as ex:
    errs = [x for x in ex.map(get, new) if x]
print(f"matched {len(ids)}, new {len(new)}, errors {errs[:3]}")
if new:
    tp = f"/home/user/{SLUG}_new.tar.gz"
    with tarfile.open(tp, "w:gz") as t:
        for i in new:
            if os.path.exists(f"{out}/{i}.eml"): t.add(f"{out}/{i}.eml", arcname=f"raw/{i}.eml")
    r, e = upload_local_file(tp)
    print("DOWNLOAD:", e or r.get("s3_url"))
