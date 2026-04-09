"""
Analysis API — Serves raw extraction and computed analysis results.
"""

import json
from fastapi import APIRouter, HTTPException

from app.core.database import SessionLocal
from app.models.document import Document

router = APIRouter()


@router.get("/statement-result/{client_id}")
def get_statement_result(client_id: str):
    """
    Get raw extraction results (account info + transactions).
    Equivalent to Finpass: /services/bsa/statement-result
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.client_id == client_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        if doc.status != "completed":
            return {
                "doc_id": doc.doc_id,
                "client_id": doc.client_id,
                "status": doc.status,
                "error_message": doc.error_message,
                "analysis_completed": False,
            }

        if not doc.raw_extraction_json:
            raise HTTPException(status_code=404, detail="Raw extraction data not available.")

        return json.loads(doc.raw_extraction_json)
    finally:
        db.close()


@router.get("/analysis-json/{client_id}")
def get_analysis_json(client_id: str):
    """
    Get full computed analytics (25 analysis sections).
    Equivalent to Finpass: /services/bsa/analysis-json
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.client_id == client_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        if doc.status != "completed":
            return {
                "client_id": doc.client_id,
                "status": doc.status,
                "error_message": doc.error_message,
                "analysis_completed": False,
            }

        if not doc.analysis_json:
            raise HTTPException(status_code=404, detail="Analysis data not available.")

        return json.loads(doc.analysis_json)
    finally:
        db.close()


@router.get("/supported-banks")
def get_supported_banks():
    """Get list of all supported banks."""
    from app.services.parser.bank_detector import get_all_supported_banks
    return {"banks": get_all_supported_banks(), "total": len(get_all_supported_banks())}


@router.get("/export/excel/{client_id}")
def export_excel(client_id: str):
    """Download analysis as Excel file."""
    from fastapi.responses import StreamingResponse
    from app.services.exporter import generate_excel

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.client_id == client_id).first()
        if not doc or doc.status != "completed":
            raise HTTPException(status_code=404, detail="Completed analysis not found")

        statement = json.loads(doc.raw_extraction_json) if doc.raw_extraction_json else {}
        analysis = json.loads(doc.analysis_json) if doc.analysis_json else {}

        buffer = generate_excel(statement, analysis)
        name = doc.account_holder_name or "Statement"
        bank = (doc.bank_name or "Bank").upper()
        filename = f"{bank}_{name}_Analysis.xlsx".replace(" ", "_")

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    finally:
        db.close()


@router.get("/export/pdf/{client_id}")
def export_pdf(client_id: str):
    """Download analysis as PDF report."""
    from fastapi.responses import StreamingResponse
    from app.services.exporter import generate_pdf

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.client_id == client_id).first()
        if not doc or doc.status != "completed":
            raise HTTPException(status_code=404, detail="Completed analysis not found")

        statement = json.loads(doc.raw_extraction_json) if doc.raw_extraction_json else {}
        analysis = json.loads(doc.analysis_json) if doc.analysis_json else {}

        buffer = generate_pdf(statement, analysis)
        name = doc.account_holder_name or "Statement"
        bank = (doc.bank_name or "Bank").upper()
        filename = f"{bank}_{name}_Report.pdf".replace(" ", "_")

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    finally:
        db.close()
