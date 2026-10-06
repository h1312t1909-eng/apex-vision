"""
Excel Attendance Report Generator Module.

Why openpyxl with Custom Academic Styling:
College administration requires official attendance reports formatted with:
1. Institutional Branding & Title Banners.
2. Color-coded status cells:
   - Green  (Confirmed / Present)
   - Yellow (Needs Review / Pending Verification)
   - Red    (Absent)
3. Cumulative statistics: Total Scheduled Hours, Attended Hours, and Attendance Percentage (%).
"""

import io
from datetime import date, datetime
from typing import Optional, List
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session
from sqlalchemy import and_, extract

from backend.database.models import Student, Period, AttendanceRecord, Classroom, Teacher


class ExcelReportGenerator:
    """
    Generates styled .xlsx spreadsheets for single period, daily, and monthly attendance reports.
    """

    # Academic Palette Styling Constants
    COLOR_HEADER_BG = "1E3A8A"       # Apex Navy Blue
    COLOR_HEADER_TXT = "FFFFFF"      # White
    COLOR_CONFIRMED_BG = "D1FAE5"    # Soft Emerald Green
    COLOR_CONFIRMED_TXT = "065F46"
    COLOR_REVIEW_BG = "FEF3C7"       # Soft Amber Yellow
    COLOR_REVIEW_TXT = "92400E"
    COLOR_ABSENT_BG = "FFE4E6"       # Soft Rose Red
    COLOR_ABSENT_TXT = "9F1239"
    COLOR_UNMARKED_BG = "F1F5F9"     # Slate Gray
    COLOR_UNMARKED_TXT = "475569"

    @classmethod
    def generate_period_report(cls, db: Session, period_id: int) -> io.BytesIO:
        """
        Generates an Excel workbook for a single classroom lecture period.
        """
        period = db.query(Period).filter(Period.id == period_id).first()
        if not period:
            raise ValueError(f"Period {period_id} not found.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Period Attendance"

        # 1. Header Banner
        ws.merge_cells("A1:G1")
        title_cell = ws["A1"]
        title_cell.value = "APEX UNIVERSITY — OFFICIAL CCTV ATTENDANCE REPORT"
        title_cell.font = Font(name="Calibri", size=14, bold=True, color=cls.COLOR_HEADER_TXT)
        title_cell.fill = PatternFill(start_color=cls.COLOR_HEADER_BG, end_color=cls.COLOR_HEADER_BG, fill_type="solid")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 35

        # 2. Metadata Rows
        metadata = [
            ("Subject / Course:", period.subject, "Classroom:", period.classroom.name if period.classroom else "N/A"),
            ("Faculty:", period.teacher.name if period.teacher else "N/A", "Date & Time:", f"{period.period_date} ({period.start_time.strftime('%H:%M')} - {period.end_time.strftime('%H:%M')})"),
            ("Report Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Verification Mode:", "CCTV ArcFace + Centroid Tracker")
        ]

        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        for row_idx, meta in enumerate(metadata, start=2):
            ws.cell(row=row_idx, column=1, value=meta[0]).font = Font(bold=True, size=10, color="475569")
            ws.cell(row=row_idx, column=2, value=meta[1]).font = Font(bold=True, size=10, color="0F172A")
            ws.cell(row=row_idx, column=4, value=meta[2]).font = Font(bold=True, size=10, color="475569")
            ws.cell(row=row_idx, column=5, value=meta[3]).font = Font(size=10, color="0F172A")
            ws.row_dimensions[row_idx].height = 20

        # 3. Table Column Headers
        headers = [
            "Roll Number", "Student Name", "Department", "Attendance Status", 
            "Confidence Score", "Entry Time", "Exit / Last Seen"
        ]
        header_row = 6
        ws.row_dimensions[header_row].height = 25

        for col_idx, header_text in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=col_idx, value=header_text)
            cell.font = Font(name="Calibri", size=11, bold=True, color=cls.COLOR_HEADER_TXT)
            cell.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid") # Slate 700
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        # 4. Data Rows
        records = db.query(AttendanceRecord).filter(AttendanceRecord.period_id == period_id).all()
        current_row = header_row + 1

        for rec in records:
            roll = rec.student.roll_no if rec.student else "N/A"
            name = rec.student.name if rec.student else "N/A"
            dept = rec.student.department if rec.student else "N/A"
            status_str = rec.status.upper().replace('_', ' ')
            conf_str = f"{(rec.confidence_score * 100):.1f}%" if rec.confidence_score else "--"
            entry_str = rec.entry_time.strftime("%H:%M:%S") if rec.entry_time else "--"
            exit_str = rec.exit_time.strftime("%H:%M:%S") if rec.exit_time else "--"

            # Determine row color
            bg_color, txt_color = cls._get_status_colors(rec.status)

            ws.cell(row=current_row, column=1, value=roll).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=2, value=name).alignment = Alignment(horizontal="left")
            ws.cell(row=current_row, column=3, value=dept).alignment = Alignment(horizontal="left")

            status_cell = ws.cell(row=current_row, column=4, value=status_str)
            status_cell.alignment = Alignment(horizontal="center")
            status_cell.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
            status_cell.font = Font(bold=True, color=txt_color)

            ws.cell(row=current_row, column=5, value=conf_str).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=6, value=entry_str).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=7, value=exit_str).alignment = Alignment(horizontal="center")

            for col in range(1, 8):
                ws.cell(row=current_row, column=col).border = thin_border

            ws.row_dimensions[current_row].height = 20
            current_row += 1

        # 5. Auto-fit column widths
        cls._autofit_columns(ws)

        # Export to memory stream
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @classmethod
    def generate_daily_report(cls, db: Session, report_date: date, department: Optional[str] = None) -> io.BytesIO:
        """
        Generates a consolidated daily report showing all scheduled periods and student attendance.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Daily Report {report_date}"

        # Header Title
        ws.merge_cells("A1:H1")
        title_cell = ws["A1"]
        title_cell.value = f"APEX UNIVERSITY — DAILY ATTENDANCE SUMMARY ({report_date})"
        title_cell.font = Font(name="Calibri", size=14, bold=True, color=cls.COLOR_HEADER_TXT)
        title_cell.fill = PatternFill(start_color=cls.COLOR_HEADER_BG, end_color=cls.COLOR_HEADER_BG, fill_type="solid")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 35

        # Query periods on this date
        period_query = db.query(Period).filter(Period.period_date == report_date)
        periods = period_query.order_by(Period.start_time.asc()).all()

        # Query students
        student_query = db.query(Student)
        if department:
            student_query = student_query.filter(Student.department == department)
        students = student_query.order_by(Student.roll_no.asc()).all()

        # Table Header
        headers = ["Roll No", "Student Name", "Department"] + [
            f"{p.subject[:12]} ({p.start_time.strftime('%H:%M')})" for p in periods
        ] + ["Present Count", "Daily %"]

        header_row = 3
        ws.row_dimensions[header_row].height = 25
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        for col_idx, h in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=col_idx, value=h)
            cell.font = Font(bold=True, color=cls.COLOR_HEADER_TXT, size=10)
            cell.fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        # Populate student rows
        current_row = 4
        for student in students:
            ws.cell(row=current_row, column=1, value=student.roll_no).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=2, value=student.name).alignment = Alignment(horizontal="left")
            ws.cell(row=current_row, column=3, value=student.department).alignment = Alignment(horizontal="left")

            present_periods = 0

            for p_idx, period in enumerate(periods):
                col = 4 + p_idx
                rec = db.query(AttendanceRecord).filter(
                    and_(
                        AttendanceRecord.student_id == student.id,
                        AttendanceRecord.period_id == period.id
                    )
                ).first()

                status_code = "A" # Default Absent
                bg_color, txt_color = cls.COLOR_ABSENT_BG, cls.COLOR_ABSENT_TXT

                if rec:
                    if rec.status == "confirmed":
                        status_code = "P" # Present
                        present_periods += 1
                        bg_color, txt_color = cls.COLOR_CONFIRMED_BG, cls.COLOR_CONFIRMED_TXT
                    elif rec.status == "needs_review":
                        status_code = "REV"
                        bg_color, txt_color = cls.COLOR_REVIEW_BG, cls.COLOR_REVIEW_TXT

                cell = ws.cell(row=current_row, column=col, value=status_code)
                cell.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
                cell.font = Font(bold=True, color=txt_color, size=10)
                cell.alignment = Alignment(horizontal="center", vertical="center")

            # Totals & %
            total_p = len(periods)
            pct = (present_periods / total_p * 100) if total_p > 0 else 0.0
            
            p_count_col = 4 + len(periods)
            pct_col = p_count_col + 1

            ws.cell(row=current_row, column=p_count_col, value=f"{present_periods}/{total_p}").alignment = Alignment(horizontal="center")
            pct_cell = ws.cell(row=current_row, column=pct_col, value=f"{pct:.1f}%")
            pct_cell.alignment = Alignment(horizontal="center")
            pct_cell.font = Font(bold=True, color="065F46" if pct >= 75.0 else "9F1239")

            for c in range(1, pct_col + 1):
                ws.cell(row=current_row, column=c).border = thin_border

            ws.row_dimensions[current_row].height = 20
            current_row += 1

        cls._autofit_columns(ws)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @classmethod
    def _get_status_colors(cls, status: str) -> tuple[str, str]:
        if status == "confirmed":
            return cls.COLOR_CONFIRMED_BG, cls.COLOR_CONFIRMED_TXT
        elif status == "needs_review":
            return cls.COLOR_REVIEW_BG, cls.COLOR_REVIEW_TXT
        elif status == "absent":
            return cls.COLOR_ABSENT_BG, cls.COLOR_ABSENT_TXT
        return cls.COLOR_UNMARKED_BG, cls.COLOR_UNMARKED_TXT

    @classmethod
    def _autofit_columns(cls, ws: openpyxl.worksheet.worksheet.Worksheet):
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
