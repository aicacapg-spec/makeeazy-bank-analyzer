"""
Bank Detection Module — Identifies bank from PDF/text content using keyword patterns.
Supports all major Indian banks.
"""

import re
from typing import Optional, Tuple

# Bank detection patterns: (bank_key, display_name, [keywords])
BANK_PATTERNS = [
    # Public Sector Banks
    ("sbi", "State Bank of India", [
        r"state\s*bank\s*of\s*india", r"\bsbin\b", r"sbi\d", r"onlinesbi",
        r"sbicard", r"sbicap"
    ]),
    ("pnb", "Punjab National Bank", [
        r"punjab\s*national\s*bank", r"\bpunb\b", r"pnbindia"
    ]),
    ("bob", "Bank of Baroda", [
        r"bank\s*of\s*baroda", r"\bbarb\b", r"bankofbaroda"
    ]),
    ("canara", "Canara Bank", [
        r"canara\s*bank", r"\bcnrb\b", r"canarabank"
    ]),
    ("union", "Union Bank of India", [
        r"union\s*bank\s*of\s*india", r"\bubin\b", r"unionbankofindia"
    ]),
    ("iob", "Indian Overseas Bank", [
        r"indian\s*overseas\s*bank", r"\bioba\b"
    ]),
    ("boi", "Bank of India", [
        r"bank\s*of\s*india", r"\bbkid\b"
    ]),
    ("central_bank", "Central Bank of India", [
        r"central\s*bank\s*of\s*india", r"\bcbin\b"
    ]),
    ("indian_bank", "Indian Bank", [
        r"indian\s*bank", r"\bidib\b"
    ]),
    ("uco", "UCO Bank", [
        r"uco\s*bank", r"\bucba\b"
    ]),
    ("bank_of_maharashtra", "Bank of Maharashtra", [
        r"bank\s*of\s*maharashtra", r"\bmahb\b"
    ]),
    ("punjab_sind", "Punjab & Sind Bank", [
        r"punjab\s*(&|and)\s*sind\s*bank", r"\bpsib\b"
    ]),

    # Private Sector Banks
    ("hdfc", "HDFC Bank", [
        r"hdfc\s*bank", r"\bhdfc\b", r"hdfcbank"
    ]),
    ("icici", "ICICI Bank", [
        r"icici\s*bank", r"\bicic\b", r"icicibank"
    ]),
    ("axis", "Axis Bank", [
        r"axis\s*bank", r"\butib\b", r"axisbank"
    ]),
    ("kotak", "Kotak Mahindra Bank", [
        r"kotak\s*mahindra", r"\bkkbk\b", r"kotak\s*bank", r"kotakbank"
    ]),
    ("yes_bank", "Yes Bank", [
        r"yes\s*bank", r"\byesb\b"
    ]),
    ("idbi", "IDBI Bank", [
        r"idbi\s*bank", r"\bibkl\b"
    ]),
    ("indusind", "IndusInd Bank", [
        r"indusind\s*bank", r"\bindb\b"
    ]),
    ("federal", "Federal Bank", [
        r"federal\s*bank", r"\bfdrl\b"
    ]),
    ("south_indian", "South Indian Bank", [
        r"south\s*indian\s*bank", r"\bsibl\b"
    ]),
    ("rbl", "RBL Bank", [
        r"rbl\s*bank", r"\bratn\b", r"ratnakar"
    ]),
    ("bandhan", "Bandhan Bank", [
        r"bandhan\s*bank", r"\bbdbl\b"
    ]),
    ("idfc", "IDFC First Bank", [
        r"idfc\s*first", r"idfc\s*bank", r"\bidfb\b"
    ]),
    ("csb", "CSB Bank", [
        r"csb\s*bank", r"catholic\s*syrian", r"\bcsbk\b"
    ]),
    ("karur_vysya", "Karur Vysya Bank", [
        r"karur\s*vysya", r"\bkvbl\b"
    ]),
    ("city_union", "City Union Bank", [
        r"city\s*union\s*bank", r"\bciub\b"
    ]),
    ("dcb", "DCB Bank", [
        r"dcb\s*bank", r"development\s*credit\s*bank", r"\bdcbl\b"
    ]),
    ("dhanlaxmi", "Dhanlaxmi Bank", [
        r"dhanlaxmi\s*bank", r"\bdlxb\b"
    ]),
    ("karnataka", "Karnataka Bank", [
        r"karnataka\s*bank", r"\bkarb\b"
    ]),
    ("tamilnad_mercantile", "Tamilnad Mercantile Bank", [
        r"tamilnad\s*mercantile", r"\btmbl\b"
    ]),

    # Small Finance Banks
    ("au_sfb", "AU Small Finance Bank", [
        r"au\s*small\s*finance", r"\baubl\b", r"au\s*bank"
    ]),
    ("equitas", "Equitas Small Finance Bank", [
        r"equitas", r"\besfb\b"
    ]),
    ("ujjivan", "Ujjivan Small Finance Bank", [
        r"ujjivan", r"\bujvn\b"
    ]),
    ("fincare", "Fincare Small Finance Bank", [
        r"fincare", r"\bfncr\b"
    ]),

    # Payments Banks & Digital
    ("paytm", "Paytm Payments Bank", [
        r"paytm\s*payments\s*bank", r"\bpytm\b"
    ]),
    ("airtel", "Airtel Payments Bank", [
        r"airtel\s*payments\s*bank"
    ]),
    ("jio", "Jio Payments Bank", [
        r"jio\s*payments\s*bank"
    ]),

    # Foreign Banks in India
    ("citi", "Citibank", [
        r"citibank", r"\bciti\b"
    ]),
    ("hsbc", "HSBC", [
        r"hsbc", r"hongkong\s*and\s*shanghai"
    ]),
    ("standard_chartered", "Standard Chartered", [
        r"standard\s*chartered", r"\bscbl\b"
    ]),
    ("deutsche", "Deutsche Bank", [
        r"deutsche\s*bank", r"\bdeut\b"
    ]),
    ("dbs", "DBS Bank", [
        r"dbs\s*bank", r"\bdbss\b"
    ]),
]

# IFSC prefix mapping for quick detection
IFSC_PREFIX_MAP = {
    "SBIN": "sbi", "PUNB": "pnb", "BARB": "bob", "CNRB": "canara",
    "UBIN": "union", "IOBA": "iob", "BKID": "boi", "CBIN": "central_bank",
    "IDIB": "indian_bank", "UCBA": "uco", "MAHB": "bank_of_maharashtra",
    "PSIB": "punjab_sind", "HDFC": "hdfc", "ICIC": "icici", "UTIB": "axis",
    "KKBK": "kotak", "YESB": "yes_bank", "IBKL": "idbi", "INDB": "indusind",
    "FDRL": "federal", "SIBL": "south_indian", "RATN": "rbl", "BDBL": "bandhan",
    "IDFB": "idfc", "CSBK": "csb", "KVBL": "karur_vysya", "CIUB": "city_union",
    "DCBL": "dcb", "DLXB": "dhanlaxmi", "KARB": "karnataka", "TMBL": "tamilnad_mercantile",
    "AUBL": "au_sfb", "ESFB": "equitas", "UJVN": "ujjivan",
    "PYTM": "paytm", "SCBL": "standard_chartered", "HSBC": "hsbc",
    "DEUT": "deutsche", "DBSS": "dbs", "CITI": "citi",
}


def detect_bank_from_text(text: str) -> Tuple[str, str]:
    """
    Detect bank from text content.
    Returns (bank_key, display_name) or ("unknown", "Unknown Bank").
    
    Order: 1) IFSC labeled in header (e.g. "IFSC: UTIB0000030")
           2) Bank name keyword near top of document (e.g. "Axis Bank")
           3) Any IFSC code in header area
           4) Keyword match in full text
           5) IFSC in full text
    """
    if not text:
        return ("unknown", "Unknown Bank")

    header = text[:3000]
    header_lower = header.lower()
    header_upper = header.upper()

    # Method 1: IFSC code explicitly labeled in header (most reliable)
    # Matches "IFSC: UTIB0000030", "IFSC Code: HDFC0001234" etc.
    ifsc_labeled = re.search(r'(?:IFSC|IFS)\s*(?:CODE)?\s*[:\s]\s*([A-Z]{4}0[A-Z0-9]{6})\b', header_upper)
    if ifsc_labeled:
        prefix = ifsc_labeled.group(1)[:4]
        if prefix in IFSC_PREFIX_MAP:
            bank_key = IFSC_PREFIX_MAP[prefix]
            for bk, name, _ in BANK_PATTERNS:
                if bk == bank_key:
                    return (bank_key, name)

    # Method 2: Bank name keyword in header (e.g. "ICICI BANK LTD", "Axis Bank")
    # Only match against explicit bank names like "XXX Bank" — skip patterns 
    # that might match narration text (e.g. "canara" in address)
    for bank_key, display_name, patterns in BANK_PATTERNS:
        for pattern in patterns:
            # Look for bank keywords followed by "bank" or at start of line
            match = re.search(pattern, header_lower)
            if match:
                # Verify it's not inside a narration/transaction context
                pos = match.start()
                context = header_lower[max(0, pos-30):pos+30]
                # Skip if the match appears in a narration/UPI context
                if any(kw in context for kw in ['/upi/', 'upi/', '/neft/', '/imps/', 'transfer to', 'transfer from', 'payment to', 'payment from']):
                    continue
                return (bank_key, display_name)

    # Method 3: Any IFSC code in header
    ifsc_match = re.search(r'\b([A-Z]{4})0[A-Z0-9]{6}\b', header_upper)
    if ifsc_match:
        prefix = ifsc_match.group(1)
        if prefix in IFSC_PREFIX_MAP:
            bank_key = IFSC_PREFIX_MAP[prefix]
            for bk, name, _ in BANK_PATTERNS:
                if bk == bank_key:
                    return (bank_key, name)

    # Method 4: Keyword match in full text (less reliable due to narrations)
    text_lower = text.lower()
    for bank_key, display_name, patterns in BANK_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return (bank_key, display_name)

    # Method 5: IFSC in full text
    ifsc_match = re.search(r'\b([A-Z]{4})0[A-Z0-9]{6}\b', text.upper())
    if ifsc_match:
        prefix = ifsc_match.group(1)
        if prefix in IFSC_PREFIX_MAP:
            bank_key = IFSC_PREFIX_MAP[prefix]
            for bk, name, _ in BANK_PATTERNS:
                if bk == bank_key:
                    return (bank_key, name)

    return ("unknown", "Unknown Bank")


def detect_bank_from_ifsc(ifsc: str) -> Tuple[str, str]:
    """Detect bank from IFSC code."""
    if not ifsc or len(ifsc) < 4:
        return ("unknown", "Unknown Bank")

    prefix = ifsc[:4].upper()
    if prefix in IFSC_PREFIX_MAP:
        bank_key = IFSC_PREFIX_MAP[prefix]
        for bk, name, _ in BANK_PATTERNS:
            if bk == bank_key:
                return (bank_key, name)

    return ("unknown", "Unknown Bank")


def get_all_supported_banks() -> list:
    """Return list of all supported banks."""
    return [{"key": bk, "name": name} for bk, name, _ in BANK_PATTERNS]
