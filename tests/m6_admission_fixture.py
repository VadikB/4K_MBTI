"""Scripted transport responses only. Never a semantic oracle or approved GC."""
import json


class RecordedAdmissionGateway:
    enabled = True

    def __init__(self, *, individual='ADMITTED', joint='COMPARABLE', fail=None):
        self.individual, self.joint, self.fail = individual, joint, fail
        self.calls = []

    def chat(self, messages, **kwargs):
        value = json.loads(messages[1]['content'])
        self.calls.append(value)
        stage, contexts = value['stage'], value['contexts']
        if self.fail == stage:
            raise TimeoutError('synthetic transport timeout')
        refs = [{'revision_id': c['revision_id'], 'kind': 'as_snapshot', 'id': c['material']['as_id']} for c in contexts]
        finding = {'feature': contexts[0]['criterion']['function'],
                   'analysis': 'Recorded synthetic analysis of the saved conditions; not expert acceptance.',
                   'refs': refs, 'consequence': 'Test the exact decision propagation without changing the saved IA.'}
        if stage == 'individual':
            rid = contexts[0]['revision_id']
            status = self.individual.get(rid, 'ADMITTED') if isinstance(self.individual, dict) else self.individual
            return json.dumps({'revision_id': rid, 'status': status,
                **{k: finding for k in ('normative_basis','opportunity','independence','clarification','contradictions')},
                'rationale': finding['analysis'], 'limitations': ['Synthetic transport fixture, not GC']})
        return json.dumps({'considered_revision_ids':[c['revision_id'] for c in contexts], 'status':self.joint,
            **{k:finding for k in ('normative_meaning','conditions','contradictions')},
            'rationale':finding['analysis'], 'limitations':['Synthetic transport fixture, not GC']})
