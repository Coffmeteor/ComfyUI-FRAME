"""Desktop recipe editor routes; no credentials or arbitrary filesystem inputs."""
from __future__ import annotations

from urllib.parse import urlsplit
from aiohttp import web
from . import config
from .nodes import register_recipe, recipe_classes
from .nodes import MobileGenerate


def require_desktop(request):
    origin = request.headers.get("Origin")
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        raise web.HTTPForbidden(text="Use the FRAME editor on your ComfyUI origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.netloc != request.host or parsed.scheme != request.scheme:
            raise web.HTTPForbidden(text="Origin mismatch")
    elif request.remote not in {"127.0.0.1", "::1"}:
        raise web.HTTPForbidden(text="A same-origin desktop request is required")


def register():
    from server import PromptServer
    routes = PromptServer.instance.routes

    @routes.get("/frame-nodes/state")
    async def state(request):
        require_desktop(request)
        recipe = config.current()
        settings = config.directory() / "editor.json"
        return web.json_response({"version": "0.1.0", "recipe": recipe,
            "workflow_path": config.read_json(settings).get("workflow_path", "FRAME/FRAME Krea2 Mobile.json") if settings.exists() else "FRAME/FRAME Krea2 Mobile.json",
            "models": {key: config.choices(category) for key, category in config.MODEL_FIELDS.items()},
            "loras": config.choices("loras")}, headers={"Cache-Control": "no-store"})

    @routes.get("/frame-nodes/trigger")
    async def trigger(request):
        require_desktop(request)
        try:
            return web.json_response(config.trigger_info(request.query.get("file", "")))
        except (OSError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post("/frame-nodes/recipe")
    async def save(request):
        require_desktop(request)
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType()
        if request.content_length is None or request.content_length > config.MAX_BYTES:
            raise web.HTTPRequestEntityTooLarge(max_size=config.MAX_BYTES, actual_size=request.content_length or 0)
        try:
            data = await request.json()
            path = None
            if isinstance(data, dict) and set(data) == {"recipe", "workflow_path"}:
                path = data["workflow_path"]
                if not isinstance(path, str) or not path.endswith(".json") or path.startswith("/") or ".." in path or "\\" in path or ":" in path:
                    raise ValueError("Invalid workflow filename")
                data = data["recipe"]
            ident, recipe = config.save(data)
            if path is not None:
                config.atomic_json(config.directory() / "editor.json", {"workflow_path": path})
            descriptor = register_recipe(ident, recipe)
            return web.json_response({"ok": True, "descriptor": descriptor})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post("/frame-nodes/preview")
    async def preview(request):
        require_desktop(request)
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType()
        if request.content_length is None or request.content_length > config.MAX_BYTES:
            raise web.HTTPRequestEntityTooLarge(max_size=config.MAX_BYTES, actual_size=request.content_length or 0)
        try:
            data = await request.json()
            if not isinstance(data, dict) or set(data) != {"snapshot", "inputs"}:
                raise ValueError("Expected a snapshot and its phone inputs")
            config.load(data["snapshot"])
            cls = type("FramePreview", (MobileGenerate,), {"SNAPSHOT": data["snapshot"]})
            result = cls().generate(**data["inputs"])
            return web.json_response({"graph": result["expand"]})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
