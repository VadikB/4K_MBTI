from __future__ import annotations

import hashlib
import json
from pathlib import Path

from Api.config import settings
from Api.assessment_configuration import definition_checksum
from Api.m6_contracts import EvidenceAnalysis

PACKAGE = Path(__file__).resolve().parents[1] / 'assessment_definitions/prompts/m6_evidence/v1'


def load_mechanism(ref: str, directory: Path = PACKAGE) -> dict:
    if ref != 'm6_evidence/1.0.0':
        raise ValueError('M6_MECHANISM_UNSUPPORTED')
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    prompt = (directory / 'prompt.md').read_bytes()
    if (manifest['schema_version'], manifest['id'], manifest['version'], manifest['status'], manifest['scope']) != (1, 'm6_evidence', '1.0.0', 'draft', 'm6_evidence_qa'):
        raise ValueError('M6_PACKAGE_INVALID')
    if manifest['artifacts'] != [{'name': 'prompt.md', 'sha256': hashlib.sha256(prompt).hexdigest()}]:
        raise ValueError('CHECKSUM_MISMATCH')
    if (manifest.get('input_contract'), manifest.get('output_contract'), manifest.get('owner')) != ('M6.EvidenceInput/1', 'M6.EvidenceAnalysis/1', 'PM-05'):
        raise ValueError('M6_PACKAGE_INVALID')
    source = manifest.get('source', {})
    if not source.get('id') or not source.get('version') or len(source.get('sha256', '')) != 64:
        raise ValueError('SOURCE_UNRESOLVED')
    root = Path(__file__).resolve().parents[1]
    entries = json.loads((root / 'docs/methodology/source-sets/2026-10-01/manifest.json').read_bytes())['entries']
    registered = next((x for x in entries if x['id'] == source['id'] and x['version'] == source['version']), None)
    if not registered or registered['sha256'] != source['sha256'] or hashlib.sha256((root / registered['path']).read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('SOURCE_UNRESOLVED')
    config = manifest['execution']
    for key in ('timeout_seconds', 'max_tokens', 'max_input_bytes', 'lease_seconds'):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError('M6_PACKAGE_INVALID')
    if config['lease_seconds'] <= config['timeout_seconds']:
        raise ValueError('M6_PACKAGE_INVALID')
    return {'ref': ref, 'manifest': manifest, 'prompt': prompt.decode(),
            'schema': EvidenceAnalysis.model_json_schema(), 'handler': 'm6-evidence/1',
            'operation': {'provider': 'deepseek', 'endpoint': str(settings.deepseek_base_url).rstrip('/') + '/chat/completions',
                          'model': str(settings.deepseek_model),
                          'parameters': {k: config[k] for k in ('temperature', 'timeout_seconds', 'max_tokens')},
                          'prompt_ref': {'id': manifest['id'], 'version': manifest['version'], 'checksum': hashlib.sha256(prompt).hexdigest()},
                          'response_format': 'json_object'},
            'max_input_bytes': config['max_input_bytes'], 'lease_seconds': config['lease_seconds']}


def verify_mechanism(value: dict, expected_hash: str) -> None:
    if definition_checksum(value) != expected_hash or value['handler'] != 'm6-evidence/1':
        raise ValueError('CHECKSUM_MISMATCH')
    if hashlib.sha256(value['prompt'].encode()).hexdigest() != value['operation']['prompt_ref']['checksum']:
        raise ValueError('CHECKSUM_MISMATCH')
    if value['schema'] != EvidenceAnalysis.model_json_schema():
        raise ValueError('M6_SCHEMA_UNSUPPORTED')
