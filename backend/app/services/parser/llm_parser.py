"""
LLM Parser v4 — Multi-provider with Gemini Flash (massive free limits).
Provider chain: Gemini Flash → Groq → DeepSeek → Regex fallback
"""

import os
import json
import re
import time
import requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

# ─── Provider Configs ───
# Groq 8B: separate limits from 70B, very fast, good for structured extraction
# Gemini Flash: massive free limits when available
# Groq 70B: highest quality but 100K TPD shared limit
PROVIDERS = [
    {
        "name": "Groq-8B",
        "type": "openai",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "model": "llama-3.1-8b-instant",
        "max_tokens": 8192,
        "temperature": 0.0,
    },
    {
        "name": "Gemini",
        "type": "gemini",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-2.0-flash",
        "max_tokens": 8192,
        "temperature": 0.0,
    },
    {
        "name": "Groq-70B",
        "type": "openai",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 8192,
        "temperature": 0.0,
    },
    {
        "name": "DeepSeek",
        "type": "openai",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "max_tokens": 8192,
        "temperature": 0.0,
    },
]

# ─── Prompts ───

ACCOUNT_INFO_PROMPT = """Extract account information from this Indian bank statement. Return ONLY valid JSON:
{
  "bank_name": "bank name",
  "account_holder_name": "full name",
  "account_number": "digits only",
  "ifsc": "IFSC code",
  "branch_name": "branch",
  "address": "",
  "customer_id": "",
  "email": "",
  "phone": "",
  "account_type": "Savings/Current",
  "statement_period_from": "DD-MM-YYYY",
  "statement_period_to": "DD-MM-YYYY",
  "opening_balance": 0.0,
  "closing_balance": 0.0
}
Use "" for missing fields. Dates in DD-MM-YYYY. Numbers without commas. ONLY JSON, nothing else.

TEXT:
"""

TRANSACTION_PROMPT = """Extract ALL transactions from this bank statement page. Return ONLY a JSON array.

Each transaction:
{"date":"DD-MM-YYYY","description":"full narration","debit":0.00,"credit":0.00,"balance":0.00}

Rules:
- Extract EVERY transaction row that has a date - do NOT skip any
- debit = money OUT (withdrawal), credit = money IN (deposit)
- If single amount column: Dr/DR = debit, Cr/CR = credit
- Amounts as plain numbers without commas (15000.50 not 15,000.50)
- balance = running balance shown in that row
- Merge multi-line descriptions into one field
- Skip headers/footers/totals/opening balance summary lines
- Return [] if no transactions on this page
- ONLY return the JSON array, no other text

PAGE TEXT:
"""

SYSTEM_MSG = "You extract structured data from bank statements. Return ONLY valid JSON. No markdown code blocks, no explanation."


def _call_gemini(prompt: str, provider: Dict) -> Optional[str]:
    """Call Google Gemini API."""
    api_key = os.getenv(provider["key_env"], "")
    if not api_key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider['model']}:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": provider["temperature"],
            "maxOutputTokens": provider["max_tokens"],
            "responseMimeType": "application/json",
        },
        "systemInstruction": {
            "parts": [{"text": SYSTEM_MSG}]
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=120)

        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return content.strip()
            return None
        elif resp.status_code == 429:
            print(f"    [!] Gemini rate limited, waiting 5s...")
            time.sleep(5)
            return None
        else:
            print(f"    [!] Gemini error {resp.status_code}: {resp.text[:150]}")
            return None

    except Exception as e:
        print(f"    [!] Gemini exception: {str(e)[:80]}")
        return None


def _call_openai_compat(prompt: str, provider: Dict) -> Optional[str]:
    """Call OpenAI-compatible API (Groq, DeepSeek)."""
    api_key = os.getenv(provider["key_env"], "")
    if not api_key:
        return None

    try:
        resp = requests.post(
            provider["url"],
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": provider["model"],
                "messages": [
                    {"role": "system", "content": SYSTEM_MSG},
                    {"role": "user", "content": prompt}
                ],
                "temperature": provider["temperature"],
                "max_tokens": provider["max_tokens"],
            },
            timeout=120,
        )

        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            finish_reason = data["choices"][0].get("finish_reason", "")
            if finish_reason == "length":
                print(f"    [!] {provider['name']} response TRUNCATED")
            return content
        elif resp.status_code == 429:
            print(f"    [!] {provider['name']} rate limited")
            time.sleep(3)
            return None
        else:
            print(f"    [!] {provider['name']} error {resp.status_code}: {resp.text[:150]}")
            return None

    except Exception as e:
        print(f"    [!] {provider['name']} exception: {str(e)[:80]}")
        return None


def _call_llm(prompt: str, provider: Dict) -> Optional[str]:
    """Route to correct API type."""
    if provider["type"] == "gemini":
        return _call_gemini(prompt, provider)
    else:
        return _call_openai_compat(prompt, provider)


def _call_with_fallback(prompt: str) -> Optional[str]:
    """Try providers in order until one succeeds."""
    for provider in PROVIDERS:
        result = _call_llm(prompt, provider)
        if result:
            return result
    return None


def _parse_json(text: str) -> Any:
    """Extract and parse JSON from LLM response."""
    if not text:
        return None
    # Strip markdown code blocks
    text = re.sub(r'^```(?:json)?\s*\n?', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$', '', text.strip(), flags=re.MULTILINE)
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON array or object
    for pattern in [r'(\[[\s\S]*\])', r'(\{[\s\S]*\})']:
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

    # Fix trailing commas
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    return None


def extract_account_info_llm(text_pages: List[str]) -> Optional[Dict[str, Any]]:
    """Extract account info from first pages."""
    header = "\n".join(text_pages[:min(3, len(text_pages))])[:6000]
    prompt = ACCOUNT_INFO_PROMPT + header

    response = _call_with_fallback(prompt)
    if not response:
        return None

    parsed = _parse_json(response)
    if not isinstance(parsed, dict):
        return None

    info = {
        "bank_name": str(parsed.get("bank_name", "")).strip(),
        "account_holder_name": str(parsed.get("account_holder_name", "")).strip(),
        "account_number": str(parsed.get("account_number", "")).strip(),
        "ifsc": str(parsed.get("ifsc", "")).strip(),
        "branch_name": str(parsed.get("branch_name", "")).strip(),
        "address": str(parsed.get("address", "")).strip(),
        "customer_id": str(parsed.get("customer_id", "")).strip(),
        "email": str(parsed.get("email", "")).strip(),
        "phone": str(parsed.get("phone", "")).strip(),
        "account_type": str(parsed.get("account_type", "")).strip(),
        "micr_code": "",
        "account_open_date": "",
        "statement_period": {
            "from": str(parsed.get("statement_period_from", "")).strip(),
            "to": str(parsed.get("statement_period_to", "")).strip(),
        },
    }

    # Normalize bank name
    bn = info["bank_name"].lower()
    bank_map = {
        "hdfc": "hdfc", "state bank": "sbi", "sbi": "sbi", "icici": "icici",
        "axis": "axis", "kotak": "kotak", "punjab national": "pnb", "pnb": "pnb",
        "baroda": "bob", "canara": "canara", "union bank": "union", "union b": "union",
        "indian overseas": "iob", "bank of india": "boi", "central bank": "central_bank",
        "indian bank": "indian_bank", "uco": "uco", "yes bank": "yes_bank",
        "idbi": "idbi", "indusind": "indusind", "federal": "federal",
        "rbl": "rbl", "bandhan": "bandhan", "idfc": "idfc",
        "au small": "au_sfb", "equitas": "equitas", "ujjivan": "ujjivan",
        "paytm": "paytm", "citi": "citi", "hsbc": "hsbc",
        "standard chartered": "standard_chartered", "dbs": "dbs",
        "karur vysya": "karur_vysya", "karur": "karur_vysya",
    }
    for keyword, key in bank_map.items():
        if keyword in bn:
            info["bank_name"] = key
            break

    print(f"  [LLM] Account: {info['bank_name']} | {info['account_holder_name']} | {info['account_number']}")
    return info


def extract_transactions_llm(text_pages: List[str]) -> Optional[List[Dict[str, Any]]]:
    """
    Extract transactions from ALL pages — ONE PAGE AT A TIME.
    """
    all_transactions = []
    total_pages = len(text_pages)
    failed_pages = 0
    skipped_pages = 0

    print(f"  [LLM] Processing {total_pages} pages individually...")

    for page_idx in range(total_pages):
        page_text = text_pages[page_idx].strip()

        # Skip very short pages
        if len(page_text) < 50:
            skipped_pages += 1
            continue

        # Skip pages without dates
        has_dates = bool(re.search(
            r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
            page_text, re.IGNORECASE
        ))
        if not has_dates:
            print(f"  [LLM] Page {page_idx + 1}: skipped (no dates)")
            skipped_pages += 1
            continue

        prompt = TRANSACTION_PROMPT + page_text
        page_label = f"Page {page_idx + 1}/{total_pages}"

        # Try with retries
        response = None
        for attempt in range(3):
            response = _call_with_fallback(prompt)
            if response:
                break
            wait_time = 2 * (attempt + 1)
            print(f"    [{page_label}] Retry {attempt + 1}, waiting {wait_time}s...")
            time.sleep(wait_time)

        if not response:
            print(f"  [LLM] {page_label}: FAILED")
            failed_pages += 1
            continue

        parsed = _parse_json(response)

        # Handle wrapped responses
        if isinstance(parsed, dict):
            for key in ["transactions", "data", "results"]:
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                for v in parsed.values():
                    if isinstance(v, list):
                        parsed = v
                        break

        if not isinstance(parsed, list):
            print(f"  [LLM] {page_label}: bad format")
            failed_pages += 1
            continue

        # Normalize
        page_count = 0
        for txn in parsed:
            if not isinstance(txn, dict):
                continue

            normalized = {
                "txn_date": _normalize_date(str(txn.get("date", txn.get("txn_date", "")))),
                "value_date": _normalize_date(str(txn.get("value_date", ""))),
                "description": str(txn.get("description", txn.get("narration", txn.get("particulars", "")))).strip(),
                "reference_no": str(txn.get("reference", txn.get("ref", txn.get("reference_no", "")))).strip(),
                "debit": _safe_float(txn.get("debit", txn.get("withdrawal", txn.get("withdrawals", 0)))),
                "credit": _safe_float(txn.get("credit", txn.get("deposit", txn.get("deposits", 0)))),
                "balance": _safe_float(txn.get("balance", txn.get("closing_balance", 0))),
            }

            if not normalized["txn_date"]:
                continue

            all_transactions.append(normalized)
            page_count += 1

        print(f"  [LLM] {page_label}: {page_count} txns")

        # Delay between calls — Gemini: 15 RPM = 4s safe, Groq: 30 RPM = 2s
        if page_idx < total_pages - 1:
            time.sleep(1.5)

    if not all_transactions:
        return None

    # Assign serial numbers and types
    for idx, txn in enumerate(all_transactions):
        txn["sr_no"] = idx + 1
        txn["txn_type"] = "Dr." if txn["debit"] > 0 else ("Cr." if txn["credit"] > 0 else "")

    print(f"  [LLM] DONE: {len(all_transactions)} txns | {failed_pages} failed | {skipped_pages} skipped")
    return all_transactions


def _normalize_date(date_str: str) -> str:
    """Normalize any date to DD-MM-YY."""
    if not date_str or date_str in ("", "None", "null", "N/A", "none"):
        return ""
    date_str = date_str.strip()
    from datetime import datetime
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
        "%Y-%m-%d", "%d %b %Y", "%d %b %y", "%d-%b-%Y", "%d-%b-%y",
        "%d.%m.%Y", "%d.%m.%y", "%m/%d/%Y", "%d %B %Y", "%d-%B-%Y",
        "%d/%b/%Y", "%d/%b/%y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d-%m-%y")
        except ValueError:
            continue
    return date_str


def _safe_float(val) -> float:
    """Convert to float safely."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return abs(float(val))
    s = str(val).strip()
    s = re.sub(r'[₹$,\s]', '', s)
    s = re.sub(r'(Dr\.?|Cr\.?|DR|CR)\s*$', '', s, flags=re.IGNORECASE).strip()
    s = s.strip('()')
    if not s or s in ('-', '--', 'None', 'nan', 'N/A', ''):
        return 0.0
    try:
        return abs(float(s))
    except (ValueError, TypeError):
        return 0.0
