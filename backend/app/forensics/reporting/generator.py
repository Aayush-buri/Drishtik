import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.case import Case, CaseMember
from app.models.user import User
from app.models.evidence import Evidence, EvidenceStatus, IntegrityStatus
from app.models.device import Device
from app.models.acquisition import Acquisition
from app.models.video_analysis import TimelineEvent, VideoAnalysisSession
from app.models.recovery import RecoveryCandidate, RecoveryScanJob
from app.models.ai_analysis import AIAnalysisJob, AIFinding
from app.models.audit import AuditLog
from app.models.blockchain import CustodyEvent, BlockchainAnchor
from app.forensics.blockchain import get_blockchain_provider

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Forensic Report Generator abstraction.
    Compiles existing case, evidence, acquisition, video, recovery, AI, audit,
    and blockchain data into structured, court-admissible forensic report payloads.
    Strictly read-only: never modifies evidence or database states.
    """

    def __init__(self, db: Session):
        self.db = db

    def _get_case_members_info(self, case: Case) -> List[Dict[str, Any]]:
        members = (
            self.db.query(CaseMember, User)
            .join(User, CaseMember.user_id == User.id)
            .filter(CaseMember.case_id == case.id)
            .all()
        )
        return [
            {
                "user_id": user.id,
                "username": user.username,
                "display_name": user.display_name or user.username,
                "role": member.role.value if hasattr(member.role, "value") else str(member.role),
            }
            for member, user in members
        ]

    def _get_blockchain_summary(self, case: Case) -> Dict[str, Any]:
        provider = get_blockchain_provider()
        health = provider.health_check()

        anchors = self.db.query(BlockchainAnchor).filter(BlockchainAnchor.case_id == case.id).all()
        anchored_count = sum(1 for a in anchors if a.blockchain_status == "ANCHORED")
        failed_count = sum(1 for a in anchors if a.blockchain_status in ("FAILED", "UNAVAILABLE"))

        return {
            "network_status": health.get("status", "UNAVAILABLE"),
            "network_name": health.get("network", "Hyperledger Fabric"),
            "peer_endpoint": health.get("peer_endpoint", "localhost:7051"),
            "channel": health.get("channel", "cctvchannel"),
            "chaincode": health.get("chaincode", "evidence_anchor"),
            "anchored_count": anchored_count,
            "failed_count": failed_count,
            "total_anchors": len(anchors),
            "service_message": health.get("message", "Blockchain service status normal.")
        }

    # =========================================================================
    # 1. CASE SUMMARY / FINAL INVESTIGATION REPORT
    # =========================================================================
    def generate_case_report(
        self,
        case: Case,
        examiner: User,
        examiner_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates Case Summary / Final Investigation Report containing Sections A–M.
        """
        evidence_list = self.db.query(Evidence).filter(Evidence.case_id == case.id).all()
        devices = self.db.query(Device).filter(Device.case_id == case.id).all()
        acquisitions = self.db.query(Acquisition).filter(Acquisition.case_id == case.id).all()
        recovered_count = sum(1 for e in evidence_list if e.evidence_status == EvidenceStatus.RECOVERED)
        ai_findings_count = self.db.query(AIFinding).filter(AIFinding.case_id == case.id).count()

        # Integrity summary
        verified_count = sum(1 for e in evidence_list if e.integrity_status == IntegrityStatus.VERIFIED)
        mismatch_count = sum(1 for e in evidence_list if e.integrity_status == IntegrityStatus.MISMATCH)
        unverified_count = sum(1 for e in evidence_list if e.integrity_status == IntegrityStatus.UNVERIFIED)

        members_info = self._get_case_members_info(case)
        blockchain_summary = self._get_blockchain_summary(case)

        # Section A: Case Information
        case_info = {
            "case_identifier": case.case_identifier,
            "name": case.name,
            "description": case.description or "No case description provided.",
            "created_at": case.created_at.isoformat() if case.created_at else "Unavailable",
            "created_by": case.creator.username if case.creator else "System",
            "status": getattr(case, "status", "ACTIVE") or "ACTIVE",
            "investigators": members_info,
        }

        # Section B: Examination Scope
        scope = {
            "objective": "Forensic examination, integrity verification, extraction, and chain-of-custody logging of digital CCTV/DVR evidence.",
            "hash_standard": "Primary: SHA-256 (64-char hexadecimal digest) | Secondary: MD5",
            "storage_policy": "Original evidence bitstreams remain strictly read-only on managed forensic storage.",
            "blockchain_policy": "Cryptographic digests and procedural custody transitions are anchored to Hyperledger Fabric when network runtime is active; video/image binaries are strictly never stored on-chain.",
        }

        # Section C: Evidence Inventory Summary
        evidence_inventory = [
            {
                "evidence_identifier": e.evidence_identifier,
                "original_filename": e.original_filename,
                "status": e.evidence_status.value if hasattr(e.evidence_status, "value") else str(e.evidence_status),
                "source_type": e.source_type or "Unavailable",
                "vendor": e.vendor or "Unavailable",
                "size_bytes": e.size_bytes,
                "sha256": e.sha256 or "Unavailable",
                "md5": e.md5_reference or "Unavailable",
                "integrity_status": e.integrity_status.value if hasattr(e.integrity_status, "value") else str(e.integrity_status),
                "blockchain_status": e.blockchain_status or "UNAVAILABLE",
                "blockchain_tx_id": e.blockchain_tx_id or "Unavailable",
            }
            for e in evidence_list
        ]

        # Section D: Device / Acquisition Summary
        device_summary = [
            {
                "device_identifier": d.device_identifier,
                "name": getattr(d, "name", None) or f"{d.manufacturer or ''} {d.model or ''}".strip() or d.device_identifier,
                "device_type": d.device_type.value if hasattr(d.device_type, "value") else str(d.device_type),
                "model": d.model or "Unavailable",
                "serial_number": d.serial_number or "Unavailable",
                "status": d.status.value if hasattr(d.status, "value") else str(d.status),
            }
            for d in devices
        ]

        acquisition_summary = [
            {
                "acquisition_identifier": a.acquisition_identifier,
                "method": (a.acquisition_method.value if hasattr(a.acquisition_method, "value") else str(a.acquisition_method)) if hasattr(a, "acquisition_method") else (a.method.value if hasattr(a.method, "value") else str(getattr(a, "method", "Unavailable"))),
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                "source_path": a.source_path or "Unavailable",
                "total_bytes": getattr(a, "size_bytes", None) if getattr(a, "size_bytes", None) is not None else getattr(a, "total_bytes", 0),
                "sha256": getattr(a, "destination_sha256", None) or getattr(a, "sha256_hash", "Unavailable"),
            }
            for a in acquisitions
        ]

        # Section E: Video Analysis Summary
        video_evidence = [e for e in evidence_list if e.media_type and "video" in e.media_type.lower() or e.file_extension in (".mp4", ".dav", ".mkv", ".avi")]
        video_summary = [
            {
                "evidence_identifier": v.evidence_identifier,
                "filename": v.original_filename,
                "duration_seconds": v.duration_seconds or 0.0,
                "resolution": f"{v.width}x{v.height}" if (v.width and v.height) else "Unavailable",
                "fps": v.fps or "Unavailable",
                "codec": v.video_codec or "Unavailable",
                "vendor": v.vendor or "Unavailable",
                "channel": v.channel_index if v.channel_index is not None else "Unavailable",
            }
            for v in video_evidence[:10]  # First 10 for overview
        ]

        # Section F: Recovery Results
        recovery_candidates = self.db.query(RecoveryCandidate).filter(RecoveryCandidate.case_id == case.id).all()
        recovery_summary = {
            "total_candidates_found": len(recovery_candidates),
            "recovered_evidence_created": recovered_count,
            "candidates": [
                {
                    "candidate_identifier": rc.candidate_identifier,
                    "offset": getattr(rc, "source_offset", None) if getattr(rc, "source_offset", None) is not None else getattr(rc, "offset", 0),
                    "size_bytes": rc.size_bytes,
                    "detected_format": rc.detected_format,
                    "vendor": rc.vendor or "Unavailable",
                    "validation_state": rc.status.value if hasattr(rc.status, "value") else str(rc.status),
                    "confidence": f"{int((getattr(rc, 'confidence', None) or getattr(rc, 'validation_confidence', 0.0)) * 100)}%",
                }
                for rc in recovery_candidates[:15]
            ]
        }

        # Section G: AI Analysis Results
        ai_findings = self.db.query(AIFinding).filter(AIFinding.case_id == case.id).order_by(AIFinding.created_at.desc()).limit(20).all()
        ai_summary = {
            "total_findings": ai_findings_count,
            "recent_findings": [
                {
                    "finding_identifier": f.finding_identifier,
                    "class_name": getattr(f, "object_class", None) or getattr(f, "class_name", "Unknown"),
                    "confidence_label": f"Model confidence: {int(f.confidence * 100)}%",
                    "media_time": f"{(getattr(f, 'media_time', None) if getattr(f, 'media_time', None) is not None else getattr(f, 'media_time_seconds', 0.0)):.2f}s" if (getattr(f, 'media_time', None) is not None or getattr(f, 'media_time_seconds', None) is not None) else "Unavailable",
                    "cctv_timestamp": (getattr(f, "source_timestamp", None) or getattr(f, "cctv_timestamp", None)).isoformat() if (getattr(f, "source_timestamp", None) or getattr(f, "cctv_timestamp", None)) else "Unavailable",
                    "channel": getattr(f, "channel", None) if getattr(f, "channel", None) is not None else getattr(f, "channel_index", "Unavailable"),
                    "frame_number": f.frame_number if f.frame_number is not None else "Unavailable",
                }
                for f in ai_findings
            ]
        }

        # Section H: Timeline Highlights
        timeline_events = (
            self.db.query(TimelineEvent)
            .filter(TimelineEvent.case_id == case.id)
            .order_by(TimelineEvent.source_timestamp.asc().nulls_last(), TimelineEvent.created_at.asc())
            .limit(15)
            .all()
        )
        timeline_summary = [
            {
                "event_type": t.event_type.value if hasattr(t.event_type, "value") else str(t.event_type),
                "timestamp": (t.source_timestamp or t.normalized_timestamp or t.created_at).isoformat() if (t.source_timestamp or t.normalized_timestamp or t.created_at) else "Unavailable",
                "label": t.title,
                "description": t.description or "",
                "channel": t.channel_id if t.channel_id is not None else "Unavailable",
            }
            for t in timeline_events
        ]

        # Section I: Integrity Verification Summary
        integrity_summary = {
            "total_evidence_evaluated": len(evidence_list),
            "verified_matching_count": verified_count,
            "mismatch_variance_count": mismatch_count,
            "unverified_pending_count": unverified_count,
            "overall_integrity_status": "COMPROMISED" if mismatch_count > 0 else ("VERIFIED" if verified_count > 0 else "UNVERIFIED"),
        }

        # Section J: Chain of Custody Excerpt
        custody_events = (
            self.db.query(CustodyEvent)
            .filter(CustodyEvent.case_id == case.id)
            .order_by(CustodyEvent.timestamp.asc())
            .limit(25)
            .all()
        )
        custody_summary = [
            {
                "timestamp_utc": c.timestamp.isoformat() if c.timestamp else "Unavailable",
                "actor": c.actor_username,
                "action": c.action,
                "evidence": c.evidence.evidence_identifier if c.evidence else "Unavailable",
                "sha256": c.sha256,
                "blockchain_status": c.blockchain_status,
                "blockchain_tx_id": c.blockchain_tx_id or "Unavailable",
            }
            for c in custody_events
        ]

        # Section K: Blockchain Anchoring Status
        # Handled in blockchain_summary

        # Section L: Examiner Notes
        examiner_notes_text = examiner_notes or "No examiner notes or subjective conclusions entered for this report."

        # Section M: Report Integrity Information (Filled during export with SHA-256)
        return {
            "report_title": f"Comprehensive Forensic Investigation Report — {case.case_identifier}",
            "report_type": "CASE_SUMMARY",
            "case_info": case_info,
            "scope": scope,
            "evidence_inventory": evidence_inventory,
            "device_summary": device_summary,
            "acquisition_summary": acquisition_summary,
            "video_summary": video_summary,
            "recovery_summary": recovery_summary,
            "ai_summary": ai_summary,
            "timeline_summary": timeline_summary,
            "integrity_summary": integrity_summary,
            "custody_summary": custody_summary,
            "blockchain_summary": blockchain_summary,
            "examiner_notes": examiner_notes_text,
            "examiner_metadata": {
                "user_id": examiner.id,
                "username": examiner.username,
                "display_name": examiner.display_name or examiner.username,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "counts": {
                "evidence_count": len(evidence_list),
                "device_count": len(devices),
                "acquisition_count": len(acquisitions),
                "recovered_evidence_count": recovered_count,
                "ai_finding_count": ai_findings_count,
            }
        }

    # =========================================================================
    # 2. EVIDENCE REPORT
    # =========================================================================
    def generate_evidence_report(
        self,
        case: Case,
        examiner: User,
        examiner_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates detailed Evidence Inventory Report.
        """
        evidence_list = self.db.query(Evidence).filter(Evidence.case_id == case.id).order_by(Evidence.id.asc()).all()

        records = []
        for e in evidence_list:
            device_str = "Unavailable"
            if e.device_id:
                dev = self.db.query(Device).filter(Device.id == e.device_id).first()
                if dev:
                    d_name = getattr(dev, "name", None) or f"{dev.manufacturer or ''} {dev.model or ''}".strip() or dev.device_identifier
                    device_str = f"{d_name} ({dev.device_identifier})"

            acq_str = "Unavailable"
            if e.acquisition_id:
                acq = self.db.query(Acquisition).filter(Acquisition.id == e.acquisition_id).first()
                if acq:
                    acq_m = getattr(acq, "acquisition_method", None) or getattr(acq, "method", "FILE_COPY")
                    acq_m_val = acq_m.value if hasattr(acq_m, 'value') else str(acq_m)
                    acq_str = f"{acq.acquisition_identifier} [{acq_m_val}]"

            parent_str = "Unavailable"
            if e.parent_evidence_id:
                parent = self.db.query(Evidence).filter(Evidence.id == e.parent_evidence_id).first()
                if parent:
                    parent_str = f"{parent.evidence_identifier} ({parent.original_filename})"

            records.append({
                "evidence_identifier": e.evidence_identifier,
                "original_filename": e.original_filename,
                "evidence_status": e.evidence_status.value if hasattr(e.evidence_status, "value") else str(e.evidence_status),
                "source_type": e.source_type or "Unavailable",
                "device": device_str,
                "acquisition": acq_str,
                "vendor": e.vendor or "Unavailable",
                "container_format": e.container or e.file_extension or "Unavailable",
                "proprietary_status": "Proprietary" if e.proprietary_format else "Standard",
                "proprietary_format": e.proprietary_format or "Unavailable",
                "size_bytes": e.size_bytes,
                "sha256": e.sha256 or "Unavailable",
                "md5": e.md5_reference or "Unavailable",
                "import_timestamp": e.created_at.isoformat() if e.created_at else "Unavailable",
                "parent_evidence": parent_str,
                "derived_operation": e.derived_operation or "Unavailable",
                "integrity_status": e.integrity_status.value if hasattr(e.integrity_status, "value") else str(e.integrity_status),
                "blockchain_status": e.blockchain_status or "UNAVAILABLE",
                "blockchain_tx_id": e.blockchain_tx_id or "Unavailable",
                "blockchain_anchored_at": e.blockchain_anchored_at.isoformat() if e.blockchain_anchored_at else "Unavailable",
            })

        return {
            "report_title": f"Evidence Inventory & Cryptographic Integrity Report — {case.case_identifier}",
            "report_type": "EVIDENCE_REPORT",
            "case_identifier": case.case_identifier,
            "case_name": case.name,
            "total_evidence_count": len(records),
            "evidence_records": records,
            "examiner_notes": examiner_notes or "No examiner notes entered.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": examiner.username,
        }

    # =========================================================================
    # 3. VIDEO SUMMARY REPORT
    # =========================================================================
    def generate_video_report(
        self,
        case: Case,
        examiner: User,
        examiner_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates Unified Video Representation Report for video evidence in case.
        """
        video_evidence = (
            self.db.query(Evidence)
            .filter(Evidence.case_id == case.id)
            .order_by(Evidence.id.asc())
            .all()
        )

        records = []
        for v in video_evidence:
            # Check if this is video media
            is_vid = (v.media_type and "video" in v.media_type.lower()) or (v.file_extension in (".mp4", ".dav", ".mkv", ".avi", ".ts"))
            if not is_vid:
                continue

            # Fetch linked timeline events
            timeline_events = (
                self.db.query(TimelineEvent)
                .filter(TimelineEvent.case_id == case.id, TimelineEvent.evidence_id == v.id)
                .order_by(TimelineEvent.source_timestamp.asc().nulls_last(), TimelineEvent.created_at.asc())
                .all()
            )

            records.append({
                "evidence_identifier": v.evidence_identifier,
                "filename": v.original_filename,
                "vendor": v.vendor or "Generic / Standard",
                "container_format": v.container or v.file_extension or "Unavailable",
                "proprietary_format": v.proprietary_format or "Standard Stream",
                "channel_index": v.channel_index if v.channel_index is not None else "Unavailable",
                "duration_seconds": v.duration_seconds or 0.0,
                "start_timestamp_osd": v.start_time_osd.isoformat() if v.start_time_osd else "Unavailable",
                "end_timestamp_osd": v.end_time_osd.isoformat() if v.end_time_osd else "Unavailable",
                "resolution": f"{v.width}x{v.height}" if (v.width and v.height) else "Unavailable",
                "fps": f"{v.fps:.2f}" if v.fps else "Unavailable",
                "video_codec": v.video_codec or "Unavailable",
                "audio_codec": v.audio_codec or "Unavailable / None",
                "bitrate_kbps": f"{v.bitrate_kbps} kbps" if v.bitrate_kbps else "Unavailable",
                "native_playback_support": "Yes" if v.file_extension in (".mp4", ".webm") else "Transmuxed Proxy Required",
                "proxy_availability": "Available" if (v.parent_evidence_id or v.derived_operation) else "Not Required / Original",
                "sha256": v.sha256 or "Unavailable",
                "timeline_events_count": len(timeline_events),
                "timeline_highlights": [
                    {
                        "event_type": te.event_type.value if hasattr(te.event_type, "value") else str(te.event_type),
                        "timestamp": (te.source_timestamp or te.normalized_timestamp or te.created_at).isoformat() if (te.source_timestamp or te.normalized_timestamp or te.created_at) else "Unavailable",
                        "label": te.title,
                        "description": te.description or "",
                    }
                    for te in timeline_events[:10]
                ]
            })

        return {
            "report_title": f"Unified Video Representation Report — {case.case_identifier}",
            "report_type": "VIDEO_SUMMARY",
            "case_identifier": case.case_identifier,
            "case_name": case.name,
            "total_video_streams": len(records),
            "video_streams": records,
            "examiner_notes": examiner_notes or "No examiner notes entered.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": examiner.username,
        }

    # =========================================================================
    # 4. RECOVERY REPORT
    # =========================================================================
    def generate_recovery_report(
        self,
        case: Case,
        examiner: User,
        examiner_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates Forensic Video/Data Recovery (Carving) Report.
        """
        scan_jobs = (
            self.db.query(RecoveryScanJob)
            .filter(RecoveryScanJob.case_id == case.id)
            .order_by(RecoveryScanJob.created_at.desc())
            .all()
        )

        job_records = []
        for job in scan_jobs:
            source_ev = self.db.query(Evidence).filter(Evidence.id == job.source_evidence_id).first()
            candidates = (
                self.db.query(RecoveryCandidate)
                .filter(RecoveryCandidate.scan_job_id == job.id)
                .order_by(getattr(RecoveryCandidate, "source_offset", RecoveryCandidate.id).asc())
                .all()
            )

            cand_list = []
            for c in candidates:
                rec_ev_str = "Unavailable"
                rec_ev_hash = "Unavailable"
                if c.recovered_evidence_id:
                    rev = self.db.query(Evidence).filter(Evidence.id == c.recovered_evidence_id).first()
                    if rev:
                        rec_ev_str = rev.evidence_identifier
                        rec_ev_hash = rev.sha256 or "Unavailable"

                cand_list.append({
                    "candidate_identifier": c.candidate_identifier,
                    "offset_bytes": getattr(c, "source_offset", None) if getattr(c, "source_offset", None) is not None else getattr(c, "offset", 0),
                    "size_bytes": c.size_bytes,
                    "detected_format": c.detected_format,
                    "vendor": c.vendor or "Generic",
                    "validation_state": c.status.value if hasattr(c.status, "value") else str(c.status),
                    "validation_confidence": f"{int((getattr(c, 'confidence', None) or getattr(c, 'validation_confidence', 0.0)) * 100)}%",
                    "recovered_evidence_identifier": rec_ev_str,
                    "recovered_evidence_sha256": rec_ev_hash,
                })

            job_records.append({
                "job_identifier": getattr(job, "scan_identifier", None) or getattr(job, "job_identifier", "Unavailable"),
                "source_evidence_identifier": source_ev.evidence_identifier if source_ev else "Unavailable",
                "source_filename": source_ev.original_filename if source_ev else "Unavailable",
                "source_type": source_ev.source_type if source_ev else "Unavailable",
                "source_sha256": source_ev.sha256 if source_ev else "Unavailable",
                "scan_method": getattr(job, "method", None) or "SIGNATURE_AND_STRUCTURE_CARVING",
                "scan_status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "started_at": job.started_at.isoformat() if job.started_at else "Unavailable",
                "completed_at": job.completed_at.isoformat() if job.completed_at else "Unavailable",
                "candidates_count": len(cand_list),
                "candidates": cand_list,
            })

        # All recovery candidates across case
        all_candidates = self.db.query(RecoveryCandidate).filter(RecoveryCandidate.case_id == case.id).all()

        return {
            "report_title": f"Forensic Video & Data Recovery Report — {case.case_identifier}",
            "report_type": "RECOVERY_REPORT",
            "case_identifier": case.case_identifier,
            "case_name": case.name,
            "total_scan_jobs": len(job_records),
            "total_candidates_detected": len(all_candidates),
            "scan_jobs": job_records,
            "examiner_notes": examiner_notes or "No examiner notes entered.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": examiner.username,
        }

    # =========================================================================
    # 5. AI REPORT
    # =========================================================================
    def generate_ai_report(
        self,
        case: Case,
        examiner: User,
        examiner_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates AI Video Analysis Report.
        Strictly labels confidence as 'Model confidence' with no claims of identification certainty.
        """
        jobs = (
            self.db.query(AIAnalysisJob)
            .filter(AIAnalysisJob.case_id == case.id)
            .order_by(AIAnalysisJob.created_at.desc())
            .all()
        )

        job_records = []
        for j in jobs:
            ev = self.db.query(Evidence).filter(Evidence.id == j.evidence_id).first()
            findings = (
                self.db.query(AIFinding)
                .filter(AIFinding.job_id == j.id)
                .order_by(AIFinding.frame_number.asc())
                .all()
            )

            f_list = []
            for f in findings:
                # Parse bounding box if present
                bbox_dict = None
                if f.bounding_box:
                    try:
                        bbox_dict = json.loads(f.bounding_box) if isinstance(f.bounding_box, str) else f.bounding_box
                    except Exception:
                        bbox_dict = str(f.bounding_box)

                cls_name = getattr(f, "object_class", None) or getattr(f, "class_name", "Unknown")
                m_time = getattr(f, "media_time", None) if getattr(f, "media_time", None) is not None else getattr(f, "media_time_seconds", None)
                ts = getattr(f, "source_timestamp", None) or getattr(f, "cctv_timestamp", None)
                ch = getattr(f, "channel", None) if getattr(f, "channel", None) is not None else getattr(f, "channel_index", "Unavailable")

                f_list.append({
                    "finding_identifier": f.finding_identifier,
                    "class_name": cls_name,
                    "model_confidence": f"Model confidence: {int(f.confidence * 100)}%",
                    "confidence_decimal": f.confidence,
                    "media_time": f"{m_time:.2f}s" if m_time is not None else "Unavailable",
                    "cctv_timestamp": ts.isoformat() if ts else "Unavailable",
                    "channel_index": ch,
                    "frame_number": f.frame_number if f.frame_number is not None else "Unavailable",
                    "bounding_box": bbox_dict or "Unavailable",
                    "motion_detected": getattr(f, "motion_detected", False) or (cls_name.lower() == "motion"),
                })

            cfg = {}
            if getattr(j, "config_json", None):
                try:
                    cfg = json.loads(j.config_json) if isinstance(j.config_json, str) else j.config_json
                except Exception:
                    pass

            job_records.append({
                "job_identifier": j.job_identifier,
                "evidence_identifier": ev.evidence_identifier if ev else "Unavailable",
                "evidence_filename": ev.original_filename if ev else "Unavailable",
                "model_name": getattr(j, "model_name", None) or cfg.get("model_name", "YOLOv8n + OpenCV MOG2"),
                "model_version": getattr(j, "model_version", None) or cfg.get("model_version", "v8.0"),
                "sampling_rate_fps": getattr(j, "sample_rate_fps", None) or cfg.get("sample_rate_fps", 1.0),
                "confidence_threshold": f"{int((getattr(j, 'confidence_threshold', None) or cfg.get('confidence_threshold', 0.25)) * 100)}%",
                "status": j.status.value if hasattr(j.status, "value") else str(j.status),
                "started_at": j.started_at.isoformat() if j.started_at else "Unavailable",
                "completed_at": j.completed_at.isoformat() if j.completed_at else "Unavailable",
                "frames_analyzed": getattr(j, "total_frames_analyzed", None) or getattr(j, "frames_analyzed", 0),
                "findings_count": len(f_list),
                "findings": f_list,
            })

        total_findings = self.db.query(AIFinding).filter(AIFinding.case_id == case.id).count()

        return {
            "report_title": f"AI Video Analytics & Object/Motion Detection Report — {case.case_identifier}",
            "report_type": "AI_REPORT",
            "case_identifier": case.case_identifier,
            "case_name": case.name,
            "disclaimer": "AI findings represent automated algorithmic pattern detections with model statistical confidence. They do not constitute conclusive forensic determinations of identity, culpability, or real-world physical certainty.",
            "total_ai_jobs": len(job_records),
            "total_findings": total_findings,
            "jobs": job_records,
            "examiner_notes": examiner_notes or "No examiner notes entered.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": examiner.username,
        }

    # =========================================================================
    # 6. CHAIN OF CUSTODY REPORT
    # =========================================================================
    def generate_chain_of_custody_report(
        self,
        case: Case,
        examiner: User,
        examiner_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates full Chronological Chain of Custody Report using existing audit
        and custody events without creating duplicate entries.
        """
        # Query existing CustodyEvent records
        custody_events = (
            self.db.query(CustodyEvent)
            .filter(CustodyEvent.case_id == case.id)
            .order_by(CustodyEvent.timestamp.asc())
            .all()
        )

        # Also query AuditLog records to provide exhaustive chronological coverage
        audit_logs = (
            self.db.query(AuditLog)
            .filter(AuditLog.case_id == case.id)
            .order_by(AuditLog.created_at.asc())
            .all()
        )

        events_table = []

        # Build chronological table
        # Priority: CustodyEvent has rich blockchain status, AuditLog has all operations
        custody_by_audit_id = {c.audit_log_id: c for c in custody_events if c.audit_log_id}

        for log in audit_logs:
            custody = custody_by_audit_id.get(log.id)
            
            # Extract evidence reference
            ev_id = "Unavailable"
            sha = "Unavailable"
            bc_status = "NOT_ANCHORED"
            tx_id = "Unavailable"

            if custody:
                ev_id = custody.evidence.evidence_identifier if custody.evidence else "Unavailable"
                sha = custody.sha256 or "Unavailable"
                bc_status = custody.blockchain_status or "NOT_ANCHORED"
                tx_id = custody.blockchain_tx_id or "Unavailable"
            elif log.target_identifier:
                ev_id = log.target_identifier
                # Try to look up evidence sha
                ev_lookup = self.db.query(Evidence).filter(
                    Evidence.case_id == case.id,
                    Evidence.evidence_identifier == log.target_identifier
                ).first()
                if ev_lookup:
                    sha = ev_lookup.sha256 or "Unavailable"
                    bc_status = ev_lookup.blockchain_status or "NOT_ANCHORED"
                    tx_id = ev_lookup.blockchain_tx_id or "Unavailable"

            # Parse module
            action = log.action
            module = "General"
            if action.startswith("BLOCKCHAIN_"):
                module = "Blockchain"
            elif "DERIVED" in action or "FRAME" in action or "TRANSMUX" in action:
                module = "Video Analysis"
            elif "INTEGRITY" in action:
                module = "Integrity"
            elif "ACQUISITION" in action:
                module = "Acquisition"
            elif "RECOVERY" in action or "CARVE" in action:
                module = "Recovery"
            elif "AI_" in action:
                module = "AI Analysis"
            elif "EVIDENCE_" in action:
                module = "Evidence"
            elif "REPORT_" in action:
                module = "Reporting"

            events_table.append({
                "timestamp_utc": log.created_at.isoformat() if log.created_at else "Unavailable",
                "actor": log.user.username if log.user else "System",
                "action": action,
                "module": module,
                "target_evidence": ev_id,
                "result": "SUCCESS" if not action.endswith("_FAILED") else "FAILED",
                "sha256": sha,
                "blockchain_status": bc_status,
                "transaction_id": tx_id,
                "details": log.details or "",
            })

        # Append any CustodyEvents not linked to audit_log_id
        unlinked_custody = [c for c in custody_events if not c.audit_log_id]
        for c in unlinked_custody:
            events_table.append({
                "timestamp_utc": c.timestamp.isoformat() if c.timestamp else "Unavailable",
                "actor": c.actor_username,
                "action": c.action,
                "module": "Chain of Custody",
                "target_evidence": c.evidence.evidence_identifier if c.evidence else "Unavailable",
                "result": "SUCCESS",
                "sha256": c.sha256,
                "blockchain_status": c.blockchain_status,
                "transaction_id": c.blockchain_tx_id or "Unavailable",
                "details": f"Custody event {c.event_identifier} (prev ref: {c.previous_event_reference or 'genesis'})",
            })

        # Sort table chronologically
        events_table.sort(key=lambda x: x["timestamp_utc"])

        return {
            "report_title": f"Forensic Chain of Custody & Audit Ledger — {case.case_identifier}",
            "report_type": "CHAIN_OF_CUSTODY",
            "case_identifier": case.case_identifier,
            "case_name": case.name,
            "total_custody_records": len(events_table),
            "events": events_table,
            "examiner_notes": examiner_notes or "No examiner notes entered.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": examiner.username,
        }
