import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from test_frame import nodes
from frame_test import catalog_selection as selection

META={'total':4,'publication':{'date':'2026-11-13','timezone':'America/Los_Angeles','today_added':4,'updated_at':'2026-11-13T00:00:00+00:00'}}
class CatalogSelectionTests(unittest.TestCase):
    def setUp(self):self.paths=[]
    def fetch(self,path):
        self.paths.append(path)
        if path.endswith('/meta'):return META
        query=parse_qs(urlsplit(path).query)
        if '/query?' in path:
            ids=['db-a','db-b'] if query['seed']==['1'] else ['db-c','db-d']
            return {**META,'items':[{'id':i,'prompt_previews':{'prompt_krea2':'Preview'}} for i in ids]}
        return {'items':[{'id':i,'prompt_krea2':'A ceramic teapot '+i,'revision':'revision-1'} for i in query['ids'][0].split(',') if i!='missing']}
    def test_random_mode_draws_new_ids_for_each_run(self):
        with patch.object(selection.secrets,'randbits',side_effect=[1,2]):
            a=selection.select('library','prompt_krea2',selection.POLICIES[1],2,fetch=self.fetch)
            b=selection.select('library','prompt_krea2',selection.POLICIES[1],2,fetch=self.fetch)
        self.assertEqual([r['id'] for r in a],['db-a','db-b'])
        self.assertEqual([r['id'] for r in b],['db-c','db-d'])
    def test_fixed_ids_keep_identity_and_order_without_drawing(self):
        a=selection.select('library','prompt_krea2',selection.POLICIES[2],2,'db-b, db-a',fetch=self.fetch)
        b=selection.select('library','prompt_krea2',selection.POLICIES[2],2,'db-b\ndb-a',fetch=self.fetch)
        self.assertEqual(a,b);self.assertEqual([r['id'] for r in a],['db-b','db-a'])
        self.assertFalse(any('/query?' in p for p in self.paths))
    def test_missing_fixed_id_never_gets_replaced(self):
        with self.assertRaisesRegex(ValueError,'unavailable'):
            selection.select('library','prompt_krea2',selection.POLICIES[2],1,'missing',fetch=self.fetch)
        self.assertFalse(any('/query?' in p for p in self.paths))
    def test_rejects_bad_ids_count_and_wrong_format(self):
        for ids in ['../path','a,a','',','.join('id'+str(i) for i in range(11))]:
            with self.assertRaises(ValueError):selection.parse_ids(ids)
        with self.assertRaises(ValueError):selection.select('library','prompt_krea2',selection.POLICIES[2],2,'one',fetch=self.fetch)
        with self.assertRaises(ValueError):selection.select('rewrite','prompt_krea2',selection.POLICIES[1],1,fetch=self.fetch)
