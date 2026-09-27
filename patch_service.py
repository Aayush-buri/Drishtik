import sys, re

path = 'backend/app/services/blockchain_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add canonicalize_custody_timestamp
canonicalize_func = '''    @staticmethod
    def canonicalize_custody_timestamp(timestamp: datetime) -> str:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        return timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")

    @staticmethod
    def canonicalize_custody_event(payload: Dict[str, Any]) -> str:'''

content = content.replace('''    @staticmethod
    def canonicalize_custody_event(payload: Dict[str, Any]) -> str:''', canonicalize_func)


# 2. Update record_custody_and_anchor payload timestamp
content = content.replace('''"timestamp_utc": current_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")''', '''"timestamp_utc": self.canonicalize_custody_timestamp(current_time)''')

# 3. Update verify_custody_chain payload timestamp
content = content.replace('''"timestamp_utc": event.timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")''', '''"timestamp_utc": self.canonicalize_custody_timestamp(event.timestamp)''')

# 4. Fix metadata hash consistency logic in record_custody_and_anchor
old_anchored = '''        if anchor_result.success and anchor_result.status == "ANCHORED":
            # 5a. Successfully anchored
            custody_event.blockchain_tx_id = anchor_result.transaction_id
            custody_event.blockchain_status = "ANCHORED"
            custody_event.blockchain_anchored_at = anchor_result.timestamp
            custody_event.blockchain_block_number = anchor_result.block_number
            custody_event.metadata_hash = anchor_result.metadata_hash

            # Update evidence summary fields
            evidence.blockchain_status = "ANCHORED"
            evidence.blockchain_tx_id = anchor_result.transaction_id
            evidence.blockchain_anchored_at = anchor_result.timestamp

            # Store BlockchainAnchor record
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
                metadata_hash=anchor_result.metadata_hash,
                status=BlockchainAnchorStatus.VERIFIED,
                verification_payload=json.dumps({"info": "Initially anchored"})
            )
            db.add(anchor_record)'''

new_anchored = '''        if anchor_result.success and anchor_result.status == "ANCHORED":
            # 5a. Successfully anchored
            if anchor_result.metadata_hash and anchor_result.metadata_hash != custody_event.metadata_hash:
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
                        "local_metadata_hash": custody_event.metadata_hash,
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
                evidence.blockchain_anchored_at = anchor_result.timestamp

                # Store BlockchainAnchor record
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
                    metadata_hash=custody_event.metadata_hash,
                    status=BlockchainAnchorStatus.VERIFIED,
                    verification_payload=json.dumps({"info": "Initially anchored"})
                )
                db.add(anchor_record)'''
                
if old_anchored in content:
    content = content.replace(old_anchored, new_anchored)
else:
    print("WARNING: Could not find old_anchored block")
    
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated BlockchainService")
