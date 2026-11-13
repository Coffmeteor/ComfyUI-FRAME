"""Persist complete expanded batches before ComfyUI starts their image nodes."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import uuid
from . import config


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def merge_graphs(graphs):
    merged = {}
    for index, graph in enumerate(graphs):
        names = {key: f'plan{index}_{key}' for key in graph}
        for key, node in graph.items():
            item = copy.deepcopy(node)
            for field, value in item['inputs'].items():
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] in names:
                    item['inputs'][field] = [names[value[0]], value[1]]
            merged[names[key]] = item
    return merged


def model_files(graphs):
    fields = {'unet_name': 'diffusion_models', 'clip_name': 'text_encoders', 'vae_name': 'vae',
              'lora_name': 'loras', 'model_name': 'upscale_models', 'ckpt_name': 'checkpoints'}
    files = {}
    for graph in graphs:
        for node in graph.values():
            for field, category in fields.items():
                value = node['inputs'].get(field)
                if isinstance(value, str):
                    if node['class_type'] == 'UltralyticsDetectorProvider' and field == 'model_name':
                        category, value = 'ultralytics_bbox', value.removeprefix('bbox/')
                    path = config.resolve(category, value)
                    stat = path.stat()
                    files[category+'|'+value] = [stat.st_size, stat.st_mtime_ns]
    return files


def freeze(snapshot, graphs):
    batch = 'F' + uuid.uuid4().hex
    items = []
    for index, graph in enumerate(graphs, 1):
        code = f'{batch}-{index:02d}'
        for node in graph.values():
            if node['class_type'] == 'FrameSave':
                receipt = json.loads(node['inputs']['receipt'])
                receipt['plan'] = {'batch_id': batch, 'item_id': code, 'index': index, 'count': len(graphs)}
                node['inputs']['receipt'] = json.dumps(receipt, ensure_ascii=False)
                node['inputs']['filename_prefix'] = 'FRAME/plans/' + code
        items.append({'id': code, 'graph': graph})
    record = {'version': 1, 'snapshot': snapshot, 'batch_id': batch, 'items': items,
              'files': model_files(graphs)}
    record['sha256'] = fingerprint(record)
    config.atomic_json(config.directory() / 'plans' / (batch + '.json'), record)
    return {'result': (), 'expand': merge_graphs(graphs), 'ui': {'text': [batch]}}


def replay(code):
    if not re.fullmatch(r'F[0-9a-f]{32}(?:-\d{2})?', code):
        raise ValueError('Use the complete FRAME batch or item code')
    batch = code.split('-')[0]
    path = config.directory() / 'plans' / (batch + '.json')
    if not path.exists():
        raise ValueError('This plan is not on this computer; use the computer that created it')
    # Plans can contain ten full prompts and expanded graphs.
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Saved plan exceeds its size limit')
    record = json.loads(path.read_text())
    digest = record.pop('sha256')
    if fingerprint(record) != digest:
        raise ValueError('Saved plan integrity check failed')
    for key, signature in record['files'].items():
        category, name = key.split('|', 1)
        stat = config.resolve(category, name).stat()
        if [stat.st_size, stat.st_mtime_ns] != signature:
            raise ValueError('A saved plan model changed: ' + name + '. Restore that model before replaying.')
    chosen = [item for item in record['items'] if code == batch or item['id'] == code]
    if not chosen:
        raise ValueError('This item is not in the saved batch')
    return {'result': (), 'expand': merge_graphs([item['graph'] for item in chosen]), 'ui': {'text': [code]}}
