"""
Report Generation Package.

Provides automated daily and monthly student attendance report generation
in Microsoft Excel (.xlsx) and PDF formats using openpyxl and reportlab.
"""

from backend.reports.excel_generator import ExcelReportGenerator

__all__ = ["ExcelReportGenerator"]
