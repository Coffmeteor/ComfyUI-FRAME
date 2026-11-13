"""Refresh optional ComfyLink metadata after hot-registering recipe nodes.

Use the already loaded plugin and its existing pairings/transport. No tokens,
backend addresses or account identifiers enter FRAME configuration or responses.
"""
from __future__ import annotations

import asyncio
import sys
import time

_LOCK = asyncio.Lock()
TIMEOUT = 30


def loaded_worker():
    for name, module in tuple(sys.modules.items()):
        if name.endswith(".comfylink.worker") and module is not None:
            return module
    return None


async def _refresh(worker) -> dict:
    needed = ("STATE", "RELAY_URL", "TokenAuth", "RelayClient", "ComfyClient",
              "detect_comfy_url", "_report_object_info")
    if not all(hasattr(worker, name) for name in needed):
        return {"status": "unsupported"}
    pairings = tuple(worker.STATE.pairings)
    if not pairings:
        return {"status": "not_paired"}
    import aiohttp
    refreshed = uploaded = failed = 0
    async with aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=15)) as session:
        comfy = worker.ComfyClient(session, worker.detect_comfy_url())
        for pairing in pairings:
            try:
                relay = worker.RelayClient(session, worker.RELAY_URL, worker.TokenAuth(pairing))
                _, changed = await worker._report_object_info(relay, comfy, pairing)
                pairing.object_info_synced_at = max(pairing.object_info_synced_at or 0, time.time())
                worker.STATE.save()
                # A successful storage PUT alone does not invalidate the phone's
                # cached definitions. Announce both fingerprint and receipt.
                await relay.heartbeat(pairing.backend_id, pairing.object_info_hash,
                                      pairing.object_info_synced_at)
                refreshed += 1
                uploaded += int(changed)
            except Exception:
                # Third-party errors may contain signed URLs or account data.
                # Saving a usable desktop recipe must still succeed offline.
                failed += 1
    return {"status": "synced" if failed == 0 else "failed",
            "refreshed": refreshed, "uploaded": uploaded, "failed": failed}


async def refresh() -> dict:
    worker = loaded_worker()
    if worker is None:
        return {"status": "not_installed"}
    try:
        async def serialized():
            async with _LOCK:
                return await _refresh(worker)
        return await asyncio.wait_for(serialized(), timeout=TIMEOUT)
    except asyncio.TimeoutError:
        return {"status": "failed", "reason": "timeout"}
    except Exception:
        return {"status": "failed", "reason": "unavailable"}
