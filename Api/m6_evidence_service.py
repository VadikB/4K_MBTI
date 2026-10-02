from __future__ import annotations
import json

from Api.assessment_configuration import definition_checksum
from Api.m6_contracts import validate_analysis
from Api.m6_package import verify_mechanism
from Api.m5_rule_engine import _gateway_for, _call_with_trace


def evaluate(material, mechanism, mechanism_hash, *, gateway=None):
    verify_mechanism(mechanism,mechanism_hash)
    encoded=json.dumps(material,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode()) > mechanism['max_input_bytes']:
        raise ValueError('M6_CONTEXT_LIMIT_EXCEEDED')
    operation=mechanism['operation']
    resolved=_gateway_for(operation,gateway)
    if not resolved.enabled: raise ValueError('M6_GATEWAY_UNAVAILABLE')
    messages=[{'role':'system','content':mechanism['prompt']+'\nJSON Schema:\n'+json.dumps(mechanism['schema'],ensure_ascii=False)},
              {'role':'user','content':encoded}]
    raw,trace=_call_with_trace(resolved,messages,operation=operation,routing_key='m6:'+definition_checksum(material))
    try:
        if trace['identity_status']!='sent_matches_snapshot': raise ValueError('M6_AI_IDENTITY_MISMATCH')
        output=validate_analysis(json.loads(raw),material)
    except Exception as exc:
        exc.ai_trace=trace
        raise
    return output,trace
