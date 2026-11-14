"""SYNTHETIC legacy source boundary for E10.2 component fixtures only.

The old stand deliberately seeds profiles without managed assignments. It cannot
prove current waiting/admission. Keep actual legacy validation/negative states;
only hide the empty managed binding relation during its readiness read. Modern
REMAIN04 and PATH fixtures never activate this substitution.
"""
from functools import wraps
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from Api import acquaintance

_actual_readiness = acquaintance.early_readiness


def legacy_readiness(connection, *, user_id):
    state_path = os.getenv('STAND_STATE')
    if os.getenv('AGENT4K_ISOLATED_STAND') != '1' or not state_path:
        raise ValueError('LEGACY_COMPONENT_OWNED_STAND_REQUIRED')
    state = json.loads(Path(state_path).read_bytes())
    if (state.get('provider_mode', 'disabled') != 'disabled' or state.get('gateway') != 1
            or state.get('path29_full_path') or state.get('path29_program_source') is not None
            or not str(state.get('database', '')).startswith('product4k_pytest_')
            or state.get('database') != os.getenv('DB_NAME')
            or not str(state.get('owner_marker', '')).startswith('stand-10.2:')
            or state.get('owner_marker') != os.getenv('AGENT4K_STAND_MARKER')):
        raise ValueError('LEGACY_COMPONENT_DISABLED_PROVIDER_OWNED_STAND_REQUIRED')
    if connection.execute('SELECT 1 FROM organization_assessment_source_bindings LIMIT 1').fetchone():
        return _actual_readiness(connection, user_id=user_id)

    class LegacyConnection:
        def execute(self, sql, params=()):
            if "to_regclass(current_schema()||'.organization_assessment_source_bindings')" in sql:
                return SimpleNamespace(fetchone=lambda: {'relation': None})
            return connection.execute(sql, params)
    return _actual_readiness(LegacyConnection(), user_id=user_id)


def legacy_component_scope(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with patch.object(acquaintance, 'early_readiness', legacy_readiness):
            return function(*args, **kwargs)
    return wrapped
