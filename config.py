"""Validated, immutable, machine-local recipes for FRAME phone workflows."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

import folder_paths

MAX_BYTES = 512 * 1024
MODEL_FIELDS = {"unet": "diffusion_models", "alternate_unet": "diffusion_models",
                "text_encoder": "text_encoders", "vae": "vae", "upscaler": "upscale_models",
                "face_detector": "ultralytics_bbox", "seedvr_model": "diffusion_models",
                "seedvr_vae": "vae"}


def directory() -> Path:
    return Path(folder_paths.get_user_directory()) / "frame-nodes"


def read_json(path: Path) -> dict:
    with path.open("rb") as f:
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("FRAME configuration exceeds 512 KiB")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("FRAME configuration must be an object")
    return value


def choices(category: str) -> list[str]:
    try:
        return [x.replace("\\", "/") for x in folder_paths.get_filename_list(category)]
    except KeyError:
        return []


def resolve(category: str, filename: str) -> Path:
    if not isinstance(filename, str) or not filename or "\\" in filename:
        raise ValueError("Select a registered relative model filename")
    p = PurePosixPath(filename)
    if p.is_absolute() or ".." in p.parts or ":" in filename or "\0" in filename:
        raise ValueError("Absolute and traversal paths are not accepted")
    if filename not in choices(category):
        raise ValueError(f"Missing {category} model: {filename}")
    actual = folder_paths.get_full_path(category, filename)
    if not actual or not Path(actual).is_file():
        raise ValueError(f"Missing {category} model: {filename}")
    return Path(actual)


def label(value, field="name") -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100 or re.search(r"[\x00-\x1f\x7f]", value):
        raise ValueError(f"Invalid {field}")
    return value.strip()


def number(value, field, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid {field}: expected {low}..{high}")
    return value


def trigger_info(filename: str) -> dict:
    path = resolve("loras", filename)
    for suffix in (".metadata.json", ".civitai.info", ".info.json"):
        sidecar = path.with_suffix(suffix)
        if sidecar.is_file():
            try:
                data = read_json(sidecar)
                words = data.get("trainedWords", data.get("trigger_words", []))
                if isinstance(words, list) and all(isinstance(x, str) for x in words):
                    text = ", ".join(x.strip() for x in words if x.strip())
                    if text and len(text) <= 2048:
                        return {"text": text, "source": suffix}
            except (OSError, ValueError):
                pass
    if path.suffix.lower() == ".safetensors":
        with path.open("rb") as f:
            size = int.from_bytes(f.read(8), "little")
            if 0 < size <= 2 * 1024 * 1024:
                try:
                    md = json.loads(f.read(size)).get("__metadata__", {})
                    text = md.get("modelspec.trigger_phrase", "")
                    if isinstance(text, str) and text.strip() and len(text) <= 2048:
                        return {"text": text.strip(), "source": "modelspec.trigger_phrase"}
                except (ValueError, AttributeError):
                    pass
    return {"text": "", "source": "not_found"}


def validate(data: dict) -> dict:
    if not isinstance(data, dict) or set(data) - {"name", "models", "generation", "groups", "schema_version", "wildcards", "language", "prompt_policy"}:
        raise ValueError("Unknown FRAME recipe fields")
    if data.get("schema_version", 1) != 1:
        raise ValueError("Unsupported FRAME recipe version")
    from .languages import LANGUAGES
    language = data.get("language", "en")
    if language not in LANGUAGES:
        raise ValueError("Choose English, Chinese or bilingual workflow labels")
    policy = data.get("prompt_policy", "explicit")
    if policy not in {"legacy", "explicit"}:
        raise ValueError("Invalid manual prompt policy")
    models = data.get("models", {})
    if not isinstance(models, dict) or set(models) - MODEL_FIELDS.keys():
        raise ValueError("Unknown model settings")
    checked_models = {}
    for field, category in MODEL_FIELDS.items():
        value = models.get(field, "")
        if value:
            resolve(category, value)
            checked_models[field] = value
        elif field in {"unet", "text_encoder", "vae"}:
            raise ValueError(f"Select {field} before exporting a phone workflow")
    g = data.get("generation", {})
    if not isinstance(g, dict) or set(g) - {"steps", "cfg", "sampler", "scheduler", "clip_type"}:
        raise ValueError("Unknown generation settings")
    import comfy.samplers
    steps = number(g.get("steps", 8), "steps", 1, 100)
    if type(steps) is not int:
        raise ValueError("steps must be an integer")
    sampler, scheduler = g.get("sampler", "euler_ancestral"), g.get("scheduler", "beta")
    if sampler not in comfy.samplers.KSampler.SAMPLERS or scheduler not in comfy.samplers.KSampler.SCHEDULERS:
        raise ValueError("Unknown sampler or scheduler")
    if g.get("clip_type", "krea2") != "krea2":
        raise ValueError("The mobile generation recipe currently supports Krea2; use generic nodes for other families")
    groups = data.get("groups", [])
    if not isinstance(groups, list) or len(groups) > 8:
        raise ValueError("Use at most eight LoRA groups")
    checked_groups, total, names = [], 0, set()
    for group in groups:
        if not isinstance(group, dict) or set(group) - {"name", "exclusive", "entries"}:
            raise ValueError("Unknown LoRA group settings")
        name = label(group.get("name"), "group name")
        if name in names or type(group.get("exclusive", False)) is not bool:
            raise ValueError("Group names must be unique and exclusive must be a Boolean")
        names.add(name)
        entries = group.get("entries", [])
        if not isinstance(entries, list) or len(entries) > 64:
            raise ValueError("Use at most 64 LoRAs per group")
        result, labels = [], set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) - {"name", "file", "strength_model", "strength_clip", "trigger", "trigger_mode", "stages", "file_signature", "trigger_source"}:
                raise ValueError("Unknown LoRA settings")
            title = label(entry.get("name"), "LoRA name")
            if title in labels or title in {"previous", "__proto__", "constructor", "prototype"}:
                raise ValueError("LoRA names must be unique in a group")
            labels.add(title)
            filename = entry.get("file")
            path = resolve("loras", filename)
            mode = entry.get("trigger_mode", "auto")
            if mode not in {"auto", "manual", "none"}:
                raise ValueError("Unknown trigger mode")
            detected = trigger_info(filename) if mode == "auto" else {"text": "", "source": mode}
            trigger = entry.get("trigger", "") if mode == "manual" else detected["text"]
            if not isinstance(trigger, str) or len(trigger) > 2048:
                raise ValueError("Trigger text is too long")
            stages = entry.get("stages", ["base", "upscale", "detailer"])
            if not isinstance(stages, list) or not stages or len(set(stages)) != len(stages) or set(stages) - {"base", "upscale", "detailer"}:
                raise ValueError("Choose valid LoRA application stages")
            st = path.stat()
            result.append({"name": title, "file": filename,
                           "strength_model": float(number(entry.get("strength_model", 1.0), "model strength", -10, 10)),
                           "strength_clip": float(number(entry.get("strength_clip", 0.0), "CLIP strength", -10, 10)),
                           "trigger_mode": mode, "trigger": trigger.strip(), "trigger_source": detected["source"],
                           "stages": stages, "file_signature": [st.st_size, st.st_mtime_ns]})
        total += len(result)
        if result:
            checked_groups.append({"name": name, "exclusive": group.get("exclusive", False), "entries": result})
    if total > 128:
        raise ValueError("Use at most 128 LoRAs per recipe")
    from . import wildcards
    libraries = data.get("wildcards", [])
    if not isinstance(libraries, list) or len(libraries) > 32:
        raise ValueError("Select at most 32 local libraries per recipe")
    checked_libraries, library_names, ids = [], set(), set()
    for row in libraries:
        if not isinstance(row, dict) or set(row) != {"id", "name"}:
            raise ValueError("Invalid local wildcard selection")
        library = wildcards.load(row["id"])
        name = label(row["name"], "wildcard name")
        if name in library_names or row["id"] in ids or name != library["name"]:
            raise ValueError("Local library names must be unique and match the imported library")
        library_names.add(name); ids.add(row["id"])
        checked_libraries.append({"id": row["id"], "name": name})
    return {"schema_version": 1, "language": language, "prompt_policy": policy, "name": label(data.get("name", "Krea2 · FRAME for ComfyLink")),
            "models": checked_models, "generation": {"steps": steps, "cfg": float(number(g.get("cfg", 1.0), "CFG", 0, 30)),
            "sampler": sampler, "scheduler": scheduler, "clip_type": "krea2"}, "groups": checked_groups,
            "wildcards": checked_libraries}


def snapshot_id(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:20]


def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".frame-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def save(data: dict) -> tuple[str, dict]:
    checked = validate(data)
    ident = snapshot_id(checked)
    path = directory() / "snapshots" / (ident + ".json")
    if path.exists() and read_json(path) != checked:
        raise ValueError("Snapshot identity collision")
    atomic_json(path, checked)
    atomic_json(directory() / "current.json", {"snapshot": ident})
    return ident, checked


def load(ident: str) -> dict:
    if not isinstance(ident, str) or not re.fullmatch(r"[a-f0-9]{20}", ident):
        raise ValueError("Invalid FRAME snapshot ID")
    value = read_json(directory() / "snapshots" / (ident + ".json"))
    if snapshot_id(value) != ident:
        raise ValueError("FRAME snapshot was changed; save a new recipe")
    return value


def current() -> dict:
    path = directory() / "current.json"
    return load(read_json(path)["snapshot"]) if path.exists() else {
        "schema_version": 1, "language": "en", "name": "Krea2 · FRAME for ComfyLink", "models": {}, "generation": {}, "groups": []}
