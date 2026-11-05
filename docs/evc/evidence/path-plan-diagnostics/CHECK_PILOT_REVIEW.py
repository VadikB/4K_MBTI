"""Free positive/source-replay and mutation checks. NOT methodological admission."""
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pilot_review_builder', HERE / 'BUILD_PILOT_REVIEW.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
saved = json.loads((HERE / 'pilot-plan-draft-v0.1.json').read_text())
assert builder.build() == saved, 'SOURCE_REPLAY_DIFFERS_FROM_REVIEW_ARTIFACT'
assert builder.markdown(saved).rstrip() + '\n' == (HERE / 'pilot-opportunity-matrix.md').read_text()
builder.validate_review(saved)


def field(name, value):
    return lambda p: p.__setitem__(name, value)


mutations = {
    'runtime_authorization': field('runtime_authorization', 'START_ALLOWED'),
    'methodology_claim': field('methodologist_approval', 'PASS'),
    'product_claim': field('productologist_approval', 'PASS'),
    'full_m2_removed': lambda p: p['full_m2_matrix'].pop(),
    'missing_planned_target': lambda p: p['proposed_target_ids'].pop(),
    'wrong_m2_pair': lambda p: p['observation_occurrences'][0].__setitem__('m2_version', 'wrong'),
    'lost_condition': lambda p: p['observation_occurrences'][0].__setitem__('observation_condition', ''),
    'fictional_actual_opportunity': lambda p: p['observation_occurrences'][0].__setitem__('actual_opportunity', 'PRESENT'),
    'pregenerate_all': lambda p: p['proposed_primary_route'][0].__setitem__('pre_generate', True),
    'restore_60_minute_default': lambda p: p['timing_basis'].__setitem__('time_budget_seconds', 3600),
}
for name, mutate in mutations.items():
    broken = copy.deepcopy(saved)
    mutate(broken['payload'])
    broken['proposal_payload_checksum'] = builder.checksum(broken['payload'])
    try:
        builder.validate_review(broken)
    except AssertionError:
        continue
    raise AssertionError('MUTATION_NOT_REJECTED:' + name)
print(json.dumps({'result': 'PASS_OFFLINE_REVIEW_STRUCTURE_NOT_ADMISSION',
    'source_replay': 'PASS', 'matrix_replay': 'PASS', 'negative_mutations_rejected': len(mutations),
    'proposal_payload_checksum': saved['proposal_payload_checksum'],
    'human_approval': 'PENDING', 'llm_calls': 0, 'database_writes': 0}, indent=2))
