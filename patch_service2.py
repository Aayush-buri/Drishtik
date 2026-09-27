import sys

path = 'backend/app/services/blockchain_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

old_block = r'''        if anchor_result.success and anchor_result.status == "ANCHORED":
            # 5a. Successfully anchored
            custody_event.blockchain_tx_id = anchor_result.transaction_id
            custody_event.blockchain_status = "ANCHORED"
            custody_event.blockchain_anchored_at = anchor_result.timestamp
            custody_event.blockchain_block_number = anchor_result.block_number
            custody_event.metadata_hash = anchor_result.metadata_hash

            # Update evidence summary fields
            evidence.blockchain_status = "ANCHORED"
            evidence.blockchain_tx_id = anchor_result.transaction_id
            evidence.blockchain_anchored_at = anchor_result.timestamp'''

new_block = '''        if anchor_result.success and anchor_result.status == "ANCHORED":
            # 5a. Successfully anchored
            if anchor_result.metadata_hash and anchor_result.metadata_hash != metadata_hash:
                # Metadata mismatch!
                custody_event.blockchain_status = "FAILED"
                # Store Audit Log
                audit_mismatch = AuditLog(
                    case_id=case.id,
                    user_id=user_id,
                    action="BLOCKCHAIN_ANCHOR_FAILED",
                    target_identifier=evidence.evidence_identifier,
                    details=json.dumps({
                        "error": "Metadata hash mismatch with provider",
                        "local_metadata_hash": metadata_hash,
                        "provider_metadata_hash": anchor_result.metadata_hash
                    })
                )
                db.add(audit_mismatch)
            else:
                custody_event.blockchain_tx_id = anchor_result.transaction_id
                custody_event.blockchain_status = "ANCHORED"
                custody_event.blockchain_anchored_at = anchor_result.timestamp
                custody_event.blockchain_block_number = anchor_result.block_number
    
                # Update evidence summary fields
                evidence.blockchain_status = "ANCHORED"
                evidence.blockchain_tx_id = anchor_result.transaction_id
                evidence.blockchain_anchored_at = anchor_result.timestamp'''

content = re.sub(old_block.replace(' ', r'\s+'), new_block, content, count=1)

# we also need to fix the anchor_record metadata_hash in the match block!
old_anchor = r'''            # Store BlockchainAnchor record
            anchor_record = BlockchainAnchor\(
                anchor_identifier=self._generate_identifier\("ANCH"\),
                case_id=case.id,
                evidence_id=evidence.id,
                custody_event_id=custody_event.id,
                sha256=evidence.sha256 or "",
                transaction_id=anchor_result.transaction_id,
                block_number=anchor_result.block_number,
                channel=anchor_result.channel,
                chaincode=anchor_result.chaincode,
                metadata_hash=anchor_result.metadata_hash,'''

new_anchor = '''                # Store BlockchainAnchor record
                anchor_record = BlockchainAnchor(
                    anchor_identifier=self._generate_identifier("ANCH"),
                    case_id=case.id,
                    evidence_id=evidence.id,
                    custody_event_id=custody_event.id,
                    sha256=evidence.sha256 or "",
                    transaction_id=anchor_result.transaction_id,
                    block_number=anchor_result.block_number,
                    channel=anchor_result.channel,
                    chaincode=anchor_result.chaincode,
                    metadata_hash=metadata_hash,'''

content = re.sub(old_anchor.replace(' ', r'\s+'), new_anchor, content, count=1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated BlockchainService correctly")
