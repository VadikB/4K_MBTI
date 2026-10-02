from Api.m6_admission import decide, load_rules


class Result:
    def __init__(self, row): self.row=row
    def fetchone(self): return self.row


class Connection:
    def execute(self, query, params):
        if "observation_requirements_json" in query:
            return Result({"observation_requirements_json":[{"indicator_id":"I1","distinct_as_required":2}]})
        as_id=params[0]
        return Result({"snapshot_json":{"base_role":"role","case_ref":{"id":as_id}}})


def observation(as_id, revision, outcome, contradictions=None):
    return {"indicator_id":"I1","assessment_situation_id":as_id,"revision_id":revision,
            "m2_version":"v1.1","outcome":outcome,"opportunity":"PRESENT",
            "refs":[{"kind":"turn","id":"t","meaning":"basis"}],
            "contradictions":contradictions or []}


def test_versioned_admission_checks_full_set_and_conditions():
    mechanism, decisions, limitations=decide(Connection(),cycle_id="cycle",
        observations=[observation("as1","r1","L1"),observation("as2","r2","L3")])
    assert mechanism=="m6_admission/1.0.0"
    assert decisions[0]["numeric_admissible"] is True
    assert decisions[0]["included_revision_ids"]==["r1","r2"]
    assert limitations and load_rules()["status"]=="draft"


def test_reported_contradiction_blocks_numeric_but_preserves_interpretation():
    _, decisions, _=decide(Connection(),cycle_id="cycle",
        observations=[observation("as1","r1","L1"),observation("as2","r2","L3",["conditions differ"])])
    assert decisions[0]["numeric_admissible"] is False
    assert decisions[0]["interpretation_admissible"] is True
    assert "no_reported_contradiction" in decisions[0]["reason_code"]
