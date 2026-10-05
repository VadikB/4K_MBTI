"""Deterministic AI gateway for isolated browser acceptance only."""
from __future__ import annotations

import json
import os
from pathlib import Path


def acceptance_fixture():
    if not enabled() or os.getenv('AGENT4K_BROWSER_SCENARIO') != 'acceptance-v1':
        return None
    return json.loads((Path(__file__).resolve().parents[1] / 'tests/browser/fixtures/v1.json').read_text())


def _acceptance_output(value, fixture):
    if 'uncertainties' in value:
        return {'schema_version':1,'admissible':True,'text':fixture['character_question'] if 'K2.I10' in value['indicator_ids'] else fixture['question'],
                'purpose':'clarify_meaning','indicator_ids':value['indicator_ids'],
                'resolving_information':['Meaning of the already submitted answer'],'refusal_reason':None}
    material=value.get('material',value)
    turns=[x for x in material['turns'] if x.get('speaker_type')=='assessee']
    # Exact fixture input only; never attribute a character's reply or arbitrary text to the participant.
    turn=next((x for x in turns if x['content'] in (fixture['answer'],fixture['clarification_answer'])),None)
    actions=fixture['actions'] if turn else {}
    if 'evidence_analysis' not in value:
        result={'schema_version':1,'fragments':[],'signals':[],'evidence':[],'attribution_notes':[],
                'bundles':[]}
        for criterion in material['criteria']:
            indicator=criterion['id'];eid='e-'+indicator;fid='f-'+indicator;sid='s-'+indicator
            action=actions.get(indicator)
            if action:
                result['fragments'].append({'id':fid,'turn_id':turn['turn_id'],'start':0,'end':len(turn['content']),'quote':turn['content']})
                result['signals'].append({'id':sid,'fragment_id':fid,'observation':action,'form_description':'direct synthetic response','context_refs':[]})
                result['evidence'].append({'id':eid,'indicator_id':indicator,'m2_version':criterion['m2_version'],'type':'Simple',
                    'interpretation':action,'bs_ids':[sid],'fragment_ids':[fid],
                    'attribution':{k:criterion[v] for k,v in {'function':'function','product':'product','evidence_pattern':'evidence_pattern','boundaries':'boundary'}.items()},
                    'context_refs':[],'limitations':[fixture['limitation']],'ordered_turn_ids':[turn['turn_id']]})
            result['bundles'].append({'indicator_id':indicator,'evidence_ids':[eid] if action else [],
                'opportunity_basis':'Synthetic case and actual submitted material','context_refs':[],
                'limitations':[fixture['limitation']],'contradictions':[]})
        return result
    interim=value['mode']=='interim'
    clarified=any(x.get('speaker_type')=='assessment' for x in material['turns'])
    targets=[]
    for criterion in material['criteria']:
        indicator=criterion['id'];action=actions.get(indicator)
        uncertainty={'missing_or_conflicting_feature':'Meaning needs confirmation' if interim else 'No supported action',
            'impact':'Limited material','clarification_needed':'Clarify existing statement','resolution_information':[],
            'requires_new_independent_action':False if interim and not clarified else True}
        targets.append({'indicator_id':indicator,'m2_version':criterion['m2_version'],
            'status':'INTERIM' if interim else 'ASSESSED','outcome':None if interim else ('L1' if action else 'INSUFFICIENT_EVIDENCE'),
            'descriptor_basis':criterion['levels']['L1'] if action and not interim else None,
            'rationale':action or 'No supported action in this synthetic material',
            'refs':[{'kind':'evidence','id':'e-'+indicator,'meaning':action}] if action else [],
            'opportunity':'PRESENT','opportunity_basis':'Synthetic case presented',
            'uncertainty':(uncertainty if not clarified else None) if interim else (None if action else uncertainty),
            'contradictions':[],'clarification_history':[],'stop_reason':None,
            'confidence':{'confirmed_features':[action] if action else [],'alternatives_considered':[],
                          'limitations':[fixture['limitation']],'reliability_protocol_ref':None}})
    return {'schema_version':1,'mode':value['mode'],'targets':targets}


class BrowserAcceptanceGateway:
    enabled = True

    def chat(self, messages, **_kwargs):
        value = json.loads(messages[1]["content"])
        fixture=acceptance_fixture()
        if fixture:
            return json.dumps(_acceptance_output(value,fixture),ensure_ascii=False)
        if "evidence_analysis" in value:
            turn = value["material"]["turns"][-1]
            return json.dumps({
                "schema_version": 1, "mode": value["mode"],
                "targets": [{
                    "indicator_id": target["indicator_id"], "m2_version": target["m2_version"],
                    "status": "ASSESSED", "outcome": "L0",
                    "descriptor_basis": "Isolated browser acceptance fixture",
                    "rationale": "A persisted assessee turn is present in the closed material",
                    "refs": [{"kind": "turn", "id": turn["turn_id"], "meaning": "persisted assessee action"}],
                    "opportunity": "PRESENT", "opportunity_basis": "The case requested an answer",
                    "uncertainty": None, "contradictions": [], "clarification_history": [], "stop_reason": None,
                    "confidence": {"confirmed_features": ["persisted closed turn"], "alternatives_considered": [],
                                   "limitations": ["test gateway; not normative GC"], "reliability_protocol_ref": None},
                } for target in value["material"]["indicator_targets"]],
            }, ensure_ascii=False)
        return json.dumps({
            "schema_version": 1, "fragments": [], "signals": [], "evidence": [], "attribution_notes": [],
            "bundles": [{
                "indicator_id": target["indicator_id"], "evidence_ids": [],
                "opportunity_basis": "Persisted closed browser acceptance dialogue",
                "context_refs": [], "limitations": ["test gateway"], "contradictions": [],
            } for target in value["indicator_targets"]],
        }, ensure_ascii=False)


def enabled() -> bool:
    import os
    if os.getenv("AGENT4K_BROWSER_TEST_GATEWAY") != "1":
        return False
    if (os.getenv("AGENT4K_ISOLATED_STAND") != "1"
            or not os.getenv("DB_NAME", "").startswith("product4k_pytest_")
            or os.getenv("DB_HOST") not in ("127.0.0.1", "localhost")
            or not os.getenv("AGENT4K_STAND_MARKER", "").startswith("stand-10.2:")):
        raise ValueError("TEST_GATEWAY_REQUIRES_OWNED_ISOLATED_STAND")
    return True
