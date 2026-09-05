import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.user import User
from app.models.report import Report, ReportType, ReportStatus, ReportFormat
from app.models.audit import AuditLog
from app.forensics.reporting.generator import ReportGenerator
from app.forensics.reporting.exporters import (
    PDFExporter, HTMLExporter, JSONExporter, compute_sha256
)
from app.forensics.blockchain import get_blockchain_provider

logger = logging.getLogger(__name__)


class ReportService:
    """
    Forensic Report Service managing compilation, rendering, disk persistence,
    cryptographic SHA-256 hashing, blockchain anchoring, and audit logging.
    """

    @staticmethod
    def _get_case_reports_dir(case_id: int) -> str:
        reports_dir = os.path.join("data", "case_data", str(case_id), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        return reports_dir

    def generate_report(
        self,
        db: Session,
        case: Case,
        examiner: User,
        report_type: str,
        examiner_notes: Optional[str] = None,
        export_format: str = "PDF"
    ) -> Report:
        """
        Compiles, renders, persists, hashes, and audits a forensic report.
        """
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        norm_type = report_type.upper()
        norm_format = export_format.upper()
        if norm_format not in ("PDF", "HTML", "JSON"):
            norm_format = "PDF"

        # 1. Audit Log: REPORT_GENERATION_STARTED
        audit_start = AuditLog(
            case_id=case.id,
            user_id=examiner.id,
            action="REPORT_GENERATION_STARTED",
            target_identifier=report_id,
            details=f"Initiated {norm_type} forensic report generation in {norm_format} format."
        )
        db.add(audit_start)
        db.commit()

        try:
            # 2. Compile structured data payload via ReportGenerator
            generator = ReportGenerator(db)
            if norm_type == ReportType.EVIDENCE_REPORT.value:
                payload = generator.generate_evidence_report(case, examiner, examiner_notes)
                title = f"Evidence Inventory Report — {case.case_identifier}"
            elif norm_type == ReportType.VIDEO_SUMMARY.value:
                payload = generator.generate_video_report(case, examiner, examiner_notes)
                title = f"Unified Video Summary Report — {case.case_identifier}"
            elif norm_type == ReportType.RECOVERY_REPORT.value:
                payload = generator.generate_recovery_report(case, examiner, examiner_notes)
                title = f"Video Recovery Report — {case.case_identifier}"
            elif norm_type == ReportType.AI_REPORT.value:
                payload = generator.generate_ai_report(case, examiner, examiner_notes)
                title = f"AI Video Analysis Report — {case.case_identifier}"
            elif norm_type == ReportType.CHAIN_OF_CUSTODY.value:
                payload = generator.generate_chain_of_custody_report(case, examiner, examiner_notes)
                title = f"Chain of Custody & Audit Report — {case.case_identifier}"
            else:
                # Default to CASE_SUMMARY
                norm_type = ReportType.CASE_SUMMARY.value
                payload = generator.generate_case_report(case, examiner, examiner_notes)
                title = f"Final Forensic Investigation Summary — {case.case_identifier}"

            # 3. Render artifact into requested format
            reports_dir = self._get_case_reports_dir(case.id)
            ext = norm_format.lower()
            file_name = f"{report_id}_{norm_type.lower()}.{ext}"
            storage_path = os.path.join(reports_dir, file_name)

            if norm_format == "PDF":
                artifact_bytes = PDFExporter.export(payload, case.case_identifier, report_id)
            elif norm_format == "HTML":
                html_str = HTMLExporter.export(payload, case.case_identifier, report_id)
                artifact_bytes = html_str.encode("utf-8")
            else:  # JSON
                json_str = JSONExporter.export(payload, case.case_identifier, report_id)
                artifact_bytes = json_str.encode("utf-8")

            # 4. Write artifact to managed case storage
            with open(storage_path, "wb") as f:
                f.write(artifact_bytes)

            file_size = len(artifact_bytes)

            # 5. Compute SHA-256 hash of report file
            report_sha256 = compute_sha256(artifact_bytes)

            # 6. Check blockchain anchoring (optional if Fabric is available)
            provider = get_blockchain_provider()
            health = provider.health_check()
            blockchain_status = "UNAVAILABLE"
            blockchain_tx_id = None
            anchored_at = None

            if health.get("available") is True:
                anchor_res = provider.anchor_evidence(
                    case_identifier=case.case_identifier,
                    evidence_identifier=report_id,
                    sha256=report_sha256,
                    event_type=f"REPORT_GENERATED_{norm_type}",
                    actor=examiner.username,
                    timestamp=datetime.now(timezone.utc),
                    source="Drishtik Reporting Engine",
                    metadata={"report_type": norm_type, "format": norm_format}
                )
                if anchor_res.success:
                    blockchain_status = "ANCHORED"
                    blockchain_tx_id = anchor_res.transaction_id
                    anchored_at = anchor_res.timestamp
                else:
                    blockchain_status = anchor_res.status

            # 7. Create Report record in database
            report = Report(
                report_identifier=report_id,
                case_id=case.id,
                report_type=norm_type,
                title=title,
                status=ReportStatus.GENERATED.value,
                created_by=examiner.id,
                generated_by=examiner.id,
                format=norm_format,
                file_size=file_size,
                storage_path=storage_path,
                sha256=report_sha256,
                examiner_notes=examiner_notes,
                data_payload=payload,
                blockchain_status=blockchain_status,
                blockchain_tx_id=blockchain_tx_id,
                blockchain_anchored_at=anchored_at
            )
            db.add(report)

            # 8. Audit Log: REPORT_GENERATION_COMPLETED
            audit_complete = AuditLog(
                case_id=case.id,
                user_id=examiner.id,
                action="REPORT_GENERATION_COMPLETED",
                target_identifier=report_id,
                details=f"Completed {norm_type} report. File: {file_name}, Size: {file_size} bytes, SHA-256: {report_sha256}, Blockchain: {blockchain_status}."
            )
            db.add(audit_complete)
            db.commit()
            db.refresh(report)
            return report

        except Exception as e:
            logger.error(f"Report generation failed for {case.case_identifier}: {e}", exc_info=True)
            db.rollback()
            audit_fail = AuditLog(
                case_id=case.id,
                user_id=examiner.id,
                action="REPORT_GENERATION_FAILED",
                target_identifier=report_id,
                details=f"Failed to generate {norm_type} report: {str(e)}"
            )
            db.add(audit_fail)
            db.commit()
            raise

    def list_case_reports(self, db: Session, case_id: int) -> List[Report]:
        return db.query(Report).filter(Report.case_id == case_id).order_by(Report.created_at.desc()).all()

    def get_report_by_identifier(self, db: Session, case_id: int, report_identifier: str) -> Optional[Report]:
        return (
            db.query(Report)
            .filter(Report.case_id == case_id, Report.report_identifier == report_identifier)
            .first()
        )

    def export_report_file(
        self,
        db: Session,
        case: Case,
        examiner: User,
        report_identifier: str,
        target_format: str
    ) -> Tuple[bytes, str, str]:
        """
        Exports report file bytes in requested format (PDF, HTML, JSON).
        Logs REPORT_EXPORTED.
        Returns (content_bytes, download_filename, media_type).
        """
        report = self.get_report_by_identifier(db, case.id, report_identifier)
        if not report:
            raise ValueError(f"Report {report_identifier} not found in case {case.case_identifier}.")

        norm_format = (target_format or report.format).upper()
        if norm_format not in ("PDF", "HTML", "JSON"):
            norm_format = "PDF"

        ext = norm_format.lower()
        filename = f"{report.report_identifier}_{report.report_type.lower()}.{ext}"

        # If existing on-disk artifact matches requested format and exists:
        if report.format == norm_format and report.storage_path and os.path.exists(report.storage_path):
            with open(report.storage_path, "rb") as f:
                content_bytes = f.read()
        else:
            # Dynamic conversion from stored canonical data_payload
            payload = report.data_payload or {}
            if norm_format == "PDF":
                content_bytes = PDFExporter.export(payload, case.case_identifier, report.report_identifier)
            elif norm_format == "HTML":
                html_str = HTMLExporter.export(payload, case.case_identifier, report.report_identifier)
                content_bytes = html_str.encode("utf-8")
            else:  # JSON
                json_str = JSONExporter.export(payload, case.case_identifier, report.report_identifier)
                content_bytes = json_str.encode("utf-8")

        # Determine media type
        if norm_format == "PDF":
            media_type = "application/pdf"
        elif norm_format == "HTML":
            media_type = "text/html; charset=utf-8"
        else:
            media_type = "application/json"

        # Log REPORT_EXPORTED
        audit_export = AuditLog(
            case_id=case.id,
            user_id=examiner.id,
            action="REPORT_EXPORTED",
            target_identifier=report.report_identifier,
            details=f"Exported forensic report {report.report_identifier} as {norm_format} ({len(content_bytes)} bytes)."
        )
        db.add(audit_export)
        db.commit()

        return content_bytes, filename, media_type

    def verify_report_integrity(
        self,
        db: Session,
        case: Case,
        examiner: User,
        report_identifier: str
    ) -> Dict[str, Any]:
        """
        Verifies the on-disk report artifact SHA-256 against recorded hash and blockchain.
        Logs REPORT_INTEGRITY_VERIFIED or REPORT_INTEGRITY_FAILED.
        """
        report = self.get_report_by_identifier(db, case.id, report_identifier)
        if not report:
            raise ValueError(f"Report {report_identifier} not found in case {case.case_identifier}.")

        if not report.storage_path or not os.path.exists(report.storage_path):
            current_sha256 = "FILE_NOT_FOUND"
            is_match = False
            reason = "Report artifact file not found on disk."
        else:
            with open(report.storage_path, "rb") as f:
                content = f.read()
            current_sha256 = compute_sha256(content)
            is_match = (current_sha256.lower() == report.sha256.lower())
            reason = (
                "Report artifact SHA-256 matches recorded forensic digest."
                if is_match else
                f"Report artifact SHA-256 ('{current_sha256}') does not match recorded digest ('{report.sha256}')."
            )

        status_str = "VERIFIED" if is_match else "MISMATCH"
        audit_action = "REPORT_INTEGRITY_VERIFIED" if is_match else "REPORT_INTEGRITY_FAILED"

        audit_verify = AuditLog(
            case_id=case.id,
            user_id=examiner.id,
            action=audit_action,
            target_identifier=report.report_identifier,
            details=f"Report integrity verification: {status_str}. Current SHA-256: {current_sha256}, Recorded: {report.sha256}."
        )
        db.add(audit_verify)
        db.commit()

        return {
            "report_identifier": report.report_identifier,
            "overall_status": status_str,
            "current_sha256": current_sha256,
            "recorded_sha256": report.sha256,
            "format": report.format,
            "file_size": report.file_size,
            "reason": reason,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "blockchain_status": report.blockchain_status,
            "blockchain_tx_id": report.blockchain_tx_id or "Unavailable"
        }


report_service = ReportService()
