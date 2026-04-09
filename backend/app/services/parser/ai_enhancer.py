"""
Groq AI Enhancement — Uses Groq LLM to VERIFY and CORRECT parsing results.
Focus: Double-check account info, fix parsing ambiguities, improve accuracy.
NOT for insights — purely for making parsed data more reliable.
"""

import os
import json
import re
import requests
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Use 8B for fast tasks; 70B for complex reasoning
MODEL_FAST = "llama-3.1-8b-instant"
MODEL_SMART = "llama-3.3-70b-versatile"


def _get_groq_key() -> str:
    """Get Groq key — check settings.json first, then .env."""
    try:
        settings_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "settings.json")
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                if settings.get("groq_api_key"):
                    return settings["groq_api_key"]
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY", "")


def _get_gemini_key() -> str:
    """Get Gemini key — check settings.json first, then .env."""
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


def _call_groq(prompt: str, system: str = "", model: str = MODEL_FAST, max_tokens: int = 4096) -> Optional[str]:
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
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            elif resp.status_code in (429, 413):
                print(f"[GROQ] {m} error {resp.status_code}, trying next...")
                time.sleep(1)
                continue
            else:
                print(f"[GROQ] {m} error {resp.status_code}: {resp.text[:80]}")
                continue
        except Exception as e:
            print(f"[GROQ] {m} exception: {str(e)[:80]}")
            continue

    return _call_gemini_fallback(prompt, system, max_tokens)


def _call_gemini_fallback(prompt: str, system: str = "", max_tokens: int = 4096) -> Optional[str]:
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
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                print("[GEMINI] Fallback succeeded")
                return content.strip()
        else:
            print(f"[GEMINI] Error {resp.status_code}")
    except Exception as e:
        print(f"[GEMINI] Exception: {str(e)[:80]}")
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
# 1. VERIFY ACCOUNT INFO (core accuracy feature)
# ═══════════════════════════════════════════════════════

def verify_account_info(header_text: str, current_info: dict) -> dict:
    """
    AI double-checks regex-extracted account info.
    Only overrides fields where AI is confident and regex result looks wrong.
    """
    prompt = f"""You are a bank statement parsing verification tool.
The regex parser extracted these values from an Indian bank statement. 
VERIFY them against the raw text and CORRECT any errors.

REGEX RESULTS (may have errors):
- Bank: {current_info.get('bank_name', 'unknown')}
- Account Holder: {current_info.get('account_holder_name', '')}
- Account Number: {current_info.get('account_number', '')}
- IFSC: {current_info.get('ifsc', '')}

RULES:
- Account holder = PRIMARY owner (NOT nominee, NOT guardian, NOT joint unless primary)
- Look for "Customer Name", "Account Holder", "Mr./Mrs./Ms." labels
- IFSC prefix determines bank: UTIB=Axis, HDFC=HDFC, ICIC=ICICI, SBIN=SBI, CNRB=Canara, KKBK=Kotak
- If regex got it right, return the SAME value 
- Only change what's actually WRONG

Return JSON:
{{"bank_name": "lowercase", "account_holder_name": "FULL NAME", "account_number": "number", "ifsc": "CODE", "confidence": "high/medium/low"}}

RAW TEXT (first 3000 chars):
{header_text[:3000]}"""

    result = _call_groq(prompt, model=MODEL_FAST, max_tokens=512)
    parsed = _parse_json_response(result)

    if not parsed or not isinstance(parsed, dict):
        print("[AI] Account verification: no response, keeping regex result")
        return current_info

    enhanced = current_info.copy()
    confidence = parsed.get("confidence", "low")

    # Only override if AI found something better
    if parsed.get("bank_name") and parsed["bank_name"] != "unknown":
        ai_bank = parsed["bank_name"].lower().strip()
        regex_bank = current_info.get("bank_name", "").lower()
        if not regex_bank or regex_bank == "unknown":
            enhanced["bank_name"] = ai_bank
            print(f"[AI] Fixed bank: '{regex_bank}' → '{ai_bank}'")

    if parsed.get("account_holder_name") and len(parsed["account_holder_name"]) > 3:
        ai_name = parsed["account_holder_name"].strip()
        current_name = current_info.get("account_holder_name", "")
        if not current_name or len(current_name) < 3 or confidence in ("high", "medium"):
            if ai_name.upper() != current_name.upper():
                print(f"[AI] Fixed name: '{current_name}' → '{ai_name}'")
            enhanced["account_holder_name"] = ai_name

    if parsed.get("account_number") and len(str(parsed["account_number"])) > 5:
        ai_acc = str(parsed["account_number"]).strip()
        curr_acc = current_info.get("account_number", "")
        if not curr_acc or len(curr_acc) < 5:
            enhanced["account_number"] = ai_acc
            print(f"[AI] Fixed account: '{curr_acc}' → '{ai_acc}'")

    if parsed.get("ifsc") and len(str(parsed["ifsc"])) == 11:
        ai_ifsc = str(parsed["ifsc"]).strip().upper()
        curr_ifsc = current_info.get("ifsc", "")
        if not curr_ifsc:
            enhanced["ifsc"] = ai_ifsc
            print(f"[AI] Fixed IFSC: '' → '{ai_ifsc}'")

    print(f"[AI] Verified: bank={enhanced.get('bank_name')} | name={enhanced.get('account_holder_name')} | conf={confidence}")
    return enhanced


# ═══════════════════════════════════════════════════════
# 2. VERIFY TRANSACTION PARSING (fix debit/credit confusion)
# ═══════════════════════════════════════════════════════

def verify_transactions(transactions: list, raw_text: str) -> list:
    """
    AI checks the first few transactions against raw text to detect 
    systematic parsing issues (swapped debit/credit columns, wrong amounts).
    If issues found, applies corrections to ALL transactions.
    """
    if len(transactions) < 5:
        return transactions

    # Sample first 10 + last 5 transactions for verification
    sample_txns = transactions[:10] + transactions[-5:]
    sample_data = []
    for t in sample_txns:
        sample_data.append({
            "date": t.get("txn_date", ""),
            "desc": t.get("description", "")[:50],
            "debit": t.get("debit", 0),
            "credit": t.get("credit", 0),
            "balance": t.get("balance", 0),
        })

    prompt = f"""You are a bank statement parsing verifier.
Check if these parsed transactions look correct:

{json.dumps(sample_data, indent=1)}

Check for these COMMON PARSING ERRORS:
1. Debit and Credit columns SWAPPED (debits showing as credits and vice versa)
2. Balance chain doesn't make sense (balance should = prev_balance - debit + credit)
3. Amounts parsed incorrectly (wrong decimal position)

Return JSON:
{{
  "columns_swapped": true/false,
  "balance_chain_ok": true/false,  
  "issues_found": ["list of specific issues"],
  "fix_needed": "none" or "swap_debit_credit" or "description"
}}

Return ONLY JSON."""

    result = _call_groq(prompt, model=MODEL_FAST, max_tokens=512)
    parsed = _parse_json_response(result)

    if not parsed or not isinstance(parsed, dict):
        print("[AI] Transaction verification: no response")
        return transactions

    fix = parsed.get("fix_needed", "none")
    issues = parsed.get("issues_found", [])

    if issues:
        print(f"[AI] Transaction issues found: {issues}")

    if fix == "swap_debit_credit" and parsed.get("columns_swapped"):
        print("[AI] FIXING: Debit/Credit columns are swapped — correcting ALL transactions")
        for t in transactions:
            old_debit = t.get("debit", 0)
            old_credit = t.get("credit", 0)
            t["debit"] = old_credit
            t["credit"] = old_debit
        print(f"[AI] Fixed {len(transactions)} transactions (swapped debit↔credit)")
    else:
        print("[AI] Transaction structure looks correct ✓")

    return transactions


# ═══════════════════════════════════════════════════════
# 3. SMART TRANSACTION CATEGORIZATION
# ═══════════════════════════════════════════════════════

def categorize_transactions(transactions: list) -> list:
    """
    Smart AI categorization — deduplicates descriptions, categorizes unique patterns,
    then applies results to all matching transactions. Max 3-4 API calls.
    """
    if not transactions:
        return transactions

    # Step 1: Extract unique description patterns
    pattern_map = {}
    for i, t in enumerate(transactions):
        desc = t.get("description", "").strip()
        if not desc:
            continue
        norm = re.sub(r'\d{10,}', 'XXXX', desc)
        norm = re.sub(r'[\d,]+\.\d{2}', '', norm)
        norm = re.sub(r'\d{2}[-/]\d{2}[-/]\d{2,4}', '', norm)
        norm = norm.strip()[:60].upper()
        if norm not in pattern_map:
            pattern_map[norm] = {"indices": [], "sample": desc[:55], "type": "debit" if t.get("debit", 0) > 0 else "credit"}
        pattern_map[norm]["indices"].append(i)

    patterns = sorted(pattern_map.items(), key=lambda x: len(x[1]["indices"]), reverse=True)[:100]
    print(f"[AI] {len(patterns)} unique patterns from {len(transactions)} transactions")

    # Step 2: Send in compact batches of 25
    batch_size = 25
    total_batches = min((len(patterns) + batch_size - 1) // batch_size, 4)

    cats = "salary,emi,rent,investment,insurance,utility,shopping,food,travel,entertainment,transfer,credit_card,government,medical,education,atm,bank_charge,refund,other"

    for b in range(total_batches):
        start = b * batch_size
        end = min(start + batch_size, len(patterns))
        batch = patterns[start:end]

        lines = "\n".join([f"{i}|{info['type']}|{info['sample']}" for i, (_, info) in enumerate(batch, start=start)])

        prompt = f"""Categorize Indian bank transactions. Format: index|type|description
{lines}

Categories: {cats}
Return JSON array: [{{"i":0,"c":"category"}}]
ONLY JSON."""

        result = _call_groq(prompt, model=MODEL_FAST, max_tokens=2048)
        parsed = _parse_json_response(result)

        if parsed and isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict) or "i" not in item:
                    continue
                idx = item["i"]
                if 0 <= idx < len(patterns):
                    cat = item.get("c", item.get("category", "other"))
                    for txn_idx in patterns[idx][1]["indices"]:
                        transactions[txn_idx]["ai_category"] = cat
            print(f"[AI] Batch {b+1}/{total_batches}: OK")
        else:
            print(f"[AI] Batch {b+1}/{total_batches}: failed")

        if b < total_batches - 1:
            time.sleep(1.5)

    tagged = sum(1 for t in transactions if t.get("ai_category"))
    print(f"[AI] Categorized: {tagged}/{len(transactions)} transactions")
    return transactions


# ═══════════════════════════════════════════════════════
# MAIN: Run AI verification pipeline
# ═══════════════════════════════════════════════════════

def run_ai_enhancement(parsed_data: dict) -> dict:
    """
    Main entry point: AI verifies and corrects parsed data.
    Called after regex parsing, before analysis.
    Focus: ACCURACY, not insights.
    """
    groq_key = _get_groq_key()
    gemini_key = _get_gemini_key()

    if not groq_key and not gemini_key:
        print("[AI] Skipping AI verification (no API key)")
        return parsed_data

    print(f"\n{'='*50}")
    print(f"[AI] Running AI Verification Pipeline")
    print(f"{'='*50}")

    # 1. Verify account info
    header_text = parsed_data.get("_raw_text", "")
    if header_text:
        current_info = parsed_data.get("account_info", {})
        verified_info = verify_account_info(header_text, current_info)
        parsed_data["account_info"] = verified_info

    # 2. Verify transaction structure (debit/credit swaps)
    transactions = parsed_data.get("transactions", [])
    if transactions:
        transactions = verify_transactions(transactions, header_text)

    # 3. Categorize transactions
    if transactions:
        categorize_transactions(transactions)
        parsed_data["transactions"] = transactions

    parsed_data["ai_verified"] = True
    print(f"[AI] Verification pipeline complete ✓\n")
    return parsed_data


def generate_ai_insights(transactions: list, account_info: dict, health_score: dict) -> dict:
    """Generate AI-powered financial insights summary."""
    credits = [t for t in transactions if t.get("credit", 0) > 0]
    debits = [t for t in transactions if t.get("debit", 0) > 0]
    total_credit = sum(t["credit"] for t in credits)
    total_debit = sum(t["debit"] for t in debits)

    top_debits = sorted(debits, key=lambda t: t.get("debit", 0), reverse=True)[:5]
    top_credits = sorted(credits, key=lambda t: t.get("credit", 0), reverse=True)[:5]

    summary = f"""Bank Statement Summary:
- Account: {account_info.get('account_holder_name', 'Unknown')} at {account_info.get('bank_name', 'Unknown')}
- Transactions: {len(transactions)} | Credits: ₹{total_credit:,.0f} | Debits: ₹{total_debit:,.0f}
- Net: ₹{total_credit - total_debit:,.0f} | Score: {health_score.get('score', 0)}/100

Top Credits: {', '.join([f"₹{t['credit']:,.0f} {t.get('description', '')[:30]}" for t in top_credits])}
Top Debits: {', '.join([f"₹{t['debit']:,.0f} {t.get('description', '')[:30]}" for t in top_debits])}
Categories: {', '.join(set(t.get('ai_category', 'other') for t in transactions if t.get('ai_category')))}"""

    prompt = f"""{summary}

Generate financial insights. Return JSON:
{{"executive_summary": "2-3 sentences", "income_assessment": "text", "spending_pattern": "text", "risk_flags": ["list"], "recommendations": ["list of 3"], "cashflow_health": "healthy/moderate/concerning", "savings_rate_estimate": "percentage"}}
Keep each field under 80 words. ONLY JSON."""

    result = _call_groq(prompt, model=MODEL_FAST, max_tokens=2048)
    parsed = _parse_json_response(result)

    if parsed and isinstance(parsed, dict):
        print(f"[AI] Insights generated ✓")
        return parsed

    return {"executive_summary": "AI insights unavailable", "income_assessment": "", "spending_pattern": "",
            "risk_flags": [], "recommendations": [], "cashflow_health": "unknown", "savings_rate_estimate": ""}
