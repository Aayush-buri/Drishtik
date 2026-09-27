with open('backend/app/services/recovery_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We need to add logic to refuse recovery if CORRUPTED
refuse_block = '''    if cand.status == RecoveryCandidateStatus.CORRUPTED:
        raise HTTPException(status_code=400, detail="Cannot recover structurally corrupted candidates")

    if cand.status == RecoveryCandidateStatus.RECOVERED and cand.recovered_evidence_id:'''

# Find the start of recover_candidate
content = re.sub(
    r'    if cand\.status == RecoveryCandidateStatus\.RECOVERED and cand\.recovered_evidence_id:',
    refuse_block,
    content,
    count=1
)

with open('backend/app/services/recovery_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
