"""Portable composable nodes and snapshot-bound phone controls."""
from __future__ import annotations

import copy
import logging
import secrets
import json
from pathlib import PurePosixPath

from . import config, plans
from . import catalog_selection as catalog_ids
from .render import build, compose
from .languages import caption, recipe_language, QUALITY

BOOLEAN = ("BOOLEAN", {"default": False})
CONTROLS = ("横图", "方图", "手机壁纸", "一百万像素", "高清重绘", "面部细修", "SeedVR2修复", "固定随机种子", "备用模型")


class FrameSetup:
    """Portable first-use entry point; the desktop button opens local setup."""
    CATEGORY = "FRAME"
    RETURN_TYPES = ()
    FUNCTION = "setup"
    DESCRIPTION = "Configure your own Krea2 models and LoRAs, then generate your local desktop/phone workflow."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    def setup(self):
        return ()


class FrameSource:
    CATEGORY = "FRAME"
    RETURN_TYPES = ("FRAME_SOURCE",)
    FUNCTION = "select"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {key: BOOLEAN for key in ("原版", "改写版", "仅今日新增")}}

    def select(self, **options):
        if set(options) != {"原版", "改写版", "仅今日新增"} or any(type(v) is not bool for v in options.values()):
            raise ValueError("Invalid FRAME source switches")
        if options["原版"] and options["改写版"]:
            raise ValueError("Choose only one of Original and Rewrite")
        if options["仅今日新增"] and not (options["原版"] or options["改写版"]):
            raise ValueError("Choose a library before enabling latest-update-only")
        return (options,)


class FramePrompt:
    CATEGORY = "FRAME"
    RETURN_TYPES = ("STRING",)
    FUNCTION = "combine"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": ("STRING", {"multiline": True, "default": ""})},
                "optional": {"triggers": ("STRING", {"forceInput": True}), "source": ("STRING", {"forceInput": True})}}

    def combine(self, text, triggers="", source=""):
        return (compose("\n".join(x.strip() for x in (source, text) if x.strip()), [triggers]),)


class FrameLora:
    CATEGORY = "FRAME"
    RETURN_TYPES = ("MODEL", "CLIP", "STRING")
    FUNCTION = "apply"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("MODEL",), "lora_name": (config.choices("loras"),),
                "enabled": ("BOOLEAN", {"default": True}),
                "strength_model": ("FLOAT", {"default": 1.0, "min": -10, "max": 10, "step": 0.05}),
                "strength_clip": ("FLOAT", {"default": 0.0, "min": -10, "max": 10, "step": 0.05}),
                "trigger_mode": (["auto", "manual", "none"],), "trigger": ("STRING", {"default": ""})},
                "optional": {"clip": ("CLIP",)}}

    @classmethod
    def VALIDATE_INPUTS(cls, lora_name, enabled):
        if type(enabled) is not bool:
            return "enabled must be a Boolean"
        if enabled:
            try:
                config.resolve("loras", lora_name)
            except ValueError as exc:
                return str(exc)
        return True

    def apply(self, model, lora_name, enabled, strength_model, strength_clip, trigger_mode, trigger, clip=None):
        if not enabled:
            return model, clip, ""
        config.resolve("loras", lora_name)
        config.number(strength_model, "model strength", -10, 10)
        config.number(strength_clip, "CLIP strength", -10, 10)
        if trigger_mode not in {"auto", "manual", "none"}:
            raise ValueError("Unknown trigger mode")
        text = config.trigger_info(lora_name)["text"] if trigger_mode == "auto" else trigger if trigger_mode == "manual" else ""
        if not isinstance(text, str) or len(text) > 2048:
            raise ValueError("Trigger text is too long")
        if strength_clip and clip is None:
            raise ValueError("Connect CLIP or use CLIP strength zero")
        from comfy_execution.graph_utils import GraphBuilder
        g = GraphBuilder()
        if strength_clip:
            node = g.node("LoraLoader", model=model, clip=clip, lora_name=lora_name,
                          strength_model=strength_model, strength_clip=strength_clip)
            return {"result": (node.out(0), node.out(1), text), "expand": g.finalize()}
        node = g.node("LoraLoaderModelOnly", model=model, lora_name=lora_name, strength_model=strength_model)
        return {"result": (node.out(0), clip, text), "expand": g.finalize()}


class FrameResizeShortEdge:
    CATEGORY = "FRAME/internal"
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "resize"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "short_edge": ("INT", {"default": 2048, "min": 32, "max": 8192})}}

    def resize(self, image, short_edge):
        import comfy.utils
        h, w = image.shape[1:3]
        scale = short_edge / min(h, w)
        result = comfy.utils.common_upscale(image.movedim(-1, 1), round(w * scale / 32) * 32,
                                            round(h * scale / 32) * 32, "bicubic", "disabled")
        return (result.movedim(1, -1),)


class FrameSave:
    CATEGORY = "FRAME/internal"
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "save"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "filename_prefix": ("STRING", {"default": "FRAME"}),
                             "receipt": ("STRING", {"default": "{}"})},
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}}

    def save(self, images, filename_prefix, receipt, prompt=None, extra_pnginfo=None):
        import nodes
        metadata = dict(extra_pnginfo or {})
        metadata["frame"] = json.loads(receipt)
        item_code = metadata["frame"].get("plan", {}).get("item_id")
        if item_code and isinstance(prompt, dict):
            prompt = copy.deepcopy(prompt)
            matches = [node for node in prompt.values() if isinstance(node, dict) and
                       node.get("class_type") == "FrameKrea2_" + metadata["frame"].get("recipe", "")]
            if len(matches) == 1:
                matches[0]["inputs"]["replay_code"] = item_code
        return nodes.SaveImage().save_images(images, filename_prefix, prompt, metadata)


class MobileGenerate:
    CATEGORY = "FRAME/Mobile"
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "generate"
    SNAPSHOT = ""
    LANGUAGE = "zh"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": ("STRING", {"default": "", "multiline": True}),
                             **{caption(en, zh, cls.LANGUAGE): BOOLEAN for en, zh in QUALITY}},
                "optional": {"source": ("FRAME_SOURCE",), "loras": ("FRAME_SELECTION",),
                             "batch_count": ("INT", {"default": 1, "min": 1, "max": 10}),
                             "catalog_selection": (list(catalog_ids.POLICIES), {"default": "Workflow source"}),
                             "catalog": (["library", "rewrite"], {"default": "library"}),
                             "prompt_format": (list(dict.fromkeys(v for values in catalog_ids.FORMATS.values() for v in values)), {"default": "prompt_krea2"}),
                             "prompt_ids": ("STRING", {"default": "", "multiline": True, "display_name": "Prompt numbers", "tooltip": "FRAME numbers starting at 1, for example 1, 2, 3. Used only in Fixed prompt IDs mode."}),
                             "replay_code": ("STRING", {"default": "", "tooltip": "Replay a saved FRAME batch or item; other controls are ignored."}),
                             "prompt_batch": ("STRING", {"default": "", "multiline": True, "tooltip": "Optional JSON prompt list prepared by FRAME."})},
                "hidden": {"extra_pnginfo": "EXTRA_PNGINFO"}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def generate(self, text, source=None, loras=None, extra_pnginfo=None, batch_count=1, replay_code="", prompt_batch="", catalog_selection="Workflow source", catalog="library", prompt_format="prompt_krea2", prompt_ids="", **options):
        if replay_code.strip():
            return plans.replay(replay_code.strip())
        if type(batch_count) is not int or not 1 <= batch_count <= 10:
            raise ValueError("Choose 1–10 images per batch")
        if catalog_selection not in catalog_ids.POLICIES:
            raise ValueError("Choose a valid prompt selection mode")
        prompts = (catalog_ids.select(catalog, prompt_format, catalog_selection, batch_count, prompt_ids)
                   if catalog_selection != "Workflow source" else json.loads(prompt_batch) if prompt_batch.strip() else None)
        if prompts is not None:
            if not isinstance(prompts, list) or len(prompts) != batch_count:
                raise ValueError("Prepared prompts must contain one full prompt per batch item")
            for entry in prompts:
                value = entry.get("text") if isinstance(entry, dict) else entry
                if not isinstance(value, str) or not value.strip() or len(value) > 16000:
                    raise ValueError("Prepared prompts must contain full text up to 16,000 characters")
                if isinstance(entry, dict) and (set(entry) - {"text", "id", "collection", "mode", "title", "thumbnail", "revision"} or
                                               any(not isinstance(v, str) or len(v) > 16000 for v in entry.values())):
                    raise ValueError("Invalid prepared prompt metadata")
        graphs = []
        for index in range(batch_count):
            selected_source = {"原版": False, "改写版": False, "仅今日新增": False} if prompts is not None else source
            entry = prompts[index] if prompts is not None else text
            result = self._generate_one(entry["text"] if isinstance(entry, dict) else entry,
                                        source=selected_source, loras=loras, extra_pnginfo=extra_pnginfo, **options)
            if isinstance(entry, dict):
                for node in result["expand"].values():
                    if node["class_type"] == "FrameSave":
                        receipt = json.loads(node["inputs"]["receipt"])
                        receipt["source"] = {"source": "prepared", "entry_id": entry.get("id", ""),
                                             **{k: v for k, v in entry.items() if k != "text"}}
                        node["inputs"]["receipt"] = json.dumps(receipt, ensure_ascii=False)
            graphs.append(result["expand"])
        return plans.freeze(self.SNAPSHOT, graphs)

    def _generate_one(self, text, source=None, loras=None, extra_pnginfo=None, **options):
        labels = {caption(en, zh, self.LANGUAGE): zh for en, zh in QUALITY}
        if set(options) != set(labels):
            raise ValueError("Invalid FRAME controls; sync the workflow for this recipe language")
        options = {labels[key]: value for key, value in options.items()}
        if not isinstance(text, str) or len(text) > 16000 or set(options) != set(CONTROLS) or any(type(v) is not bool for v in options.values()):
            raise ValueError("Invalid FRAME phone controls")
        recipe = config.load(self.SNAPSHOT)
        source = source or {"原版": False, "改写版": False, "仅今日新增": False}
        selection = loras or {"snapshot": self.SNAPSHOT, "ids": [], **({"strengths": {}} if recipe.get("mobile_strengths") else {})}
        if not isinstance(selection, dict) or selection.get("snapshot") != self.SNAPSHOT or set(selection) != ({"snapshot", "ids", "strengths"} if recipe.get("mobile_strengths") else {"snapshot", "ids"}):
            raise ValueError("LoRA groups belong to a different recipe; regenerate the phone workflow")
        seed = 0 if options["固定随机种子"] else secrets.randbits(63)
        receipt = None
        if isinstance(source, dict) and "snapshot" in source:
            if source["snapshot"] != self.SNAPSHOT:
                raise ValueError("Prompt source belongs to a different recipe")
            from .selections import resolve
            text, receipt = resolve(text, source)
        else:
            FrameSource().select(**source)
        if "snapshot" not in source and (source["原版"] or source["改写版"]):
            from .frame_source import resolve_frame_prompt
            text, receipt = resolve_frame_prompt(text, {"FRAME 原版": source["原版"], "FRAME 改写版": source["改写版"],
                               "仅今日更新": source["仅今日新增"], "固定随机种子": options["固定随机种子"]})
        if not text.strip():
            raise ValueError("Enter a prompt or choose an online/local library")
        prefix = (extra_pnginfo or {}).get("frame_output_prefix", "FRAME/" + self.SNAPSHOT)
        if not isinstance(prefix, str) or not prefix or PurePosixPath(prefix).is_absolute() or ".." in PurePosixPath(prefix).parts or "\\" in prefix or ":" in prefix:
            raise ValueError("Invalid output prefix")
        return build(recipe, selection["ids"], text, options, seed, prefix, receipt, strengths=selection.get("strengths"))


def recipe_classes(ident: str, recipe: dict) -> tuple[dict, dict, dict]:
    from .selections import choices, modes
    language = recipe_language(recipe)
    source_label = caption("Prompt source", "提示词来源", language)
    mode_label = caption("Selection mode", "抽词方式", language)
    append_label = caption("Append manual text", "追加手动提示词", language)
    explicit = recipe.get("prompt_policy", "legacy") == "explicit"
    main_title = caption("Prompt & Quality", "提示词与画质", language)
    main = "FrameKrea2_" + ident
    mappings = {main: type(main, (MobileGenerate,), {"SNAPSHOT": ident, "LANGUAGE": language})}
    names = {main: main_title}
    source_type = "FrameSources_" + ident
    source_choices = choices(recipe)
    mode_choices = modes(recipe)

    def source_schema(cls):
        sources, mode_names = list(source_choices), list(mode_choices)
        # Include the complete two-part widget spec and explicit enum metadata
        # for remote form readers, not only the minimal ComfyUI tuple.
        required = {
            source_label: (sources, {"default": sources[0], "options": sources,
                              "tooltip": caption("Choose a manual prompt, FRAME online catalog or imported local library", "选择手动提示词、FRAME 在线来源或已导入的本地词库", language)}),
            mode_label: (mode_names, {"default": mode_names[0], "options": mode_names,
                            "tooltip": caption("Reuse keeps the current prompt; random updates it. Image seeds are independent.", "沿用当前保留已选条目；每次随机会更新当前条目，图片种子独立", language)})}
        if explicit:
            required[append_label] = ("BOOLEAN", {"default": False, "tooltip": caption(
                "Online/local libraries ignore manual text unless this switch is on. Manual-only mode always uses your text.",
                "在线或本地词库默认忽略手动框，开启后才追加；手动填写模式始终使用手动提示词。", language)})
        return {"required": required}

    def select_source(self, **options):
        expected = {source_label, mode_label} | ({append_label} if explicit else set())
        if set(options) != expected or options[source_label] not in source_choices or options[mode_label] not in mode_choices:
            raise ValueError("Invalid prompt source or selection mode")
        selected = {"snapshot": ident, "choice": source_choices[options[source_label]], "mode": mode_choices[options[mode_label]]}
        if explicit:
            if type(options[append_label]) is not bool:
                raise ValueError("Append manual text must be a Boolean")
            selected["append_manual"] = options[append_label]
        return (selected,)

    mappings[source_type] = type(source_type, (), {"CATEGORY": "FRAME/Mobile", "RETURN_TYPES": ("FRAME_SOURCE",),
                     "FUNCTION": "select", "INPUT_TYPES": classmethod(source_schema), "select": select_source})
    names[source_type] = source_label
    groups = []
    for gi, group in enumerate(recipe["groups"]):
        kind = f"FrameLoRAs_{ident}_{gi}"
        controls = {}
        strength_fields = {}
        for ei, entry in enumerate(group["entries"]):
            controls[entry["name"]] = BOOLEAN
            if recipe.get("mobile_strengths"):
                field = entry["name"] + caption(" · Strength", " · 强度", language)
                if field in {e["name"] for e in group["entries"]}:
                    raise ValueError("LoRA name conflicts with a strength control")
                strength_fields[field] = (f"{gi}:{ei}", entry["strength_model"])
                controls[field] = ("FLOAT", {"default": entry["strength_model"], "min": -10, "max": 10, "step": 0.05})

        def schema(cls, controls=controls):
            return {"required": copy.deepcopy(controls), "optional": {"previous": ("FRAME_SELECTION",)}}

        def select(self, previous=None, _gi=gi, _group=group, _strength_fields=strength_fields, **values):
            labels = {e["name"] for e in _group["entries"]}
            if set(values) != labels | set(_strength_fields) or any(type(values[k]) is not bool for k in labels):
                raise ValueError("Invalid LoRA controls; resync this workflow")
            picked = [f"{_gi}:{i}" for i, e in enumerate(_group["entries"]) if values[e["name"]]]
            if _group["exclusive"] and len(picked) > 1:
                raise ValueError(f"Allow only one active LoRA in {_group['name']}")
            expected = {"snapshot", "ids", "strengths"} if recipe.get("mobile_strengths") else {"snapshot", "ids"}
            if previous is not None and (not isinstance(previous, dict) or previous.get("snapshot") != ident or set(previous) != expected):
                raise ValueError("LoRA groups belong to a different recipe")
            result = {"snapshot": ident, "ids": (previous["ids"] if previous else []) + picked}
            if recipe.get("mobile_strengths"):
                strengths = dict(previous["strengths"] if previous else {})
                for field, (key, _) in _strength_fields.items():
                    value = float(config.number(values[field], field, -10, 10))
                    if key in picked:
                        strengths[key] = value
                result["strengths"] = strengths
            return (result,)

        mappings[kind] = type(kind, (), {"CATEGORY": "FRAME/Mobile", "RETURN_TYPES": ("FRAME_SELECTION",),
                    "FUNCTION": "select", "INPUT_TYPES": classmethod(schema), "select": select})
        names[kind] = group["name"]
        groups.append({"type": kind, "title": group["name"], "labels": list(controls)})
    return mappings, names, {"snapshot": ident, "name": recipe["name"], "main": main, "main_title": main_title,
                            "source": source_type, "source_title": source_label,
                            "source_fields": [source_label, mode_label], "language": language, "groups": groups,
                            "mobile_strengths": bool(recipe.get("mobile_strengths"))}


NODE_CLASS_MAPPINGS = {"FrameSource": FrameSource, "FramePrompt": FramePrompt, "FrameLora": FrameLora,
                       "FrameResizeShortEdge": FrameResizeShortEdge, "FrameSave": FrameSave, "FrameSetup": FrameSetup}
NODE_DISPLAY_NAME_MAPPINGS = {"FrameSource": "FRAME · Legacy source switches", "FramePrompt": "FRAME · Prompt Composer",
                            "FrameLora": "FRAME · LoRA & Triggers", "FrameResizeShortEdge": "FRAME · Resize Short Edge",
                            "FrameSetup": "FRAME · Start Here"}


def register_recipe(ident, recipe):
    mapping, names, descriptor = recipe_classes(ident, recipe)
    for cls in mapping.values():
        cls.RELATIVE_PYTHON_MODULE = FrameSource.RELATIVE_PYTHON_MODULE if hasattr(FrameSource, "RELATIVE_PYTHON_MODULE") else "custom_nodes.ComfyUI-FRAME"
    NODE_CLASS_MAPPINGS.update(mapping)
    NODE_DISPLAY_NAME_MAPPINGS.update(names)
    import nodes
    nodes.NODE_CLASS_MAPPINGS.update(mapping)
    nodes.NODE_DISPLAY_NAME_MAPPINGS.update(names)
    return descriptor


def restore_recipes():
    directory = config.directory() / "snapshots"
    if directory.is_dir():
        for path in directory.glob("*.json"):
            try:
                ident = path.stem
                mapping, names, _ = recipe_classes(ident, config.load(ident))
                NODE_CLASS_MAPPINGS.update(mapping)
                NODE_DISPLAY_NAME_MAPPINGS.update(names)
            except (OSError, ValueError, KeyError) as e:
                logging.getLogger(__name__).warning("Skipped invalid FRAME recipe %s: %s", path.name, type(e).__name__)
