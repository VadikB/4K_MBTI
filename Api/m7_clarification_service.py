from __future__ import annotations
import json,re
from Api.m5_rule_engine import _call_with_trace,_gateway_for
from Api.m7_clarification_contracts import ClarificationQuestion

def generate(value:dict,mechanism:dict,*,gateway=None):
    encoded=json.dumps(value,ensure_ascii=False)
    if len(encoded.encode())>mechanism['max_input_bytes']:raise ValueError('M7_CLARIFICATION_CONTEXT_LIMIT')
    resolved=_gateway_for(mechanism['operation'],gateway)
    if not resolved.enabled:raise ValueError('M7_CLARIFICATION_GATEWAY_UNAVAILABLE')
    raw,trace=_call_with_trace(resolved,[{'role':'system','content':mechanism['prompt']+'\nJSON Schema:\n'+json.dumps(mechanism['schema'],ensure_ascii=False)},
        {'role':'user','content':encoded}],operation=mechanism['operation'],routing_key='m7-clarification:'+value['c54_revision_id'])
    if trace['identity_status']!='sent_matches_snapshot':raise ValueError('M7_AI_IDENTITY_MISMATCH')
    output=ClarificationQuestion.model_validate(json.loads(raw)).model_dump()
    allowed=set(value['indicator_ids'])
    if not set(output['indicator_ids'])<=allowed:raise ValueError('TARGET_SET_MISMATCH')
    if output['admissible']:
        forbidden=re.compile('|'.join(f'(?:{x})' for x in mechanism['validation']['forbidden_patterns']),re.I)
        if not output['text'] or not output['purpose'] or forbidden.search(output['text']) or output['text'].count('?')!=1:raise ValueError('M7_QUESTION_NOT_NEUTRAL')
        if len(output['text'])>mechanism['validation']['max_question_chars']:raise ValueError('M7_QUESTION_TOO_LONG')
    elif not output['refusal_reason']:raise ValueError('M7_REFUSAL_REASON_REQUIRED')
    return output,trace
