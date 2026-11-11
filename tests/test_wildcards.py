from __future__ import annotations

import copy
import importlib
import unittest
from unittest.mock import patch

import test_frame as fixture

wildcards = importlib.import_module("frame_test.wildcards")
selections = importlib.import_module("frame_test.selections")
config, nodes = fixture.config, fixture.nodes


class WildcardTests(unittest.TestCase):
    setUp = fixture.FrameTests.setUp

    def source(self, choice="FRAME 原版 · 全库", mode="沿用当前", recipe=None):
        ident, _ = config.save(recipe or self.recipe)
        return {"snapshot": ident, "choice": choice, "mode": mode}

    @staticmethod
    def draw(prompt, options):
        label = "rewrite" if options.get("FRAME 改写版") else "original"
        text = "A complete " + label + " prompt."
        return text, {"entry_id": label, "eligible_count": 1, "selected_prompt": text,
                      "publication": {"date": "2026-11-11"}}

    def test_utf8_bom_comments_crlf_and_multiline_formats(self):
        self.assertEqual(wildcards.parse("\ufeff# comment\r\n  蓝色茶壶  \r\n\r\nA cup\r\n", "lines"), ["蓝色茶壶", "A cup"])
        self.assertEqual(wildcards.parse("Line one\r\nLine two\r\n \r\n# comment\r\nOther prompt", "blocks"), ["Line one\nLine two", "Other prompt"])
        self.assertEqual(wildcards.parse("__literal__ {red|blue}", "lines"), ["__literal__ {red|blue}"])

    def test_rejects_empty_binary_oversize_and_invalid_format(self):
        for text, mode in [("# only comments", "lines"), ("binary\0", "lines"), ("\x01", "lines"),
                           ("one", "yaml"), ("x" * 32769, "lines"), ("x\n" * 50001, "lines")]:
            with self.subTest(mode=mode, length=len(text)), self.assertRaises(ValueError):
                wildcards.parse(text, mode)
        with patch.object(wildcards, "MAX_IMPORT_BYTES", 2), self.assertRaises(ValueError):
            wildcards.parse("测试", "lines")

    def test_import_deduplicates_and_freezes_library_versions(self):
        a = wildcards.import_text("My library", "A teapot\nAn orange", "lines")
        self.assertEqual(a, wildcards.import_text("My library", "A teapot\nAn orange", "lines"))
        b = wildcards.import_text("My library", "A new prompt", "lines")
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(len(wildcards.index()), 2)
        self.assertEqual(wildcards.load(a["id"])["entries"], ["A teapot", "An orange"])
        for ident in ("../private", "/etc/passwd", "g" * 20):
            with self.assertRaises(ValueError): wildcards.load(ident)
        path = config.directory() / "wildcards" / (a["id"] + ".json")
        path.write_text(path.read_text().replace("A teapot", "Changed"))
        with self.assertRaises(ValueError): wildcards.load(a["id"])

    def test_snapshot_binds_only_chosen_libraries_and_unique_names(self):
        a = wildcards.import_text("Mine", "A teapot", "lines")
        b = wildcards.import_text("Mine", "An orange", "lines")
        self.recipe["wildcards"] = [{"id": a["id"], "name": a["name"]}]
        ident, recipe = config.save(self.recipe)
        self.assertIn(a["id"], selections.choices(recipe).values())
        self.assertNotIn(b["id"], selections.choices(recipe).values())
        self.recipe["wildcards"].append({"id": b["id"], "name": b["name"]})
        with self.assertRaises(ValueError): config.save(self.recipe)
        self.assertEqual(config.load(ident), recipe)

    def test_source_schema_has_two_single_choice_menus(self):
        ident, recipe = config.save(self.recipe)
        mapping, _, descriptor = nodes.recipe_classes(ident, recipe)
        cls = mapping[descriptor["source"]]
        schema = cls.INPUT_TYPES()["required"]
        self.assertEqual(list(schema), ["提示词来源", "抽词方式"])
        self.assertEqual(schema["抽词方式"][0], ["沿用当前", "每次随机"])
        self.assertEqual(len(schema["提示词来源"][0]), 5)
        for spec in schema.values():
            self.assertEqual(len(spec), 2)
            self.assertEqual(spec[1]["default"], spec[0][0])
            self.assertEqual(spec[1]["options"], spec[0])
        for source in schema["提示词来源"][0]:
            self.assertEqual(cls().select(**{"提示词来源": source, "抽词方式": "沿用当前"})[0]["snapshot"], ident)
        with self.assertRaises(ValueError): cls().select(**{"提示词来源": "bad", "抽词方式": "沿用当前"})

    def test_reuse_persists_without_network_and_updates_manual_supplement(self):
        source = self.source()
        with patch.object(selections, "resolve_frame_prompt", side_effect=self.draw) as draw:
            first, a = selections.resolve("Warm light", source)
            second, b = selections.resolve("Cool light", source)
            self.assertEqual(draw.call_count, 1)
        self.assertEqual(first, "A complete original prompt.\nWarm light")
        self.assertEqual(second, "A complete original prompt.\nCool light")
        self.assertFalse(a["reused_selection"]); self.assertTrue(b["reused_selection"])
        with patch.object(selections, "resolve_frame_prompt", side_effect=ValueError("offline")):
            self.assertEqual(selections.resolve("", source)[0], "A complete original prompt.")

    def test_random_updates_current_then_reuse_holds_latest(self):
        source = self.source()
        def draw(prompt, options):
            number = mock.call_count
            text = f"Prompt {number}"
            return text, {"entry_id": str(number), "eligible_count": 10, "selected_prompt": text}
        with patch.object(selections, "resolve_frame_prompt", side_effect=draw) as mock:
            self.assertEqual(selections.resolve("", source)[0], "Prompt 1")
            source["mode"] = "每次随机"
            self.assertEqual(selections.resolve("", source)[0], "Prompt 2")
            self.assertEqual(selections.resolve("", source)[0], "Prompt 3")
            source["mode"] = "沿用当前"
            self.assertEqual(selections.resolve("", source)[0], "Prompt 3")
            self.assertEqual(mock.call_count, 3)

    def test_new_source_and_recipe_have_separate_current_items(self):
        a, b = self.source(), self.source("FRAME 改写版 · 全库")
        changed = copy.deepcopy(self.recipe); changed["name"] = "Other recipe"
        c = self.source(recipe=changed)
        with patch.object(selections, "resolve_frame_prompt", side_effect=self.draw) as draw:
            for source in (a, b, c, a, b): selections.resolve("", source)
            self.assertEqual(draw.call_count, 3)

    def test_failed_random_keeps_current_and_invalid_sources_fail_closed(self):
        source = self.source()
        with patch.object(selections, "resolve_frame_prompt", side_effect=self.draw): selections.resolve("", source)
        source["mode"] = "每次随机"
        with patch.object(selections, "resolve_frame_prompt", side_effect=ValueError("offline")), self.assertRaises(ValueError):
            selections.resolve("", source)
        source["mode"] = "沿用当前"
        self.assertEqual(selections.resolve("", source)[0], "A complete original prompt.")
        for bad in [{**source, "choice": "unselected"}, {**source, "mode": "bad"}, {**source, "extra": True}]:
            with self.assertRaises(ValueError): selections.resolve("", bad)

    def test_local_library_reuse_random_no_network_and_single_entry(self):
        lib = wildcards.import_text("My prompts", "A teapot\nAn orange", "lines")
        self.recipe["wildcards"] = [{"id": lib["id"], "name": lib["name"]}]
        source = self.source(lib["id"])
        with patch.object(selections, "resolve_frame_prompt", side_effect=AssertionError("network")):
            a, receipt = selections.resolve("Warm light", source)
            self.assertEqual(selections.resolve("Warm light", source)[0], a)
            source["mode"] = "每次随机"
            b, _ = selections.resolve("Warm light", source)
            self.assertNotEqual(a, b)
        self.assertEqual(receipt["source"], "local")
        one = wildcards.import_text("Single", "One prompt", "lines")
        self.recipe["wildcards"] = [{"id": one["id"], "name": one["name"]}]
        source = self.source(one["id"], "每次随机")
        self.assertEqual(selections.resolve("", source)[0], selections.resolve("", source)[0])

    def test_image_seeds_remain_independent_of_reused_prompt(self):
        source = self.source()
        cls = type("Main", (nodes.MobileGenerate,), {"SNAPSHOT": source["snapshot"]})
        options = {key: False for key in nodes.CONTROLS}
        with patch.object(selections, "resolve_frame_prompt", side_effect=self.draw) as draw, \
             patch.object(nodes.secrets, "randbits", side_effect=[123, 456]), patch.object(nodes, "build", return_value={}) as build:
            cls().generate("Supplement", source=source, **options)
            cls().generate("Supplement", source=source, **options)
        self.assertEqual(draw.call_count, 1)
        self.assertEqual([call.args[4] for call in build.call_args_list], [123, 456])
        self.assertEqual(build.call_args_list[0].args[2], build.call_args_list[1].args[2])


if __name__ == "__main__": unittest.main()
