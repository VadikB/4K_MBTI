"""Offline mutation regression; no database connections or file modifications."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent
module = runpy.run_path(str(ROOT / 'COMPARE.py'))
compare, checksum = module['compare'], module['checksum']
expected = json.loads((ROOT / 'expected-schema.json').read_bytes())
actual = json.loads((ROOT / 'working-schema.json').read_bytes())
assert compare(expected, actual)['result'] == 'EXACT_SCOPED_SCHEMA_MATCH'
mutations = [
    lambda m: m['columns'].pop(),
    lambda m: m['columns'][0].update(type='SYNTHETIC_WRONG_TYPE'),
    lambda m: m['columns'][0].update(not_null=not m['columns'][0]['not_null']),
    lambda m: m['constraints'].pop(),
    lambda m: m['constraints'][0].update(validated=False),
    lambda m: m['indexes'].pop(),
    lambda m: m['indexes'][0].update(valid=not m['indexes'][0]['valid']),
    lambda m: m['triggers'].pop(),
    lambda m: m['triggers'][0].update(enabled='D'),
    lambda m: m['triggers'][0].update(function_definition_md5='0' * 32),
    lambda m: m['columns'].append({**m['columns'][0], 'name': 'synthetic_extra_column'}),
]
for mutate in mutations:
    variant = deepcopy(actual)
    mutate(variant['metadata'])
    variant['metadata_checksum'] = checksum(variant['metadata'])
    assert compare(expected, variant)['result'] == 'SCHEMA_DIFFERENCES_REQUIRE_REVIEW'
for field, value in [('metadata_checksum', '0' * 64), ('transaction_read_only', False),
                     ('schema_or_data_writes', True), ('business_rows_read', True)]:
    variant = deepcopy(actual)
    variant[field] = value
    try:
        compare(expected, variant)
    except AssertionError:
        pass
    else:
        raise AssertionError('unsafe record accepted')
tree = ast.parse((ROOT / 'READ_SCHEMA.py').read_text())
queries = [node.args[0].value for node in ast.walk(tree)
           if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
           and node.func.attr == 'execute' and isinstance(node.args[0], ast.Constant)]
assert len(queries) == 7 and all(q.lstrip().split()[0].upper() in {'SELECT', 'SHOW'} for q in queries)
assert not any(isinstance(node, ast.ImportFrom) and (node.module or '').startswith('Api') for node in ast.walk(tree))
print(json.dumps({'result': 'PASS_OFFLINE_SCHEMA_REGRESSION', 'positive_comparison': 1,
                  'negative_schema_mutations': len(mutations), 'invalid_record_rejections': 4,
                  'read_only_sql_literals_checked': len(queries), 'database_calls': 0}))
