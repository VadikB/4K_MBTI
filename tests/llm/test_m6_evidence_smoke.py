"""Синтетический transport smoke; не экспертный GC и не QA оценивания."""
import os
import json
import pytest
from Api.m6_input_resolver import M2, load_criteria
from Api.m6_package import load_mechanism
from Api.m6_evidence_service import evaluate
from Api.assessment_configuration import definition_checksum

pytestmark=pytest.mark.llm


def test_m6_real_provider_synthetic_smoke():
    if os.getenv('RUN_M6_PROVIDER_SMOKE')!='1':
        pytest.skip('explicit RUN_M6_PROVIDER_SMOKE=1 and separately authorized provider budget required')
    manifest=json.loads((M2/'manifest.json').read_text())
    target={'indicator_id':'K1.I01','m2_version':'v1.1','component_id':'K1.C01','skill_id':'K1.1'}
    criteria=load_criteria({'methodology_refs':[{'checksum':manifest['artifact']['sha256']}],'indicator_targets':[target]})
    material={'as_id':'synthetic-smoke','dialogue_id':'synthetic-smoke-dialogue','mode':'interim',
              'indicator_targets':[target],'criteria':criteria,'turns':[], 'events':[], 'materials':[],
              'context':{},'initial_presentation':{'note':'Синтетический транспортный тест без пользовательских ответов.'}}
    mechanism=load_mechanism('m6_evidence/1.0.0')
    output,trace=evaluate(material,mechanism,definition_checksum(mechanism))
    assert output['fragments']==[] and output['evidence']==[]
    assert trace['identity_status']=='sent_matches_snapshot'
    assert trace['provider'] and trace['response']['checksum']
