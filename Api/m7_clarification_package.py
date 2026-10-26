from __future__ import annotations
import hashlib,json
from pathlib import Path
from Api.m5_case_runtime import checksum
from Api.llm.provider_contract import load_provider_contract
from Api.m7_clarification_contracts import ClarificationQuestion

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'assessment_definitions/prompts/m7_assessment_clarification/v1'

def load_mechanism(package_path:Path=PACKAGE,source_set_path:Path|None=None,provider_contract_path:Path|None=None):
    manifest=json.loads((package_path/'manifest.json').read_bytes());prompt=(package_path/'prompt.md').read_bytes()
    expected=(1,'m7_assessment_clarification','1.0.0','draft','m7_assessment_clarification_qa','PM-04')
    if tuple(manifest.get(k) for k in ('schema_version','id','version','status','scope','owner'))!=expected:raise ValueError('M7_CLARIFICATION_PACKAGE_INVALID')
    if manifest['artifacts']!=[{'name':'prompt.md','sha256':hashlib.sha256(prompt).hexdigest()}]:raise ValueError('CHECKSUM_MISMATCH')
    source=manifest['source'];entries=json.loads((source_set_path or ROOT/'docs/methodology/source-sets/2026-10-01/manifest.json').read_bytes())['entries']
    registered=next((x for x in entries if x['id']==source['id'] and x['version']==source['version']),None)
    if not registered or registered['sha256']!=source['sha256'] or hashlib.sha256((ROOT/registered['path']).read_bytes()).hexdigest()!=source['sha256']:raise ValueError('SOURCE_UNRESOLVED')
    config=manifest['execution'];provider=load_provider_contract(provider_contract_path)
    value={'ref':'m7_assessment_clarification/1.0.0','prompt':prompt.decode(),'schema':ClarificationQuestion.model_json_schema(),
        'operation':{'provider':provider['provider'],'endpoint':provider['endpoint'],'model':provider['model'],
        'parameters':{k:config[k] for k in ('temperature','timeout_seconds','max_tokens')},
        'prompt_ref':{'id':manifest['id'],'version':manifest['version'],'checksum':hashlib.sha256(prompt).hexdigest(),
                      'path':package_path.relative_to(ROOT).as_posix()},'response_format':'json_object','thinking':provider['thinking'],
        'provider_contract':{k:provider[k] for k in ('version','checksum','provider','endpoint','model','thinking','supported_response_formats')}},
        'max_input_bytes':config['max_input_bytes'],'decision':manifest['decision'],'validation':manifest['validation']}
    value['snapshot_checksum']=checksum(value);return value
