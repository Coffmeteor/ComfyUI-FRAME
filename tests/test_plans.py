import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_frame import nodes, config
from frame_test import plans


def graph(text='A teapot', seed=123):
    return {'1': {'class_type': 'KSampler', 'inputs': {'seed': seed}},
            '2': {'class_type': 'FrameSave', 'inputs': {'images': ['1', 0], 'filename_prefix': 'test',
                  'receipt': json.dumps({'text': text, 'seed': seed})}}}


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = patch.object(config, 'directory', return_value=Path(self.tmp.name))
        self.directory.start(); self.addCleanup(self.directory.stop)

    def test_batch_is_saved_before_execution_and_replay_reuses_inputs(self):
        original = [graph('First', 12), graph('Second', 34)]
        result = plans.freeze('snapshot', copy.deepcopy(original))
        code = result['ui']['text'][0]
        saved = json.loads((Path(self.tmp.name)/'plans'/(code+'.json')).read_text())
        self.assertEqual(len(saved['items']), 2)
        self.assertNotEqual(saved['items'][0]['id'], saved['items'][1]['id'])
        replay = plans.replay(saved['items'][1]['id'])
        sample = next(n for n in replay['expand'].values() if n['class_type']=='KSampler')
        self.assertEqual(sample['inputs']['seed'], 34)
        save = next(n for n in replay['expand'].values() if n['class_type']=='FrameSave')
        self.assertEqual(json.loads(save['inputs']['receipt'])['text'], 'Second')
        self.assertIn(save['inputs']['images'][0], replay['expand'])
        self.assertEqual(plans.replay(code)['expand'], result['expand'])

    def test_changed_plan_and_unknown_item_are_rejected(self):
        code = plans.freeze('snapshot', [graph()])['ui']['text'][0]
        with self.assertRaises(ValueError): plans.replay(code+'-99')
        path=Path(self.tmp.name)/'plans'/(code+'.json')
        data=json.loads(path.read_text());data['items'][0]['graph']['1']['inputs']['seed']=999
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'integrity'): plans.replay(code)
        with self.assertRaises(ValueError): plans.replay('../escape')

    def test_failed_draw_does_not_leave_a_partial_plan(self):
        cls=type('Test', (nodes.MobileGenerate,), {'SNAPSHOT':'snapshot'})
        with patch.object(cls,'_generate_one',side_effect=[{'expand':graph()},ValueError('API failed')]):
            with self.assertRaisesRegex(ValueError,'API failed'): cls().generate('',batch_count=2)
        self.assertFalse((Path(self.tmp.name)/'plans').exists())

    def test_prepared_batch_bypasses_random_source_and_replay_never_draws(self):
        cls=type('Test', (nodes.MobileGenerate,), {'SNAPSHOT':'snapshot'})
        with patch.object(cls,'_generate_one',side_effect=[{'expand':graph('First')},{'expand':graph('Second')}]) as build:
            code=cls().generate('',batch_count=2,prompt_batch='["First","Second"]')['ui']['text'][0]
            self.assertEqual([c.args[0] for c in build.call_args_list], ['First','Second'])
            self.assertFalse(build.call_args.kwargs['source']['原版'])
        with patch.object(cls,'_generate_one',side_effect=AssertionError('must not draw')):
            cls().generate('',replay_code=code)
