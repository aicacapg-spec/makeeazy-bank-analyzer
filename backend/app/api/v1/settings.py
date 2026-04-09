"""
Settings API — Manage API keys and trigger re-analysis with AI.
"""

import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# Runtime API key storage (persisted in a simple JSON file)
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "settings.json")


def _load_settings() -> dict:
    """Load settings from file."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_settings(settings: dict):
    """Save settings to file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"[SETTINGS] Failed to save: {e}")


def get_active_groq_key() -> str:
    """Get the active Groq API key — user-saved takes priority over .env."""
    settings = _load_settings()
    user_key = settings.get("groq_api_key", "")
    if user_key:
        return user_key
    return os.getenv("GROQ_API_KEY", "")


def get_active_gemini_key() -> str:
    """Get the active Gemini API key."""
    settings = _load_settings()
    user_key = settings.get("gemini_api_key", "")
    if user_key:
        return user_key
    return os.getenv("GEMINI_API_KEY", "")


class APIKeyRequest(BaseModel):
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


@router.get("/settings/api-status")
async def get_api_status():
    """Check which API keys are configured and their status."""
    import requests as req

    groq_key = get_active_groq_key()
    gemini_key = get_active_gemini_key()
    settings = _load_settings()

    result = {
        "groq": {
            "configured": bool(groq_key),
            "source": "user" if settings.get("groq_api_key") else ("env" if groq_key else "none"),
            "valid": False,
            "key_preview": f"{groq_key[:8]}...{groq_key[-4:]}" if groq_key and len(groq_key) > 12 else "",
        },
        "gemini": {
            "configured": bool(gemini_key),
            "source": "user" if settings.get("gemini_api_key") else ("env" if gemini_key else "none"),
            "valid": False,
            "key_preview": f"{gemini_key[:8]}...{gemini_key[-4:]}" if gemini_key and len(gemini_key) > 12 else "",
        },
    }

    # Validate Groq key
    if groq_key:
        try:
            resp = req.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq_key}"},
                timeout=5
            )
            result["groq"]["valid"] = resp.status_code == 200
        except Exception:
            pass

    # Validate Gemini key
    if gemini_key:
        try:
            resp = req.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}",
                timeout=5
            )
            result["gemini"]["valid"] = resp.status_code == 200
        except Exception:
            pass

    return result


@router.post("/settings/save-api-key")
async def save_api_key(body: APIKeyRequest):
    """Save API key for the session. Validates before saving."""
    import requests as req

    settings = _load_settings()
    saved = []

    if body.groq_api_key is not None:
        key = body.groq_api_key.strip()
        if key:
            # Validate
            try:
                resp = req.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=5
                )
                if resp.status_code != 200:
                    raise HTTPException(status_code=400, detail="Invalid Groq API key. Please check and try again.")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=400, detail="Could not validate Groq API key. Check your internet connection.")

            settings["groq_api_key"] = key
            # Also update the environment for current process
            os.environ["GROQ_API_KEY"] = key
            saved.append("groq")
        else:
            # Clear user key, fall back to .env
            settings.pop("groq_api_key", None)
            saved.append("groq (cleared)")

    if body.gemini_api_key is not None:
        key = body.gemini_api_key.strip()
        if key:
            try:
                resp = req.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                    timeout=5
                )
                if resp.status_code != 200:
                    raise HTTPException(status_code=400, detail="Invalid Gemini API key. Please check and try again.")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=400, detail="Could not validate Gemini API key. Check your internet connection.")

            settings["gemini_api_key"] = key
            os.environ["GEMINI_API_KEY"] = key
            saved.append("gemini")
        else:
            settings.pop("gemini_api_key", None)
            saved.append("gemini (cleared)")

    _save_settings(settings)
    return {"status": "saved", "keys_updated": saved}


@router.post("/settings/reanalyze-ai/{client_id}")
async def reanalyze_with_ai(client_id: str):
    """Re-run AI analysis on an existing statement using current API keys."""
    from app.core.database import SessionLocal
    from app.models.document import Document
    from app.services.parser.ai_enhancer import run_ai_enhancement, generate_ai_insights
    from app.services.analyzer.engine import run_full_analysis
    import importlib
    import app.services.parser.ai_enhancer as ai_mod

    # Reload the module to pick up new env vars
    importlib.reload(ai_mod)

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.client_id == client_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Statement not found")

        if not doc.raw_extraction_json:
            raise HTTPException(status_code=400, detail="No parsed data available")

        # Get parsed data
        parsed_data = json.loads(doc.raw_extraction_json)

        # Run AI enhancement
        parsed_data["_raw_text"] = ""  # Try to get from existing data
        # Reconstruct minimal raw text from account info
        ai = parsed_data.get("account_info", {})
        parsed_data["_raw_text"] = f"Bank: {ai.get('bank_name','')} Account: {ai.get('account_holder_name','')} IFSC: {ai.get('ifsc','')} Account No: {ai.get('account_number','')}"

        groq_key = get_active_groq_key()
        if not groq_key:
            raise HTTPException(status_code=400, detail="No Groq API key configured. Please add one in Settings.")

        # Update env for this run
        os.environ["GROQ_API_KEY"] = groq_key
        gemini_key = get_active_gemini_key()
        if gemini_key:
            os.environ["GEMINI_API_KEY"] = gemini_key

        # Run AI categorization on transactions
        from app.services.parser.ai_enhancer import categorize_transactions_ai, generate_ai_insights as gen_insights
        transactions = parsed_data.get("transactions", [])
        if transactions:
            categorize_transactions_ai(transactions)
            parsed_data["transactions"] = transactions

        # Re-run full analysis
        analysis = run_full_analysis(parsed_data, client_id=client_id)

        # Generate AI insights
        ai_insights = gen_insights(
            transactions,
            parsed_data.get("account_info", {}),
            analysis.get("health_score", {})
        )
        analysis["ai_insights"] = ai_insights

        # Save updated results
        doc.raw_extraction_json = json.dumps(parsed_data, default=str)
        doc.analysis_json = json.dumps(analysis, default=str)
        db.commit()

        categorized = sum(1 for t in transactions if t.get("ai_category"))
        return {
            "status": "success",
            "message": f"AI analysis complete. {categorized}/{len(transactions)} transactions categorized.",
            "ai_insights_available": bool(ai_insights.get("executive_summary", "") != "AI insights unavailable"),
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)[:200]}")
    finally:
        db.close()
