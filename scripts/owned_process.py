"""Bounded POSIX process-group ownership for isolated test runners."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time


def _members(pgid):
    output = subprocess.check_output(['ps', '-axo', 'pid=,pgid=,stat=,lstart='], text=True)
    result = {}
    for line in output.splitlines():
        fields = line.split(None, 3)
        if len(fields) == 4 and int(fields[1]) == pgid and not fields[2].startswith('Z'):
            result[int(fields[0])] = fields[3]
    return result


class OwnedProcess:
    def __init__(self, registry):
        self.registry = Path(registry)
        self.process = None

    def recover(self):
        if not self.registry.exists():
            return
        saved = json.loads(self.registry.read_text())
        if saved['owner'] != str(self.registry.resolve()):
            raise RuntimeError('OWNED_PROCESS_REGISTRY_MISMATCH')
        pgid = saved['pgid']
        if pgid <= 1 or pgid == os.getpgrp():
            raise RuntimeError('OWNED_PROCESS_GROUP_UNSAFE')
        members = _members(pgid)
        # A reused leader PID must never authorize killing another group.
        if pgid in members and members[pgid] != saved['leader_started']:
            raise RuntimeError('OWNED_PROCESS_IDENTITY_CHANGED')
        self._stop(pgid)
        self.registry.unlink(missing_ok=True)

    def start(self, command, **kwargs):
        self.recover()
        self.process = subprocess.Popen(command, start_new_session=True, **kwargs)
        pgid = self.process.pid
        try:
            members = _members(pgid)
            self.registry.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.registry.with_suffix('.pending')
            temporary.write_text(json.dumps({'owner': str(self.registry.resolve()),
                'pid': pgid, 'pgid': pgid, 'leader_started': members.get(pgid),
                'restart_policy': 'no', 'ports': [], 'containers': []}) + '\n')
            temporary.replace(self.registry)
        except BaseException:
            # Registration/storage failure must not leave an untracked worker.
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=5)
            raise
        return self.process

    def _stop(self, pgid, grace=1.0):
        def send(sig):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                pass
        send(signal.SIGTERM)
        until = time.monotonic() + grace
        while _members(pgid) and time.monotonic() < until:
            if self.process is not None:
                self.process.poll()
            time.sleep(.02)
        if _members(pgid):
            send(signal.SIGKILL)
        if self.process is not None:
            self.process.wait(timeout=5)
        until = time.monotonic() + 5
        while _members(pgid) and time.monotonic() < until:
            time.sleep(.02)
        if _members(pgid):
            raise RuntimeError('OWNED_PROCESS_TEARDOWN_INCOMPLETE')

    def stop(self):
        self.recover()


def run_bounded(command, *, registry, deadline_seconds, no_progress_seconds,
                progress_file, **kwargs):
    if any(not math.isfinite(value) or value <= 0 for value in (deadline_seconds, no_progress_seconds)):
        raise ValueError('RUN_LIMITS_MUST_BE_POSITIVE')
    owner = OwnedProcess(registry)
    started = last_progress = time.monotonic()
    progress = None
    process = owner.start(command, **kwargs)
    reason = None
    try:
        while process.poll() is None:
            now = time.monotonic()
            try:
                target = Path(progress_file)
                if target.is_dir():
                    files = sorted(target.glob('*/driver-progress.json'))
                    value = [(str(file), json.loads(file.read_text()).get('progress_key')) for file in files] or None
                else:
                    value = json.loads(target.read_text()).get('progress_key')
            except (OSError, ValueError):
                value = None
            if value is not None and value != progress:
                progress, last_progress = value, now
            if now - started >= deadline_seconds:
                reason = 'RUN_DEADLINE_EXCEEDED'
                break
            if now - last_progress >= no_progress_seconds:
                reason = 'RUN_NO_PROGRESS_EXCEEDED'
                break
            time.sleep(.02)
    finally:
        owner.stop()
    return {'returncode': process.returncode if reason is None else 1,
            'reason': reason, 'wall_seconds': time.monotonic() - started}
