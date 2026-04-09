"""
Transaction Categorization Rules — 50+ categories with keyword-based matching.
Covers payment modes, merchant categories, and sub-categories from UPI narration parsing.
"""

import re
from typing import Tuple

# ─── Mode detection keywords ───

MODE_PATTERNS = {
    # Credit modes
    "credit_salary": [
        r'\bsalary\b', r'\bsal\b', r'\bpayroll\b', r'\bwages\b', r'\bstipend\b',
        r'\bmonthly\s*pay\b', r'\bsalaries\b',
    ],
    "credit_neft": [r'\bneft\b'],
    "credit_rtgs": [r'\brtgs\b'],
    "credit_imps": [r'\bimps\b'],
    "credit_imps_reversal": [r'\bimps\b.*\breversal\b', r'\breversal\b.*\bimps\b', r'\brev\b.*\bimps\b'],
    "credit_upi": [r'\bupi\b', r'\bupi[-/]cr\b'],
    "credit_interest": [
        r'\binterest\b', r'\bint\s*credit\b', r'\bint\.\s*on\b', r'\binterest\s*paid\b',
        r'\bint\.pd\b', r'\bint\s*pd\b',
    ],
    # Debit modes
    "debit_upi": [r'\bupi\b', r'\bupi[-/]dr\b'],
    "debit_neft": [r'\bneft\b'],
    "debit_rtgs": [r'\brtgs\b'],
    "debit_imps": [r'\bimps\b'],
    "debit_cheque": [
        r'\bchq\b', r'\bcheque\b', r'\bchk\b', r'\bclg\b', r'\bclearing\b',
        r'\bchq\s*paid\b', r'\bchq\s*no\b',
    ],
    "debit_cash_withdrawal": [
        r'\batm\b', r'\bcash\s*withdrawal\b', r'\bwithdrawal\b', r'\bcash\s*w/d\b',
        r'\batm\s*w/d\b', r'\batm\s*wd\b', r'\bcash\s*wd\b', r'\bself\b.*\bchq\b',
    ],
    "debit_bank_charges": [
        r'\bcharges?\b', r'\bfee\b', r'\bpenalty\b', r'\bgst\b.*\bcharges?\b',
        r'\bservice\s*charge\b', r'\bsms\s*charges?\b', r'\bmaintenance\s*charge\b',
        r'\bfolio\s*charge\b', r'\bmin\s*bal\b.*\bcharge\b', r'\bamb\s*charge\b',
        r'\bservice\s*tax\b', r'\btax\s*recovery\b', r'\bcess\b',
    ],
}

# ─── Sub-category keywords (merchant/purpose classification) ───

SUBCATEGORY_KEYWORDS = {
    "food_dining": [
        r'\bswiggy\b', r'\bzomato\b', r'\bdunzo\b', r'\bbigbasket\b', r'\bgrofers\b',
        r'\bblinkit\b', r'\bdominos\b', r'\bmcdonalds\b', r'\bkfc\b', r'\bsubway\b',
        r'\bburger\s*king\b', r'\bpizza\s*hut\b', r'\bstarbucks\b', r'\bcafe\b',
        r'\brestaurant\b', r'\bfood\b', r'\beating\b', r'\bdining\b', r'\bfreshmenufood\b',
        r'\bbarbeque\b', r'\bhaldiram\b', r'\bchaipoint\b', r'\bjuice\b',
        r'\bzepto\b', r'\binstamart\b',
    ],
    "shopping": [
        r'\bamazon\b', r'\bflipkart\b', r'\bmyntra\b', r'\bajio\b', r'\bnykaa\b',
        r'\bsnapdeala?\b', r'\bmeesho\b', r'\btatacliq\b', r'\breliance\s*digital\b',
        r'\bcroma\b', r'\bshopping\b', r'\bmart\b', r'\bmall\b', r'\bdmart\b',
        r'\bvishal\s*mega\b', r'\bbigbazaar\b', r'\blifestyle\b', r'\bwestside\b',
        r'\bpantaloons\b', r'\bmax\s*fashion\b', r'\bfirstcry\b', r'\bpurplle\b',
    ],
    "travel": [
        r'\buber\b', r'\bola\b', r'\brapido\b', r'\bredo?\s*bus\b', r'\birctc\b',
        r'\bmakemytrip\b', r'\bgoibibo\b', r'\bcleartrip\b', r'\byatra\b',
        r'\beasemytrip\b', r'\bixigo\b', r'\bair\s*india\b', r'\bindigo\b',
        r'\bspicejet\b', r'\bvistara\b', r'\bbooking\.com\b', r'\boyo\b',
        r'\btravel\b', r'\btransport\b', r'\bfuel\b', r'\bpetrol\b', r'\bhpcl\b',
        r'\bbpcl\b', r'\biocl\b', r'\btoll\b', r'\bfastag\b', r'\bnhai\b',
    ],
    "utilities": [
        r'\belectricity\b', r'\belectric\b', r'\bwatercharge\b', r'\bwater\b',
        r'\bgas\b(?!.*station)', r'\bpipedgas\b', r'\bbill\s*pay\b',
        r'\bbilldesk\b', r'\brecharge\b', r'\bjio\b(?!.*bank)', r'\bairtel\b(?!.*bank)',
        r'\bvi\b', r'\bvodafone\b', r'\bbsnl\b', r'\bmtnl\b', r'\bact\s*fibernet\b',
        r'\bbroadband\b', r'\binternet\b', r'\bdth\b', r'\btatasky\b', r'\bdishTV\b',
        r'\btata\s*play\b', r'\bapsbcl\b', r'\bbescom\b', r'\bmsedcl\b',
    ],
    "medical": [
        r'\bhospital\b', r'\bpharmacy\b', r'\bmedical\b', r'\bdoctor\b',
        r'\bclinic\b', r'\blab\b.*\btest\b', r'\bdiagnostic\b', r'\bapollo\b',
        r'\bmedplus\b', r'\b1mg\b', r'\bpharmeasy\b', r'\bnetmeds\b',
        r'\bpracto\b', r'\bhealth\b', r'\bdental\b', r'\bfortis\b', r'\bmax\s*hospital\b',
    ],
    "education": [
        r'\bschool\b', r'\bcollege\b', r'\buniversity\b', r'\btuition\b',
        r'\bfees?\b', r'\beducation\b', r'\bacademy\b', r'\binstitute\b',
        r'\bbyju\b', r'\bunacademy\b', r'\bvedantu\b', r'\bcoaching\b',
        r'\bexam\b', r'\bcourse\b', r'\btraining\b', r'\budemy\b',
    ],
    "insurance": [
        r'\binsurance\b', r'\blic\b', r'\bpremium\b', r'\bpolicy\b',
        r'\bhdfc\s*life\b', r'\bicici\s*pru\b', r'\bsbi\s*life\b',
        r'\bmax\s*life\b', r'\bstar\s*health\b', r'\bniva\s*bupa\b',
        r'\bcare\s*insurance\b', r'\bnew\s*india\s*assurance\b',
    ],
    "investment": [
        r'\bmutual\s*fund\b', r'\bsip\b', r'\bzerodha\b', r'\bgroww\b',
        r'\bkuvera\b', r'\bpaytm\s*money\b', r'\bcoin\b.*\bzerodha\b',
        r'\bnps\b', r'\bppf\b', r'\bfixed\s*deposit\b', r'\bfd\b',
        r'\brd\b', r'\brecurring\s*deposit\b', r'\binvestment\b',
        r'\bshares?\b', r'\bstock\b', r'\bdemat\b', r'\bbse\b', r'\bnse\b',
    ],
    "paylater": [
        r'\bpaylater\b', r'\bpay\s*later\b', r'\bpostpaid\b', r'\blazypay\b',
        r'\bsimpl\b', r'\bslice\b', r'\buni\s*card\b', r'\bkreditbee\b',
        r'\bmoneyview\b', r'\bfreecharge\s*pay\b', r'\bamazon\s*pay\s*later\b',
        r'\bflipkart\s*pay\s*later\b', r'\bpaytm\s*postpaid\b',
    ],
    "emi": [
        r'\bemi\b', r'\bloan\b', r'\binstall?ment\b', r'\bequated\s*monthly\b',
        r'\bfinance\b', r'\blending\b', r'\brepayment\b', r'\bbajaj\s*fin\b',
        r'\btata\s*capital\b', r'\bhdb\s*fin\b', r'\bmanappuram\b', r'\bmuthoot\b',
        r'\bshriram\b', r'\bhero\s*fincorp\b',
    ],
    "rent": [
        r'\brent\b', r'\bhouse\s*rent\b', r'\bpg\b', r'\bhostel\b',
        r'\baccommodation\b', r'\bflat\s*rent\b',
    ],
    "government": [
        r'\btax\b', r'\bgst\b', r'\btds\b', r'\bincome\s*tax\b',
        r'\bgovt\b', r'\bgovernment\b', r'\bmunicip\b', r'\bcorporation\b',
        r'\bestamp\b', r'\bstamp\s*duty\b',
    ],
}

# P2M (Person to Merchant) indicators
P2M_INDICATORS = [
    r'\b[A-Za-z]+\.com\b', r'\b[A-Za-z]+\.in\b', r'\b[A-Za-z]+\.org\b',
    r'@paytm\b', r'@ybl\b', r'@upi\b', r'@okaxis\b', r'@oksbi\b',
    r'@okhdfcbank\b', r'@okicici\b', r'@axl\b', r'@ibl\b',
]


def categorize_transaction(description: str, debit: float, credit: float) -> Tuple[str, str]:
    """
    Categorize a transaction based on its description and amount.

    Returns:
        (category, sub_category) tuple.
        category: e.g., 'debit_upi', 'credit_neft', 'debit_bank_charges'
        sub_category: e.g., 'food_dining', 'shopping', 'travel', ''
    """
    desc_lower = description.lower() if description else ""
    is_debit = debit > 0
    is_credit = credit > 0

    # ─── Step 1: Detect payment mode ───
    category = "debit" if is_debit else "credit"

    if is_credit:
        # Check credit modes (most specific first)
        for mode, patterns in MODE_PATTERNS.items():
            if not mode.startswith("credit_"):
                continue
            for pattern in patterns:
                if re.search(pattern, desc_lower):
                    # Handle reversal before generic imps
                    if mode == "credit_imps_reversal":
                        category = mode
                        break
                    elif mode == "credit_imps" and category == "credit_imps_reversal":
                        continue  # Don't overwrite reversal
                    else:
                        category = mode
                        break
            if category != "credit":
                break
    else:
        # Check debit modes (most specific first)
        # Check bank charges first
        for pattern in MODE_PATTERNS.get("debit_bank_charges", []):
            if re.search(pattern, desc_lower):
                category = "debit_bank_charges"
                break

        if category == "debit":
            for pattern in MODE_PATTERNS.get("debit_cash_withdrawal", []):
                if re.search(pattern, desc_lower):
                    category = "debit_cash_withdrawal"
                    break

        if category == "debit":
            for pattern in MODE_PATTERNS.get("debit_cheque", []):
                if re.search(pattern, desc_lower):
                    category = "debit_cheque"
                    break

        if category == "debit":
            for mode in ["debit_neft", "debit_rtgs", "debit_imps", "debit_upi"]:
                for pattern in MODE_PATTERNS.get(mode, []):
                    if re.search(pattern, desc_lower):
                        category = mode
                        break
                if category != "debit":
                    break

    # ─── Step 2: Detect sub-category (merchant/purpose) ───
    sub_category = ""

    for sub_cat, keywords in SUBCATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if re.search(keyword, desc_lower):
                sub_category = sub_cat
                break
        if sub_category:
            break

    # ─── Step 3: Refine category with sub-category for UPI transactions ───
    if sub_category and "upi" in category:
        # Check if P2M (person to merchant)
        is_p2m = any(re.search(p, desc_lower) for p in P2M_INDICATORS)

        if is_p2m and is_debit:
            category = f"debit_upi_p2m_{sub_category}"
        elif is_debit:
            category = f"debit_upi_{sub_category}"
    elif sub_category and "imps" in category and is_debit:
        category = f"debit_imps_{sub_category}"

    return category, sub_category


def categorize_all_transactions(transactions: list) -> list:
    """
    Categorize all transactions in a list.
    Modifies transactions in-place and returns the list.
    """
    for txn in transactions:
        desc = txn.get("description", "")
        debit = txn.get("debit", 0)
        credit = txn.get("credit", 0)
        category, sub_category = categorize_transaction(desc, debit, credit)
        txn["category"] = category
        txn["sub_category"] = sub_category

    return transactions
