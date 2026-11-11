from __future__ import annotations

import copy
import importlib
import unittest
from unittest.mock import patch

import test_frame as fixture

config, nodes = fixture.config, fixture.nodes
selections = importlib.import_module('frame_test.selections')
languages = importlib.import_module('frame_test.languages')


class LanguageTests(unittest.TestCase):
    setUp = fixture.FrameTests.setUp

    def test_new_recipes_default_to_english_and_language_binds_schema(self):
        self.recipe.pop('language')
        ident, recipe = config.save(self.recipe)
        self.assertEqual(recipe['language'], 'en')
        mapping, names, d = nodes.recipe_classes(ident, recipe)
        schema = mapping[d['source']].INPUT_TYPES()['required']
        self.assertEqual(list(schema), ['Prompt source', 'Selection mode'])
        self.assertEqual(schema['Selection mode'][0], ['Reuse current', 'Random each generation'])
        self.assertEqual(schema['Prompt source'][0][1], 'FRAME Original · Full library')
        self.assertEqual(names[d['main']], 'Prompt & Quality')
        self.assertTrue(all(not any('\u4e00' <= c <= '\u9fff' for c in str(spec)) for spec in schema.values()))
        self.recipe['language'] = 'bilingual'
        other, saved = config.save(self.recipe)
        self.assertNotEqual(ident, other)
        self.assertEqual(config.load(ident), recipe)
        self.assertIn('Landscape / 横图', nodes.recipe_classes(other, saved)[0]['FrameKrea2_' + other].INPUT_TYPES()['required'])
        self.recipe['language'] = 'unsupported'
        with self.assertRaises(ValueError): config.save(self.recipe)

    def test_legacy_snapshot_keeps_chinese_schema_and_identity(self):
        legacy = config.validate(self.recipe)
        legacy.pop('language')
        ident = config.snapshot_id(legacy)
        config.atomic_json(config.directory() / 'snapshots' / (ident + '.json'), legacy)
        self.assertEqual(config.load(ident), legacy)
        mapping, _, d = nodes.recipe_classes(ident, config.load(ident))
        schema = mapping[d['source']].INPUT_TYPES()['required']
        self.assertEqual(list(schema), ['提示词来源', '抽词方式'])
        self.assertEqual(schema['抽词方式'][0], ['沿用当前', '每次随机'])
        self.assertEqual(set(mapping[d['main']].INPUT_TYPES()['required']) - {'text'}, set(nodes.CONTROLS))

    def test_all_languages_normalize_to_the_same_internal_source_and_controls(self):
        normalized = []
        for language in languages.LANGUAGES:
            self.recipe['language'] = language
            ident, recipe = config.save(self.recipe)
            mapping, _, d = nodes.recipe_classes(ident, recipe)
            cls = mapping[d['source']]
            fields = cls.INPUT_TYPES()['required']
            source = cls().select(**{key: spec[0][1] for key, spec in fields.items()})[0]
            self.assertEqual(source['choice'], 'FRAME 原版 · 全库')
            self.assertEqual(source['mode'], '每次随机')
            source['choice'] = 'manual'
            main = mapping[d['main']]
            options = {key: key == languages.caption('Square', '方图', language) for key in main.INPUT_TYPES()['required'] if key != 'text'}
            with patch.object(nodes, 'build', return_value={}) as build:
                main().generate('A teapot', source=source, **options)
                normalized.append(build.call_args.args[3])
            with self.assertRaises(ValueError): main().generate('A teapot', **{'wrong field': True})
        self.assertEqual(normalized[0], normalized[1])
        self.assertEqual(normalized[1], normalized[2])
        self.assertTrue(normalized[0]['方图'])

    def test_custom_names_are_not_translated(self):
        self.recipe['language'] = 'en'
        self.recipe['groups'][0]['name'] = '我的风格'
        self.recipe['groups'][0]['entries'][0]['name'] = '自己命名'
        ident, recipe = config.save(self.recipe)
        _, _, d = nodes.recipe_classes(ident, recipe)
        self.assertEqual(d['groups'][0]['title'], '我的风格')
        self.assertEqual(d['groups'][0]['labels'], ['自己命名'])


if __name__ == '__main__': unittest.main()
