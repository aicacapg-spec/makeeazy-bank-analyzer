"""
Documents API — CRUD operations for uploaded documents.
"""

import json
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.core.database import SessionLocal
from app.models.document import Document

router = APIRouter()


@router.get("/documents")
def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by filename or account holder"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all uploaded documents with optional filtering."""
    db = SessionLocal()
    try:
        query = db.query(Document).order_by(Document.created_at.desc())

        if status:
            query = query.filter(Document.status == status)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Document.filename.ilike(search_term)) |
                (Document.account_holder_name.ilike(search_term)) |
                (Document.bank_name.ilike(search_term))
            )

        total = query.count()
        documents = query.offset(offset).limit(limit).all()

        # Status counts
        all_docs = db.query(Document).all()
        status_counts = {
            "total": len(all_docs),
            "completed": len([d for d in all_docs if d.status == "completed"]),
            "processing": len([d for d in all_docs if d.status == "processing"]),
            "failed": len([d for d in all_docs if d.status == "failed"]),
            "pending": len([d for d in all_docs if d.status == "pending"]),
        }

        return {
            "total": total,
            "documents": [{
                "id": doc.id,
                "doc_id": doc.doc_id,
                "client_id": doc.client_id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "bank_name": doc.bank_name or "",
                "account_holder_name": doc.account_holder_name or "",
                "account_number": doc.account_number or "",
                "status": doc.status,
                "error_message": doc.error_message,
                "created_at": doc.created_at.isoformat() if doc.created_at else "",
                "completed_at": doc.completed_at.isoformat() if doc.completed_at else None,
                "statement_period_from": doc.statement_period_from or "",
                "statement_period_to": doc.statement_period_to or "",
            } for doc in documents],
            "status_counts": status_counts,
        }
    finally:
        db.close()


@router.get("/documents/{client_id}")
def get_document(client_id: str):
    """Get document details by client_id."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.client_id == client_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        return {
            "id": doc.id,
            "doc_id": doc.doc_id,
            "client_id": doc.client_id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "bank_name": doc.bank_name or "",
            "account_holder_name": doc.account_holder_name or "",
            "account_number": doc.account_number or "",
            "ifsc_code": doc.ifsc_code or "",
            "status": doc.status,
            "error_message": doc.error_message,
            "created_at": doc.created_at.isoformat() if doc.created_at else "",
            "completed_at": doc.completed_at.isoformat() if doc.completed_at else None,
            "statement_period_from": doc.statement_period_from or "",
            "statement_period_to": doc.statement_period_to or "",
        }
    finally:
        db.close()


@router.delete("/documents/{client_id}")
def delete_document(client_id: str):
    """Delete a document and its analysis."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.client_id == client_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        # Delete file from disk
        import os
        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except:
                pass

        db.delete(doc)
        db.commit()
        return {"message": "Document deleted successfully.", "client_id": client_id}
    finally:
        db.close()
