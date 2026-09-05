from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.case import CaseMember
from app.dependencies.auth import (
    require_case_member,
    require_case_investigator_or_admin,
)
from app.schemas.report import (
    ReportCreateRequest,
    ReportSummaryResponse,
    ReportDetailResponse,
    ReportIntegrityVerifyResponse,
)
from app.services.report_service import report_service

router = APIRouter()


@router.post("/{case_identifier}/reports/generate", response_model=ReportDetailResponse)
def generate_report_endpoint(
    case_identifier: str,
    req: ReportCreateRequest,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db),
):
    """
    Generate a court-admissible forensic report for the case.
    Requires Investigator or Admin role on the case.
    """
    try:
        report = report_service.generate_report(
            db=db,
            case=member.case,
            examiner=member.user,
            report_type=req.report_type,
            examiner_notes=req.examiner_notes,
            export_format=req.format or "PDF"
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate forensic report: {str(e)}")


@router.get("/{case_identifier}/reports", response_model=List[ReportSummaryResponse])
def list_reports_endpoint(
    case_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    """
    List all generated forensic reports for the active case.
    """
    reports = report_service.list_case_reports(db, member.case.id)
    return reports


@router.get("/{case_identifier}/reports/{report_identifier}", response_model=ReportDetailResponse)
def get_report_detail_endpoint(
    case_identifier: str,
    report_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    """
    Get full metadata, structured payload, and examiner notes for a report.
    """
    report = report_service.get_report_by_identifier(db, member.case.id, report_identifier)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found in this case.")
    return report


@router.get("/{case_identifier}/reports/{report_identifier}/export")
def export_report_endpoint(
    case_identifier: str,
    report_identifier: str,
    format: Optional[str] = Query(None, description="Export format: PDF, HTML, or JSON"),
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    """
    Export/download the forensic report artifact in PDF, HTML, or JSON format.
    """
    try:
        content_bytes, filename, media_type = report_service.export_report_file(
            db=db,
            case=member.case,
            examiner=member.user,
            report_identifier=report_identifier,
            target_format=format
        )
        return Response(
            content=content_bytes,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report export failed: {str(e)}")


@router.post("/{case_identifier}/reports/{report_identifier}/verify", response_model=ReportIntegrityVerifyResponse)
def verify_report_integrity_endpoint(
    case_identifier: str,
    report_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    """
    Verify report file on disk against recorded SHA-256 and blockchain.
    """
    try:
        res = report_service.verify_report_integrity(
            db=db,
            case=member.case,
            examiner=member.user,
            report_identifier=report_identifier
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integrity check failed: {str(e)}")
