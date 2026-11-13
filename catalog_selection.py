"""Select persistent public database IDs independently of image seeds and plans."""
import re
import secrets
from urllib.parse import urlencode
from .frame_source import get_json, publication

POLICIES = ('Workflow source', 'Random IDs each run', 'Fixed prompt IDs')
FORMATS = {'library': ('prompt_krea2', 'prompt_flux', 'prompt_midjourney', 'tags_sdxl', 'prompt_krea2_style_ref'),
           'rewrite': ('prompt', 'clean_prompt', 'subject_prompt')}


def parse_ids(value):
    ids = [v for v in re.split(r'[\s,]+', value.strip()) if v]
    if not 1 <= len(ids) <= 10 or len(set(ids)) != len(ids) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', v) for v in ids):
        raise ValueError('Enter 1–10 distinct database prompt IDs, separated by commas or newlines')
    return ids


def select(collection, mode, policy, count, ids_text='', *, fetch=None):
    fetch = fetch or get_json
    if collection not in FORMATS or mode not in FORMATS[collection] or policy not in POLICIES[1:]:
        raise ValueError('Choose a catalog, prompt format and random/fixed selection mode')
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError('Choose 1–10 prompts')
    fixed = parse_ids(ids_text) if policy == POLICIES[2] else None
    if fixed is not None and len(fixed) != count:
        raise ValueError('Batch count must match the number of fixed prompt IDs')
    before = publication(fetch(collection+'/meta'))
    if fixed is None:
        page = fetch(collection+'/query?'+urlencode({'sort':'shuffle','seed':secrets.randbits(32),'page':1,'limit':24}))
        if publication(page) != before:
            raise ValueError('Catalog changed during selection; retry before starting generation')
        ids = [row['id'] for row in page.get('items', [])
               if isinstance(row, dict) and (row.get(mode) or row.get('prompt_previews', {}).get(mode))][:count]
        if len(ids) != count:
            raise ValueError('Not enough prompts for this format; choose fewer prompts or another format')
        ids = parse_ids(','.join(ids))
    else:
        ids = fixed
    records = fetch(collection+'/items?'+urlencode({'ids':','.join(ids)})).get('items', [])
    by_id = {row['id']:row for row in records if isinstance(row, dict) and isinstance(row.get('id'),str)}
    selected = []
    for ident in ids:
        row = by_id.get(ident)
        if row is None:
            raise ValueError('Database prompt ID is unavailable: '+ident+'; no substitute was drawn')
        text = row.get(mode)
        if not isinstance(text,str) or not text.strip() or len(text)>16000:
            raise ValueError('The selected prompt ID has no usable text for this format: '+ident)
        selected.append({'id':ident,'collection':collection,'mode':mode,'revision':row.get('revision',''),
                         'text':text,'title':row.get('title',''),'thumbnail':row.get('thumb_file','')})
    if publication(fetch(collection+'/meta')) != before:
        raise ValueError('Catalog changed during selection; no images were started')
    return selected
