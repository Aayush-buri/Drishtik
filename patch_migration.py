import sys, glob

migs = glob.glob('backend/alembic/versions/*_add_cryptographic_chain_of_custody.py')
path = migs[0]

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We need to replace the definition of canonicalize_custody_event and add canonicalize_custody_timestamp
old_funcs = r'''def canonicalize_custody_event\(payload\) -> str:
    return json.dumps\(payload, sort_keys=True, separators=\(',', ':'\)\)'''

new_funcs = '''from datetime import timezone

def canonicalize_custody_timestamp(timestamp) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)
    return timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")

def canonicalize_custody_event(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))'''

content = re.sub(old_funcs.replace(' ', r'\s+'), new_funcs, content, count=1)

# Now fix the payload timestamp in migration
content = content.replace('''"timestamp_utc": event.timestamp.isoformat()''', '''"timestamp_utc": canonicalize_custody_timestamp(event.timestamp)''')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated Migration correctly")
