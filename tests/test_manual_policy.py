from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

import test_frame as fixture

config, nodes = fixture.config, fixture.nodes
selections = importlib.import_module('frame_test.selections')
languages = importlib.import_module('frame_test.languages')


class ManualPolicyTests(unittest.TestCase):
    setUp = fixture.FrameTests.setUp

    def prepare(self, language='en'):
        self.recipe['language'] = language
        self.recipe.pop('prompt_policy', None)
        ident, recipe = config.save(self.recipe)
        mapping, _, d = nodes.recipe_classes(ident, recipe)
        return ident, recipe, mapping, d

    def source(self, ident, append=False, choice='FRAME 原版 · 全库'):
        return {'snapshot': ident, 'choice': choice, 'mode': '沿用当前', 'append_manual': append}

    @staticmethod
    def draw(*args):
        return 'A teapot on a table', {'entry_id':'one','eligible_count':1,'selected_prompt':'A teapot on a table'}

    def test_new_policy_has_explicit_off_switch_in_all_languages(self):
        for language in languages.LANGUAGES:
            ident, recipe, mapping, d = self.prepare(language)
            self.assertEqual(recipe['prompt_policy'], 'explicit')
            schema = mapping[d['source']].INPUT_TYPES()['required']
            switch = languages.caption('Append manual text', '追加手动提示词', language)
            self.assertEqual(schema[switch][0], 'BOOLEAN')
            self.assertFalse(schema[switch][1]['default'])
            values = {key: spec[0][0] for key, spec in schema.items() if key != switch}
            values[switch] = False
            self.assertFalse(mapping[d['source']]().select(**values)[0]['append_manual'])
            values[switch] = 'false'
            with self.assertRaises(ValueError): mapping[d['source']]().select(**values)

    def test_online_manual_text_only_applies_when_enabled_without_redrawing(self):
        ident, _, _, _ = self.prepare()
        source = self.source(ident)
        original = dict(source)
        with patch.object(selections, 'resolve_frame_prompt', side_effect=self.draw) as draw:
            text, receipt = selections.resolve('A different complete scene', source)
            self.assertEqual(text, 'A teapot on a table')
            self.assertEqual(receipt['supplement'], '')
            self.assertTrue(receipt['manual_text_ignored'])
            source['append_manual'] = True
            text, receipt = selections.resolve('Warm light', source)
            self.assertEqual(text, 'A teapot on a table\nWarm light')
            self.assertFalse(receipt['manual_text_ignored'])
            source['append_manual'] = False
            self.assertEqual(selections.resolve('Warm light', source)[0], 'A teapot on a table')
            self.assertEqual(draw.call_count, 1)
        self.assertEqual(source, original)

    def test_manual_only_mode_uses_text_with_append_off(self):
        ident, _, _, _ = self.prepare()
        with patch.object(selections, 'resolve_frame_prompt', side_effect=AssertionError('network')):
            self.assertEqual(selections.resolve('  My own prompt  ', self.source(ident, choice='manual')), ('My own prompt', None))

    def test_local_library_uses_the_same_explicit_policy(self):
        wildcards = importlib.import_module('frame_test.wildcards')
        library = wildcards.import_text('Test', 'A teapot', 'lines')
        self.recipe['wildcards'] = [{'id':library['id'],'name':library['name']}]
        ident, _, _, _ = self.prepare()
        source = self.source(ident, choice=library['id'])
        with patch.object(selections, 'resolve_frame_prompt', side_effect=AssertionError('network')):
            self.assertEqual(selections.resolve('Keep this text', source)[0], 'A teapot')
            source['append_manual'] = True
            self.assertEqual(selections.resolve('Keep this text', source)[0], 'A teapot\nKeep this text')

    def test_old_snapshot_keeps_two_fields_and_automatic_append(self):
        recipe = config.validate(self.recipe)
        recipe.pop('prompt_policy')
        ident = config.snapshot_id(recipe)
        config.atomic_json(config.directory()/'snapshots'/(ident+'.json'), recipe)
        mapping, _, d = nodes.recipe_classes(ident, recipe)
        self.assertEqual(len(mapping[d['source']].INPUT_TYPES()['required']), 2)
        source = {'snapshot':ident,'choice':'FRAME 原版 · 全库','mode':'沿用当前'}
        with patch.object(selections,'resolve_frame_prompt',side_effect=self.draw):
            self.assertEqual(selections.resolve('Legacy supplement',source)[0], 'A teapot on a table\nLegacy supplement')

    def test_missing_or_invalid_new_switch_fails_and_policy_binds_identity(self):
        ident, _, _, _ = self.prepare()
        source = self.source(ident)
        for bad in [{k:v for k,v in source.items()if k!='append_manual'}, {**source,'append_manual':1}]:
            with self.assertRaises(ValueError): selections.resolve('Text', bad)
        self.recipe['prompt_policy']='legacy'
        other, _ = config.save(self.recipe)
        self.assertNotEqual(ident, other)


if __name__ == '__main__': unittest.main()
