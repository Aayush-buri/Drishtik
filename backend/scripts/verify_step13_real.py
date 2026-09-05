"""Real Forensic Verification Script for Step 13:
Part A: Real Recovery Test on Disk Image
Part B: Real AI Analysis Test with YOLOv8 & OpenCV Motion on Imported CCTV Video
"""
import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.evidence import Evidence, EvidenceStatus
from app.models.recovery import RecoveryCandidateStatus
from app.services.recovery_service import (
    start_recovery_scan,
    validate_candidate,
    recover_candidate,
)
from app.services.ai_service import (
    start_ai_analysis_job,
    export_ai_frame,
)
from app.models.video_analysis import TimelineEvent

def run_real_recovery_test(db, case, user):
    print("==================================================================")
    print("RUNNING REAL RECOVERY TEST (Section 28)")
    print("==================================================================")
    
    # 1. Create a non-private synthetic test disk image
    disk_dir = Path("data") / "recovery_test"
    disk_dir.mkdir(parents=True, exist_ok=True)
    disk_path = disk_dir / "cctv_forensic_evidence_source.raw"

    # MBR/Partition Header (512 bytes)
    mbr = b"\x00" * 512
    # Embedded Dahua DHAV Stream with Annex-B video payload and second DHAV block
    dhav_stream = (
        b"DHAV"
        + b"\x01\x00\x00\x00"
        + b"\x00\x00\x00\x01\x67"
        + b"\x42\x00\x1f"
        + (b"\xaa" * 2048)
        + b"DHAV"
        + b"\x01\x00\x00\x00"
        + (b"\xbb" * 1024)
    )
    # Unallocated slack space (2048 bytes)
    slack = b"\xFF" * 2048
    # Embedded MP4 video container box
    mp4_stream = (
        (32).to_bytes(4, "big")
        + b"ftypisom\x00\x00\x02\x00isommp41\x00\x00\x00\x00"
        + (64).to_bytes(4, "big")
        + b"moov" + (b"\x00" * 56)
        + (128).to_bytes(4, "big")
        + b"mdat" + (b"\x55" * 120)
    )
    # Trailing raw block
    trailing = b"\x00" * 4096

    image_content = mbr + dhav_stream + slack + mp4_stream + trailing
    disk_path.write_bytes(image_content)

    initial_sha256 = hashlib.sha256(image_content).hexdigest()
    initial_md5 = hashlib.md5(image_content).hexdigest()
    print(f"[+] Created test raw disk image: {disk_path} ({len(image_content)} bytes)")
    print(f"[+] Source Disk Image Pre-Scan SHA-256: {initial_sha256}")

    # Register as Evidence
    ev_ident = "EVD-TEST-DISK-01"
    ev = db.query(Evidence).filter(Evidence.evidence_identifier == ev_ident).first()
    if not ev:
        ev = Evidence(
            case_id=case.id,
            evidence_identifier=ev_ident,
            original_filename="cctv_forensic_evidence_source.raw",
            storage_path=str(disk_path),
            source_type="DISK_IMAGE",
            media_type="application/octet-stream",
            file_extension=".raw",
            size_bytes=len(image_content),
            sha256=initial_sha256,
            md5_reference=initial_md5,
            evidence_status=EvidenceStatus.ORIGINAL,
            imported_by=user.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

    # 2. Recovery Scan
    print("[+] Starting Recovery Scan on source disk image...")
    job, candidates = start_recovery_scan(db, case, ev.id, user_id=user.id)
    print(f"[+] Scan completed! Job ID: {job.id}, Candidates Discovered: {len(candidates)}")
    for c in candidates:
        print(f"    - Candidate {c.candidate_identifier}: format={c.detected_format}, vendor={c.vendor}, offset={c.source_offset}, size={c.size_bytes}B, status={c.status.value}")

    assert len(candidates) >= 2, "Failed to detect stream candidates"

    # 3. Validate Candidate
    dhav_cand = next((c for c in candidates if "DAV" in c.detected_format or "DHAV" in c.detected_format), None)
    assert dhav_cand is not None, "Dahua candidate not found"
    print(f"[+] Validating candidate {dhav_cand.candidate_identifier}...")
    val_cand = validate_candidate(db, case, dhav_cand.id, user_id=user.id)
    print(f"[+] Validation Result: status={val_cand.status.value}, confidence={val_cand.confidence:.2f}, details={val_cand.validation_details}")
    assert val_cand.status in (RecoveryCandidateStatus.VALIDATED, RecoveryCandidateStatus.PARTIAL)

    # 4. Recover Candidate into Evidence
    print(f"[+] Carving candidate {dhav_cand.candidate_identifier} into RECOVERED Evidence...")
    cand_after, recovered_ev = recover_candidate(db, case, dhav_cand.id, user_id=user.id)
    print(f"[+] Successfully created RECOVERED Evidence: {recovered_ev.evidence_identifier}")
    print(f"    - Evidence Status: {recovered_ev.evidence_status.value}")
    print(f"    - Carved File: {recovered_ev.storage_path}")
    print(f"    - File Size: {recovered_ev.size_bytes} bytes")
    print(f"    - SHA-256: {recovered_ev.sha256}")
    print(f"    - MD5: {recovered_ev.md5_reference}")
    print(f"    - Derived Parameters (Provenance): {recovered_ev.derived_parameters}")

    # 5. Verify Source Disk Image Immutability
    after_content = disk_path.read_bytes()
    after_sha256 = hashlib.sha256(after_content).hexdigest()
    assert initial_sha256 == after_sha256, "CRITICAL FORENSIC ERROR: Source disk image bytes modified during carving!"
    print(f"[+] SOURCE DISK IMAGE IMMUTABILITY VERIFIED: SHA-256 unchanged ({after_sha256})")
    print("REAL RECOVERY TEST: PASS\n")
    return recovered_ev


def run_real_ai_test(db, case, user):
    print("==================================================================")
    print("RUNNING REAL AI TEST (Section 27)")
    print("==================================================================")

    # Find real CCTV video evidence
    ev = db.query(Evidence).filter(
        Evidence.case_id == case.id,
        Evidence.evidence_identifier == "EVD-6C7364"
    ).first()

    if not ev:
        print("[!] EVD-6C7364 not found in case, looking for any MP4 video in case...")
        ev = db.query(Evidence).filter(
            Evidence.case_id == case.id,
            Evidence.file_extension == ".mp4",
            Evidence.is_deleted == False
        ).first()

    assert ev is not None, "No real video evidence found for AI test"
    print(f"[+] Target Real Video: {ev.evidence_identifier} ({ev.original_filename})")
    print(f"[+] Video Storage Path: {ev.storage_path}")
    initial_video_sha = hashlib.sha256(open(ev.storage_path, "rb").read()).hexdigest()
    print(f"[+] Original Video Pre-Analysis SHA-256: {initial_video_sha}")

    # Run AI Analysis with real YOLOv8 & OpenCV motion detection
    print("[+] Starting Real AI Analysis (YOLOv8n object detection + OpenCV motion)...")
    job, findings = start_ai_analysis_job(
        db=db,
        case=case,
        evidence=ev,
        user_id=user.id,
        sample_rate_fps=0.5, # 1 frame every 2 seconds for high performance
        confidence_threshold=0.30,
        detect_objects=True,
        detect_motion=True,
    )

    print(f"[+] AI Job Completed: {job.job_identifier}")
    print(f"    - Frames Analyzed: {job.total_frames_analyzed}")
    print(f"    - Findings Discovered: {job.findings_count}")
    print(f"    - Elapsed Time: {(job.completed_at - job.started_at).total_seconds():.2f}s")

    for idx, f in enumerate(findings[:10]):
        print(f"    [{idx+1}] {f.object_class} (Model confidence: {int(f.confidence * 100)}%) at media_time={f.media_time:.2f}s, frame={f.frame_number}, bbox={f.bounding_box}")

    # Verify Timeline Events populated
    timeline_events = db.query(TimelineEvent).filter(TimelineEvent.evidence_id == ev.id).all()
    ai_events = [e for e in timeline_events if "AI:" in e.title]
    print(f"[+] Synced AI Timeline Events: {len(ai_events)} events on Step 12 timeline")
    if ai_events:
        print(f"    - Sample Timeline Event: Title='{ai_events[0].title}', Time={ai_events[0].media_time}s, Type={ai_events[0].event_type.value}")

    # Export an AI Frame
    if findings:
        sample_finding = findings[0]
        print(f"[+] Testing AI Frame Export on finding {sample_finding.finding_identifier} ({sample_finding.object_class})...")
        _, derived_ev = export_ai_frame(db, case, sample_finding.id, user_id=user.id)
        print(f"[+] Derived Frame Evidence created: {derived_ev.evidence_identifier}")
        print(f"    - Evidence Status: {derived_ev.evidence_status.value}")
        print(f"    - Operation: {derived_ev.derived_operation}")
        print(f"    - Frame SHA-256: {derived_ev.sha256}")
        print(f"    - Storage: {derived_ev.storage_path}")

    # Verify Original Video Immutability
    after_video_sha = hashlib.sha256(open(ev.storage_path, "rb").read()).hexdigest()
    assert initial_video_sha == after_video_sha, "CRITICAL FORENSIC ERROR: Original video modified by AI analysis or frame export!"
    print(f"[+] ORIGINAL VIDEO IMMUTABILITY VERIFIED: SHA-256 unchanged ({after_video_sha})")
    print("REAL AI TEST: PASS\n")


def main():
    db = SessionLocal()
    try:
        # Get active case CASE-BDE2CDFE
        case = db.query(Case).filter(Case.case_identifier == "CASE-BDE2CDFE").first()
        if not case:
            case = db.query(Case).first()
        assert case is not None, "No forensic case available in database"

        # Get admin user
        user = db.query(User).first()
        assert user is not None, "No user available in database"

        print(f"Forensic Case: {case.case_identifier} - {case.name}")
        print(f"Investigator: {user.username} ({user.display_name})\n")

        run_real_recovery_test(db, case, user)
        run_real_ai_test(db, case, user)

        print("==================================================================")
        print("ALL STEP 13 REAL VERIFICATIONS COMPLETED SUCCESSFULLY!")
        print("==================================================================")
    finally:
        db.close()


if __name__ == "__main__":
    main()
