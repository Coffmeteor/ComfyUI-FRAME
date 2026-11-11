from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("frame_test")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
folder = types.ModuleType("folder_paths")
folder.get_user_directory = lambda: "unused"
folder.get_filename_list = lambda category: []
folder.get_full_path = lambda category, name: None
samplers = types.ModuleType("comfy.samplers")
samplers.KSampler = types.SimpleNamespace(SAMPLERS=["euler_ancestral", "euler"], SCHEDULERS=["beta", "simple"])
comfy = types.ModuleType("comfy")
comfy.samplers = samplers
host_nodes = types.ModuleType("nodes")
host_nodes.NODE_CLASS_MAPPINGS = {}
host_nodes.NODE_DISPLAY_NAME_MAPPINGS = {}
with patch.dict(sys.modules, {"folder_paths": folder, "comfy": comfy, "comfy.samplers": samplers}):
    config = importlib.import_module("frame_test.config")
    render = importlib.import_module("frame_test.render")
    nodes = importlib.import_module("frame_test.nodes")
    source = importlib.import_module("frame_test.frame_source")


class Graph:
    def __init__(self):
        self.data = {}

    def node(self, kind, **inputs):
        ident = str(len(self.data) + 1)
        self.data[ident] = {"class_type": kind, "inputs": inputs}
        return types.SimpleNamespace(out=lambda index: [ident, index])

    def finalize(self):
        return self.data


class FrameTests(unittest.TestCase):
    def test_portable_starter_uses_static_registry_node_without_local_recipe(self):
        template = json.loads((ROOT / 'workflows' / 'FRAME Krea2 - Start Here.json').read_text(encoding='utf-8'))
        executable = [n for n in template['nodes'] if n['type'] != 'MarkdownNote']
        self.assertEqual([n['type'] for n in executable], ['FrameSetup'])
        self.assertEqual(executable[0]['properties']['cnr_id'], 'frame-nodes')
        self.assertEqual(executable[0]['properties']['aux_id'], 'Coffmeteor/ComfyUI-FRAME')
        self.assertNotIn('snapshot', template.get('extra', {}).get('frame', {}))
        self.assertEqual(nodes.FrameSetup.INPUT_TYPES(), {'required': {}})
        self.assertEqual(nodes.FrameSetup().setup(), ())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {}
        for category, name in [("diffusion_models", "model.safetensors"), ("text_encoders", "text.safetensors"),
                                ("vae", "vae.safetensors"), ("loras", "style.safetensors")]:
            p = self.root / category / name
            p.parent.mkdir(parents=True, exist_ok=True)
            header = json.dumps({"__metadata__": {"modelspec.trigger_phrase": "style_anchor"}}).encode()
            p.write_bytes(struct.pack("<Q", len(header)) + header)
            self.files.setdefault(category, {})[name] = p
        self.patches = [patch.object(folder, "get_user_directory", lambda: str(self.root / "user")),
                        patch.object(folder, "get_filename_list", lambda c: list(self.files.get(c, {}))),
                        patch.object(folder, "get_full_path", lambda c, n: str(self.files[c][n])),
                        patch.dict(sys.modules, {"comfy": comfy, "comfy.samplers": samplers, "nodes": host_nodes,
                            "comfy_execution.graph_utils": types.SimpleNamespace(GraphBuilder=Graph)})]
        for p in self.patches:
            p.start(); self.addCleanup(p.stop)
        self.recipe = {"name": "FRAME Test", "language": "zh", "models": {"unet": "model.safetensors", "text_encoder": "text.safetensors", "vae": "vae.safetensors"},
            "groups": [{"name": "My styles", "exclusive": False, "entries": [{"name": "My style", "file": "style.safetensors"}]}]}

    def test_snapshot_immutable_and_current_survives_new_recipe(self):
        first, saved = config.save(self.recipe)
        self.assertEqual(config.load(first), saved)
        self.recipe["groups"][0]["entries"][0]["strength_model"] = 0.4
        second, _ = config.save(self.recipe)
        self.assertNotEqual(first, second)
        self.assertEqual(config.load(first)["groups"][0]["entries"][0]["strength_model"], 1.0)
        path = config.directory() / "snapshots" / (first + ".json")
        path.write_text(path.read_text().replace('"FRAME Test"', '"Changed"'))
        with self.assertRaises(ValueError): config.load(first)

    def test_numeric_widget_roundtrip_keeps_snapshot_identity(self):
        self.recipe['groups'][0]['entries'][0]['strength_model']=1
        first,_=config.save(self.recipe)
        self.recipe['groups'][0]['entries'][0]['strength_model']=1.0
        second,_=config.save(self.recipe)
        self.assertEqual(first,second)

    def test_named_phone_controls_are_required_booleans_only(self):
        ident, saved = config.save(self.recipe)
        mapping, _, descriptor = nodes.recipe_classes(ident, saved)
        group = mapping[descriptor["groups"][0]["type"]]
        schema = group.INPUT_TYPES()
        self.assertEqual(list(schema["required"]), ["My style"])
        self.assertEqual(schema["required"]["My style"][0], "BOOLEAN")
        result = group().select(**{"My style": True})[0]
        self.assertEqual(result, {"snapshot": ident, "ids": ["0:0"]})
        main = mapping[descriptor["main"]].INPUT_TYPES()["required"]
        self.assertEqual({spec[0] for spec in main.values()}, {"STRING", "BOOLEAN"})
        with self.assertRaises(ValueError): group().select(previous={"snapshot": "other", "ids": []}, **{"My style": True})

    def test_group_exclusivity_and_duplicate_names(self):
        entries = self.recipe["groups"][0]["entries"]
        entries.append({**entries[0], "name": "Second style"})
        self.recipe["groups"][0]["exclusive"] = True
        ident, saved = config.save(self.recipe)
        mapping, _, d = nodes.recipe_classes(ident, saved)
        with self.assertRaises(ValueError): mapping[d["groups"][0]["type"]]().select(**{"My style": True, "Second style": True})
        entries[1]["name"] = "My style"
        with self.assertRaises(ValueError): config.validate(self.recipe)

    def test_trigger_metadata_manual_override_and_none(self):
        self.assertEqual(config.trigger_info("style.safetensors")["text"], "style_anchor")
        entry = self.recipe["groups"][0]["entries"][0]
        entry.update(trigger_mode="manual", trigger="manual_anchor")
        saved = config.validate(self.recipe)
        self.assertEqual(saved["groups"][0]["entries"][0]["trigger"], "manual_anchor")
        entry["trigger_mode"] = "none"
        self.assertEqual(config.validate(self.recipe)["groups"][0]["entries"][0]["trigger"], "")
        path = self.files["loras"]["style.safetensors"].with_suffix(".metadata.json")
        path.write_text(json.dumps({"trainedWords": ["sidecar_anchor"]}))
        self.assertEqual(config.trigger_info("style.safetensors")["text"], "sidecar_anchor")

    def test_rejects_paths_nonfinite_strength_and_unknown_fields(self):
        for value in ["/etc/passwd", "../secret", "C:/private", "nested\\bad", "missing.safetensors"]:
            with self.subTest(value=value), self.assertRaises(ValueError): config.resolve("loras", value)
        for value in [float("nan"), float("inf"), True, 11]:
            self.recipe["groups"][0]["entries"][0]["strength_model"] = value
            with self.subTest(value=value), self.assertRaises(ValueError): config.validate(self.recipe)
        self.recipe["shell"] = "not supported"
        with self.assertRaises(ValueError): config.validate(self.recipe)

    def graph(self, selected):
        recipe = config.validate(self.recipe)
        return render.build(recipe, selected, "A teapot", {}, 0, "test")['expand']

    def test_native_loading_and_automatic_trigger_toggle(self):
        on, off = self.graph(["0:0"]), self.graph([])
        self.assertTrue(any(n["class_type"] == "LoraLoaderModelOnly" for n in on.values()))
        self.assertFalse(any(n["class_type"].startswith("LoraLoader") for n in off.values()))
        self.assertEqual(next(n['inputs']['text'] for n in on.values() if n['class_type']=='CLIPTextEncode'), "style_anchor\nA teapot")
        self.assertEqual(next(n['inputs']['text'] for n in off.values() if n['class_type']=='CLIPTextEncode'), "A teapot")
        self.recipe["groups"][0]["entries"][0]["strength_clip"] = 0.5
        self.assertTrue(any(n['class_type']=='LoraLoader' for n in self.graph(["0:0"]).values()))

    def test_missing_disabled_lora_does_not_block_but_active_replacement_does(self):
        recipe = config.validate(self.recipe)
        self.files['loras']['style.safetensors'].unlink()
        render.build(recipe, [], "A teapot", {}, 0, "test")
        with self.assertRaises(ValueError): render.build(recipe, ['0:0'], "A teapot", {}, 0, "test")

    def test_stage_scope_and_dependency_errors_precede_model_loading(self):
        self.recipe['groups'][0]['entries'][0]['stages'] = ['detailer']
        self.assertFalse(any(n['class_type'].startswith('LoraLoader') for n in self.graph(['0:0']).values()))
        with self.assertRaises(ValueError): render.build(config.validate(self.recipe), [], "A teapot", {'高清重绘':True}, 0, 'test')

    def test_canvas_exclusive_and_auto_words_do_not_rewrite_manual_text(self):
        self.assertEqual(render.canvas(), (1184,1760))
        with self.assertRaises(ValueError): render.canvas(True, True)
        self.assertEqual(render.compose('anchor in my own prompt',['anchor','anchor']), 'anchor\nanchor in my own prompt')

    def test_source_validation_and_no_network_when_disabled(self):
        with self.assertRaises(ValueError): nodes.FrameSource().select(**{'原版':True,'改写版':True,'仅今日新增':False})
        self.assertEqual(source.resolve_frame_prompt('  A teapot  ',{},fetch=lambda p:self.fail('network')),('A teapot',None))

    def test_generated_types_register_without_overwriting_old_types(self):
        first, saved = config.save(self.recipe)
        old = nodes.register_recipe(first,saved)
        self.recipe['name']='New recipe'
        second,saved = config.save(self.recipe)
        new = nodes.register_recipe(second,saved)
        self.assertIn(old['main'],host_nodes.NODE_CLASS_MAPPINGS)
        self.assertIn(new['main'],host_nodes.NODE_CLASS_MAPPINGS)
        self.assertNotEqual(old['main'],new['main'])


if __name__ == '__main__': unittest.main()
