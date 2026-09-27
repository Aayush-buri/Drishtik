import sys

path = 'docs/hyperledger_fabric_anchoring.md'
with open(path, 'a', encoding='utf-8') as f:
    f.write('''
## Cryptographic Chain of Custody Hardening

The local chain of custody implementation utilizes deterministic cryptographic hashing:
* **Timestamp Canonicalization**: Timestamp canonicalization is deterministic and UTC-normalized. All timestamps are converted to a standard ISO-8601 UTC format including microseconds before hashing.
* **Immutable Custody Digest**: The local metadata_hash is part of the immutable custody digest (chain_digest).
* **Metadata Consistency**: Provider metadata must agree with local metadata before anchoring is considered successful. If the metadata hash returned by the blockchain provider does not match the locally calculated hash, the event is marked as FAILED and the mismatch is explicitly audited.
* **Verification Scope**: Local custody verification is distinct from blockchain ledger verification. The local verification endpoint (/api/v1/cases/{case_identifier}/blockchain/custody/verify) verifies the cryptographically linked list of local events, regardless of whether Fabric anchoring succeeded or was offline.

*(Note: Real Fabric transaction execution is currently mocked for testing purposes.)*
''')
print("Documentation updated")
