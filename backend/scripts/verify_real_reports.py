"""Script to execute Section 23 Real Report Test on real Drishtik case data.

Verifies:
1. Case with real evidence items, AI findings, carving results, audit logs.
2. Generates Evidence Report, AI Analysis Report, and Chain of Custody Report.
3. Confirms files are genuinely created on disk.
4. Confirms SHA-256 hashes are calculated and stored.
5. Confirms integrity verification passes.
6. Confirms original evidence files remain 100% byte-for-byte immutable.
"""
import os
import sys
import hashlib
from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.user import User
from app.models.report import ReportType, ReportFormat
from app.services.report_service import report_service


def compute_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def run_real_report_verification():
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == 1).first()
        if not case:
            print("ERROR: Case 1 not found in database.")
            sys.exit(1)

        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = db.query(User).first()

        print(f"============================================================")
        print(f"STEP 15: SECTION 23 REAL REPORT TEST")
        print(f"============================================================")
        print(f"Target Case: {case.case_identifier} ({case.name})")
        print(f"Examiner:    {admin.username} (ID: {admin.id})")

        # Check existing evidence and record disk hashes prior to report generation
        evidence_items = db.query(Evidence).filter(Evidence.case_id == case.id).all()
        print(f"Total Evidence in Case: {len(evidence_items)}")

        pre_hashes = {}
        for ev in evidence_items[:5]:  # Sample first 5 files with physical storage
            if ev.storage_path and os.path.exists(ev.storage_path):
                disk_sha = compute_file_sha256(ev.storage_path)
                pre_hashes[ev.id] = (ev.storage_path, disk_sha, ev.sha256)
                print(f"  Pre-check Evidence {ev.evidence_identifier}: SHA-256={disk_sha[:16]}... (Matches DB: {disk_sha == ev.sha256})")

        # 1. Generate Evidence Report
        print("\n--- Generating Report 1: EVIDENCE_REPORT ---")
        ev_report = report_service.generate_report(
            db=db,
            case=case,
            examiner=admin,
            report_type=ReportType.EVIDENCE_REPORT.value,
            examiner_notes="Section 23 Real Evidence Inventory Verification Report",
            export_format=ReportFormat.PDF.value
        )
        print(f"  Report Identifier: {ev_report.report_identifier}")
        print(f"  Disk Path:         {ev_report.storage_path}")
        print(f"  File Size:         {ev_report.file_size} bytes")
        print(f"  SHA-256 Digest:    {ev_report.sha256}")
        assert os.path.exists(ev_report.storage_path), "Evidence report file must exist on disk"
        disk_sha = compute_file_sha256(ev_report.storage_path)
        assert disk_sha == ev_report.sha256, "Calculated report SHA-256 must match disk file"
        print(f"  Disk SHA-256 Match: TRUE")

        # 2. Generate AI Analysis Report
        print("\n--- Generating Report 2: AI_REPORT ---")
        ai_report = report_service.generate_report(
            db=db,
            case=case,
            examiner=admin,
            report_type=ReportType.AI_REPORT.value,
            examiner_notes="Section 23 Real AI Video Object Detection Verification Report",
            export_format=ReportFormat.PDF.value
        )
        print(f"  Report Identifier: {ai_report.report_identifier}")
        print(f"  Disk Path:         {ai_report.storage_path}")
        print(f"  File Size:         {ai_report.file_size} bytes")
        print(f"  SHA-256 Digest:    {ai_report.sha256}")
        assert os.path.exists(ai_report.storage_path), "AI report file must exist on disk"
        disk_sha = compute_file_sha256(ai_report.storage_path)
        assert disk_sha == ai_report.sha256, "Calculated report SHA-256 must match disk file"
        print(f"  Disk SHA-256 Match: TRUE")

        # 3. Generate Chain of Custody Report
        print("\n--- Generating Report 3: CHAIN_OF_CUSTODY ---")
        coc_report = report_service.generate_report(
            db=db,
            case=case,
            examiner=admin,
            report_type=ReportType.CHAIN_OF_CUSTODY.value,
            examiner_notes="Section 23 Real Forensic Chain of Custody & Blockchain Anchoring Report",
            export_format=ReportFormat.PDF.value
        )
        print(f"  Report Identifier: {coc_report.report_identifier}")
        print(f"  Disk Path:         {coc_report.storage_path}")
        print(f"  File Size:         {coc_report.file_size} bytes")
        print(f"  SHA-256 Digest:    {coc_report.sha256}")
        assert os.path.exists(coc_report.storage_path), "Chain of custody report file must exist on disk"
        disk_sha = compute_file_sha256(coc_report.storage_path)
        assert disk_sha == coc_report.sha256, "Calculated report SHA-256 must match disk file"
        print(f"  Disk SHA-256 Match: TRUE")

        # 4. Verify Report Integrity API
        print("\n--- Verifying Report Integrity ---")
        for rpt in [ev_report, ai_report, coc_report]:
            v_res = report_service.verify_report_integrity(db, case, admin, rpt.report_identifier)
            print(f"  Report {rpt.report_identifier}: Status={v_res['overall_status']} (Current={v_res['current_sha256'][:16]}...)")
            assert v_res["overall_status"] == "VERIFIED", f"Report {rpt.report_identifier} must verify as VERIFIED"

        # 5. Export JSON format test
        print("\n--- Testing JSON Export ---")
        content_bytes, filename, media_type = report_service.export_report_file(
            db, case, admin, ev_report.report_identifier, "JSON"
        )
        print(f"  Exported File: {filename} ({len(content_bytes)} bytes, {media_type})")
        assert filename.endswith(".json")
        assert b"DRISHTIK_FORENSIC_REPORT_V1" in content_bytes

        # 6. Post-verification of original evidence immutability
        print("\n--- Verifying Original Evidence Immutability ---")
        for ev_id, (path, pre_sha, db_sha) in pre_hashes.items():
            post_sha = compute_file_sha256(path)
            print(f"  Evidence ID {ev_id}: Pre-hash={pre_sha[:16]}... Post-hash={post_sha[:16]}... Identical={pre_sha == post_sha}")
            assert pre_sha == post_sha, f"CRITICAL FAILURE: Evidence {ev_id} was modified during report generation!"

        print("\n============================================================")
        print("ALL SECTION 23 REAL REPORT VERIFICATION CHECKS PASSED!")
        print("============================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_real_report_verification()
