"""Read-only reproduction on the immutable parent, not an oracle of comparability."""
import json
import subprocess
from pathlib import Path


def test_baseline_omits_conditions():
    root=Path(__file__).resolve().parents[5]
    source=subprocess.check_output(['git','show','d5752740770e7241756a3bb42fa94e743da89605:Api/m6_admission.py'],cwd=root,text=True)
    module={'__file__':str(root/'Api/m6_admission.py')}
    exec(compile(source,'baseline/Api/m6_admission.py','exec'),module)
    class Result:
        def __init__(self,row):self.row=row
        def fetchone(self):return self.row
    class Connection:
        def execute(self,query,params):
            if 'observation_requirements_json' in query:
                return Result({'observation_requirements_json':[{'indicator_id':'I1','distinct_as_required':1}]})
            return Result({'snapshot_json':{'base_role':'same-role','case_ref':{'id':params[0]},
                'participant_payload':{'authority':'approve' if params[0]=='as1' else 'recommend',
                    'materials':'full statements' if params[0]=='as1' else 'summary only'}}})
    observations=[{'indicator_id':'I1','assessment_situation_id':f'as{n}','revision_id':f'r{n}',
        'outcome':level,'opportunity':'PRESENT','m2_version':'v1.1','refs':[{'kind':'turn','id':'t'}],'contradictions':[]}
        for n,level in ((1,'L1'),(2,'L3'))]
    _,decisions,_=module['decide'](Connection(),cycle_id='synthetic-cycle',observations=observations)
    assert decisions[0]['numeric_admissible'] is True
    assert all(set(x)=={'assessment_situation_id','base_role','case_ref'} for x in decisions[0]['contexts'])
    print(json.dumps({'baseline':'d5752740770e7241756a3bb42fa94e743da89605',
        'observed':'Substantive conditions are absent from the admission input and decision.',
        'not_claimed':'Different conditions do not automatically mean incomparable.', 'decision':decisions[0]},indent=2))
