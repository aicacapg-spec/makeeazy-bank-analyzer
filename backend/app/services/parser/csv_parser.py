"""
CSV Parser — Extracts transactions from bank statement CSV/TXT files.
Uses built-in csv module (no pandas dependency for low memory).
"""

import re
import csv
from typing import Dict, Any, List
from datetime import datetime

from app.services.parser.bank_detector import detect_bank_from_text


def _detect_delimiter(file_path: str) -> str:
    """Detect CSV delimiter."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        sample = f.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        return dialect.delimiter
    except csv.Error:
        return ','


def _normalize_date(date_str: str) -> str:
    """Normalize date from CSV."""
    if not date_str or not date_str.strip():
        return ""
    date_str = date_str.strip()
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
        "%Y-%m-%d", "%d %b %Y", "%d %b %y", "%d-%b-%Y", "%d-%b-%y",
        "%m/%d/%Y", "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%d-%m-%y")
        except ValueError:
            continue
    return date_str


def _parse_amount(val: str) -> float:
    """Parse amount value."""
    if not val or not str(val).strip():
        return 0.0
    cleaned = re.sub(r'[₹,\s"\'()]', '', str(val).strip())
    cleaned = re.sub(r'(Dr\.?|Cr\.?|DR|CR)$', '', cleaned, flags=re.IGNORECASE).strip()
    try:
        return abs(float(cleaned))
    except (ValueError, TypeError):
        return 0.0


COLUMN_MAPPINGS = {
    "date": ["date", "txn date", "transaction date", "trans date", "posting date"],
    "value_date": ["value date", "val date"],
    "description": ["description", "narration", "particulars", "details", "remarks"],
    "reference": ["reference", "ref no", "ref", "chq no", "cheque no", "utr"],
    "debit": ["debit", "withdrawal", "dr", "debit amount", "withdrawals"],
    "credit": ["credit", "deposit", "cr", "credit amount", "deposits"],
    "balance": ["balance", "closing balance", "running balance"],
}


def parse_csv(file_path: str) -> Dict[str, Any]:
    """Parse CSV/TXT bank statement file."""
    delimiter = _detect_delimiter(file_path)

    # Try different encodings
    rows = []
    headers = []
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                reader = csv.reader(f, delimiter=delimiter)
                all_rows = list(reader)
                if all_rows:
                    headers = [h.strip() for h in all_rows[0]]
                    rows = all_rows[1:]
                break
        except Exception:
            continue

    if not headers or not rows:
        raise ValueError("Could not read CSV file or file is empty.")

    # Detect bank from content
    all_text = ' '.join([' '.join(r) for r in rows[:50]])
    bank_key, _ = detect_bank_from_text(all_text[:2000])

    # Map columns
    col_map = {}
    for i, col in enumerate(headers):
        col_lower = col.lower().strip()
        for field, keywords in COLUMN_MAPPINGS.items():
            if any(kw == col_lower or kw in col_lower for kw in keywords):
                if field not in col_map:
                    col_map[field] = i
                    break

    if "date" not in col_map:
        raise ValueError("Could not identify date column in CSV file.")

    # Extract transactions
    transactions = []
    for row in rows:
        if len(row) <= col_map.get("date", 0):
            continue
        date_str = _normalize_date(row[col_map["date"]])
        if not date_str:
            continue

        def get_val(field):
            idx = col_map.get(field)
            if idx is not None and idx < len(row):
                return row[idx]
            return ""

        debit = _parse_amount(get_val("debit"))
        credit = _parse_amount(get_val("credit"))

        txn = {
            "sr_no": len(transactions) + 1,
            "txn_date": date_str,
            "value_date": _normalize_date(get_val("value_date")) if "value_date" in col_map else "",
            "reference_no": get_val("reference").strip(),
            "description": get_val("description").strip(),
            "debit": debit,
            "credit": credit,
            "balance": _parse_amount(get_val("balance")),
            "txn_type": "Dr." if debit > 0 else ("Cr." if credit > 0 else ""),
        }
        transactions.append(txn)

    account_info = {
        "bank_name": bank_key,
        "account_holder_name": "",
        "account_number": "",
        "address": "",
        "ifsc": "",
        "micr_code": "",
        "customer_id": "",
        "email": "",
        "phone": "",
        "account_type": "",
        "account_open_date": "",
        "branch_name": "",
        "statement_period": {
            "from": transactions[0]["txn_date"] if transactions else "",
            "to": transactions[-1]["txn_date"] if transactions else "",
        },
    }

    return {
        "account_info": account_info,
        "transactions": transactions,
        "mismatched_sequence_date": [],
        "negative_balance": [],
        "discrepancies": {"balance_errors": [], "swapped_credit_debit_rows": [], "corrected_row_indices": []},
    }
