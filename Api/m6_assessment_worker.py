from Api.assessment_configuration import definition_checksum
from Api.m6_assessment_repository import claim, finish
from Api.m6_assessment_service import evaluate


def run_request(request_id, *, connection_factory=None, gateway=None):
    if connection_factory is None:
        from Api.database import get_connection
        connection_factory = get_connection
    with connection_factory() as connection:
        job = claim(connection,request_id); connection.commit()
    if job is None: return
    trace = {}
    try:
        if definition_checksum(job["input_json"]) != job["input_hash"]:
            raise ValueError("CHECKSUM_MISMATCH")
        output,trace=evaluate(job["input_json"],job["mechanism_json"],job["mechanism_hash"],gateway=gateway)
    except Exception as exc:
        output=None;trace=getattr(exc,"ai_trace",{});error=type(exc).__name__
    else:error=None
    with connection_factory() as connection:
        finish(connection,job,output,trace,error);connection.commit()
