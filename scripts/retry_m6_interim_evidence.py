"""Preview or retry one M6 Evidence request from the authorized host shell."""
import argparse
import json
import os
import pwd
from uuid import UUID


def main(argv=None, *, connection_factory=None, gateway=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-origin", required=True)
    parser.add_argument("--assignment-id", type=int, required=True)
    parser.add_argument("--cycle-id", type=UUID, required=True)
    parser.add_argument("--situation-id", type=UUID, required=True)
    parser.add_argument("--handoff-id", type=UUID, required=True)
    parser.add_argument("--request-id", type=UUID, required=True)
    parser.add_argument("--failed-attempt", type=int, required=True)
    parser.add_argument("--apply", action="store_true", help="claim and run a retry; default is read-only")
    args = parser.parse_args(argv)
    if args.assignment_id < 1 or args.failed_attempt < 1:
        parser.error("assignment ID and failed attempt number must be positive")

    from Api.config import settings
    from Api.m6_interim_retry import RetryRefused, RetryTarget, retry

    try:
        if settings.public_app_origin != args.expected_origin:
            raise RetryRefused("M6_RETRY_ORIGIN_MISMATCH")
        if connection_factory is None:
            from Api.database import get_connection
            connection_factory = get_connection
        result = retry(
            RetryTarget(args.assignment_id, args.cycle_id, args.situation_id, args.handoff_id,
                        args.request_id, args.failed_attempt),
            connection_factory=connection_factory, apply=args.apply,
            operator=pwd.getpwuid(os.getuid()).pw_name if args.apply else "", gateway=gateway,
        )
    except RetryRefused as exc:
        print(json.dumps({"error_code": str(exc)}))
        return 2
    except Exception as exc:
        print(json.dumps({"error_code": "M6_RETRY_EXECUTION_ERROR", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(result, default=str))
    return int(args.apply and result["request_status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
