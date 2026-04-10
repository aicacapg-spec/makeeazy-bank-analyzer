"""
Groq AI Enhancement — Uses Groq LLM to VERIFY and CORRECT parsing results.
Hardcoded API key for production. Works with ALL file sizes.
Memory-optimized: uses smart sampling for large files.
"""

import os
import json
import re
import gc
import requests
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Default key loaded from environment variable GROQ_API_KEY
DEFAULT_GROQ_KEY = os.getenv("GROQ_API_KEY", "")

# Models: 8B for fast tasks, 70B for reasoning
MODEL_FAST = "llama-3.1-8b-instant"
MODEL_SMART = "llama-3.3-70b-versatile"


def _get_groq_key() -> str:
    """Get Groq key: settings.json → env → hardcoded default."""
    try:
        settings_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "settings.json")
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                if settings.get("groq_api_key"):
                    return settings["groq_api_key"]
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY", "") or DEFAULT_GROQ_KEY


def _get_gemini_key() -> str:
    """Get Gemini key: settings.json → env."""
    try:
        settings_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "settings.json")
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                if settings.get("gemini_api_key"):
                    return settings["gemini_api_key"]
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


def _call_groq(prompt: str, system: str = "", model: str = MODEL_FAST, max_tokens: int = 2048) -> Optional[str]:
    """Call Groq API with fallback: 8B → 70B → Gemini Flash."""
    groq_key = _get_groq_key()
    if not groq_key:
        return _call_gemini_fallback(prompt, system, max_tokens)

    models_to_try = [model]
    if model == MODEL_FAST:
        models_to_try.append(MODEL_SMART)

    for m in models_to_try:
        try:
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": m,
                    "messages": [
                        {"role": "system", "content": system or "You extract structured data. Return ONLY valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.0,
                    "max_tokens": max_tokens,
                },
                timeout=25,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            elif resp.status_code in (429, 413):
                print(f"[GROQ] {m} rate-limited, trying next...")
                time.sleep(2)
                continue
            else:
                print(f"[GROQ] {m} error {resp.status_code}: {resp.text[:80]}")
                continue
        except Exception as e:
            print(f"[GROQ] {m} exception: {str(e)[:80]}")
            continue

    return _call_gemini_fallback(prompt, system, max_tokens)


def _call_gemini_fallback(prompt: str, system: str = "", max_tokens: int = 2048) -> Optional[str]:
    """Fallback to Gemini Flash when Groq unavailable."""
    gemini_key = _get_gemini_key()
    if not gemini_key:
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"},
            "systemInstruction": {"parts": [{"text": system or "Return ONLY valid JSON."}]},
        }
        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                print("[GEMINI] Fallback OK")
                return content.strip()
    except Exception as e:
        print(f"[GEMINI] Error: {str(e)[:80]}")
    return None


def _parse_json_response(text: str) -> Any:
    """Parse JSON from LLM response, handling markdown blocks."""
    if not text:
        return None
    text = re.sub(r'^```(?:json)?\s*\n?', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$', '', text.strip(), flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pat in [r'(\{[\s\S]*\})', r'(\[[\s\S]*\])']:
        m = re.search(pat, text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    return None


# ═══════════════════════════════════════════════════════
# 1. VERIFY ACCOUNT INFO
# ═══════════════════════════════════════════════════════

def verify_account_info(header_text: str, current_info: dict) -> dict:
    """AI double-checks regex-extracted account info. Only uses first 2000 chars."""
    prompt = f"""Verify these Indian bank statement parsing results against the raw text.
ONLY correct what's clearly WRONG. Keep correct values unchanged.

REGEX RESULTS:
- Bank: {current_info.get('bank_name', 'unknown')}
- Name: {current_info.get('account_holder_name', '')}
- Account: {current_info.get('account_number', '')}
- IFSC: {current_info.get('ifsc', '')}

RULES:
- Name = PRIMARY owner (not nominee/guardian)
- IFSC prefix: UTIB=Axis, HDFC=HDFC, ICIC=ICICI, SBIN=SBI, CNRB=Canara, KKBK=Kotak
- Only change what's actually wrong

Return JSON: {{"bank_name":"lowercase","account_holder_name":"NAME","account_number":"num","ifsc":"CODE","confidence":"high/medium/low"}}

RAW TEXT:
{header_text[:2000]}"""

    result = _call_groq(prompt, model=MODEL_FAST, max_tokens=256)
    parsed = _parse_json_response(result)

    if not parsed or not isinstance(parsed, dict):
        return current_info

    enhanced = current_info.copy()
    confidence = parsed.get("confidence", "low")

    if parsed.get("bank_name") and parsed["bank_name"] != "unknown":
        ai_bank = parsed["bank_name"].lower().strip()
        regex_bank = current_info.get("bank_name", "").lower()
        if not regex_bank or regex_bank == "unknown":
            enhanced["bank_name"] = ai_bank
            print(f"[AI] Fixed bank: '{regex_bank}' -> '{ai_bank}'")

    if parsed.get("account_holder_name") and len(parsed["account_holder_name"]) > 3:
        ai_name = parsed["account_holder_name"].strip()
        current_name = current_info.get("account_holder_name", "")
        if not current_name or len(current_name) < 3 or confidence in ("high", "medium"):
            enhanced["account_holder_name"] = ai_name

    if parsed.get("account_number") and len(str(parsed["account_number"])) > 5:
        curr_acc = current_info.get("account_number", "")
        if not curr_acc or len(curr_acc) < 5:
            enhanced["account_number"] = str(parsed["account_number"]).strip()

    if parsed.get("ifsc") and len(str(parsed["ifsc"])) == 11:
        curr_ifsc = current_info.get("ifsc", "")
        if not curr_ifsc:
            enhanced["ifsc"] = str(parsed["ifsc"]).strip().upper()

    print(f"[AI] Verified: bank={enhanced.get('bank_name')} | name={enhanced.get('account_holder_name')}")
    return enhanced


# ═══════════════════════════════════════════════════════
# 2. VERIFY TRANSACTION STRUCTURE
# ═══════════════════════════════════════════════════════

def verify_transactions(transactions: list) -> list:
    """Check if debit/credit columns are swapped using 10 sample transactions."""
    if len(transactions) < 5:
        return transactions

    sample = transactions[:10]
    sample_data = [{"d": t.get("txn_date", ""), "desc": t.get("description", "")[:40],
                    "dr": t.get("debit", 0), "cr": t.get("credit", 0), "bal": t.get("balance", 0)}
                   for t in sample]

    prompt = f"""Check if debit/credit columns are SWAPPED in these bank transactions:
{json.dumps(sample_data)}

Check: balance should = prev_balance - debit + credit
Return JSON: {{"columns_swapped": true/false, "fix": "none" or "swap_debit_credit"}}"""

    result = _call_groq(prompt, model=MODEL_FAST, max_tokens=128)
    parsed = _parse_json_response(result)

    if parsed and isinstance(parsed, dict) and parsed.get("columns_swapped"):
        print(f"[AI] FIXING: Swapped debit/credit for {len(transactions)} transactions")
        for t in transactions:
            t["debit"], t["credit"] = t.get("credit", 0), t.get("debit", 0)
    else:
        print("[AI] Transaction structure OK")

    return transactions


# ═══════════════════════════════════════════════════════
# 3. SMART CATEGORIZATION (memory-optimized)
# ═══════════════════════════════════════════════════════

def categorize_transactions(transactions: list) -> list:
    """Categorize via unique pattern sampling. Max 3 API calls for ANY file size."""
    if not transactions:
        return transactions

    # Deduplicate descriptions into patterns
    pattern_map = {}
    for i, t in enumerate(transactions):
        desc = t.get("description", "").strip()
        if not desc:
            continue
        norm = re.sub(r'\d{10,}', 'X', desc)
        norm = re.sub(r'[\d,]+\.\d{2}', '', norm)
        norm = re.sub(r'\d{2}[-/]\d{2}[-/]\d{2,4}', '', norm)
        norm = norm.strip()[:50].upper()
        if norm not in pattern_map:
            pattern_map[norm] = {"idx": [], "s": desc[:45], "t": "dr" if t.get("debit", 0) > 0 else "cr"}
        pattern_map[norm]["idx"].append(i)

    # Take top 75 patterns (covers 95%+ of transactions)
    patterns = sorted(pattern_map.items(), key=lambda x: len(x[1]["idx"]), reverse=True)[:75]
    print(f"[AI] {len(patterns)} unique patterns from {len(transactions)} txns")

    cats = "salary,emi,rent,investment,insurance,utility,shopping,food,travel,entertainment,transfer,credit_card,government,medical,education,atm,bank_charge,refund,other"

    # Process in batches of 25 (max 3 batches)
    for b in range(min(3, (len(patterns) + 24) // 25)):
        batch = patterns[b*25:(b+1)*25]
        lines = "\n".join([f"{i}|{info['t']}|{info['s']}" for i, (_, info) in enumerate(batch, start=b*25)])

        prompt = f"""Categorize Indian bank transactions:
{lines}

Categories: {cats}
Return JSON array: [{{"i":0,"c":"category"}}]"""

        result = _call_groq(prompt, model=MODEL_FAST, max_tokens=1024)
        parsed = _parse_json_response(result)

        if parsed and isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict) or "i" not in item:
                    continue
                idx = item["i"]
                if 0 <= idx < len(patterns):
                    cat = item.get("c", item.get("category", "other"))
                    for txn_idx in patterns[idx][1]["idx"]:
                        transactions[txn_idx]["ai_category"] = cat
            print(f"[AI] Batch {b+1}: categorized")
        else:
            print(f"[AI] Batch {b+1}: failed")

        if b < 2:
            time.sleep(1.5)

    tagged = sum(1 for t in transactions if t.get("ai_category"))
    print(f"[AI] Categorized: {tagged}/{len(transactions)}")
    return transactions


# ═══════════════════════════════════════════════════════
# MAIN: AI verification pipeline (memory-safe)
# ═══════════════════════════════════════════════════════

def run_ai_enhancement(parsed_data: dict) -> dict:
    """Main entry: AI verifies and corrects parsed data. Works for ALL file sizes."""
    groq_key = _get_groq_key()
    gemini_key = _get_gemini_key()

    if not groq_key and not gemini_key:
        print("[AI] No API key available, skipping")
        return parsed_data

    print(f"\n{'='*50}")
    print(f"[AI] Running AI Verification")
    print(f"{'='*50}")

    # 1. Verify account info (uses only header text, tiny memory)
    header_text = parsed_data.get("_raw_text", "")
    if header_text:
        current_info = parsed_data.get("account_info", {})
        verified_info = verify_account_info(header_text, current_info)
        parsed_data["account_info"] = verified_info

    # Free raw text immediately
    parsed_data.pop('_raw_text', None)
    gc.collect()

    # 2. Verify transaction structure
    transactions = parsed_data.get("transactions", [])
    if transactions:
        transactions = verify_transactions(transactions)

    # 3. Categorize (uses smart sampling, same 3 API calls regardless of file size)
    if transactions:
        categorize_transactions(transactions)
        parsed_data["transactions"] = transactions

    parsed_data["ai_verified"] = True
    gc.collect()
    print(f"[AI] Verification complete\n")
    return parsed_data


def generate_ai_insights(transactions: list, account_info: dict, health_score: dict) -> dict:
    """Generate concise AI insights (memory-safe sampling)."""
    credits = sorted([t for t in transactions if t.get("credit", 0) > 0], key=lambda t: -t["credit"])[:5]
    debits = sorted([t for t in transactions if t.get("debit", 0) > 0], key=lambda t: -t["debit"])[:5]
    total_cr = sum(t.get("credit", 0) for t in transactions)
    total_dr = sum(t.get("debit", 0) for t in transactions)

    cats = {}
    for t in transactions:
        c = t.get("ai_category", "other")
        cats[c] = cats.get(c, 0) + (t.get("debit", 0) or t.get("credit", 0))
    top_cats = sorted(cats.items(), key=lambda x: -x[1])[:6]

    summary = f"""Account: {account_info.get('account_holder_name', 'N/A')} | {account_info.get('bank_name', 'N/A')}
Txns: {len(transactions)} | Credits: {total_cr:,.0f} | Debits: {total_dr:,.0f} | Net: {total_cr-total_dr:,.0f}
Score: {health_score.get('score', 0)}/100
Top spends: {', '.join(f'{k}:{v:,.0f}' for k,v in top_cats)}"""

    prompt = f"""{summary}
Give financial insights. Return JSON:
{{"executive_summary":"2 sentences","income_assessment":"text","spending_pattern":"text","risk_flags":["list"],"recommendations":["3 items"],"cashflow_health":"healthy/moderate/concerning"}}
Keep each under 60 words. ONLY JSON."""

    result = _call_groq(prompt, model=MODEL_FAST, max_tokens=1024)
    parsed = _parse_json_response(result)
    if parsed and isinstance(parsed, dict):
        print("[AI] Insights generated")
        return parsed
    return {"executive_summary": "AI insights unavailable", "risk_flags": [], "recommendations": []}
