import os

files = [
    'workflow_state (2).json',
    'workflow_state (3).json',
    'workflow_state (4).json',
    'workflow_state_backup_20260428_112544 (2).json',
    'workflow_state_backup_20260428_112113 (2).json',
    'workflow_state.json',
    'workflow_state_backup_20260428_112544.json',
    'workflow_state_backup_20260428_112113.json',
]
for f in files:
    path = f'e:/PL5/logs/{f}'
    if os.path.exists(path):
        size = os.path.getsize(path)
        with open(path, 'rb') as fh:
            head = fh.read(10)
        is_text = all(32 <= b < 127 or b in (9, 10, 13) for b in head)
        label = "TEXT" if is_text else "BINARY"
        print(f'{f}: {size:,} bytes -> {label} (head={head[:6]!r})')
    else:
        print(f'{f}: MISSING')
