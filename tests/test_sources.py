from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import importlib.util
spec = importlib.util.spec_from_file_location("public_frame_source", Path(__file__).resolve().parents[1] / "frame_source.py")
frame = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frame)

NOW = datetime(2026, 11, 11, 6, tzinfo=timezone.utc)  # Still Nov 10 in FRAME's timezone.
PUBLICATION = {"date": "2026-11-10", "timezone": "America/Los_Angeles", "today_added": 3,
               "updated_at": "2026-11-11T03:00:00+00:00"}


class FrameWildcardTests(unittest.TestCase):
    def setUp(self):
        self.meta = {"total": 50, "publication": copy.deepcopy(PUBLICATION)}
        self.calls = []

    def fetch(self, path):
        self.calls.append(path)
        url = urlsplit(path)
        query = parse_qs(url.query)
        if url.path.endswith("/meta"):
            return copy.deepcopy(self.meta)
        if url.path.endswith("/query"):
            page = int(query["page"][0])
            self.assertEqual(query["sort"], ["newest"])
            return {**copy.deepcopy(self.meta), "page": page, "page_size": 24,
                    "items": [{"id": f"entry-{i}", "added_at": "2026-11-11T01:30:00+00:00",
                               "prompt": f"Full rewritten prompt {i}.", "clean_prompt": "Alternate text"}
                              for i in range((page - 1) * 24, min(page * 24, self.meta["total"]))]}
        if url.path.endswith("/items"):
            return {"items": [{"id": query["ids"][0], "prompt_krea2": "An intact original prompt.",
                               "prompt_krea2_style_ref": "Use the reference only."}]}
        self.fail(path)

    def resolve(self, options, prompt="", fetch=None):
        return frame.resolve_frame_prompt(prompt, options, now=NOW, fetch=fetch or self.fetch)

    def test_disabled_preserves_manual_prompt_and_makes_no_network_request(self):
        self.assertEqual(self.resolve({}, "  A teapot.  "), ("A teapot.", None))
        self.assertEqual(self.calls, [])

    def test_full_library_draw_can_reach_beyond_first_page_and_preserves_supplement(self):
        text, receipt = self.resolve({"FRAME 原版": True, "固定随机种子": True}, "Warm light.")
        index = random.Random(0).randrange(50)
        self.assertGreaterEqual(index, 24)
        self.assertEqual(receipt["entry_id"], f"entry-{index}")
        self.assertEqual(text, "An intact original prompt.\nWarm light.")
        self.assertEqual(receipt["prompt_field"], "prompt_krea2")
        self.assertEqual(receipt["scope"], "all")
        self.assertEqual(receipt["eligible_count"], 50)
        self.assertEqual(receipt["prompt_sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertIn("library/items?", self.calls[2])

    def test_rewrite_uses_its_full_prompt_without_original_or_style_reference(self):
        text, receipt = self.resolve({"FRAME 改写版": True, "固定随机种子": True})
        self.assertEqual(text, f"Full rewritten prompt {receipt['index']}.")
        self.assertEqual(receipt["source"], "rewrite")
        self.assertFalse(any("/items" in path or path.startswith("library") for path in self.calls))

    def test_today_uses_website_timezone_and_today_count_with_fixed_selection(self):
        options = {"FRAME 原版": True, "仅今日更新": True, "固定随机种子": True}
        a, receipt = self.resolve(options)
        b, again = self.resolve(options)
        self.assertEqual(receipt, again)
        self.assertEqual(a, b)
        self.assertEqual(receipt["selection_date"], "2026-11-10")
        self.assertEqual(receipt["eligible_count"], 3)
        self.assertLess(receipt["index"], 3)
        self.assertEqual(receipt["scope"], "today")
        self.assertEqual(receipt["scope_date"], "2026-11-10")

    def test_unfixed_selection_records_a_fresh_draw_seed(self):
        with patch.object(frame.secrets, "randbits", return_value=12345):
            _, receipt = self.resolve({"FRAME 改写版": True})
        self.assertEqual(receipt["seed"], 12345)

    def test_empty_published_batch_does_not_fall_back_to_full_library(self):
        self.meta["publication"]["today_added"] = 0
        with self.assertRaisesRegex(ValueError, "no entries in the latest publication"):
            self.resolve({"FRAME 原版": True, "仅今日更新": True})
        self.assertEqual(self.calls, ["library/meta"])

    def test_five_item_batch_keeps_website_pool_across_midnight(self):
        options = {"FRAME 改写版": True, "仅今日更新": True}
        start = datetime(2026, 11, 11, 7, 59, tzinfo=timezone.utc)
        receipts = []
        with patch.object(frame.secrets, "randbits", side_effect=range(1, 6)):
            for i in range(5):
                _, receipt = frame.resolve_frame_prompt("", options, now=start + timedelta(minutes=i), fetch=self.fetch)
                receipts.append(receipt)
        self.assertEqual([r["selection_date"] for r in receipts],
                         ["2026-11-10", *(["2026-11-11"] * 4)])
        self.assertEqual({r["scope_date"] for r in receipts}, {"2026-11-10"})
        self.assertEqual({r["eligible_count"] for r in receipts}, {3})
        self.assertEqual(len({r["seed"] for r in receipts}), 5)
        self.assertTrue(all(r["index"] < 3 for r in receipts))

    def test_next_published_day_replaces_the_previous_update_pool(self):
        options = {"FRAME 改写版": True, "仅今日更新": True, "固定随机种子": True}
        _, before = self.resolve(options)
        self.meta["publication"].update(date="2026-11-11", today_added=2,
                                        updated_at="2026-11-12T03:00:00+00:00")
        def fetch(path):
            value = self.fetch(path)
            for row in value.get("items", []):
                row["added_at"] = "2026-11-11T16:30:00+00:00"
            return value
        _, after = frame.resolve_frame_prompt("", options, now=NOW + timedelta(days=1), fetch=fetch)
        self.assertEqual(before["scope_date"], "2026-11-10")
        self.assertEqual(after["scope_date"], "2026-11-11")
        self.assertEqual(after["eligible_count"], 2)

    def test_today_rejects_a_row_outside_the_day_or_in_the_future(self):
        for added in ("2026-11-10T01:00:00+00:00", "2026-11-11T07:00:00+00:00"):
            def fetch(path):
                value = self.fetch(path)
                for row in value.get("items", []):
                    row["added_at"] = added
                return value
            with self.subTest(added=added), self.assertRaisesRegex(ValueError, "entry dates do not match"):
                self.resolve({"FRAME 改写版": True, "仅今日更新": True}, fetch=fetch)

    def test_legacy_naive_date_matches_the_websites_pacific_interpretation(self):
        def fetch(path):
            value = self.fetch(path)
            for row in value.get("items", []):
                row["added_at"] = "2026-11-10 01:30:00"
            return value
        self.resolve({"FRAME 改写版": True, "仅今日更新": True}, fetch=fetch)

    def test_changed_publication_retries_once_and_never_mixes_snapshots(self):
        def fetch(path):
            value = self.fetch(path)
            if "/query?" in path:
                value["publication"]["updated_at"] = "2026-11-11T04:00:00+00:00"
            return value
        with self.assertRaisesRegex(ValueError, "catalog is updating"):
            self.resolve({"FRAME 原版": True}, fetch=fetch)
        self.assertEqual(len(self.calls), 4)
        self.assertFalse(any("/items" in path for path in self.calls))

    def test_a_new_website_release_is_used_on_the_next_draw(self):
        options = {"FRAME 改写版": True, "固定随机种子": True}
        _, before = self.resolve(options)
        self.meta["total"] = 60
        self.meta["publication"]["updated_at"] = "2026-11-11T05:00:00+00:00"
        _, after = self.resolve(options)
        self.assertEqual(after["catalog_total"], 60)
        self.assertNotEqual(before["publication"], after["publication"])

    def test_one_publication_race_can_recover_without_reusing_the_first_page(self):
        def fetch(path):
            value = self.fetch(path)
            if "/query?" in path and sum("/query?" in p for p in self.calls) == 1:
                value["publication"]["updated_at"] = "2026-11-11T04:00:00+00:00"
            return value
        _, receipt = self.resolve({"FRAME 改写版": True}, fetch=fetch)
        self.assertEqual(receipt["publication"], PUBLICATION)
        self.assertEqual(sum("/query?" in p for p in self.calls), 2)

    def test_missing_prompt_is_not_replaced_with_another_model_or_category(self):
        def fetch(path):
            value = self.fetch(path)
            if "/items?" in path:
                value["items"][0].pop("prompt_krea2")
            return value
        with self.assertRaisesRegex(ValueError, "lacks a complete prompt"):
            self.resolve({"FRAME 原版": True}, fetch=fetch)

    def test_network_request_is_bounded_public_and_contains_no_user_prompt(self):
        from io import BytesIO
        response = BytesIO(json.dumps(self.meta).encode())
        response.geturl = lambda: frame.API + "library/meta"
        with patch.object(frame, "urlopen", return_value=response) as urlopen:
            self.assertEqual(frame.get_json("library/meta"), self.meta)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, frame.API + "library/meta")
        self.assertEqual(request.get_header("Origin"), frame.ORIGIN)
        self.assertIsNone(request.data)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 12)


if __name__ == "__main__":
    unittest.main()
