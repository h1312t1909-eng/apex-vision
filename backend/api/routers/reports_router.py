"""
Reports API Router.

Endpoints:
- GET /api/reports/period/{period_id}/excel : Download styled Excel report for a period
- GET /api/reports/daily/excel              : Download consolidated daily Excel report
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.reports.excel_generator import ExcelReportGenerator

router = APIRouter(prefix="/api/reports", tags=["Reports & Analytics"])


@router.get("/period/{period_id}/excel")
def download_period_excel(period_id: int, db: Session = Depends(get_db)):
    """
    Generates and streams an official Microsoft Excel (.xlsx) attendance report for a period.
    """
    try:
        excel_stream = ExcelReportGenerator.generate_period_report(db, period_id)
        filename = f"Attendance_Period_{period_id}_{date.today()}.xlsx"

        return StreamingResponse(
            excel_stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation error: {exc}")


@router.get("/daily/excel")
def download_daily_excel(
    report_date: Optional[date] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generates and streams a consolidated daily Excel attendance report.
    """
    target_date = report_date or date.today()
    try:
        excel_stream = ExcelReportGenerator.generate_daily_report(db, target_date, department)
        filename = f"Daily_Attendance_{target_date}.xlsx"

        return StreamingResponse(
            excel_stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Daily report generation error: {exc}")
