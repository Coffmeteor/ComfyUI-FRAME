"""Read complete prompts from FRAME's existing public catalog APIs on demand."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import random
import re
import secrets
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ORIGIN = "https://frame.coffmetoer.tech"
API = ORIGIN + "/frame-api/v1/"
FRAME_OPTIONS = {
    "FRAME 原版": "Draw a complete Krea2 prompt from the FRAME Original catalog; manual text is optional.",
    "FRAME 改写版": "Draw from the FRAME Rewrite catalog; choose only one catalog.",
    "仅今日更新": "Draw only from the latest published update batch, or disable for the full library.",
}
SOURCES = {"FRAME 原版": ("original", "library", "prompt_krea2"),
           "FRAME 改写版": ("rewrite", "rewrite", "prompt")}
PAGE_SIZE = 24
MAX_RESPONSE = 2 * 1024 * 1024


def selected_source(options: dict[str, Any]) -> str | None:
    active = [key for key in SOURCES if options.get(key, False)]
    if len(active) > 1:
        raise ValueError("Choose only one of FRAME Original and Rewrite")
    if options.get("仅今日更新", False) and not active:
        raise ValueError("Choose FRAME Original or Rewrite before limiting to the latest update")
    return active[0] if active else None


def get_json(path: str) -> dict[str, Any]:
    # Only fixed public catalog paths are constructed here. No user prompt,
    # identity selection, image, account credential or private API is sent.
    endpoints = (API, "https://api.coffmetoer.tech/frame-api/v1/")
    for index, endpoint in enumerate(endpoints):
        request = Request(endpoint + path, headers={"Accept": "application/json", "Origin": ORIGIN,
                                                   "User-Agent": "FRAME-Nodes/0.2.3"})
        try:
            with urlopen(request, timeout=12) as response:
                if not response.geturl().startswith(endpoint):
                    raise ValueError("FRAME API returned an unexpected destination")
                body = response.read(MAX_RESPONSE + 1)
            if len(body) > MAX_RESPONSE:
                raise ValueError("FRAME API response exceeds the size limit")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("FRAME API response has an invalid format")
            return result
        except HTTPError as exc:
            exc.close()
            # Retry only public reads, once, through FRAME's existing API host.
            # Never retry rate limits/auth failures or change the selected pool.
            if exc.code in (502, 503, 504) and index == 0:
                continue
            raise ValueError(f"FRAME prompt API returned HTTP {exc.code}; try again later") from exc
        except (URLError, TimeoutError, OSError) as exc:
            if index == 0:
                continue
            raise ValueError("FRAME prompt API could not be reached through either endpoint; try again later") from exc
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("FRAME prompt API returned invalid JSON; try again later") from exc


def publication(meta: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    total, published = meta.get("total"), meta.get("publication")
    if (type(total) is not int or not 0 <= total <= 50_000 or not isinstance(published, dict)
            or published.get("timezone") != "America/Los_Angeles"
            or type(published.get("today_added")) is not int
            or not 0 <= published["today_added"] <= total):
        raise ValueError("Invalid FRAME catalog publication metadata")
    try:
        datetime.strptime(published["date"], "%Y-%m-%d")
        updated = datetime.fromisoformat(published["updated_at"])
        if updated.tzinfo is None:
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid FRAME catalog publication date") from exc
    return total, published


def resolve_frame_prompt(prompt: str, options: dict[str, Any], *,
                         now: datetime | None = None,
                         fetch: Callable[[str], dict[str, Any]] | None = None,
                         ) -> tuple[str, dict[str, Any] | None]:
    label = selected_source(options)
    if label is None:
        return prompt.strip(), None
    fetch = fetch or get_json
    source, catalog, field = SOURCES[label]
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("FRAME selection time must include a timezone")
    today = now.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
    today_only = options.get("仅今日更新", False)
    seed = 0 if options.get("固定随机种子", False) else secrets.randbits(63)
    for _ in range(2):
        total, published = publication(fetch(catalog + "/meta"))
        # Follow the website's published update batch until it publishes a new
        # one. A client crossing midnight must not empty an unchanged pool.
        scope_date = published["date"] if today_only else None
        eligible = published["today_added"] if today_only else total
        if not eligible:
            raise ValueError(f"{source}: no entries in the latest publication ({scope_date}); choose Full library to use the complete catalog"
                             if today_only else f"The {source} catalog is empty")
        index = random.Random(seed).randrange(eligible)
        page, slot = divmod(index, PAGE_SIZE)
        query = fetch(catalog + "/query?" + urlencode({"sort": "newest", "page": page + 1, "limit": PAGE_SIZE}))
        # The website's today_added is the newest prefix ordered by added/id.
        # Match metadata to the page and verify the publication date below;
        # never expand the selected batch into an implicit full-library pool.
        if publication(query) != (total, published):
            continue
        rows = query.get("items")
        if (query.get("page") != page + 1 or query.get("page_size") != PAGE_SIZE
                or not isinstance(rows, list) or slot >= len(rows)):
            raise ValueError("Incomplete FRAME catalog page")
        row = rows[slot]
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", row["id"])):
            raise ValueError("Invalid FRAME entry ID")
        if today_only:
            try:
                added = datetime.fromisoformat(row.get("added_at") or row.get("created_at") or "")
                # Match FRAME's catalog timestamp helper for legacy naive dates.
                added = added.replace(tzinfo=ZoneInfo(published["timezone"])) if added.tzinfo is None else added
                if added.astimezone(ZoneInfo(published["timezone"])).date().isoformat() != scope_date or added > now:
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise ValueError("FRAME publication count and entry dates do not match; try again later") from exc
        if catalog == "library":
            items = fetch(catalog + "/items?" + urlencode({"ids": row["id"]})).get("items")
            if (not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict)
                    or items[0].get("id") != row["id"]):
                raise ValueError("FRAME full-prompt entry does not match the selection")
            record = items[0]
        else:
            record = row  # Rewrite query cards already include the full prompt.
        text = record.get(field)
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 32768:
            raise ValueError("The FRAME entry lacks a complete prompt for the selected catalog")
        # Detect publication during the query/item pair. Retry one fresh draw,
        # bounded above; do not mix a page from one release with another total.
        if publication(fetch(catalog + "/meta")) != (total, published):
            continue
        supplement = prompt.strip()
        expanded = text.strip() + ("\n" + supplement if supplement else "")
        receipt = {"source": source, "label": label, "scope": "today" if today_only else "all",
                   "website": ORIGIN, "publication": published, "selection_date": today,
                   "scope_date": scope_date,
                   "catalog_total": total, "eligible_count": eligible, "index": index,
                   "entry_id": row["id"], "entry_revision": record.get("revision", ""), "added_at": row.get("added_at"), "seed": seed,
                   "prompt_field": field, "selected_prompt": text.strip(), "supplement": supplement,
                   "expanded_prompt": expanded, "prompt_sha256": hashlib.sha256(expanded.encode()).hexdigest()}
        return expanded, receipt
    raise ValueError("The FRAME catalog is updating; try again later. Publication versions have not been mixed.")
