from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_frame

sync = importlib.import_module('frame_test.comfylink_sync')
find_worker = sync.loaded_worker


class Session:
    def __init__(self, **kwargs):
        self.options = kwargs

    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False


class ComfyLinkSyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        sync._LOCK = asyncio.Lock()
        self.pairing = types.SimpleNamespace(backend_id='private-backend',
            object_info_hash='old', object_info_synced_at=0)
        self.relay = types.SimpleNamespace(heartbeat=AsyncMock(return_value={}))
        self.worker = types.SimpleNamespace(
            STATE=types.SimpleNamespace(pairings=[self.pairing], save=Mock()),
            RELAY_URL='https://configured-relay.invalid', TokenAuth=Mock(),
            RelayClient=Mock(return_value=self.relay), ComfyClient=Mock(),
            detect_comfy_url=Mock(return_value='http://127.0.0.1:8188'))

        async def report(*args):
            self.pairing.object_info_hash = 'new-node-definitions'
            return 3590, True
        self.worker._report_object_info = AsyncMock(side_effect=report)
        self.patches = [patch.object(sync, 'loaded_worker', return_value=self.worker),
            patch.dict(sys.modules, {'aiohttp':types.SimpleNamespace(
                ClientSession=Session, ClientTimeout=lambda **kw:kw)})]
        for p in self.patches: p.start(); self.addCleanup(p.stop)

    async def test_absent_or_unpaired_plugin_does_not_attempt_transport(self):
        with patch.object(sync, 'loaded_worker', return_value=None):
            self.assertEqual(await sync.refresh(), {'status':'not_installed'})
        self.worker.STATE.pairings = []
        self.assertEqual(await sync.refresh(), {'status':'not_paired'})
        self.worker.RelayClient.assert_not_called()

    async def test_existing_transport_upload_precedes_phone_cache_announcement(self):
        result = await sync.refresh()
        self.assertEqual(result, {'status':'synced','refreshed':1,'uploaded':1,'failed':0})
        self.relay.heartbeat.assert_awaited_once_with('private-backend',
            'new-node-definitions', self.pairing.object_info_synced_at)
        self.assertGreater(self.pairing.object_info_synced_at, 0)
        self.worker._report_object_info.assert_awaited_once()
        self.assertNotIn('private-backend', str(result))
        self.assertNotIn('configured-relay', str(result))

    async def test_unchanged_definitions_still_announce_completed_refresh(self):
        self.worker._report_object_info = AsyncMock(return_value=(3590, False))
        result = await sync.refresh()
        self.assertEqual(result['uploaded'], 0)
        self.assertEqual(result['status'], 'synced')
        self.relay.heartbeat.assert_awaited_once()

    async def test_upload_failure_is_not_announced_and_does_not_leak_details(self):
        self.worker._report_object_info = AsyncMock(side_effect=RuntimeError('secret signed URL'))
        result = await sync.refresh()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['failed'], 1)
        self.assertNotIn('secret', str(result))
        self.assertEqual(self.pairing.object_info_synced_at, 0)
        self.relay.heartbeat.assert_not_awaited()

    async def test_announcement_failure_is_reported_even_if_storage_upload_succeeded(self):
        self.relay.heartbeat.side_effect = RuntimeError('offline')
        result = await sync.refresh()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['refreshed'], 0)

    async def test_timeout_is_bounded_and_cancels_incomplete_refresh(self):
        async def never(*args): await asyncio.Event().wait()
        self.worker._report_object_info = AsyncMock(side_effect=never)
        with patch.object(sync, 'TIMEOUT', .01): result = await sync.refresh()
        self.assertEqual(result, {'status':'failed','reason':'timeout'})
        self.relay.heartbeat.assert_not_awaited()

    async def test_other_accounts_are_attempted_after_one_failure(self):
        self.worker.STATE.pairings.append(types.SimpleNamespace(
            backend_id='second',object_info_hash='old',object_info_synced_at=0))
        self.worker._report_object_info = AsyncMock(side_effect=[RuntimeError('offline'), (3590,False)])
        result = await sync.refresh()
        self.assertEqual(result, {'status':'failed','refreshed':1,'uploaded':0,'failed':1})

    async def test_unsupported_plugin(self):
        with patch.object(sync, 'loaded_worker', return_value=types.SimpleNamespace()):
            self.assertEqual(await sync.refresh(), {'status':'unsupported'})

    def test_uses_loaded_plugin_without_importing_or_starting_another_worker(self):
        with patch.dict(sys.modules, {'custom_nodes.example.comfylink.worker':self.worker}):
            self.assertIs(find_worker(), self.worker)


if __name__ == '__main__': unittest.main()
