"""Только внешняя защита диагностики; не часть Product 4K."""
import atexit, json, os, sys
from pathlib import Path
counts = {"socket_connect_blocked": 0, "dns_blocked": 0, "env_read_blocked": 0}
def guard(event, args):
    key = None
    if event == "socket.connect": key = "socket_connect_blocked"
    elif event == "socket.getaddrinfo": key = "dns_blocked"
    elif event == "open" and isinstance(args[0], (str, bytes)) and Path(os.fsdecode(args[0])).name.startswith('.env') and not Path(os.fsdecode(args[0])).name.endswith('.example') and 'pytest-of-' not in str(args[0]):
        key = "env_read_blocked"
    if key:
        counts[key] += 1
        raise RuntimeError("AUDIT_EXTERNAL_GUARD:" + key)
sys.addaudithook(guard)
@atexit.register
def record():
    if os.getenv('AUDIT_GUARD_FILE'):
        file = Path(os.environ['AUDIT_GUARD_FILE'])
        file.write_text(json.dumps(counts) + '\n')
        file.with_name(file.stem + '-' + str(os.getpid()) + '.json').write_text(json.dumps(counts) + '\n')
