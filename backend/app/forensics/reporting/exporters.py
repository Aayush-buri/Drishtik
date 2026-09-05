import os
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas that accumulates pages and renders exact headers,
    footers, case identifier, report reference, and 'Page X of Y'.
    """
    def __init__(self, *args, **kwargs):
        kwargs["pageCompression"] = 0
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.case_id = getattr(self, "case_id", "CASE-UNKNOWN")
        self.report_id = getattr(self, "report_id", "RPT-UNKNOWN")

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_and_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_and_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#4B5563"))  # Gray 600

        page_width, page_height = letter

        # Running Header
        self.drawString(54, page_height - 36, "DRISHTIK")
        self.setFont("Helvetica", 8)
        self.drawString(104, page_height - 36, "—  Digital Video & Forensic Investigation Platform")
        self.drawRightString(page_width - 54, page_height - 36, "FORENSIC EXAMINATION REPORT")

        self.setStrokeColor(colors.HexColor("#D1D5DB"))  # Gray 300
        self.setLineWidth(0.75)
        self.line(54, page_height - 42, page_width - 54, page_height - 42)

        # Running Footer
        self.line(54, 45, page_width - 54, 45)
        self.setFont("Helvetica", 8)
        self.drawString(54, 32, f"Case: {self.case_id}   |   Ref: {self.report_id}   |   CONFIDENTIAL FORENSIC RECORD")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(page_width - 54, 32, page_str)
        self.restoreState()


def make_canvas_factory(case_id: str, report_id: str):
    class ConfiguredNumberedCanvas(NumberedCanvas):
        def __init__(self, *args, **kwargs):
            self.case_id = case_id
            self.report_id = report_id
            super().__init__(*args, **kwargs)
    return ConfiguredNumberedCanvas


class PDFExporter:
    """
    Renders structured forensic report data into professional court-admissible PDF.
    Features:
    - Page numbered ('Page X of Y')
    - Full un-truncated SHA-256 wrapping
    - Structured tables and sections
    - Light forensic styling consistent with Drishtik
    """

    @staticmethod
    def export(data: Dict[str, Any], case_id: str, report_id: str) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54,
            pageCompression=0
        )

        styles = getSampleStyleSheet()
        
        # Custom Typography Styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#111827"),
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=14
        )
        h2_style = ParagraphStyle(
            'SectionH2',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1E3A8A"),  # Indigo 900
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True
        )
        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#374151")
        )
        body_bold = ParagraphStyle(
            'ReportBodyBold',
            parent=body_style,
            fontName='Helvetica-Bold'
        )
        mono_style = ParagraphStyle(
            'ReportMono',
            parent=styles['Normal'],
            fontName='Courier',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#1F2937")
        )
        notes_box_style = ParagraphStyle(
            'NotesBox',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1F2937")
        )

        story = []

        # 1. Header Box
        story.append(Paragraph(data.get("report_title", f"Forensic Examination Report — {case_id}"), title_style))
        report_type = data.get("report_type", "FORENSIC_REPORT")
        gen_time = data.get("generated_at", datetime.now(timezone.utc).isoformat())
        story.append(Paragraph(f"Document Type: <b>{report_type}</b> &nbsp;|&nbsp; Reference: <b>{report_id}</b> &nbsp;|&nbsp; Generated: <b>{gen_time}</b>", subtitle_style))

        # 2. Metadata Grid Table
        meta_data = [
            [
                Paragraph("<b>Case Identifier:</b>", body_style),
                Paragraph(case_id, body_bold),
                Paragraph("<b>Report Ref:</b>", body_style),
                Paragraph(report_id, mono_style)
            ],
            [
                Paragraph("<b>Examiner:</b>", body_style),
                Paragraph(data.get("generated_by", data.get("examiner_metadata", {}).get("username", "Examiner")), body_style),
                Paragraph("<b>Hash Algorithm:</b>", body_style),
                Paragraph("SHA-256 (Primary) / MD5", body_style)
            ],
            [
                Paragraph("<b>Status:</b>", body_style),
                Paragraph("<font color='#059669'><b>OFFICIAL FORENSIC RECORD</b></font>", body_style),
                Paragraph("<b>Blockchain Anchor:</b>", body_style),
                Paragraph(f"<b>{data.get('blockchain_summary', {}).get('network_status', 'UNAVAILABLE')}</b>", body_style)
            ]
        ]
        meta_table = Table(meta_data, colWidths=[100, 150, 95, 159])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#F3F4F6")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # 3. Examiner Notes / Subjective Conclusions
        examiner_notes = data.get("examiner_notes", "")
        if examiner_notes:
            story.append(Paragraph("Investigator Examination Notes & Conclusions", h2_style))
            notes_table = Table([[Paragraph(examiner_notes, notes_box_style)]], colWidths=[504])
            notes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),  # Blue 50
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#93C5FD")),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(notes_table)
            story.append(Spacer(1, 10))

        # 4. Report Type Specific Content
        if report_type in ("CASE_SUMMARY", "FINAL_INVESTIGATION"):
            PDFExporter._build_case_summary_section(story, data, h2_style, body_style, mono_style)
        elif report_type == "EVIDENCE_REPORT":
            PDFExporter._build_evidence_section(story, data, h2_style, body_style, mono_style)
        elif report_type == "VIDEO_SUMMARY":
            PDFExporter._build_video_section(story, data, h2_style, body_style, mono_style)
        elif report_type == "RECOVERY_REPORT":
            PDFExporter._build_recovery_section(story, data, h2_style, body_style, mono_style)
        elif report_type == "AI_REPORT":
            PDFExporter._build_ai_section(story, data, h2_style, body_style, mono_style)
        elif report_type == "CHAIN_OF_CUSTODY":
            PDFExporter._build_custody_section(story, data, h2_style, body_style, mono_style)

        # 5. Attestation Block
        story.append(Spacer(1, 14))
        attest_text = (
            "I hereby attest that the digital evidence catalogued in this report was processed strictly in accordance "
            "with forensic science digital evidence principles. Original evidence bitstreams have remained unaltered. "
            "All derived images, frames, and carved streams were generated deterministically and verified cryptographically."
        )
        story.append(Paragraph("<b>Examiner Attestation</b>", h2_style))
        story.append(Paragraph(attest_text, body_style))
        story.append(Spacer(1, 14))

        sig_data = [
            [
                Paragraph("<b>Examiner Signature:</b> ___________________________", body_style),
                Paragraph(f"<b>Date:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", body_style)
            ]
        ]
        sig_table = Table(sig_data, colWidths=[320, 184])
        sig_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        story.append(sig_table)

        # Build document with custom canvas factory
        canvas_factory = make_canvas_factory(case_id, report_id)
        doc.build(story, canvasmaker=canvas_factory)
        return buffer.getvalue()

    # --- Section Helpers ---
    @staticmethod
    def _build_case_summary_section(story, data, h2_style, body_style, mono_style):
        counts = data.get("counts", {})
        story.append(Paragraph("1. Case Overview & Forensic Counts", h2_style))
        overview_data = [
            [
                Paragraph("<b>Total Evidence Items:</b>", body_style),
                Paragraph(str(counts.get("evidence_count", 0)), body_style),
                Paragraph("<b>Forensic Acquisitions:</b>", body_style),
                Paragraph(str(counts.get("acquisition_count", 0)), body_style),
            ],
            [
                Paragraph("<b>Recovered Carved Streams:</b>", body_style),
                Paragraph(str(counts.get("recovered_evidence_count", 0)), body_style),
                Paragraph("<b>AI Detections Catalogued:</b>", body_style),
                Paragraph(str(counts.get("ai_finding_count", 0)), body_style),
            ]
        ]
        t = Table(overview_data, colWidths=[140, 112, 140, 112])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

        # Evidence Inventory Excerpt
        ev_list = data.get("evidence_inventory", [])
        if ev_list:
            story.append(Paragraph(f"2. Evidence Inventory ({len(ev_list)} items)", h2_style))
            PDFExporter._render_evidence_table(story, ev_list[:15], body_style, mono_style)

    @staticmethod
    def _build_evidence_section(story, data, h2_style, body_style, mono_style):
        ev_list = data.get("evidence_records", [])
        story.append(Paragraph(f"Evidence Inventory & Hash Records ({len(ev_list)} items)", h2_style))
        PDFExporter._render_evidence_table(story, ev_list, body_style, mono_style)

    @staticmethod
    def _render_evidence_table(story, ev_list, body_style, mono_style):
        table_rows = [
            [
                Paragraph("<b>Evidence ID</b>", body_style),
                Paragraph("<b>File Name</b>", body_style),
                Paragraph("<b>Status</b>", body_style),
                Paragraph("<b>Size</b>", body_style),
                Paragraph("<b>SHA-256 Hash</b>", body_style),
                Paragraph("<b>Blockchain</b>", body_style)
            ]
        ]
        for e in ev_list:
            sha = e.get("sha256", "Unavailable")
            table_rows.append([
                Paragraph(e.get("evidence_identifier", ""), body_style),
                Paragraph(e.get("original_filename", ""), body_style),
                Paragraph(e.get("evidence_status", e.get("status", "")), body_style),
                Paragraph(f"{e.get('size_bytes', 0):,} B", body_style),
                Paragraph(sha, mono_style),
                Paragraph(e.get("blockchain_status", "UNAVAILABLE"), body_style)
            ])
        t = Table(table_rows, colWidths=[65, 95, 55, 55, 174, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    @staticmethod
    def _build_video_section(story, data, h2_style, body_style, mono_style):
        streams = data.get("video_streams", [])
        story.append(Paragraph(f"Unified Video Representation ({len(streams)} streams)", h2_style))
        table_rows = [
            [
                Paragraph("<b>Evidence ID</b>", body_style),
                Paragraph("<b>Resolution / FPS</b>", body_style),
                Paragraph("<b>Duration</b>", body_style),
                Paragraph("<b>Codec / Vendor</b>", body_style),
                Paragraph("<b>SHA-256 Hash</b>", body_style),
            ]
        ]
        for s in streams:
            table_rows.append([
                Paragraph(s.get("evidence_identifier", ""), body_style),
                Paragraph(f"{s.get('resolution', '')} @ {s.get('fps', '')} fps", body_style),
                Paragraph(f"{s.get('duration_seconds', 0):.1f}s", body_style),
                Paragraph(f"{s.get('video_codec', '')} ({s.get('vendor', '')})", body_style),
                Paragraph(s.get("sha256", "Unavailable"), mono_style),
            ])
        t = Table(table_rows, colWidths=[75, 95, 55, 105, 174])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    @staticmethod
    def _build_recovery_section(story, data, h2_style, body_style, mono_style):
        jobs = data.get("scan_jobs", [])
        story.append(Paragraph(f"Recovery Scan Jobs & Carved Candidates ({len(jobs)} jobs)", h2_style))
        for j in jobs:
            story.append(Paragraph(f"<b>Job:</b> {j.get('job_identifier')} &nbsp;|&nbsp; <b>Source:</b> {j.get('source_evidence_identifier')} ({j.get('source_filename')})", body_style))
            story.append(Paragraph(f"<b>Source SHA-256:</b> <font face='Courier' size='7'>{j.get('source_sha256')}</font>", body_style))
            candidates = j.get("candidates", [])
            if candidates:
                cand_rows = [
                    [
                        Paragraph("<b>Candidate ID</b>", body_style),
                        Paragraph("<b>Offset / Size</b>", body_style),
                        Paragraph("<b>Format / Vendor</b>", body_style),
                        Paragraph("<b>Validation</b>", body_style),
                        Paragraph("<b>Recovered ID</b>", body_style),
                    ]
                ]
                for c in candidates:
                    cand_rows.append([
                        Paragraph(c.get("candidate_identifier", ""), body_style),
                        Paragraph(f"{c.get('offset_bytes', 0):,} B / {c.get('size_bytes', 0):,} B", body_style),
                        Paragraph(f"{c.get('detected_format', '')} ({c.get('vendor', '')})", body_style),
                        Paragraph(f"{c.get('validation_state', '')} ({c.get('validation_confidence', '')})", body_style),
                        Paragraph(c.get("recovered_evidence_identifier", "Unavailable"), body_style),
                    ])
                t = Table(cand_rows, colWidths=[90, 110, 110, 94, 100])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
            story.append(Spacer(1, 6))

    @staticmethod
    def _build_ai_section(story, data, h2_style, body_style, mono_style):
        jobs = data.get("jobs", [])
        disclaimer = data.get("disclaimer", "")
        if disclaimer:
            disc_table = Table([[Paragraph(f"<b>Notice:</b> {disclaimer}", body_style)]], colWidths=[504])
            disc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),  # Amber 50
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#FCD34D")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(disc_table)
            story.append(Spacer(1, 6))

        story.append(Paragraph(f"AI Detection Jobs & Findings ({data.get('total_findings', 0)} findings)", h2_style))
        for j in jobs:
            story.append(Paragraph(f"<b>Job:</b> {j.get('job_identifier')} &nbsp;|&nbsp; <b>Model:</b> {j.get('model_name')} &nbsp;|&nbsp; <b>Evidence:</b> {j.get('evidence_identifier')}", body_style))
            findings = j.get("findings", [])
            if findings:
                f_rows = [
                    [
                        Paragraph("<b>Finding ID</b>", body_style),
                        Paragraph("<b>Class</b>", body_style),
                        Paragraph("<b>Model Confidence</b>", body_style),
                        Paragraph("<b>Media Time</b>", body_style),
                        Paragraph("<b>Frame</b>", body_style),
                    ]
                ]
                for f in findings:
                    f_rows.append([
                        Paragraph(f.get("finding_identifier", ""), body_style),
                        Paragraph(f.get("class_name", ""), body_style),
                        Paragraph(f.get("model_confidence", ""), body_style),
                        Paragraph(f.get("media_time", ""), body_style),
                        Paragraph(str(f.get("frame_number", "")), body_style),
                    ])
                t = Table(f_rows, colWidths=[100, 100, 114, 95, 95])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
            story.append(Spacer(1, 6))

    @staticmethod
    def _build_custody_section(story, data, h2_style, body_style, mono_style):
        events = data.get("events", [])
        story.append(Paragraph(f"Chronological Chain of Custody & Audit Ledger ({len(events)} events)", h2_style))
        table_rows = [
            [
                Paragraph("<b>Timestamp (UTC)</b>", body_style),
                Paragraph("<b>Actor</b>", body_style),
                Paragraph("<b>Action</b>", body_style),
                Paragraph("<b>Target</b>", body_style),
                Paragraph("<b>SHA-256 Hash</b>", body_style),
                Paragraph("<b>Blockchain</b>", body_style),
            ]
        ]
        for ev in events:
            sha = ev.get("sha256", "Unavailable")
            table_rows.append([
                Paragraph(ev.get("timestamp_utc", "")[:19].replace("T", " "), mono_style),
                Paragraph(ev.get("actor", ""), body_style),
                Paragraph(ev.get("action", ""), body_style),
                Paragraph(ev.get("target_evidence", ""), body_style),
                Paragraph(sha, mono_style),
                Paragraph(ev.get("blockchain_status", "UNAVAILABLE"), body_style),
            ])
        t = Table(table_rows, colWidths=[90, 60, 95, 65, 134, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t)


class HTMLExporter:
    """
    Renders structured forensic report data into printable HTML with
    embedded CSS, page header/footer for print, and light forensic styling.
    """

    @staticmethod
    def export(data: Dict[str, Any], case_id: str, report_id: str) -> str:
        report_title = data.get("report_title", f"Forensic Examination Report — {case_id}")
        report_type = data.get("report_type", "FORENSIC_REPORT")
        gen_time = data.get("generated_at", datetime.now(timezone.utc).isoformat())
        examiner = data.get("generated_by", data.get("examiner_metadata", {}).get("username", "Examiner"))
        examiner_notes = data.get("examiner_notes", "")
        blockchain_status = data.get("blockchain_summary", {}).get("network_status", "UNAVAILABLE")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{report_title}</title>
  <style>
    @page {{
      size: letter;
      margin: 18mm 15mm 18mm 15mm;
      @top-center {{
        content: "DRISHTIK — Digital Video & Forensic Investigation Platform";
        font-family: sans-serif;
        font-size: 8pt;
        color: #6b7280;
      }}
      @bottom-left {{
        content: "Case: {case_id}  |  Ref: {report_id}  |  CONFIDENTIAL FORENSIC RECORD";
        font-family: sans-serif;
        font-size: 8pt;
        color: #6b7280;
      }}
      @bottom-right {{
        content: "Page " counter(page) " of " counter(pages);
        font-family: sans-serif;
        font-size: 8pt;
        color: #6b7280;
      }}
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 9pt;
      line-height: 1.4;
      color: #111827;
      background: #ffffff;
      margin: 0;
      padding: 20px;
    }}
    .header-bar {{
      border-bottom: 2px solid #111827;
      padding-bottom: 12px;
      margin-bottom: 16px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }}
    .header-title {{
      font-size: 16pt;
      font-weight: bold;
      color: #111827;
      margin: 0 0 4px 0;
    }}
    .header-subtitle {{
      font-size: 8.5pt;
      color: #4b5563;
      margin: 0;
    }}
    .meta-box {{
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 4px;
      padding: 10px 14px;
      margin-bottom: 16px;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      font-size: 8pt;
    }}
    .meta-label {{
      font-weight: bold;
      color: #6b7280;
      text-transform: uppercase;
      font-size: 7pt;
      margin-bottom: 2px;
    }}
    .meta-value {{
      font-weight: 600;
      color: #111827;
    }}
    .notes-box {{
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 4px;
      padding: 10px 14px;
      margin-bottom: 16px;
      font-style: italic;
      color: #1e3a8a;
    }}
    h2 {{
      font-size: 10.5pt;
      font-weight: bold;
      color: #1e3a8a;
      border-bottom: 1px solid #e5e7eb;
      padding-bottom: 4px;
      margin: 16px 0 8px 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 8pt;
      margin-bottom: 14px;
    }}
    th {{
      background: #f3f4f6;
      font-weight: bold;
      text-align: left;
      padding: 6px 8px;
      border: 1px solid #d1d5db;
    }}
    td {{
      padding: 5px 8px;
      border: 1px solid #e5e7eb;
      vertical-align: top;
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 7.5pt;
      word-break: break-all;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 7pt;
      font-weight: bold;
    }}
    .badge-verified {{ background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }}
    .badge-unavail {{ background: #f3f4f6; color: #4b5563; border: 1px solid #d1d5db; }}
    .attest-box {{
      margin-top: 24px;
      border-top: 1px solid #d1d5db;
      padding-top: 12px;
      font-size: 8pt;
    }}
    @media print {{
      body {{ padding: 0; }}
      .no-print {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="header-bar">
    <div>
      <h1 class="header-title">{report_title}</h1>
      <p class="header-subtitle">DRISHTIK Digital Video & Forensic Investigation Platform</p>
    </div>
    <div style="text-align: right; font-size: 8pt; color: #4b5563;">
      <div>REF: <strong>{report_id}</strong></div>
      <div>DATE: <strong>{gen_time[:10]}</strong></div>
    </div>
  </div>

  <div class="meta-box">
    <div>
      <div class="meta-label">Case Identifier</div>
      <div class="meta-value">{case_id}</div>
    </div>
    <div>
      <div class="meta-label">Report Type</div>
      <div class="meta-value">{report_type}</div>
    </div>
    <div>
      <div class="meta-label">Examiner</div>
      <div class="meta-value">{examiner}</div>
    </div>
    <div>
      <div class="meta-label">Blockchain Status</div>
      <div class="meta-value">{blockchain_status}</div>
    </div>
  </div>

  {f'<div class="notes-box"><strong>Investigator Notes:</strong> {examiner_notes}</div>' if examiner_notes else ''}

  <!-- Structured Payload Render -->
  {HTMLExporter._render_body_sections(data)}

  <div class="attest-box">
    <p><strong>Examiner Attestation:</strong> I hereby attest that the digital evidence catalogued in this report was processed strictly in accordance with forensic digital evidence principles. Original evidence bitstreams have remained unaltered.</p>
    <table style="width: 100%; border: none; margin-top: 16px;">
      <tr style="border: none;">
        <td style="border: none; width: 60%;"><strong>Examiner Signature:</strong> ___________________________</td>
        <td style="border: none; width: 40%; text-align: right;"><strong>Date:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</td>
      </tr>
    </table>
  </div>
</body>
</html>
"""
        return html

    @staticmethod
    def _render_body_sections(data: Dict[str, Any]) -> str:
        report_type = data.get("report_type", "")
        out = []

        if report_type == "EVIDENCE_REPORT" or "evidence_records" in data:
            records = data.get("evidence_records", data.get("evidence_inventory", []))
            out.append(f"<h2>Evidence Inventory ({len(records)} items)</h2>")
            out.append("<table><thead><tr><th>ID</th><th>Filename</th><th>Status</th><th>Size</th><th>SHA-256</th><th>Blockchain</th></tr></thead><tbody>")
            for r in records:
                out.append(f"<tr><td><strong>{r.get('evidence_identifier')}</strong></td><td>{r.get('original_filename')}</td><td>{r.get('evidence_status', r.get('status', ''))}</td><td>{r.get('size_bytes', 0):,} B</td><td class='mono'>{r.get('sha256', 'Unavailable')}</td><td>{r.get('blockchain_status', 'UNAVAILABLE')}</td></tr>")
            out.append("</tbody></table>")

        elif report_type == "VIDEO_SUMMARY" or "video_streams" in data:
            streams = data.get("video_streams", [])
            out.append(f"<h2>Unified Video Streams ({len(streams)} items)</h2>")
            out.append("<table><thead><tr><th>ID</th><th>Filename</th><th>Resolution</th><th>Duration</th><th>Codec / Vendor</th><th>SHA-256</th></tr></thead><tbody>")
            for s in streams:
                out.append(f"<tr><td><strong>{s.get('evidence_identifier')}</strong></td><td>{s.get('filename')}</td><td>{s.get('resolution')} @ {s.get('fps')} fps</td><td>{s.get('duration_seconds', 0):.1f}s</td><td>{s.get('video_codec')} ({s.get('vendor')})</td><td class='mono'>{s.get('sha256')}</td></tr>")
            out.append("</tbody></table>")

        elif report_type == "RECOVERY_REPORT" or "scan_jobs" in data:
            jobs = data.get("scan_jobs", [])
            out.append(f"<h2>Recovery Jobs & Carved Streams ({len(jobs)} jobs)</h2>")
            for j in jobs:
                out.append(f"<p><strong>Job:</strong> {j.get('job_identifier')} | <strong>Source:</strong> {j.get('source_evidence_identifier')} | <strong>SHA-256:</strong> <span class='mono'>{j.get('source_sha256')}</span></p>")
                candidates = j.get("candidates", [])
                if candidates:
                    out.append("<table><thead><tr><th>Candidate ID</th><th>Offset / Size</th><th>Format</th><th>Validation</th><th>Recovered ID</th></tr></thead><tbody>")
                    for c in candidates:
                        out.append(f"<tr><td>{c.get('candidate_identifier')}</td><td>{c.get('offset_bytes', 0):,} B / {c.get('size_bytes', 0):,} B</td><td>{c.get('detected_format')} ({c.get('vendor')})</td><td>{c.get('validation_state')} ({c.get('validation_confidence')})</td><td>{c.get('recovered_evidence_identifier')}</td></tr>")
                    out.append("</tbody></table>")

        elif report_type == "AI_REPORT" or "jobs" in data:
            jobs = data.get("jobs", [])
            out.append(f"<h2>AI Detection Jobs & Findings</h2>")
            for j in jobs:
                out.append(f"<p><strong>Job:</strong> {j.get('job_identifier')} | <strong>Model:</strong> {j.get('model_name')} | <strong>Evidence:</strong> {j.get('evidence_identifier')}</p>")
                findings = j.get("findings", [])
                if findings:
                    out.append("<table><thead><tr><th>Finding ID</th><th>Class</th><th>Model Confidence</th><th>Media Time</th><th>Frame</th></tr></thead><tbody>")
                    for f in findings:
                        out.append(f"<tr><td>{f.get('finding_identifier')}</td><td>{f.get('class_name')}</td><td>{f.get('model_confidence')}</td><td>{f.get('media_time')}</td><td>{f.get('frame_number')}</td></tr>")
                    out.append("</tbody></table>")

        elif report_type == "CHAIN_OF_CUSTODY" or "events" in data:
            events = data.get("events", [])
            out.append(f"<h2>Chronological Chain of Custody ({len(events)} events)</h2>")
            out.append("<table><thead><tr><th>Timestamp (UTC)</th><th>Actor</th><th>Action</th><th>Target</th><th>SHA-256</th><th>Blockchain</th></tr></thead><tbody>")
            for ev in events:
                out.append(f"<tr><td class='mono'>{ev.get('timestamp_utc', '')[:19].replace('T', ' ')}</td><td>{ev.get('actor')}</td><td><strong>{ev.get('action')}</strong></td><td>{ev.get('target_evidence')}</td><td class='mono'>{ev.get('sha256')}</td><td>{ev.get('blockchain_status')}</td></tr>")
            out.append("</tbody></table>")

        elif report_type == "CASE_SUMMARY":
            counts = data.get("counts", {})
            out.append("<h2>1. Forensic Counts</h2>")
            out.append("<table><thead><tr><th>Evidence Count</th><th>Acquisitions</th><th>Recovered Streams</th><th>AI Findings</th></tr></thead><tbody>")
            out.append(f"<tr><td>{counts.get('evidence_count', 0)}</td><td>{counts.get('acquisition_count', 0)}</td><td>{counts.get('recovered_evidence_count', 0)}</td><td>{counts.get('ai_finding_count', 0)}</td></tr>")
            out.append("</tbody></table>")

            ev_list = data.get("evidence_inventory", [])
            if ev_list:
                out.append(f"<h2>2. Evidence Inventory Excerpt ({len(ev_list)} items)</h2>")
                out.append("<table><thead><tr><th>ID</th><th>Filename</th><th>Status</th><th>Size</th><th>SHA-256</th><th>Blockchain</th></tr></thead><tbody>")
                for r in ev_list[:15]:
                    out.append(f"<tr><td><strong>{r.get('evidence_identifier')}</strong></td><td>{r.get('original_filename')}</td><td>{r.get('status')}</td><td>{r.get('size_bytes', 0):,} B</td><td class='mono'>{r.get('sha256')}</td><td>{r.get('blockchain_status')}</td></tr>")
                out.append("</tbody></table>")

        return "\n".join(out)


class JSONExporter:
    """
    Renders structured canonical JSON document with sorted keys and indent.
    """

    @staticmethod
    def export(data: Dict[str, Any], case_id: str, report_id: str) -> str:
        payload = {
            "report_metadata": {
                "report_identifier": report_id,
                "case_identifier": case_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "format": "JSON",
                "standard": "DRISHTIK_FORENSIC_REPORT_V1"
            },
            "report_data": data
        }
        return json.dumps(payload, indent=2, sort_keys=True)


def compute_sha256(content: bytes) -> str:
    """
    Computes standard SHA-256 hexadecimal digest from raw bytes.
    """
    return hashlib.sha256(content).hexdigest()
