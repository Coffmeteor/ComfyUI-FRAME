"""Draw from FRAME's immutable public export without a live catalog-origin hop."""
from __future__ import annotations

from datetime import datetime
import gzip
import io
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ORIGIN = "https://frame.coffmetoer.tech"
LOCK = threading.Lock()
MAX_COMPRESSED = 25 * 1024 * 1024
MAX_JSON = 128 * 1024 * 1024


def download(path, limit):
    url = ORIGIN + path
    with urlopen(Request(url, headers={"User-Agent": "FRAME-Nodes/0.2.5", "Accept": "*/*"}), timeout=20) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected FRAME snapshot destination")
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError("FRAME snapshot exceeds size limit")
    return body


def decode(blob):
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as compressed:
        raw = compressed.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError("FRAME snapshot expands beyond size limit")
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) > 50000:
        raise ValueError("Invalid FRAME snapshot")
    return rows


def timestamp(row):
    stamp = datetime.fromisoformat(row.get("added_at") or row.get("created_at") or "")
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    return stamp.timestamp()


def snapshot_reader(rows, meta):
    if len(rows) != meta.get("total") or any(not isinstance(r, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", r.get("id", "")) for r in rows):
        raise ValueError("FRAME snapshot does not match its publication")
    by_id = {r["id"]: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError("Duplicate FRAME snapshot entry")
    ordered = sorted(rows, key=lambda r: (timestamp(r), r["id"]), reverse=True)

    def fetch(path):
        parsed = urlsplit(path)
        params = parse_qs(parsed.query)
        if parsed.path == "library/meta":
            return meta
        if parsed.path == "library/query":
            page, size = int(params["page"][0]), int(params["limit"][0])
            if page < 1 or size != 24 or params.get("sort") != ["newest"]:
                raise ValueError("Unsupported snapshot query")
            return {**meta, "page": page, "page_size": size, "items": ordered[(page-1)*size:page*size]}
        if parsed.path == "library/items":
            return {"items": [by_id[key] for key in params["ids"][0].split(",") if key in by_id]}
        raise ValueError("Unsupported FRAME snapshot path")
    return fetch


def published_library():
    import folder_paths
    cache = Path(folder_paths.get_user_directory()) / "frame-nodes" / "catalog-cache"
    with LOCK:
        cache.mkdir(parents=True, exist_ok=True)
        pointer = cache / "publication.json"
        fresh = pointer.exists() and time.time() - pointer.stat().st_mtime < 60
        if fresh:
            boot = json.loads(pointer.read_text())
        else:
            html = download("/index.html", 2 * 1024 * 1024).decode()
            match = re.search(r'<script id="frame-bootstrap" type="application/json">(.*?)</script>', html, re.S)
            if not match:
                raise ValueError("FRAME publication metadata is missing")
            boot = json.loads(match.group(1))
        revision = boot.get("exportRevision", "")
        if not re.fullmatch(r"[a-f0-9]{40}", revision):
            raise ValueError("Invalid FRAME publication revision")
        meta = boot["initialMeta"]
        if meta["publication"] != boot["publication"]:
            raise ValueError("Mixed FRAME publication metadata")
        target = cache / (revision + ".json.gz")
        blob = target.read_bytes() if target.exists() else download("/archive/" + revision + "/library.json.gz", MAX_COMPRESSED)
        reader = snapshot_reader(decode(blob), meta)
        if not target.exists():
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(blob)
            temporary.replace(target)
        if not fresh:
            temporary = pointer.with_suffix(".tmp")
            temporary.write_text(json.dumps({"exportRevision": revision, "initialMeta": meta, "publication": boot["publication"]}))
            temporary.replace(pointer)
        # Each draw uses one immutable version even if publication changes mid-draw.
        return reader
