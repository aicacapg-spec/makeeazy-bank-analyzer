"""
CSV Parser — Extracts transactions from bank statement CSV/TXT files.
Auto-detects delimiters, column headers, and maps to standard format.
"""

import pandas as pd
import re
import csv
from typing import Dict, Any, List
from datetime import datetime
from io import StringIO

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


def _normalize_date(date_val) -> str:
    """Normalize date from CSV."""
    if pd.isna(date_val) or not str(date_val).strip():
        return ""
    date_str = str(date_val).strip()
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


def _parse_amount(val) -> float:
    """Parse amount value."""
    if pd.isna(val) or val is None or str(val).strip() == '':
        return 0.0
    cleaned = re.sub(r'[₹,\s"\']', '', str(val).strip())
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
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, dtype=str)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    else:
        raise ValueError("Could not read CSV file with any supported encoding.")

    if df.empty:
        raise ValueError("CSV file is empty.")

    # Detect bank from content
    all_text = ' '.join(df.astype(str).values.flatten())
    bank_key, _ = detect_bank_from_text(all_text[:2000])

    # Map columns
    col_map = {}
    for col in df.columns:
        col_lower = str(col).strip().lower()
        for field, keywords in COLUMN_MAPPINGS.items():
            if any(kw == col_lower or kw in col_lower for kw in keywords):
                if field not in col_map:
                    col_map[field] = col
                    break

    if "date" not in col_map:
        raise ValueError("Could not identify date column in CSV file.")

    # Extract transactions
    transactions = []
    for _, row in df.iterrows():
        date_str = _normalize_date(row.get(col_map.get("date", ""), ""))
        if not date_str:
            continue

        txn = {
            "sr_no": len(transactions) + 1,
            "txn_date": date_str,
            "value_date": _normalize_date(row.get(col_map.get("value_date", ""), "")) if "value_date" in col_map else "",
            "reference_no": str(row.get(col_map.get("reference", ""), "")).strip() if "reference" in col_map else "",
            "description": str(row.get(col_map.get("description", ""), "")).strip() if "description" in col_map else "",
            "debit": _parse_amount(row.get(col_map.get("debit", ""), 0)) if "debit" in col_map else 0.0,
            "credit": _parse_amount(row.get(col_map.get("credit", ""), 0)) if "credit" in col_map else 0.0,
            "balance": _parse_amount(row.get(col_map.get("balance", ""), 0)) if "balance" in col_map else 0.0,
        }

        if txn["debit"] > 0:
            txn["txn_type"] = "Dr."
        elif txn["credit"] > 0:
            txn["txn_type"] = "Cr."
        else:
            txn["txn_type"] = ""

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
