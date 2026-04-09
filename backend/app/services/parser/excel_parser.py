"""
Excel Parser — Extracts transactions from bank statement Excel files (.xlsx, .xls).
Auto-detects column headers and maps to standard transaction format.
"""

import pandas as pd
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.parser.bank_detector import detect_bank_from_text


# Common column name mappings
COLUMN_MAPPINGS = {
    "date": ["date", "txn date", "transaction date", "trans date", "posting date", "value date",
             "txn dt", "trans dt", "dated"],
    "value_date": ["value date", "val date", "value dt"],
    "description": ["description", "narration", "particulars", "details", "remarks",
                     "transaction details", "transaction description", "trans description", "narrative"],
    "reference": ["reference", "ref no", "ref", "chq no", "cheque no", "utr", "txn ref",
                   "reference no", "instrument no"],
    "debit": ["debit", "withdrawal", "dr", "debit amount", "withdrawals", "debit(dr)",
              "amount(dr)", "dr amount", "debit (inr)"],
    "credit": ["credit", "deposit", "cr", "credit amount", "deposits", "credit(cr)",
               "amount(cr)", "cr amount", "credit (inr)"],
    "balance": ["balance", "closing balance", "running balance", "available balance",
                "bal", "closing bal", "balance (inr)"],
}


def _find_header_row(df: pd.DataFrame) -> int:
    """Find the row containing column headers."""
    for idx in range(min(20, len(df))):
        row = df.iloc[idx]
        row_text = ' '.join(str(val).lower() for val in row if pd.notna(val))
        # Check for key header words
        if any(kw in row_text for kw in ["date", "narration", "description", "particulars"]):
            if any(kw in row_text for kw in ["debit", "credit", "withdrawal", "deposit", "balance", "amount"]):
                return idx
    return 0


def _map_columns(headers: List[str]) -> Dict[str, int]:
    """Map actual column names to standard field names."""
    col_map = {}
    for idx, header in enumerate(headers):
        if not header or pd.isna(header):
            continue
        header_lower = str(header).strip().lower()
        for field, keywords in COLUMN_MAPPINGS.items():
            if any(kw == header_lower or kw in header_lower for kw in keywords):
                if field not in col_map:
                    col_map[field] = idx
                    break
    return col_map


def _normalize_date(date_val) -> str:
    """Normalize date values from Excel."""
    if pd.isna(date_val):
        return ""
    if isinstance(date_val, datetime):
        return date_val.strftime("%d-%m-%y")
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
    cleaned = re.sub(r'[₹,\s]', '', str(val).strip())
    cleaned = re.sub(r'(Dr\.?|Cr\.?|DR|CR)$', '', cleaned, flags=re.IGNORECASE).strip()
    try:
        return abs(float(cleaned))
    except (ValueError, TypeError):
        return 0.0


def parse_excel(file_path: str) -> Dict[str, Any]:
    """
    Parse Excel bank statement file.
    Returns structured data with account_info and transactions.
    """
    # Read Excel file
    try:
        df = pd.read_excel(file_path, header=None, engine='openpyxl')
    except Exception:
        try:
            df = pd.read_excel(file_path, header=None, engine='xlrd')
        except Exception as e:
            raise ValueError(f"Could not read Excel file: {str(e)}")

    if df.empty:
        raise ValueError("Excel file is empty.")

    # Extract text from first few rows for bank detection
    header_text = ' '.join(str(val) for row in df.head(10).values for val in row if pd.notna(val))

    # Detect bank
    bank_key, bank_name = detect_bank_from_text(header_text)

    # Find header row
    header_row = _find_header_row(df)

    # Get headers and map columns
    headers = [str(val).strip() if pd.notna(val) else "" for val in df.iloc[header_row]]
    col_map = _map_columns(headers)

    if "date" not in col_map:
        raise ValueError("Could not identify date column in Excel file.")

    # Extract transactions
    transactions = []
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]

        # Get date
        date_val = row.iloc[col_map["date"]] if "date" in col_map else None
        date_str = _normalize_date(date_val)
        if not date_str:
            continue

        txn = {
            "sr_no": len(transactions) + 1,
            "txn_date": date_str,
            "value_date": _normalize_date(row.iloc[col_map["value_date"]]) if "value_date" in col_map else "",
            "reference_no": str(row.iloc[col_map["reference"]]).strip() if "reference" in col_map and pd.notna(row.iloc[col_map["reference"]]) else "",
            "description": str(row.iloc[col_map["description"]]).strip() if "description" in col_map and pd.notna(row.iloc[col_map["description"]]) else "",
            "debit": _parse_amount(row.iloc[col_map["debit"]]) if "debit" in col_map else 0.0,
            "credit": _parse_amount(row.iloc[col_map["credit"]]) if "credit" in col_map else 0.0,
            "balance": _parse_amount(row.iloc[col_map["balance"]]) if "balance" in col_map else 0.0,
        }

        # Determine txn type
        if txn["debit"] > 0:
            txn["txn_type"] = "Dr."
        elif txn["credit"] > 0:
            txn["txn_type"] = "Cr."
        else:
            txn["txn_type"] = ""

        transactions.append(txn)

    # Build account info
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

    # Try to extract more info from header rows
    for idx in range(min(header_row, 15)):
        row_text = ' '.join(str(val) for val in df.iloc[idx] if pd.notna(val))
        # Account number
        acc_match = re.search(r'(?:account\s*(?:no|number|#)[\s.:]*)\s*(\d{6,20})', row_text, re.IGNORECASE)
        if acc_match:
            account_info["account_number"] = acc_match.group(1)
        # Name
        name_match = re.search(r'(?:name|holder|customer)[\s.:]+([A-Za-z\s.]+)', row_text, re.IGNORECASE)
        if name_match:
            account_info["account_holder_name"] = name_match.group(1).strip()
        # IFSC
        ifsc_match = re.search(r'\b([A-Z]{4}0[A-Z0-9]{6})\b', row_text.upper())
        if ifsc_match:
            account_info["ifsc"] = ifsc_match.group(1)

    return {
        "account_info": account_info,
        "transactions": transactions,
        "mismatched_sequence_date": [],
        "negative_balance": [],
        "discrepancies": {"balance_errors": [], "swapped_credit_debit_rows": [], "corrected_row_indices": []},
    }
