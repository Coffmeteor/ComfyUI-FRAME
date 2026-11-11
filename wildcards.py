"""Bounded text imports and immutable, local wildcard libraries."""
from __future__ import annotations

import hashlib
import json
import re

from . import config

MAX_IMPORT_BYTES = 4 * 1024 * 1024
MAX_STORED_BYTES = 12 * 1024 * 1024
MAX_ENTRIES = 50_000


def identity(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()[:20]


def parse(text: str, mode: str) -> list[str]:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise ValueError("Wildcard files must be UTF-8 text, at most 4 MiB")
    if "\0" in text or any(ord(c) < 32 and c not in "\r\n\t" for c in text):
        raise ValueError("Wildcard files must be plain text without binary control characters")
    if mode not in {"lines", "blocks"}:
        raise ValueError("Choose lines or blank-line-separated blocks")
    text = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in text.split("\n") if not line.lstrip().startswith("#")]
    raw = lines if mode == "lines" else re.split(r"\n[ \t]*\n", "\n".join(lines))
    entries = [entry.strip() for entry in raw if entry.strip()]
    if not entries or len(entries) > MAX_ENTRIES:
        raise ValueError("Wildcard libraries must contain 1 to 50000 entries")
    if any(len(entry.encode("utf-8")) > 32768 for entry in entries):
        raise ValueError("Each wildcard entry must be at most 32 KiB")
    return entries


def index() -> list[dict]:
    path = config.directory() / "wildcards" / "index.json"
    return config.read_json(path).get("libraries", []) if path.exists() else []


def load(ident: str) -> dict:
    if not isinstance(ident, str) or not re.fullmatch(r"[a-f0-9]{20}", ident):
        raise ValueError("Invalid wildcard library ID")
    path = config.directory() / "wildcards" / (ident + ".json")
    with path.open("rb") as f:
        body = f.read(MAX_STORED_BYTES + 1)
    if len(body) > MAX_STORED_BYTES:
        raise ValueError("Wildcard library is too large")
    value = json.loads(body)
    if not isinstance(value, dict) or identity(value) != ident:
        raise ValueError("The wildcard library changed; import it again and save a new recipe")
    return value


def import_text(name: str, text: str, mode: str) -> dict:
    name = config.label(name, "wildcard name")
    entries = parse(text, mode)
    value = {"schema_version": 1, "name": name, "mode": mode, "entries": entries}
    ident = identity(value)
    libraries = index()
    if len(libraries) >= 128 and not any(row["id"] == ident for row in libraries):
        raise ValueError("Import at most 128 local libraries")
    result = {"id": ident, "name": name, "count": len(entries), "mode": mode}
    path = config.directory() / "wildcards" / (ident + ".json")
    config.atomic_json(path, value)
    if not any(row["id"] == ident for row in libraries):
        config.atomic_json(path.parent / "index.json", {"libraries": [*libraries, result]})
    return result
