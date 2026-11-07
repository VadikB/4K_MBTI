"""Read only the explicit owned stand; no .env or runtime/provider imports."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import psycopg
    from psycopg.rows import dict_row
    from scripts.test_stand import owned

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--revision-id', type=int, required=True)
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    with psycopg.connect(**{**state['connection'], 'dbname': state['database']},
                         row_factory=dict_row) as connection:
        connection.execute('SET TRANSACTION READ ONLY')
        revision = connection.execute('''SELECT id,organization_id,assignment_ref,status,
            source_author,answers_json,recipient_mapping_json
            FROM questionnaire_response_revisions WHERE id=%s''', (args.revision_id,)).fetchone()
        counts = {name: connection.execute('SELECT COUNT(*) AS n FROM ' + table).fetchone()['n']
                  for name, table in {
                      'questionnaire_revisions': 'questionnaire_response_revisions',
                      'assignments': 'organization_assessment_assignments',
                      'profiles': 'assessment_personalized_profiles',
                      'preparation_operations': 'product_cycle_preparation_operations',
                      'cycles': 'm5_cycles',
                      'assessment_situations': 'm5_assessment_situations',
                      'assessment_answers': 'm5_dialogue_turns',
                  }.items()}
        connection.rollback()
    print(json.dumps({'run_id': state['run_id'], 'database': state['database'],
                      'owner_verified': True, 'read_only_rollback': True,
                      'revision': revision, 'counts': counts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
