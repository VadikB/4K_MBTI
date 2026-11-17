from Api.m8_report_corrections import diff


def test_correction_diff_uses_stable_skill_id_and_only_changed_public_fields():
    old = {'skills': [
        {'skill_id': 'S2', 'skill_name': 'Второй', 'score': {'value': 2}, 'outcome': 'full_score'},
        {'skill_id': 'S1', 'skill_name': 'Первый', 'score': {'value': 1}, 'outcome': 'full_score'},
    ], 'descriptive': {'summary': ['Было'], 'claims': [
        {'skill_ids': ['S1'], 'text': 'Старое наблюдение', 'basis_refs': ['internal-old']},
    ]}, 'provenance': {'incident': 'never-public'}}
    new = {'skills': [
        {'skill_id': 'S1', 'skill_name': 'Первый', 'score': {'value': 3}, 'outcome': 'full_score'},
        {'skill_id': 'S2', 'skill_name': 'Второй', 'score': {'value': 2}, 'outcome': 'full_score'},
    ], 'descriptive': {'summary': ['Стало'], 'claims': [
        {'skill_ids': ['S1'], 'text': 'Новое наблюдение', 'basis_refs': ['internal-new']},
    ]}, 'provenance': {'incident': 'never-public'}}
    changes = diff(old, new)
    assert [(item['skill_id'], item['field']) for item in changes] == [
        ('S1', 'score'), (None, 'summary'), ('S1', 'explanation')]
    assert 'internal' not in str(changes)
    assert 'incident' not in str(changes)


def test_whitespace_only_change_is_not_a_correction():
    before = {'skills': [], 'descriptive': {'summary': ['Вывод по  навыку.'], 'claims': []}}
    after = {'skills': [], 'descriptive': {'summary': ['  Вывод по навыку. '], 'claims': []}}
    assert diff(before, after) == []
