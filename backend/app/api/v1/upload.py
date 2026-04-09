"""
Upload API — Handles file upload, validation, processing, and analysis.
"""

import os
import uuid
import json
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.services.parser.factory import parse_file
from app.services.analyzer.engine import run_full_analysis
from app.services.parser.ai_enhancer import run_ai_enhancement, generate_ai_insights

router = APIRouter()


@router.post("/upload")
async def upload_statement(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    advanced_options: Optional[str] = Form(None),
):
    """
    Upload a bank statement file for analysis.
    Supports PDF, Excel (.xlsx/.xls), CSV, and TXT files.
    """
    # ─── Validate file ───
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(settings.allowed_extensions_list)}"
        )

    # Read file content
    content = await file.read()
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    # ─── Generate IDs ───
    unique_id = uuid.uuid4().hex[:12]
    doc_id = f"bsa_{unique_id}"
    client_id = f"bank_statement_{unique_id}"

    # ─── Save file ───
    safe_filename = f"{unique_id}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    with open(file_path, 'wb') as f:
        f.write(content)

    # ─── Create document record ───
    db = SessionLocal()
    try:
        doc = Document(
            doc_id=doc_id,
            client_id=client_id,
            filename=file.filename,
            file_path=file_path,
            file_type=ext.lstrip('.'),
            file_size=len(content),
            status=DocumentStatus.PROCESSING.value,
            password_used=password,
            processing_started_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Parse advanced options
        options = {}
        if advanced_options:
            try:
                options = json.loads(advanced_options)
            except json.JSONDecodeError:
                pass

        # ─── Process file ───
        try:
            # Step 1: Parse (regex)
            parsed_data = parse_file(file_path, password=password)

            # Step 1.5: AI Enhancement (Groq) — verify account info + categorize transactions
            try:
                parsed_data = run_ai_enhancement(parsed_data)
            except Exception as ai_err:
                print(f"[UPLOAD] AI enhancement failed (non-fatal): {str(ai_err)[:100]}")

            # Step 2: Apply manual overrides (take priority over AI)
            account_info = parsed_data.get("account_info", {})
            if options.get("bank_override"):
                account_info["bank_name"] = options["bank_override"]
            if options.get("name_override"):
                account_info["account_holder_name"] = options["name_override"]
            parsed_data["account_info"] = account_info

            doc.bank_name = account_info.get("bank_name", "")
            doc.account_holder_name = account_info.get("account_holder_name", "")
            doc.account_number = account_info.get("account_number", "")
            doc.ifsc_code = account_info.get("ifsc", "")
            period = account_info.get("statement_period", {})
            doc.statement_period_from = period.get("from", "") if isinstance(period, dict) else ""
            doc.statement_period_to = period.get("to", "") if isinstance(period, dict) else ""

            # Step 3: Store raw extraction
            raw_result = {
                "doc_id": doc_id,
                "client_id": client_id,
                "status": "completed",
                "checkpoint": "analysing_completed",
                "analysis_completed": True,
                "account_info": account_info,
                "transactions": parsed_data.get("transactions", []),
                "total_transactions": len(parsed_data.get("transactions", [])),
                "mismatched_sequence_date": parsed_data.get("mismatched_sequence_date", []),
                "negative_balance": parsed_data.get("negative_balance", []),
                "discrepancies": parsed_data.get("discrepancies", {}),
            }
            doc.raw_extraction_json = json.dumps(raw_result, default=str)

            # Step 4: Run analysis (pass custom keywords if provided)
            config_overrides = {}
            if options.get("salary_keywords"):
                config_overrides["salary_keywords"] = options["salary_keywords"]
            if options.get("emi_keywords"):
                config_overrides["emi_keywords"] = options["emi_keywords"]
            analysis = run_full_analysis(parsed_data, client_id=client_id, config_overrides=config_overrides)

            # Step 4.5: Generate AI Insights
            try:
                ai_insights = generate_ai_insights(
                    parsed_data.get("transactions", []),
                    account_info,
                    analysis.get("health_score", {})
                )
                analysis["ai_insights"] = ai_insights
            except Exception as ai_err:
                print(f"[UPLOAD] AI insights failed (non-fatal): {str(ai_err)[:100]}")
                analysis["ai_insights"] = {}

            doc.analysis_json = json.dumps(analysis, default=str)

            # Step 5: Mark complete
            doc.status = DocumentStatus.COMPLETED.value
            doc.completed_at = datetime.now(timezone.utc)
            db.commit()

            return {
                "doc_id": doc_id,
                "client_id": client_id,
                "filename": file.filename,
                "status": "completed",
                "message": f"Successfully analyzed {len(parsed_data.get('transactions', []))} transactions.",
                "bank_name": account_info.get("bank_name", "unknown"),
                "account_holder": account_info.get("account_holder_name", ""),
                "transaction_count": len(parsed_data.get("transactions", [])),
            }

        except ValueError as e:
            doc.status = DocumentStatus.FAILED.value
            doc.error_message = str(e)
            db.commit()
            raise HTTPException(status_code=422, detail=str(e))

        except Exception as e:
            doc.status = DocumentStatus.FAILED.value
            doc.error_message = f"Processing failed: {str(e)}"
            db.commit()
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    finally:
        db.close()
