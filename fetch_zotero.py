"""Pull the Zotero library via the web API and write library.json (+ library.bib).
Runs in GitHub Actions; needs env vars ZOTERO_USER_ID and ZOTERO_API_KEY. Standard library only."""
import json, os, sys, urllib.request

UID, KEY = os.environ["ZOTERO_USER_ID"], os.environ["ZOTERO_API_KEY"]
BASE = f"https://api.zotero.org/users/{UID}"
HDR = {"Zotero-API-Key": KEY, "Zotero-API-Version": "3"}

# Fields that are never published (local paths, private notes, etc.)
DROP = {"relations", "dateAdded", "dateModified", "version", "parentItem", "linkMode", "path", "filename",
        "note", "extra", "accessDate", "libraryCatalog", "callNumber", "rights", "archive", "archiveLocation"}
# Set to True to also drop the abstract from the public file
DROP_ABSTRACT = False

def get(url):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8"), r.headers

def paged(path, extra=""):
    out, start = [], 0
    while True:
        body, h = get(f"{BASE}/{path}?limit=100&start={start}{extra}")
        chunk = json.loads(body)
        out += chunk
        start += 100
        if start >= int(h.get("Total-Results", 0)) or not chunk:
            return out

cols = {c["key"]: c["data"] for c in paged("collections")}

items = []
for it in paged("items/top", "&itemType=-attachment%20||%20note&include=data"):
    d = it["data"]
    if d["itemType"] in ("attachment", "note"):
        continue
    rec = {k: v for k, v in d.items() if k not in DROP and v not in ("", [], None)}
    if DROP_ABSTRACT:
        rec.pop("abstractNote", None)
    rec["key"] = d["key"]
    rec["tags"] = sorted(t["tag"] for t in d.get("tags", []))
    rec["collections"] = sorted(c for c in d.get("collections", []) if c in cols)  # collection keys
    items.append(rec)

items.sort(key=lambda r: (r.get("date", ""), r.get("title", "")), reverse=True)
if not items:
    sys.exit("Got 0 items - refusing to overwrite the library file.")
collections = [{"key": k, "name": d["name"], "parent": d["parentCollection"] or None} for k, d in cols.items()]
collections.sort(key=lambda c: c["name"].lower())
json.dump({"count": len(items), "collections": collections, "items": items}, open("library.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

parts, start = [], 0
while True:
    body, h = get(f"{BASE}/items/top?format=bibtex&limit=100&start={start}&itemType=-attachment%20||%20note")
    parts.append(body)
    start += 100
    if start >= int(h.get("Total-Results", 0)):
        break
open("library.bib", "w", encoding="utf-8").write("\n".join(parts))
print(f"Wrote {len(items)} items")
