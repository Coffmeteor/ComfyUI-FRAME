"""Build native ComfyUI graphs; no private runner, extra queue or model runtime."""
from __future__ import annotations

import math
import json

from .config import resolve, snapshot_id


def compose(text: str, triggers: list[str]) -> str:
    words = list(dict.fromkeys(x.strip() for x in triggers if x.strip()))
    return (", ".join(words) + "\n" if words else "") + text.strip()


def canvas(landscape=False, square=False, wallpaper=False, small=False):
    if sum((landscape, square, wallpaper)) > 1:
        raise ValueError("横图、方图、手机壁纸只能打开一个")
    ratio = 3 / 2 if landscape else 1 if square else 9 / 16 if wallpaper else 2 / 3
    pixels = (1 if small else 2) * 1_048_576
    return round(math.sqrt(pixels * ratio) / 32) * 32, round(math.sqrt(pixels / ratio) / 32) * 32


def build(recipe: dict, selected: list[str], text: str, options: dict, seed: int, prefix: str, receipt=None):
    from comfy_execution.graph_utils import GraphBuilder
    import nodes
    g = GraphBuilder()
    models, settings = recipe["models"], recipe["generation"]
    features = {"高清重绘": ("upscaler", ["UltimateSDUpscale"]),
                "面部细修": ("face_detector", ["UltralyticsDetectorProvider", "FaceDetailer"]),
                "SeedVR2修复": ("seedvr_model", ["SeedVR2Preprocess", "SeedVR2Conditioning", "SeedVR2PostProcessing"])}
    for flag, (field, types) in features.items():
        if options.get(flag):
            if not models.get(field) or any(t not in nodes.NODE_CLASS_MAPPINGS for t in types):
                raise ValueError(f"{flag}需要先在电脑配置模型并安装对应扩展")
    if options.get("SeedVR2修复") and (not models.get("seedvr_vae") or not models.get("upscaler")):
        raise ValueError("SeedVR2修复需要配置 VAE 和图像放大模型")
    model_name = models.get("alternate_unet") if options.get("备用模型") else models["unet"]
    if not model_name:
        raise ValueError("请先在电脑配置备用模型")
    for field, category in (("unet", "diffusion_models"), ("text_encoder", "text_encoders"), ("vae", "vae")):
        resolve(category, model_name if field == "unet" else models[field])
    entries = {}
    for gi, group in enumerate(recipe["groups"]):
        for ei, entry in enumerate(group["entries"]):
            entries[f"{gi}:{ei}"] = entry
    if not isinstance(selected, list) or len(set(selected)) != len(selected) or set(selected) - entries.keys():
        raise ValueError("LoRA selection does not belong to this recipe")
    active = [entries[key] for key in selected]
    for entry in active:
        path = resolve("loras", entry["file"])
        st = path.stat()
        if [st.st_size, st.st_mtime_ns] != entry["file_signature"]:
            raise ValueError(f"LoRA 已更换，请在电脑保存新配方：{entry['name']}")
    for gi, group in enumerate(recipe["groups"]):
        if group["exclusive"] and sum(key.startswith(f"{gi}:") for key in selected) > 1:
            raise ValueError(f"{group['name']}只能开启一个")
    base_model = g.node("UNETLoader", unet_name=model_name, weight_dtype="default").out(0)
    base_clip = g.node("CLIPLoader", clip_name=models["text_encoder"], type=settings["clip_type"], device="default").out(0)
    vae = g.node("VAELoader", vae_name=models["vae"]).out(0)

    def stage(name):
        model, clip, triggers = base_model, base_clip, []
        for entry in active:
            if name not in entry["stages"]:
                continue
            triggers.append(entry["trigger"])
            if entry["strength_clip"] == 0:
                model = g.node("LoraLoaderModelOnly", model=model, lora_name=entry["file"], strength_model=entry["strength_model"]).out(0)
            else:
                lora = g.node("LoraLoader", model=model, clip=clip, lora_name=entry["file"],
                              strength_model=entry["strength_model"], strength_clip=entry["strength_clip"])
                model, clip = lora.out(0), lora.out(1)
        positive = g.node("CLIPTextEncode", text=compose(text, triggers), clip=clip).out(0)
        negative = g.node("ConditioningZeroOut", conditioning=positive).out(0)
        return model, clip, positive, negative

    width, height = canvas(options.get("横图", False), options.get("方图", False),
                           options.get("手机壁纸", False), options.get("一百万像素", False))
    model, clip, positive, negative = stage("base")
    latent = g.node("EmptyLatentImage", width=width, height=height, batch_size=1).out(0)
    sample = g.node("KSampler", model=model, positive=positive, negative=negative, latent_image=latent,
                    seed=seed, steps=settings["steps"], cfg=settings["cfg"], sampler_name=settings["sampler"],
                    scheduler=settings["scheduler"], denoise=1.0).out(0)
    image = g.node("VAEDecode", samples=sample, vae=vae).out(0)
    if options.get("高清重绘"):
        resolve("upscale_models", models["upscaler"])
        model, clip, positive, negative = stage("upscale")
        upscaler = g.node("UpscaleModelLoader", model_name=models["upscaler"]).out(0)
        image = g.node("UltimateSDUpscale", image=image, model=model, positive=positive, negative=negative,
                       vae=vae, upscale_by=1.7, seed=seed, steps=3, cfg=settings["cfg"],
                       sampler_name=settings["sampler"], scheduler=settings["scheduler"], denoise=0.15,
                       upscale_model=upscaler, mode_type="Chess", tile_width=width, tile_height=height,
                       mask_blur=64, tile_padding=96, seam_fix_mode="None", seam_fix_denoise=1.0,
                       seam_fix_width=64, seam_fix_mask_blur=8, seam_fix_padding=16, force_uniform_tiles=True,
                       tiled_decode=False, batch_size=1).out(0)
    if options.get("面部细修"):
        resolve("ultralytics_bbox", models["face_detector"])
        model, clip, positive, negative = stage("detailer")
        detector = g.node("UltralyticsDetectorProvider", model_name="bbox/" + models["face_detector"]).out(0)
        values = {"image": image, "model": model, "clip": clip, "vae": vae, "positive": positive,
                  "negative": negative, "bbox_detector": detector, "guide_size": 1440.0, "max_size": 1440.0,
                  "guide_size_for": True, "seed": seed, "steps": settings["steps"], "cfg": settings["cfg"],
                  "sampler_name": settings["sampler"], "scheduler": settings["scheduler"], "denoise": 0.2,
                  "feather": 100, "noise_mask": True, "force_inpaint": True, "wildcard": "", "cycle": 1}
        for key, spec in nodes.NODE_CLASS_MAPPINGS["FaceDetailer"].INPUT_TYPES()["required"].items():
            if key in values:
                continue
            if len(spec) > 1 and "default" in spec[1]:
                values[key] = spec[1]["default"]
            elif isinstance(spec[0], list) and spec[0]:
                values[key] = spec[0][0]
            else:
                raise ValueError(f"Unsupported FaceDetailer schema: {key}")
        image = g.node("FaceDetailer", **values).out(0)
    if options.get("SeedVR2修复"):
        resolve("diffusion_models", models["seedvr_model"])
        resolve("vae", models["seedvr_vae"])
        resolve("upscale_models", models["upscaler"])
        original = g.node("FrameResizeShortEdge", image=image, short_edge=2048).out(0)
        upscaler = g.node("UpscaleModelLoader", model_name=models["upscaler"]).out(0)
        enlarged = g.node("ImageUpscaleWithModel", image=image, upscale_model=upscaler).out(0)
        resized = g.node("FrameResizeShortEdge", image=enlarged, short_edge=2048).out(0)
        processed = g.node("SeedVR2Preprocess", resized_images=resized).out(0)
        seed_vae = g.node("VAELoader", vae_name=models["seedvr_vae"]).out(0)
        seed_model = g.node("UNETLoader", unet_name=models["seedvr_model"], weight_dtype="default").out(0)
        encoded = g.node("VAEEncode", pixels=processed, vae=seed_vae).out(0)
        cond = g.node("SeedVR2Conditioning", model=seed_model, vae_conditioning=encoded)
        restored = g.node("KSampler", seed=seed, steps=1, cfg=1.0, sampler_name="euler", scheduler="simple",
                          denoise=1.0, model=seed_model, positive=cond.out(0), negative=cond.out(1), latent_image=encoded).out(0)
        decoded = g.node("VAEDecode", samples=restored, vae=seed_vae).out(0)
        corrected = g.node("SeedVR2PostProcessing", images=decoded, original_resized_images=resized, color_correction_method="lab").out(0)
        image = g.node("ImageBlend", image1=corrected, image2=original, blend_factor=0.4, blend_mode="normal").out(0)
    record = {"schema_version": 1, "recipe": snapshot_id(recipe), "seed": seed, "text": text, "selection": selected,
              "prompts": {stage_name: compose(text, [e["trigger"] for e in active if stage_name in e["stages"]])
                          for stage_name in ("base", "upscale", "detailer")},
              "loras": [{"name": e["name"], "trigger": e["trigger"], "stages": e["stages"]} for e in active],
              "source": receipt}
    g.node("FrameSave", images=image, filename_prefix=prefix, receipt=json.dumps(record, ensure_ascii=False))
    return {"result": (), "expand": g.finalize()}
