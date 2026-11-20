export const shortProgramReport = {
  id: 'r1', cycle_id: 'c1', owner_user_id: 18, revision_no: 1,
  created_at: '2026-11-15T12:00:00Z', program_name: 'Короткая программа',
  c67: {
    skills: [{ skill_id: 'S1', skill_name: 'Взаимодействие', competency_id: 'K1',
      competency_name: 'Коммуникация', outcome: 'full_score',
      score: { value: 0, numerator: 0, denominator: 1 },
      presentation: { label: 'Полный показатель по навыку', reasons: [
        { code: 'plan_scope', message: 'Программа охватывала только часть состава этого навыка.' }] } }],
    competencies: [{ competency_id: 'K1', competency_name: 'Коммуникация', skill_ids: ['S1'] }],
    coverage: {}, reliability: { status: 'not_verified' }, limitations: [],
    descriptive: { status: 'historical', summary: [], claims: [] },
    partial_result: { plan_completed: true, is_incomplete: false, progress: { completed: 3, planned: 3 },
      messages: { title: 'Оценка завершена' }, limitation_reasons: [
        { code: 'plan_scope', message: 'Принятый план покрывал часть целевой области.' }] },
  },
};
