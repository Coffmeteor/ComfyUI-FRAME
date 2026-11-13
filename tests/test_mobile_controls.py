import unittest
from unittest.mock import patch
from test_frame import FrameTests, config, nodes

class MobileControlsTests(unittest.TestCase):
    setUp = FrameTests.setUp
    def test_new_layout_has_one_localized_batch_editor(self):
        self.recipe['mobile_controls']=2
        for language in ('zh','en'):
            self.recipe['language']=language
            ident, recipe=config.save(self.recipe)
            classes,_,d=nodes.recipe_classes(ident,recipe)
            main=classes[d['main']].INPUT_TYPES()
            self.assertFalse({'batch_count','catalog_selection','catalog','prompt_format','prompt_ids','prompt_batch'} & set(main['optional']))
            self.assertIn(d['text_field'], main['required'])
            schema=classes[d['batch']].INPUT_TYPES()['required']
            values={k:v[1]['default'] for k,v in schema.items()}
            values[d['batch_field_names']['catalog_selection']]=d['batch_option_names']['catalog_selection']['Fixed prompt IDs']
            values[d['batch_field_names']['batch_count']]=2
            values[d['batch_field_names']['prompt_ids']]='1,2'
            batch=classes[d['batch']]().select(**values)[0]
            self.assertEqual(batch['catalog_selection'],'Fixed prompt IDs')
            self.assertEqual(batch['prompt_ids'],'1,2')
            with patch.object(nodes.MobileGenerate,'generate',return_value={'ok':True}) as generate:
                classes[d['main']]().generate(**{d['text_field']:'test',d['replay_field']:'', 'catalog_batch':batch})
                self.assertEqual(generate.call_args.kwargs['text'],'test')
                self.assertEqual(generate.call_args.kwargs['catalog_batch'],batch)
            if language=='zh':
                self.assertIn('选择方式',schema)
                self.assertEqual(schema['词库'][0],['原版词库','改写词库'])
                self.assertNotIn('prompt_ids',schema)
    def test_old_snapshot_schema_keeps_legacy_controls(self):
        ident,recipe=config.save(self.recipe)
        classes,_,d=nodes.recipe_classes(ident,recipe)
        self.assertIn('prompt_batch',classes[d['main']].INPUT_TYPES()['optional'])
        self.assertIn('batch_count',classes[d['batch']].INPUT_TYPES()['required'])
        self.recipe['mobile_controls']=2
        new_id,_=config.save(self.recipe)
        self.assertNotEqual(ident,new_id)
        self.assertNotIn('mobile_controls',config.load(ident))

    def test_legacy_api_inputs_remain_accepted_without_visible_widgets(self):
        self.recipe['mobile_controls']=2
        ident,recipe=config.save(self.recipe)
        classes,_,d=nodes.recipe_classes(ident,recipe)
        cls=classes[d['main']]
        self.assertEqual(cls.INPUT_TYPES()['hidden']['prompt'],'PROMPT')
        raw={'7':{'inputs':{'text':'legacy text','replay_code':'saved-code','prompt_batch':'["one","two"]','batch_count':2}}}
        with patch.object(nodes.MobileGenerate,'generate',return_value={}) as generate:
            cls().generate(**{d['text_field']:'',d['replay_field']:'', 'prompt':raw,'unique_id':'7','catalog_batch':{'batch_count':1}})
            self.assertEqual(generate.call_args.kwargs['text'],'legacy text')
            self.assertEqual(generate.call_args.kwargs['replay_code'],'saved-code')
            self.assertEqual(generate.call_args.kwargs['batch_count'],2)
            self.assertIsNone(generate.call_args.kwargs['catalog_batch'])
