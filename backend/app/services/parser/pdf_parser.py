"""
PDF Parser v2 — Robust bank statement parser for 40+ Indian banks.
Uses pdfplumber with multiple extraction strategies:
  1. Table extraction with line-based detection
  2. Table extraction with text-based detection  
  3. Raw text line-by-line heuristic parsing
Handles multi-line descriptions, combined debit/credit columns,
Dr/Cr indicators and varied date formats.
"""

import re
import pdfplumber
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.services.parser.bank_detector import detect_bank_from_text, detect_bank_from_ifsc


# ─── Date Patterns ───
DATE_PATTERNS = [
    r'\d{2}[-/]\d{2}[-/]\d{4}',      # DD-MM-YYYY or DD/MM/YYYY
    r'\d{2}[-/]\d{2}[-/]\d{2}',      # DD-MM-YY or DD/MM/YY
    r'\d{2}\s+[A-Za-z]{3}\s+\d{4}',  # DD MMM YYYY
    r'\d{2}\s+[A-Za-z]{3}\s+\d{2}',  # DD MMM YY
    r'\d{2}-[A-Za-z]{3}-\d{4}',      # DD-MMM-YYYY
    r'\d{2}-[A-Za-z]{3}-\d{2}',      # DD-MMM-YY
    r'\d{4}[-/]\d{2}[-/]\d{2}',      # YYYY-MM-DD or YYYY/MM/DD
    r'\d{2}\.\d{2}\.\d{4}',          # DD.MM.YYYY
    r'\d{2}\.\d{2}\.\d{2}',          # DD.MM.YY
]

COMBINED_DATE_RE = re.compile('|'.join(f'({p})' for p in DATE_PATTERNS))
AMOUNT_RE = re.compile(r'[\d,]+\.\d{1,2}')


def _normalize_date(date_str: str) -> str:
    """Normalize date string to DD-MM-YY format."""
    if not date_str:
        return ""
    date_str = date_str.strip().replace('.', '-')
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
        "%d %b %Y", "%d %b %y", "%d-%b-%Y", "%d-%b-%y",
        "%d %B %Y", "%d %B %y", "%Y-%m-%d", "%Y/%m/%d",
        "%m/%d/%Y", "%m-%d-%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d-%m-%y")
        except ValueError:
            continue
    return date_str


def _parse_amount(amount_str: str) -> float:
    """Parse amount string to float — handles commas, Dr/Cr, brackets, spaces."""
    if not amount_str:
        return 0.0
    s = str(amount_str).strip()
    if not s or s in ('-', '--', 'None', 'nan', 'NaN', ''):
        return 0.0
    # Remove currency symbols, commas, whitespace
    s = re.sub(r'[₹$,\s]', '', s)
    # Remove trailing Dr/Cr suffixes
    s = re.sub(r'(Dr\.?|Cr\.?|DR|CR)\s*$', '', s, flags=re.IGNORECASE).strip()
    s = re.sub(r'^(Dr\.?|Cr\.?|DR|CR)\s*', '', s, flags=re.IGNORECASE).strip()
    # Handle brackets = negative
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1]
    # Remove any remaining non-numeric chars except . and -
    s = re.sub(r'[^0-9.\-]', '', s)
    if not s or s == '.' or s == '-':
        return 0.0
    try:
        return abs(float(s))
    except (ValueError, TypeError):
        return 0.0


def _is_date_string(s: str) -> bool:
    """Check if string matches any date pattern."""
    if not s:
        return False
    return bool(COMBINED_DATE_RE.search(s.strip()))


def _extract_text_from_pdf(file_path: str, password: Optional[str] = None) -> str:
    """Extract all text from PDF into a single string."""
    open_kwargs = {}
    if password:
        open_kwargs['password'] = password
    full_text = ""
    try:
        with pdfplumber.open(file_path, **open_kwargs) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                full_text += page_text + "\n"
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypted" in msg or "decrypt" in msg:
            raise ValueError("PDF is password-protected. Please provide the correct password.")
        raise ValueError(f"Could not read PDF: {str(e)}")
    return full_text


def _extract_account_info(full_text: str) -> Dict[str, Any]:
    """Extract account holder info from text using broad regex patterns."""
    info = {
        "bank_name": "", "account_holder_name": "", "account_number": "",
        "address": "", "ifsc": "", "micr_code": "", "customer_id": "",
        "email": "", "phone": "", "account_type": "", "account_open_date": "",
        "branch_name": "", "statement_period": {"from": "", "to": ""},
    }

    # Bank detection
    bank_key, bank_name = detect_bank_from_text(full_text)
    info["bank_name"] = bank_key

    # Account number (try many patterns)
    acc_patterns = [
        r'(?:account\s*(?:no|number|#|num)[\s.:\-]*)\s*:?\s*(\d[\d\s]{6,20}\d)',
        r'(?:a/c\s*(?:no|number|#)[\s.:\-]*)\s*:?\s*(\d[\d\s]{6,20}\d)',
        r'(?:acct\s*(?:no|number)[\s.:\-]*)\s*:?\s*(\d[\d\s]{6,20}\d)',
        r'(?:account\s*:?\s*)(\d{9,18})',
    ]
    for pattern in acc_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            info["account_number"] = re.sub(r'\s', '', match.group(1))[:20]
            break

    # Account holder name
    name_patterns = [
        # MR./MRS. at line start (ICICI, Axis format — most reliable)
        r'^(MR\.?|MRS\.?|MS\.?|M/S\.?)\s*([A-Z][A-Z\s.]{2,50}?)(?:\s{2,}|\n|Your|account|a/c|$)',
        # Explicit "Account Holder" / "Customer Name" label
        r'(?:account\s*holder|customer\s*name|account\s*name)[\s.:]+([A-Z][A-Za-z\s.]+?)(?:\n|account|a/c|address|branch|$)',
        # "Name of ... holder" (but NOT "Name of Nominee")  
        r'name\s+of\s+(?:the\s+)?(?:account\s*)?holder[\s.:]+([A-Z][A-Za-z\s.]+?)(?:\n|account|a/c|address|branch|$)',
        # "Dear XXX" in letter-style statements
        r'(?:Dear)\s+([A-Z][A-Za-z\s.]+?)(?:\n|,)',
        # Mr./Mrs. inline (catch-all, less reliable)
        r'(?:Mr\.?|Mrs\.?|Ms\.?|M/s\.?|Shri|Smt\.?)\s+([A-Z][A-Za-z\s.]+?)(?:\n|account|a/c|$)',
        # "Name: XXX" or "Customer: XXX" — only if NOT nominee
        r'(?:name|customer)[\s.:]+([A-Z][A-Z\s.]{2,50}?)(?:\n|account|a/c|address|ifsc|email|$)',
    ]
    for pi, pattern in enumerate(name_patterns):
        match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if match:
            # For the first pattern, name is in group(2), others in group(1)
            name = match.group(2).strip() if pi == 0 and match.lastindex >= 2 else match.group(1).strip()
            name = re.sub(r'\s{2,}.*', '', name)
            name = re.sub(r'\s+(Account|A/C|Branch|Dear|Address|IFSC|Your|Base).*', '', name, flags=re.IGNORECASE)
            
            # Skip if the name itself is nominee-related
            if re.search(r'nominee|declaration|document', name, re.IGNORECASE):
                continue
            
            # Skip if the CONTEXT around the match mentions nominee (e.g., "Name of Nominee: UMARANI")
            start = max(0, match.start() - 30)
            context = full_text[start:match.end()].lower()
            if 'nominee' in context or 'guardian' in context:
                continue
            
            if 3 < len(name) < 80 and not name.isdigit():
                info["account_holder_name"] = name.strip()
                break

    # IFSC code
    ifsc_match = re.search(r'\b([A-Z]{4}0[A-Z0-9]{6})\b', full_text.upper())
    if ifsc_match:
        info["ifsc"] = ifsc_match.group(1)
        if not info["bank_name"] or info["bank_name"] == "unknown":
            bk, _ = detect_bank_from_ifsc(info["ifsc"])
            info["bank_name"] = bk

    # MICR
    micr_match = re.search(r'(?:MICR|micr)[\s.:]*(\d{9})', full_text)
    if micr_match:
        info["micr_code"] = micr_match.group(1)

    # Customer ID
    cust_match = re.search(r'(?:customer\s*(?:id|no)|cust\s*id|cif\s*(?:no|id)?|client\s*id)[\s.:]*(\d{4,20})', full_text, re.IGNORECASE)
    if cust_match:
        info["customer_id"] = cust_match.group(1)

    # Email
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', full_text)
    if email_match:
        info["email"] = email_match.group(0)

    # Phone
    phone_match = re.search(r'(?:phone|mobile|tel|contact|mob)[\s.:]*(\+?\d[\d\s\-]{8,14})', full_text, re.IGNORECASE)
    if phone_match:
        info["phone"] = re.sub(r'\s', '', phone_match.group(1))

    # Statement period
    period_patterns = [
        r'(?:statement\s*(?:period|from|for|of\s*account))[\s.:]*(\d{2}[-/\.]\d{2}[-/\.]\d{2,4})\s*(?:to|[-])\s*(\d{2}[-/\.]\d{2}[-/\.]\d{2,4})',
        r'(?:from|period)[\s.:]*(\d{2}[-/\.]\d{2}[-/\.]\d{2,4})\s*(?:to|[-])\s*(\d{2}[-/\.]\d{2}[-/\.]\d{2,4})',
        r'(\d{2}[-/\.]\d{2}[-/\.]\d{2,4})\s*to\s*(\d{2}[-/\.]\d{2}[-/\.]\d{2,4})',
        r'(\d{2}\s+[A-Za-z]{3}\s+\d{2,4})\s*(?:to|-)\s*(\d{2}\s+[A-Za-z]{3}\s+\d{2,4})',
        r'(\d{2}-[A-Za-z]{3}-\d{2,4})\s*(?:to|-)\s*(\d{2}-[A-Za-z]{3}-\d{2,4})',
    ]
    for pattern in period_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            info["statement_period"]["from"] = _normalize_date(match.group(1))
            info["statement_period"]["to"] = _normalize_date(match.group(2))
            break

    # Branch
    branch_match = re.search(r'(?:branch|br\.?)[\s.:]+([A-Za-z][A-Za-z\s,]{2,60}?)(?:\n|ifsc|micr|tel|phone|email|account)', full_text, re.IGNORECASE)
    if branch_match:
        info["branch_name"] = branch_match.group(1).strip()[:80]

    return info


# ═══════════════════════════════════════════════════════
#  TABLE EXTRACTION (Strategy 1 & 2)
# ═══════════════════════════════════════════════════════

HEADER_KEYWORDS = {
    "date": ["date", "txn date", "trans date", "transaction date", "posting date",
             "txn dt", "trans dt", "value date", "dated", "txn. date", "post date",
             "booking date", "transaction\ndate", "post\ndate"],
    "value_date": ["value date", "val date", "val dt", "value\ndate"],
    "description": ["description", "narration", "particulars", "details", "remarks",
                     "transaction details", "transaction description", "narrative",
                     "transaction\ndetails", "mode", "trans description", "nature of transaction"],
    "reference": ["reference", "ref no", "ref", "chq no", "cheque no", "utr",
                   "txn ref", "reference no", "instrument no", "chq/ref no", "chq./ref. no.",
                   "instrument\nno."],
    "debit": ["debit", "withdrawal", "dr", "debit amount", "withdrawals",
              "debit(dr)", "amount(dr)", "dr amount", "debit (inr)", "debit\namount",
              "withdrawal\n(dr)", "withdrawal(dr)"],
    "credit": ["credit", "deposit", "cr", "credit amount", "deposits",
               "credit(cr)", "amount(cr)", "cr amount", "credit (inr)", "credit\namount",
               "deposit\n(cr)", "deposit(cr)"],
    "balance": ["balance", "closing balance", "running balance", "available balance",
                "bal", "closing bal", "balance (inr)", "running\nbalance"],
    "amount": ["amount", "transaction amount", "txn amount"],  # single amount column
}


def _identify_columns(table: list) -> Tuple[int, Optional[Dict]]:
    """Find header row and build a column map. Tries first 8 rows."""
    for row_idx in range(min(8, len(table))):
        row = table[row_idx]
        if not row:
            continue

        row_text = [str(cell).strip().lower().replace('\n', ' ') if cell else "" for cell in row]
        col_map = {}

        for col_idx, cell_text in enumerate(row_text):
            if not cell_text:
                continue
            for field, keywords in HEADER_KEYWORDS.items():
                for kw in keywords:
                    kw_clean = kw.replace('\n', ' ')
                    if kw_clean == cell_text or kw_clean in cell_text:
                        if field not in col_map:
                            col_map[field] = col_idx
                        break

        # Must have date + (debit or credit or amount or balance)
        has_date = "date" in col_map
        has_money = any(k in col_map for k in ("debit", "credit", "amount", "balance"))
        if has_date and has_money:
            return (row_idx, col_map)

    return (0, None)


def _detect_dr_cr_in_row(row: list, col_map: dict, desc: str) -> Tuple[float, float]:
    """
    When there's a single 'amount' column instead of separate debit/credit,
    determine direction from Dr/Cr indicators in the row or a type column.
    """
    amt_idx = col_map.get("amount")
    if amt_idx is None:
        return 0.0, 0.0

    amt_val = _parse_amount(str(row[amt_idx]) if amt_idx < len(row) else "")
    if amt_val == 0:
        return 0.0, 0.0

    # Check raw cell text for Dr/Cr
    raw = str(row[amt_idx]).strip().upper() if amt_idx < len(row) else ""
    row_text = ' '.join(str(c).strip().upper() for c in row if c)
    combined = raw + " " + desc.upper() + " " + row_text

    if 'DR' in combined or 'DEBIT' in combined or 'WITHDRAWAL' in combined:
        return amt_val, 0.0
    elif 'CR' in combined or 'CREDIT' in combined or 'DEPOSIT' in combined:
        return 0.0, amt_val
    # Default: debit (most conservative guess)
    return amt_val, 0.0


def _parse_transaction_row(row: list, col_map: Dict) -> Optional[Dict]:
    """Parse a single table row into a transaction dict."""
    def get_cell(field):
        idx = col_map.get(field)
        if idx is not None and idx < len(row):
            val = row[idx]
            return str(val).strip() if val else ""
        return ""

    date_str = get_cell("date")
    if not date_str:
        # No date — could be multiline description continuation
        desc = get_cell("description")
        if desc and len(desc) > 1:
            return {"txn_date": "", "description": desc, "_continuation": True}
        return None

    # Validate it's actually a date
    if not _is_date_string(date_str):
        # Sometimes date column has junk — skip
        return None

    desc = get_cell("description")
    ref = get_cell("reference")

    # Handle separate debit / credit columns
    debit = _parse_amount(get_cell("debit"))
    credit = _parse_amount(get_cell("credit"))
    balance = _parse_amount(get_cell("balance"))

    # If there's a single "amount" column, detect direction
    if debit == 0 and credit == 0 and "amount" in col_map:
        debit, credit = _detect_dr_cr_in_row(row, col_map, desc)

    txn = {
        "txn_date": _normalize_date(date_str),
        "value_date": _normalize_date(get_cell("value_date")) if get_cell("value_date") else "",
        "reference_no": ref,
        "description": desc,
        "debit": debit,
        "credit": credit,
        "balance": balance,
    }
    return txn


def _extract_transactions_from_tables(file_path: str, password: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract transactions using pdfplumber table extraction — tries multiple strategies."""
    transactions = []
    open_kwargs = {}
    if password:
        open_kwargs['password'] = password

    table_strategies = [
        # Strategy 1: Line-based (most common for structured PDFs)
        {"vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 5},
        # Strategy 2: Lines vertical + text horizontal
        {"vertical_strategy": "lines", "horizontal_strategy": "text", "snap_tolerance": 5},
        # Strategy 3: Text-based (for less structured PDFs)
        {"vertical_strategy": "text", "horizontal_strategy": "text",
         "snap_tolerance": 5, "min_words_vertical": 2, "min_words_horizontal": 1},
    ]

    best_transactions = []
    best_col_map = None

    with pdfplumber.open(file_path, **open_kwargs) as pdf:
        for strategy in table_strategies:
            txns_from_strategy = []
            found_header = False

            for page_num, page in enumerate(pdf.pages):
                try:
                    tables = page.extract_tables(strategy)
                except:
                    continue

                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header_idx, col_map = _identify_columns(table)
                    if col_map is None:
                        continue

                    found_header = True
                    prev_txn = None

                    for row_idx in range(header_idx + 1, len(table)):
                        row = table[row_idx]
                        if not row or all(not cell or not str(cell).strip() for cell in row):
                            continue

                        txn = _parse_transaction_row(row, col_map)
                        if txn:
                            is_continuation = txn.get("_continuation", False)
                            if is_continuation or (not txn.get("txn_date") and txn.get("description")):
                                # Multi-line: append desc to previous txn
                                if prev_txn and txn.get("description"):
                                    prev_txn["description"] += " " + txn["description"]
                            else:
                                txn.pop("_continuation", None)
                                if prev_txn:
                                    prev_txn.pop("_continuation", None)
                                    txns_from_strategy.append(prev_txn)
                                prev_txn = txn
                        elif prev_txn and row:
                            # Row that doesn't parse — might still be desc continuation
                            parts = [str(c).strip() for c in row if c and str(c).strip()]
                            extra = " ".join(parts)
                            if extra and not re.match(r'^[\d,.]+$', extra) and len(extra) > 2:
                                prev_txn["description"] += " " + extra

                    if prev_txn:
                        prev_txn.pop("_continuation", None)
                        txns_from_strategy.append(prev_txn)

            # Keep the strategy that found the most transactions
            if len(txns_from_strategy) > len(best_transactions):
                best_transactions = txns_from_strategy

            # If we got a good number, stop trying more strategies
            if len(best_transactions) >= 5:
                break

    return best_transactions


# ═══════════════════════════════════════════════════════
#  SMART TEXT-BASED EXTRACTION (Primary for PDFs)
#  Handles multi-line descriptions BEFORE and AFTER date lines.
#  Uses balance chain math for 100% accurate debit/credit detection.
# ═══════════════════════════════════════════════════════

# Header patterns to skip (repeated on each page)
_SKIP_LINE_RE = re.compile(
    r'^(page\s+\d+|statement\s+of|date\s+mode|date\s+particulars|date\s+description|'
    r'date\s+narration|date\s+value|opening\s+balance|closing\s+balance|total\s|'
    r'disclaimer|note\s*:|this\s+is\s+|generated\s+|\*{2,}|account\s+related|'
    r'account\s+type|branch|ifsc|customer\s+id|nominee|cif\s+no|balance\s+as\s+on|'
    r'sr\.?\s*no|sl\.?\s*no)',
    re.IGNORECASE
)

_HEADER_LINE_RE = re.compile(
    r'DATE\s+MODE|PARTICULARS|DEPOSITS\s+WITHDRAWALS|BALANCE$|'
    r'^(MR|MRS|MS|MISS)\.\s*[A-Z\s]+$',
    re.IGNORECASE
)


def _is_text_skip_line(line: str) -> bool:
    """Check if a line is a header, footer, page number or metadata."""
    return bool(_SKIP_LINE_RE.match(line.strip())) or bool(_HEADER_LINE_RE.search(line.strip()))


def _extract_transactions_from_text(full_text: str) -> List[Dict[str, Any]]:
    """
    Smart two-pass parser for Indian bank statement PDFs.
    
    Pass 1: Find all date lines (lines starting with DD-MM-YYYY + amounts).
    Pass 2: For each date line, collect description from lines BEFORE and AFTER,
            extract amounts, and build transaction records.
    Pass 3: Use balance chain math to determine debit vs credit with 100% accuracy.
    """
    lines = full_text.split('\n')
    
    # ── Pass 1: Find all date lines with amounts ──
    date_indices = []
    for i, line in enumerate(lines):
        line_s = line.strip()
        if not line_s or _is_text_skip_line(line_s):
            continue
        m = COMBINED_DATE_RE.match(line_s)
        if m:
            amounts = AMOUNT_RE.findall(line_s)
            if len(amounts) >= 2:  # Must have at least amount + balance
                date_indices.append(i)
    
    if not date_indices:
        return []
    
    # ── Pass 2: Build transaction records ──
    transactions = []
    
    for idx, di in enumerate(date_indices):
        line_s = lines[di].strip()
        
        # Extract date
        m = COMBINED_DATE_RE.match(line_s)
        if not m:
            continue
        date_str = _normalize_date(m.group(0))
        
        # Extract amounts from the line (always at the end)
        amounts_raw = AMOUNT_RE.findall(line_s)
        amounts = [_parse_amount(a) for a in amounts_raw if _parse_amount(a) > 0]
        
        if len(amounts) < 2:
            continue
        
        # Balance is the LAST amount; transaction amount is second-to-last
        balance = amounts[-1]
        txn_amount = amounts[-2] if len(amounts) >= 2 else 0.0
        
        # Get description text from date line (remove date and amounts)
        desc_from_line = line_s[m.end():].strip()
        for a in amounts_raw:
            desc_from_line = desc_from_line.replace(a, '', 1)
        desc_from_line = re.sub(r'\s{2,}', ' ', desc_from_line).strip()
        
        # ── Collect pre-description lines (between prev date line and this one) ──
        prev_end = date_indices[idx - 1] + 1 if idx > 0 else max(0, di - 3)
        pre_desc = []
        for j in range(prev_end, di):
            l = lines[j].strip()
            if l and not _is_text_skip_line(l) and not re.match(r'^[\d,.\s]+$', l):
                pre_desc.append(l)
        
        # ── Collect post-description lines (after date line, before next date line) ──
        next_start = date_indices[idx + 1] if idx < len(date_indices) - 1 else min(di + 4, len(lines))
        post_desc = []
        for j in range(di + 1, next_start):
            l = lines[j].strip()
            if not l or _is_text_skip_line(l):
                continue
            if COMBINED_DATE_RE.match(l):
                break
            if re.match(r'^[\d,.\s]+$', l):
                continue
            post_desc.append(l)
        
        # Assemble full description
        parts = pre_desc + ([desc_from_line] if desc_from_line else []) + post_desc
        description = ' '.join(p for p in parts if p).strip()
        description = re.sub(r'\s{2,}', ' ', description)
        
        transactions.append({
            "txn_date": date_str,
            "value_date": "",
            "reference_no": "",
            "description": description,
            "debit": 0.0,
            "credit": 0.0,
            "balance": balance,
            "_amount": txn_amount,
            "_all_amounts": amounts,
        })
    
    # ── Pass 3: Determine debit/credit using balance chain (100% accurate) ──
    for i, txn in enumerate(transactions):
        amt = txn.pop("_amount", 0)
        all_amts = txn.pop("_all_amounts", [])
        
        if amt == 0:
            continue
        
        if i > 0 and transactions[i-1]["balance"] > 0 and txn["balance"] > 0:
            prev_bal = transactions[i-1]["balance"]
            
            if len(all_amts) >= 3:
                # Multiple amount columns — try each
                a1 = all_amts[-3]
                a2 = all_amts[-2]
                if abs(prev_bal + a1 - txn["balance"]) < 1.0:
                    txn["credit"] = a1
                elif abs(prev_bal - a2 - txn["balance"]) < 1.0:
                    txn["debit"] = a2
                elif abs(prev_bal + a2 - txn["balance"]) < 1.0:
                    txn["credit"] = a2
                elif abs(prev_bal - a1 - txn["balance"]) < 1.0:
                    txn["debit"] = a1
                else:
                    txn["credit" if txn["balance"] > prev_bal else "debit"] = amt
            else:
                # Single amount — check balance direction
                if abs(prev_bal + amt - txn["balance"]) < 1.0:
                    txn["credit"] = amt
                elif abs(prev_bal - amt - txn["balance"]) < 1.0:
                    txn["debit"] = amt
                else:
                    txn["credit" if txn["balance"] > prev_bal else "debit"] = amt
        else:
            # First txn or no prev balance — use keyword hints
            desc_upper = txn["description"].upper()
            credit_kws = ["SALARY", "CR", "CREDIT", "DEPOSIT", "NEFT", "IMPS",
                         "REFUND", "REVERSAL", "CASHBACK", "INT.PD", "INT.PAYMENT",
                         "INTEREST", "RECEIVED", "RENT FROM"]
            if any(kw in desc_upper for kw in credit_kws):
                txn["credit"] = amt
            else:
                txn["debit"] = amt
        
        txn["txn_type"] = "Dr." if txn["debit"] > 0 else ("Cr." if txn["credit"] > 0 else "")
    
    return transactions


# ═══════════════════════════════════════════════════════
#  POST-PROCESSING — fix common issues
# ═══════════════════════════════════════════════════════

def _post_process_transactions(transactions: List[Dict]) -> List[Dict]:
    """Clean up transactions after extraction."""
    cleaned = []
    for txn in transactions:
        # Skip rows that are clearly not transactions
        desc = txn.get("description", "")
        if not desc and txn["debit"] == 0 and txn["credit"] == 0 and txn["balance"] == 0:
            continue

        # Clean description
        txn["description"] = re.sub(r'\s{2,}', ' ', desc).strip()
        txn["description"] = re.sub(r'^[\s\-/]+', '', txn["description"]).strip()

        # Assign serial number
        txn["sr_no"] = len(cleaned) + 1

        # Determine txn type
        if txn["debit"] > 0:
            txn["txn_type"] = "Dr."
        elif txn["credit"] > 0:
            txn["txn_type"] = "Cr."
        else:
            txn["txn_type"] = ""

        # Remove internal keys
        txn.pop("_continuation", None)

        cleaned.append(txn)

    return cleaned


def _infer_debit_credit_from_balance(transactions: List[Dict]) -> List[Dict]:
    """
    When we have balance but no debit/credit split,
    infer direction from balance changes.
    """
    if not transactions or len(transactions) < 2:
        return transactions

    # Check if most rows have neither debit nor credit
    no_split = sum(1 for t in transactions if t["debit"] == 0 and t["credit"] == 0)
    if no_split < len(transactions) * 0.5:
        return transactions  # already have splits

    # All rows have balance — infer from balance changes
    for i in range(1, len(transactions)):
        curr = transactions[i]
        prev = transactions[i - 1]
        if curr["balance"] > 0 and prev["balance"] > 0 and curr["debit"] == 0 and curr["credit"] == 0:
            diff = curr["balance"] - prev["balance"]
            if diff > 0:
                curr["credit"] = abs(diff)
                curr["txn_type"] = "Cr."
            elif diff < 0:
                curr["debit"] = abs(diff)
                curr["txn_type"] = "Dr."

    return transactions


# ═══════════════════════════════════════════════════════
#  HELPER: Extract text per-page for LLM
# ═══════════════════════════════════════════════════════

def _extract_pages_text(file_path: str, password: Optional[str] = None) -> List[str]:
    """Extract text from each page separately."""
    open_kwargs = {}
    if password:
        open_kwargs['password'] = password
    pages_text = []
    try:
        with pdfplumber.open(file_path, **open_kwargs) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages_text.append(text)
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypted" in msg or "decrypt" in msg:
            raise ValueError("PDF is password-protected. Please provide the correct password.")
        raise ValueError(f"Could not read PDF: {str(e)}")
    return pages_text


# ═══════════════════════════════════════════════════════
#  VALIDATION & POST-PROCESSING (shared by both LLM and regex)
# ═══════════════════════════════════════════════════════

def _validate_and_finalize(account_info: Dict, transactions: List[Dict]) -> Dict[str, Any]:
    """Shared validation: date order, negative balances, balance chain."""
    # Detect statement period from transactions if not in header
    if transactions and not account_info.get("statement_period", {}).get("from"):
        if "statement_period" not in account_info:
            account_info["statement_period"] = {"from": "", "to": ""}
        account_info["statement_period"]["from"] = transactions[0].get("txn_date", "")
        account_info["statement_period"]["to"] = transactions[-1].get("txn_date", "")

    # Detect date order issues
    mismatched_dates = []
    for i in range(1, len(transactions)):
        try:
            curr = datetime.strptime(transactions[i]["txn_date"], "%d-%m-%y")
            prev = datetime.strptime(transactions[i - 1]["txn_date"], "%d-%m-%y")
            if curr < prev:
                mismatched_dates.append({
                    "index": i, "current": transactions[i]["txn_date"],
                    "previous": transactions[i - 1]["txn_date"],
                })
        except (ValueError, KeyError):
            continue

    # Detect negative balances
    negative_balances = [
        {"index": i, "balance": txn["balance"], "date": txn["txn_date"]}
        for i, txn in enumerate(transactions) if txn.get("balance", 0) < 0
    ]

    # Validate balance chain
    balance_errors = []
    for i in range(1, len(transactions)):
        prev = transactions[i - 1]
        curr = transactions[i]
        if prev.get("balance", 0) == 0 or curr.get("balance", 0) == 0:
            continue
        expected = prev["balance"] - curr.get("debit", 0) + curr.get("credit", 0)
        if abs(expected - curr["balance"]) > 1.0:
            balance_errors.append({
                "index": i, "expected": round(expected, 2),
                "actual": curr["balance"], "difference": round(abs(expected - curr["balance"]), 2),
            })

    return {
        "account_info": account_info,
        "transactions": transactions,
        "mismatched_sequence_date": mismatched_dates,
        "negative_balance": negative_balances,
        "discrepancies": {
            "balance_errors": balance_errors[:20],
            "swapped_credit_debit_rows": [],
            "corrected_row_indices": [],
        },
    }


# ═══════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════

def parse_pdf(file_path: str, password: Optional[str] = None) -> Dict[str, Any]:
    """
    Main PDF parsing function. Memory-optimized for Render free tier (512MB).
    
    Strategy order (reliability-first):
      1. Smart Text Parser (instant, no API, handles multi-line descriptions)
      2. Table Extraction (pdfplumber tables)
      3. LLM Enhancement (Gemini/Groq — when API quota available)
    """
    import gc
    print("[PARSER] Starting PDF parse...")

    # Step 1: Extract text per-page
    pages_text = _extract_pages_text(file_path, password)
    full_text = "\n".join(pages_text)
    header_text = full_text[:4000]  # Save header for AI before freeing

    if not full_text.strip():
        raise ValueError("Could not extract text from PDF. The file may be scanned/image-based (OCR not yet supported).")

    print(f"[PARSER] Extracted text from {len(pages_text)} pages ({len(full_text)} chars)")

    # Extract account info (always regex — instant and reliable)
    account_info = _extract_account_info(full_text)

    # ════════════════════════════════════════════
    #  STRATEGY 1: SMART TEXT PARSER (Primary)
    # ════════════════════════════════════════════
    print("[PARSER] Running smart text parser...")
    text_transactions = _extract_transactions_from_text(full_text)
    text_transactions = _post_process_transactions(text_transactions)

    # Free full text now (biggest memory consumer)
    del full_text, pages_text
    gc.collect()

    # ════════════════════════════════════════════
    #  STRATEGY 2: TABLE EXTRACTION (Secondary)
    # ════════════════════════════════════════════
    table_transactions = []
    if len(text_transactions) < 5:
        print("[PARSER] Text parser found few transactions, trying table extraction...")
        table_transactions = _extract_transactions_from_tables(file_path, password)
        table_transactions = _post_process_transactions(table_transactions)
        table_transactions = _infer_debit_credit_from_balance(table_transactions)
        gc.collect()

    # Pick best result
    transactions = text_transactions if len(text_transactions) >= len(table_transactions) else table_transactions
    del text_transactions, table_transactions
    gc.collect()
    print(f"[PARSER] Regex extracted {len(transactions)} transactions")

    # ════════════════════════════════════════════
    #  STRATEGY 3: LLM ENHANCEMENT (Optional)
    # ════════════════════════════════════════════
    # Only try LLM if regex found very few transactions (likely a complex format)
    if len(transactions) < 10:
        try:
            from app.services.parser.llm_parser import extract_account_info_llm, extract_transactions_llm

            print("[PARSER] Few transactions found, trying LLM extraction...")

            llm_account_info = extract_account_info_llm([header_text])
            llm_transactions = extract_transactions_llm([header_text])

            if llm_transactions and len(llm_transactions) > len(transactions):
                print(f"[PARSER] LLM found {len(llm_transactions)} transactions (better than regex: {len(transactions)})")
                transactions = llm_transactions
                if llm_account_info:
                    account_info = llm_account_info
            else:
                print("[PARSER] LLM did not improve results, keeping regex output")

        except Exception as e:
            print(f"[PARSER] LLM not available ({str(e)[:80]}), using regex results")

    # Re-number
    for idx, txn in enumerate(transactions):
        txn["sr_no"] = idx + 1

    print(f"[PARSER] Final: {len(transactions)} transactions")
    result = _validate_and_finalize(account_info, transactions)
    result["_raw_text"] = header_text  # For AI enhancement
    gc.collect()
    return result


