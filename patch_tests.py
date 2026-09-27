import sys

path = 'backend/tests/test_blockchain_custody.py'
with open(path, 'a', encoding='utf-8') as f:
    f.write('''

def test_canonical_timestamp_consistency():
    from app.services.blockchain_service import BlockchainService
    from datetime import datetime, timezone
    
    dt = datetime(2025, 1, 1, 12, 0, 0, 123456)
    
    # Simulate migration style vs runtime style
    migration_style = BlockchainService.canonicalize_custody_timestamp(dt)
    runtime_style = BlockchainService.canonicalize_custody_timestamp(dt.replace(tzinfo=timezone.utc))
    
    assert migration_style == runtime_style
    assert migration_style == "2025-01-01T12:00:00.123456+00:00"

def test_utc_normalization():
    from app.services.blockchain_service import BlockchainService
    from datetime import datetime, timezone, timedelta
    
    dt_utc = datetime(2025, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
    # create a timezone offset +05:30
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    dt_ist = datetime(2025, 1, 1, 17, 30, 0, 123456, tzinfo=tz_ist)
    
    str_utc = BlockchainService.canonicalize_custody_timestamp(dt_utc)
    str_ist = BlockchainService.canonicalize_custody_timestamp(dt_ist)
    
    assert str_utc == str_ist
    assert str_ist == "2025-01-01T12:00:00.123456+00:00"

def test_metadata_mismatch_with_provider(test_case: Case, test_user: User, db_session: Session):
    class MismatchProvider(MockBlockchainProvider):
        def anchor_custody_event(self, *args, **kwargs) -> AnchorResult:
            return AnchorResult(
                success=True, 
                status="ANCHORED", 
                timestamp=datetime.now(timezone.utc), 
                transaction_id="TX_123", 
                block_number=42, 
                channel="custody", 
                chaincode="cc", 
                metadata_hash="FAKE_METADATA_HASH_FROM_PROVIDER",
                error_message=None
            )
            
    set_blockchain_provider(MismatchProvider())
    try:
        evidence = Evidence(
            case_id=test_case.id,
            evidence_identifier=f"EVID-TEST-{uuid.uuid4().hex[:6]}",
            original_filename="mismatch.mp4",
            storage_path="/tmp/mismatch.mp4",
            source_type="Imported",
            size_bytes=100,
            sha256=hashlib.sha256(b"mismatch").hexdigest(),
            file_extension="mp4",
            media_type="Video",
            imported_by=test_user.id,
            evidence_status=EvidenceStatus.ORIGINAL,
            integrity_status=IntegrityStatus.VERIFIED,
        )
        db_session.add(evidence)
        db_session.commit()
        
        # Action
        ev = record_custody_and_anchor(db=db_session, case=test_case, evidence=evidence, action="A1", user_id=test_user.id, username=test_user.username)
        
        # Mismatch handled locally as FAILED
        assert ev.blockchain_status == "FAILED"
        assert ev.blockchain_tx_id is None
        assert ev.metadata_hash != "FAKE_METADATA_HASH_FROM_PROVIDER"
        assert ev.chain_digest is not None
        
        audit_log = db_session.query(AuditLog).filter(AuditLog.action == "BLOCKCHAIN_ANCHOR_FAILED").first()
        assert audit_log is not None
        
    finally:
        set_blockchain_provider(MockBlockchainProvider())

def test_metadata_match_with_provider(test_case: Case, test_user: User, db_session: Session):
    class MatchProvider(MockBlockchainProvider):
        def anchor_custody_event(self, *args, **kwargs) -> AnchorResult:
            # Reconstruct the metadata_hash that the provider would receive/calculate if it matches
            import json, hashlib
            meta_str = json.dumps(kwargs.get("metadata", {}), sort_keys=True, separators=(",", ":"))
            metadata_hash = hashlib.sha256(meta_str.encode("utf-8")).hexdigest()
            
            return AnchorResult(
                success=True, 
                status="ANCHORED", 
                timestamp=datetime.now(timezone.utc), 
                transaction_id="TX_MATCH", 
                block_number=43, 
                channel="custody", 
                chaincode="cc", 
                metadata_hash=metadata_hash,
                error_message=None
            )
            
    set_blockchain_provider(MatchProvider())
    try:
        evidence = Evidence(
            case_id=test_case.id,
            evidence_identifier=f"EVID-TEST-{uuid.uuid4().hex[:6]}",
            original_filename="match.mp4",
            storage_path="/tmp/match.mp4",
            source_type="Imported",
            size_bytes=100,
            sha256=hashlib.sha256(b"match").hexdigest(),
            file_extension="mp4",
            media_type="Video",
            imported_by=test_user.id,
            evidence_status=EvidenceStatus.ORIGINAL,
            integrity_status=IntegrityStatus.VERIFIED,
        )
        db_session.add(evidence)
        db_session.commit()
        
        ev = record_custody_and_anchor(db=db_session, case=test_case, evidence=evidence, action="A1", user_id=test_user.id, username=test_user.username)
        
        assert ev.blockchain_status == "ANCHORED"
        assert ev.blockchain_tx_id == "TX_MATCH"
    finally:
        set_blockchain_provider(MockBlockchainProvider())

def test_partial_legacy_chain_unverified(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    # Setup legacy chain segment
    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-TEST-{uuid.uuid4().hex[:6]}",
        original_filename="partial.mp4",
        storage_path="/tmp/partial.mp4",
        source_type="Imported",
        size_bytes=100,
        sha256=hashlib.sha256(b"partial").hexdigest(),
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()
    
    # Legacy event 1 (missing cryptographic fields)
    legacy_event = CustodyEvent(
        event_identifier=BlockchainService._generate_identifier("CUST"),
        case_id=test_case.id,
        evidence_id=evidence.id,
        action="LEGACY_IMPORT",
        actor_id=test_user.id,
        actor_username=test_user.username,
        timestamp=datetime.now(timezone.utc),
        sha256=evidence.sha256,
        blockchain_status="NOT_ANCHORED",
        verification_status="VERIFIED", # previously claimed verified
        previous_event_reference=None,
        previous_event_hash=None, # Missing!
        chain_digest=None # Missing!
    )
    db_session.add(legacy_event)
    db_session.commit()
    
    # Subsequent cryptographic event 2
    record_custody_and_anchor(db=db_session, case=test_case, evidence=evidence, action="A2", user_id=test_user.id, username=test_user.username)
    
    # Verification of entire chain should stop at Event 1 and return UNVERIFIED
    service = BlockchainService()
    result = service.verify_custody_chain(db=db_session, case=test_case, evidence=evidence)
    
    assert result["verified"] is False
    assert result["status"] == "UNVERIFIED"
    assert "missing cryptographic link fields" in result["reason"]
''')
print("Tests appended")
