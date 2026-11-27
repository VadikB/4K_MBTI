"""Cycle-manifest-bound adapter for saved C-45 inputs."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import UUID

from Api import m5_battery_scenario
from Api.assessment_configuration import definition_checksum
from Api.cycle_execution_manifest import resolve_cycle_dependency
from Api.m5_case_runtime import checksum
from Api.m6_input_resolver import normalize as normalize_v1

DOCUMENT_EVENTS = {'material_disclosed', 'mandatory_update'}


def load_criteria(snapshot: dict, directory: Path, sources_path: Path) -> list[dict]:
    data = (directory / "methodology.json").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if digest != manifest["artifact"]["sha256"] or not any(
        item["checksum"] == digest for item in snapshot["methodology_refs"]
    ):
        raise ValueError("CHECKSUM_MISMATCH")
    sources = json.loads(sources_path.read_bytes())["entries"]
    criteria = {}
    for competency in json.loads(data)["competencies"]:
        source = next(item for item in sources if item["id"] == f"M2.{competency['id']}.matrix")
        if not any(item["sha256"] == source["sha256"] for item in manifest["sources"]):
            raise ValueError("SOURCE_UNRESOLVED")
        for skill in competency["skills"]:
            for component in skill["components"]:
                for indicator in component["indicators"]:
                    criteria[indicator["id"]] = {
                        **indicator,
                        "skill_id": skill["id"],
                        "component_id": component["id"],
                        "m2_version": "v" + source["version"],
                        "source_ref": source,
                        "package_sha256": digest,
                    }
    result = []
    for target in snapshot["indicator_targets"]:
        criterion = criteria.get(target["indicator_id"])
        if not criterion or any(
            criterion[key] != target[key] for key in ("m2_version", "component_id", "skill_id")
        ):
            raise ValueError("TARGET_SET_MISMATCH")
        if not all(criterion.get(key) for key in ("function", "product", "evidence_pattern", "boundary")) \
                or set(criterion["levels"]) != {"L0", "L1", "L2", "L3"}:
            raise ValueError("SOURCE_UNRESOLVED")
        result.append(criterion)
    return result


def _unresolved(field: str) -> ValueError:
    return ValueError(f'SOURCE_UNRESOLVED:{field}')


def _battery_delivery(design: dict, event: dict, turns: dict, path: str) -> dict:
    material_id = event['material_id']
    content = design['concrete_materials'].get(material_id)
    if content is None:
        raise _unresolved(f'{path}.material_id')
    payload, cause = event['payload'], event['cause']
    rule = next((item for item in design['events'] if item['id'] == cause.get('rule_id')), None)
    if (not rule or rule['kind'] != 'delivery' or rule['delivery_id'] != material_id
            or payload.get('scenario_event_id') != rule['id']):
        raise _unresolved(f'{path}.payload.scenario_event_id')
    trigger = turns.get(cause.get('turn_id'))
    if not trigger or trigger['speaker_type'] != 'assessee' or trigger['sequence_no'] >= event['sequence_no']:
        raise _unresolved(f'{path}.cause.turn_id')
    if rule['audience'] != 'assessee' or payload.get('recipient_ids') != ['assessee']:
        raise _unresolved(f'{path}.payload.recipient_ids')
    if payload.get('speaker_id') != rule['speaker_ids'][0]:
        raise _unresolved(f'{path}.payload.speaker_id')
    if payload.get('author_id') != rule['author_id']:
        raise _unresolved(f'{path}.payload.author_id')
    if payload.get('content') != m5_battery_scenario.delivery_content(material_id, content):
        raise _unresolved(f'{path}.payload.content')
    return content


def _battery_reply(event: dict, turns: dict, design: dict, runtime_state: dict, path: str) -> None:
    payload, cause = event['payload'], event['cause']
    character = turns.get(cause.get('character_turn_id'))
    trigger = turns.get(cause.get('trigger_turn_id'))
    if (not character or character['speaker_type'] != 'character'
            or character['speaker_id'] != payload.get('speaker_id')
            or character['content'] != payload.get('response') or character['sequence_no'] >= event['sequence_no']):
        raise _unresolved(f'{path}.cause.character_turn_id')
    if not trigger or trigger['speaker_type'] != 'assessee' or trigger['sequence_no'] >= character['sequence_no']:
        raise _unresolved(f'{path}.cause.trigger_turn_id')
    recipients = payload.get('recipient_ids')
    allowed = {'assessee', *(design['roles'] or (m5_battery_scenario.FACILITATOR,))}
    if (not isinstance(recipients, list) or 'assessee' not in recipients
            or any(not isinstance(item, str) or item not in allowed for item in recipients)
            or len(recipients) != len(set(recipients))):
        raise _unresolved(f'{path}.payload.recipient_ids')
    if 'battery_audiences' in runtime_state:
        by_turn = runtime_state['battery_audiences']
        recorded = by_turn.get(character['turn_id']) if isinstance(by_turn, dict) else None
        if (not isinstance(recorded, list) or len(recorded) != len(recipients)
                or any(recipient not in recorded for recipient in recipients)):
            raise _unresolved(f'{path}.payload.recipient_ids')


def _presented_materials(envelope: dict, execution: dict, battery: dict) -> list[dict]:
    documents = {item['material_id']: item for item in execution['materials']}
    turns = {turn['turn_id']: turn for turn in envelope['dialogue']['turns']}
    events = {event['event_id']: (index, event) for index, event in enumerate(envelope['dialogue']['events'])}
    reply_labels = set()
    for event_id, (index, event) in events.items():
        if event['event_type'] == 'character_response' and event['material_id'] not in documents:
            path = f'dialogue.events.{index}'
            if not m5_battery_scenario.is_character_response_label(
                    battery, event['material_id'], event['payload'].get('speaker_id')):
                raise _unresolved(f'{path}.material_id')
            _battery_reply(event, turns, battery, envelope.get('runtime_state') or {}, path)
            reply_labels.add(event_id)

    materials = []
    seen_events = set()
    for index, presented in enumerate(envelope['presented_materials']):
        ref = f'presented_materials.{index}'
        event_id = presented.get('event_id')
        if not isinstance(event_id, str) or event_id not in events or event_id in seen_events:
            raise _unresolved(f'{ref}.event_id')
        event_index, event = events[event_id]
        event_type, material_id = event['event_type'], event['material_id']
        if event_type not in DOCUMENT_EVENTS and event_type != 'character_response':
            raise _unresolved(f'{ref}.event_id')
        for field, actual in (('material_id', material_id), ('sequence_no', event['sequence_no']),
                              ('event_type', event_type), ('available_at', event['created_at'])):
            if presented.get(field) != actual:
                raise _unresolved(f'{ref}.{field}')
        seen_events.add(event_id)
        if event_id in reply_labels:
            # Historical battery C-45 included reply labels. The dialogue still owns the reply.
            continue

        path = f'dialogue.events.{event_index}'
        payload = event['payload']
        if payload.get('recipient', 'assessee') != 'assessee' or (
                event_type in DOCUMENT_EVENTS and payload.get('recipient') != 'assessee'):
            raise _unresolved(f'{path}.payload.recipient')
        if event_type == 'mandatory_update':
            content = _battery_delivery(battery, event, turns, path)
        else:
            if material_id not in documents:
                raise _unresolved(f'{ref}.material_id')
            content = documents[material_id].get('participant_payload')
            if event_type in DOCUMENT_EVENTS:
                if payload.get('recipient_ids', ['assessee']) != ['assessee']:
                    raise _unresolved(f'{path}.payload.recipient_ids')
                if payload.get('content') != content:
                    raise _unresolved(f'{path}.payload.content')
        materials.append({'material_id': material_id, 'available_sequence': event['sequence_no'],
                          'content': deepcopy(content), 'event_id': event_id})

    if any(event['event_type'] in DOCUMENT_EVENTS and event_id not in seen_events
                       for event_id, (_, event) in events.items()):
        raise _unresolved('presented_materials.event_id')
    return materials


def normalize(handoff: dict, row: dict, cycle: dict, session: dict, criteria: list[dict]) -> dict:
    execution = row['execution_payload_json']
    battery = m5_battery_scenario.scenario_contract(execution)
    if not battery:
        return normalize_v1(handoff, row, cycle, session, criteria)

    envelope = handoff['envelope_json']
    digest = handoff['envelope_checksum']
    if checksum(envelope) != digest:
        raise ValueError('CHECKSUM_MISMATCH')

    # Reuse the frozen v1 boundary and ownership checks on the common fields.
    # Resolve the document list separately and bind the result to the original C-45.
    dialogue_only = {**envelope, 'presented_materials': []}
    material = normalize_v1(
        {**handoff, 'envelope_json': dialogue_only, 'envelope_checksum': checksum(dialogue_only)},
        row, cycle, session, criteria,
    )
    material['materials'] = _presented_materials(envelope, execution, battery)
    material['handoff_ref']['checksum'] = digest
    revision = material.pop('material_revision')
    revision['material_sha256'] = definition_checksum(material)
    material['material_revision'] = revision
    return material


def resolve(connection, handoff_id: str) -> tuple[int, dict]:
    handoff = connection.execute(
        "SELECT * FROM m5_c45_handoffs WHERE handoff_id=%s", (UUID(handoff_id),)
    ).fetchone()
    if not handoff:
        raise ValueError("M6_HANDOFF_NOT_FOUND")
    row = connection.execute(
        "SELECT * FROM m5_assessment_situations WHERE id=%s", (handoff["assessment_situation_db_id"],)
    ).fetchone()
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE id=%s", (row["cycle_db_id"],)).fetchone()
    session = connection.execute(
        "SELECT * FROM m5_cycle_sessions WHERE id=%s", (row["session_db_id"],)
    ).fetchone()
    if not cycle or not session:
        raise ValueError("M6_OWNER_MISMATCH")
    cycle = dict(cycle)
    methodology = resolve_cycle_dependency(cycle, "m2_methodology")
    source_set = resolve_cycle_dependency(cycle, "source_set")
    criteria = load_criteria(row["snapshot_json"], methodology, source_set / "manifest.json")
    return row["id"], normalize(dict(handoff), dict(row), cycle, dict(session), criteria)
