import unittest
from unittest.mock import patch

import test_frame
from test_frame import config, nodes


class MossGeneratorTests(unittest.TestCase):
    setUp = test_frame.FrameTests.setUp

    def test_mobile_controls_expand_to_native_moss_graph(self):
        self.recipe["language"] = "en"
        self.recipe["prompt_policy"] = "explicit"
        self.recipe["generation"] = {"clip_type": "moss_image", "negative_prompt": "banding"}
        other = self.files["loras"]["style.safetensors"].with_name("other.safetensors")
        other.write_bytes(b"test")
        self.files["loras"][other.name] = other
        self.recipe["groups"][0]["entries"].append({
            "name": "Other style", "file": other.name, "trigger_mode": "manual", "trigger": "other_anchor",
        })
        ident, recipe = config.save(self.recipe)
        classes, _, descriptor = nodes.recipe_classes(ident, recipe)
        primary = classes[descriptor["main"]]
        main_fields = primary.INPUT_TYPES()["required"]
        self.assertTrue({"Landscape", "Square", "Phone wallpaper", "1 MP"}.isdisjoint(main_fields))
        self.assertEqual(len(main_fields["Resolution"][1]["options"]), 7)
        self.assertEqual(len(descriptor["groups"]), 1)
        stack = classes[descriptor["groups"][0]["type"]]()
        stack_fields = stack.INPUT_TYPES()["required"]
        self.assertEqual(len(stack_fields), 8)
        self.assertEqual(stack_fields["LoRA 1"][1]["options"], ["None", "My style", "Other style"])
        values = {key: spec[1]["default"] for key, spec in stack_fields.items()}
        values.update({"LoRA 2": "Other style", "Strength 2": 0.6, "LoRA 4": "My style", "Strength 4": 0.4})
        selection, = stack.select(**values)
        source = classes[descriptor["source"]]()
        source_values = {key: spec[1]["default"] for key, spec in source.INPUT_TYPES()["required"].items()}
        source_values["Prompt source"] = next(x for x in source.INPUT_TYPES()["required"]["Prompt source"][0] if "FRAME Original" in x)
        library, = source.select(**source_values)
        inputs = {key: spec[1]["default"] for key, spec in main_fields.items()}
        inputs.update({"Prompt": "manual text", "Resolution": "Portrait preview · 1024 × 1792"})

        with patch("frame_test.selections.resolve", return_value=("a teapot", {"entry_id": "test"})) as resolve:
            result = primary().generate(source=library, loras=selection, **inputs)
        resolve.assert_called_once_with("manual text", library)
        graph = result["expand"]

        def matching(kind):
            return [(key, node["inputs"]) for key, node in graph.items() if node["class_type"] == kind]

        self.assertEqual(matching("CLIPLoader")[0][1]["type"], "moss_image")
        self.assertEqual(matching("EmptyLatentImage")[0][1], {"width": 1024, "height": 1792, "batch_size": 1})
        self.assertEqual([values["text"] for _, values in matching("CLIPTextEncode")], ["other_anchor, style_anchor\na teapot", "banding"])
        shift, shift_inputs = matching("ModelSamplingAuraFlow")[0]
        self.assertEqual(shift_inputs["shift"], 5.0)
        self.assertFalse(matching("LoraLoader"))
        (first, first_inputs), (second, second_inputs) = matching("LoraLoaderModelOnly")
        self.assertEqual(first_inputs, {"model": [shift, 0], "lora_name": other.name, "strength_model": 0.6})
        self.assertEqual(second_inputs, {"model": [first, 0], "lora_name": "style.safetensors", "strength_model": 0.4})
        self.assertEqual(matching("KSampler")[0][1]["model"], [second, 0])
        values["Strength 4"] = 0.0
        self.assertEqual(stack.select(**values)[0]["ids"], ["0:1"])
        values.update({"LoRA 1": "Other style", "Strength 1": 0.2})
        with self.assertRaisesRegex(ValueError, "only once"):
            stack.select(**values)

    def test_family_recipes_and_legacy_snapshots_stay_separate(self):
        krea_id, krea = config.save(self.recipe)
        self.recipe.update(generation={"clip_type": "moss_image"}, groups=[])
        moss_id, moss = config.save(self.recipe)
        self.assertNotEqual(krea_id, moss_id)
        self.assertEqual(config.current(), krea)
        self.assertEqual(config.load(krea_id), krea)
        self.assertEqual(config.current("moss_image"), moss)
        classes, _, descriptor = nodes.recipe_classes(moss_id, moss)
        schema = classes[descriptor["groups"][0]["type"]].INPUT_TYPES()["required"]
        self.assertEqual(schema["LoRA 槽位 1"][0], ["None"])
