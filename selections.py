"""Keep prompt draws independent of image seeds until the user changes them."""
from __future__ import annotations

import copy
import hashlib
import random
import secrets
import threading

from . import config, wildcards
from .frame_source import resolve_frame_prompt

MANUAL = "手动填写（不抽词）"
ONLINE = {"FRAME 原版 · 全库": ("FRAME 原版", False),
          "FRAME 原版 · 最新更新": ("FRAME 原版", True),
          "FRAME 改写版 · 全库": ("FRAME 改写版", False),
          "FRAME 改写版 · 最新更新": ("FRAME 改写版", True)}
MODES = ("沿用当前", "每次随机")
LOCK = threading.RLock()


def choices(recipe: dict) -> dict[str, str]:
    return {MANUAL: "manual", **{name: name for name in ONLINE},
            **{"本地 · " + row["name"]: row["id"] for row in recipe.get("wildcards", [])}}


def resolve(text: str, source: dict) -> tuple[str, dict | None]:
    if set(source) != {"snapshot", "choice", "mode"} or source["mode"] not in MODES:
        raise ValueError("Invalid prompt selection")
    recipe = config.load(source["snapshot"])
    allowed = set(choices(recipe).values())
    choice = source["choice"]
    if not isinstance(choice, str) or choice not in allowed:
        raise ValueError("Prompt source does not belong to this recipe")
    if choice == "manual":
        return text.strip(), None
    key = hashlib.sha256((source["snapshot"] + ":" + choice).encode()).hexdigest()[:32]
    path = config.directory() / "selections" / (key + ".json")
    with LOCK:
        cached = config.read_json(path) if path.exists() else None
        reused = cached is not None and source["mode"] == MODES[0]
        if not reused:
            previous = cached["receipt"]["entry_id"] if cached else None
            if choice in ONLINE:
                label, latest = ONLINE[choice]
                # Avoid reselecting the previous item when a pool has alternatives.
                # Each attempt is bounded by the existing source client.
                for _ in range(4):
                    selected, receipt = resolve_frame_prompt("", {label: True, "仅今日更新": latest})
                    if receipt["entry_id"] != previous or receipt["eligible_count"] <= 1:
                        break
                if receipt["entry_id"] == previous and receipt["eligible_count"] > 1:
                    raise ValueError("暂未抽到新条目，请再次生成；当前条目仍保留")
            else:
                library = wildcards.load(choice)
                entries = library["entries"]
                seed = secrets.randbits(63)
                old_text = entries[int(previous)] if previous is not None and str(previous).isdigit() and int(previous) < len(entries) else None
                candidates = [i for i, entry in enumerate(entries) if entry != old_text] or list(range(len(entries)))
                selected_index = random.Random(seed).choice(candidates)
                selected = entries[selected_index]
                receipt = {"source": "local", "scope": "library", "library_id": choice,
                           "name": library["name"], "entry_id": str(selected_index), "seed": seed,
                           "eligible_count": len(entries), "selected_prompt": selected}
            cached = {"selected": selected, "receipt": receipt}
            config.atomic_json(path, cached)
        receipt = copy.deepcopy(cached["receipt"])
        expanded = cached["selected"] + ("\n" + text.strip() if text.strip() else "")
        receipt.update(supplement=text.strip(), expanded_prompt=expanded,
                       selection_mode=source["mode"], reused_selection=reused,
                       prompt_sha256=hashlib.sha256(expanded.encode()).hexdigest())
        return expanded, receipt
