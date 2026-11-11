"""Portable composable nodes and snapshot-bound phone controls."""
from __future__ import annotations

import copy
import logging
import secrets
import json
from pathlib import PurePosixPath

from . import config
from .render import build, compose

BOOLEAN = ("BOOLEAN", {"default": False})
CONTROLS = ("横图", "方图", "手机壁纸", "一百万像素", "高清重绘", "面部细修", "SeedVR2修复", "固定随机种子", "备用模型")


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
            raise ValueError("原版与改写版只能选择一个")
        if options["仅今日新增"] and not (options["原版"] or options["改写版"]):
            raise ValueError("仅今日新增需要先选择词库")
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
        return nodes.SaveImage().save_images(images, filename_prefix, prompt, metadata)


class MobileGenerate:
    CATEGORY = "FRAME/Mobile"
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "generate"
    SNAPSHOT = ""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": ("STRING", {"default": "", "multiline": True}),
                             **{key: BOOLEAN for key in CONTROLS}},
                "optional": {"source": ("FRAME_SOURCE",), "loras": ("FRAME_SELECTION",)},
                "hidden": {"extra_pnginfo": "EXTRA_PNGINFO"}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def generate(self, text, source=None, loras=None, extra_pnginfo=None, **options):
        if not isinstance(text, str) or len(text) > 16000 or set(options) != set(CONTROLS) or any(type(v) is not bool for v in options.values()):
            raise ValueError("Invalid FRAME phone controls")
        recipe = config.load(self.SNAPSHOT)
        source = source or {"原版": False, "改写版": False, "仅今日新增": False}
        selection = loras or {"snapshot": self.SNAPSHOT, "ids": []}
        if not isinstance(selection, dict) or selection.get("snapshot") != self.SNAPSHOT or set(selection) != {"snapshot", "ids"}:
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
            raise ValueError("请输入提示词，或选择一个在线/本地词库")
        prefix = (extra_pnginfo or {}).get("frame_output_prefix", "FRAME/" + self.SNAPSHOT)
        if not isinstance(prefix, str) or not prefix or PurePosixPath(prefix).is_absolute() or ".." in PurePosixPath(prefix).parts or "\\" in prefix or ":" in prefix:
            raise ValueError("Invalid output prefix")
        return build(recipe, selection["ids"], text, options, seed, prefix, receipt)


def recipe_classes(ident: str, recipe: dict) -> tuple[dict, dict, dict]:
    from .selections import choices, MODES
    main = "FrameKrea2_" + ident
    mappings = {main: type(main, (MobileGenerate,), {"SNAPSHOT": ident})}
    names = {main: "提示词与画质"}
    source_type = "FrameSources_" + ident
    source_choices = choices(recipe)

    def source_schema(cls):
        sources, modes = list(source_choices), list(MODES)
        # Include the complete two-part widget spec and explicit enum metadata
        # for remote form readers, not only the minimal ComfyUI tuple.
        return {"required": {
            "提示词来源": (sources, {"default": sources[0], "options": sources,
                              "tooltip": "选择手动提示词、FRAME 在线来源或已导入的本地词库"}),
            "抽词方式": (modes, {"default": modes[0], "options": modes,
                            "tooltip": "沿用当前保留已选条目；每次随机会更新当前条目，图片种子独立"})}}

    def select_source(self, **options):
        if set(options) != {"提示词来源", "抽词方式"} or options["提示词来源"] not in source_choices or options["抽词方式"] not in MODES:
            raise ValueError("Invalid prompt source or selection mode")
        return ({"snapshot": ident, "choice": source_choices[options["提示词来源"]], "mode": options["抽词方式"]},)

    mappings[source_type] = type(source_type, (), {"CATEGORY": "FRAME/Mobile", "RETURN_TYPES": ("FRAME_SOURCE",),
                     "FUNCTION": "select", "INPUT_TYPES": classmethod(source_schema), "select": select_source})
    names[source_type] = "提示词来源"
    groups = []
    for gi, group in enumerate(recipe["groups"]):
        kind = f"FrameLoRAs_{ident}_{gi}"
        controls = {e["name"]: BOOLEAN for e in group["entries"]}

        def schema(cls, controls=controls):
            return {"required": copy.deepcopy(controls), "optional": {"previous": ("FRAME_SELECTION",)}}

        def select(self, previous=None, _gi=gi, _group=group, **switches):
            if set(switches) != {e["name"] for e in _group["entries"]} or any(type(v) is not bool for v in switches.values()):
                raise ValueError("Invalid LoRA switches; resync this workflow")
            picked = [f"{_gi}:{i}" for i, e in enumerate(_group["entries"]) if switches[e["name"]]]
            if _group["exclusive"] and len(picked) > 1:
                raise ValueError(f"{_group['name']}只能开启一个")
            if previous is not None and (not isinstance(previous, dict) or previous.get("snapshot") != ident or set(previous) != {"snapshot", "ids"}):
                raise ValueError("LoRA groups belong to a different recipe")
            return ({"snapshot": ident, "ids": (previous["ids"] if previous else []) + picked},)

        mappings[kind] = type(kind, (), {"CATEGORY": "FRAME/Mobile", "RETURN_TYPES": ("FRAME_SELECTION",),
                    "FUNCTION": "select", "INPUT_TYPES": classmethod(schema), "select": select})
        names[kind] = group["name"]
        groups.append({"type": kind, "title": group["name"], "labels": list(controls)})
    return mappings, names, {"snapshot": ident, "name": recipe["name"], "main": main, "source": source_type, "groups": groups}


NODE_CLASS_MAPPINGS = {"FrameSource": FrameSource, "FramePrompt": FramePrompt, "FrameLora": FrameLora,
                       "FrameResizeShortEdge": FrameResizeShortEdge, "FrameSave": FrameSave}
NODE_DISPLAY_NAME_MAPPINGS = {"FrameSource": "FRAME · 在线词库", "FramePrompt": "FRAME · 提示词组合",
                            "FrameLora": "FRAME · LoRA 与触发词", "FrameResizeShortEdge": "FRAME · 短边缩放"}


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
