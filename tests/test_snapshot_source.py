import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('snapshot_source_test', Path(__file__).resolve().parents[1] / 'snapshot_source.py')
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)

class SnapshotTests(unittest.TestCase):
    def fixture(self):
        rows = [{"id": str(i), "added_at": "2026-11-12T12:00:00+00:00", "prompt_krea2": "Complete prompt " + str(i)} for i in range(30)]
        meta = {"total": 30, "publication": {"date": "2026-11-12", "timezone": "America/Los_Angeles", "today_added": 30, "updated_at": "2026-11-12T13:00:00+00:00"}}
        return rows, meta

    def test_snapshot_pages_and_full_items_use_identical_version(self):
        rows, meta = self.fixture()
        read = snapshot.snapshot_reader(rows, meta)
        page = read('library/query?sort=newest&page=2&limit=24')
        self.assertEqual(page['items'], sorted(rows,key=lambda r:r['id'],reverse=True)[24:])
        self.assertEqual(page['publication'], read('library/meta')['publication'])
        self.assertEqual(read('library/items?ids=4')['items'][0]['prompt_krea2'], 'Complete prompt 4')
        with self.assertRaises(ValueError): snapshot.snapshot_reader(rows, {**meta,'total':31})
        with self.assertRaises(ValueError): snapshot.snapshot_reader([rows[0]]*30, meta)

    def test_validated_disk_cache_avoids_network_on_repeated_draws(self):
        rows, meta = self.fixture()
        boot = {'exportRevision':'a'*40,'publication':meta['publication'],'initialMeta':meta}
        html = ('<script id="frame-bootstrap" type="application/json">'+json.dumps(boot)+'</script>').encode()
        with tempfile.TemporaryDirectory() as root, patch.dict('sys.modules', {'folder_paths':types.SimpleNamespace(get_user_directory=lambda:root)}):
            with patch.object(snapshot,'download',side_effect=[html,gzip.compress(json.dumps(rows).encode())]) as download:
                first = snapshot.published_library()
                second = snapshot.published_library()
                self.assertEqual(first('library/meta'),second('library/meta'))
                self.assertEqual(download.call_count,2)
            with patch.object(snapshot,'download',side_effect=AssertionError('network must not be needed')):
                self.assertEqual(snapshot.published_library()('library/items?ids=4')['items'][0]['id'],'4')

    def test_expansion_is_bounded_and_bad_revision_is_rejected(self):
        with patch.object(snapshot,'MAX_JSON',20), self.assertRaises(ValueError):
            snapshot.decode(gzip.compress(b' ' * 1000))
        rows,meta=self.fixture()
        boot={'exportRevision':'../escape','publication':meta['publication'],'initialMeta':meta}
        html=('<script id="frame-bootstrap" type="application/json">'+json.dumps(boot)+'</script>').encode()
        with tempfile.TemporaryDirectory() as root, patch.dict('sys.modules',{'folder_paths':types.SimpleNamespace(get_user_directory=lambda:root)}), patch.object(snapshot,'download',return_value=html):
            with self.assertRaises(ValueError):snapshot.published_library()
