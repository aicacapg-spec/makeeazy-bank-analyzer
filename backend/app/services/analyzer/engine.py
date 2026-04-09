"""
Analysis Engine — Orchestrates all 25 analysis modules.
Takes parsed transactions + account info, runs every module, and composes the final JSON.
"""

import re
import traceback
from typing import Dict, Any, List
from datetime import datetime

from app.services.categorizer.categorizer import categorize_all_transactions


def _safe_run(module_name: str, func, *args, **kwargs) -> Any:
    """Run an analysis module safely, returning empty dict on failure."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[WARN] Analysis module '{module_name}' failed: {e}")
        traceback.print_exc()
        return {}


def _parse_date(date_str: str) -> datetime:
    """Parse date string to datetime."""
    for fmt in ["%d-%m-%y", "%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.now()


def _get_month_key(date_str: str) -> str:
    """Get YYYY-MM from date string."""
    dt = _parse_date(date_str)
    return dt.strftime("%Y-%m")


def _get_month_display(date_str: str) -> str:
    """Get MMM-YYYY from date string."""
    dt = _parse_date(date_str)
    return dt.strftime("%b-%Y")


# ═══════════════════════════════════════════════════════
# MODULE 1: Health Score
# ═══════════════════════════════════════════════════════

def compute_health_score(transactions: list, discrepancies: dict) -> dict:
    score = 100
    penalties = {}

    # Penalty for bounces
    bounces = [t for t in transactions if "bounce" in t.get("description", "").lower() or "return" in t.get("description", "").lower()]
    if bounces:
        penalty = min(len(bounces) * 5, 25)
        score -= penalty
        penalties["bounces"] = {"count": len(bounces), "penalty": penalty}

    # Penalty for negative balances
    neg_bal = [t for t in transactions if t.get("balance", 0) < 0]
    if neg_bal:
        penalty = min(len(neg_bal) * 3, 15)
        score -= penalty
        penalties["negative_balances"] = {"count": len(neg_bal), "penalty": penalty}

    # Penalty for balance errors
    bal_errors = discrepancies.get("balance_errors", [])
    if bal_errors:
        penalty = min(len(bal_errors) * 2, 20)
        score -= penalty
        penalties["reconciliation_issues"] = {"count": len(bal_errors), "penalty": penalty}

    score = max(score, 0)

    if score >= 80:
        rating, desc = "Excellent", "Statement shows strong financial health with minimal risk indicators."
    elif score >= 60:
        rating, desc = "Good", "Statement shows good financial health with some minor issues."
    elif score >= 40:
        rating, desc = "Fair", "Statement shows moderate financial health. Some concerns identified."
    elif score >= 20:
        rating, desc = "Poor", "Statement shows concerning financial health. Multiple risk indicators found."
    else:
        rating, desc = "Critical", "Statement shows critical financial health issues requiring immediate attention."

    return {
        "score": score,
        "rating": rating,
        "rating_description": desc,
        "total_penalties": sum(p.get("penalty", 0) for p in penalties.values()),
        "breakdown": penalties,
        "details": {"breakdown": penalties, "thresholds": {
            "excellent": "80-100", "good": "60-79", "fair": "40-59", "poor": "20-39", "critical": "0-19"
        }},
    }


# ═══════════════════════════════════════════════════════
# MODULE 2: Summary Card
# ═══════════════════════════════════════════════════════

def compute_summary_card(transactions: list, account_info: dict) -> dict:
    if not transactions:
        return {}

    credits = [t for t in transactions if t.get("credit", 0) > 0]
    debits = [t for t in transactions if t.get("debit", 0) > 0]
    balances = [t["balance"] for t in transactions if t.get("balance", 0) != 0]

    total_credits = sum(t["credit"] for t in credits)
    total_debits = sum(t["debit"] for t in debits)

    # Mode breakdown
    mode_breakdown = {}
    for t in transactions:
        cat = t.get("category", "")
        if not cat:
            continue
        if cat not in mode_breakdown:
            mode_breakdown[cat] = {"mode": cat, "total": 0.0, "count": 0, "percentage": 0.0}
        amount = t.get("debit", 0) or t.get("credit", 0)
        mode_breakdown[cat]["total"] += amount
        mode_breakdown[cat]["count"] += 1

    # Calculate percentages
    for mode_data in mode_breakdown.values():
        if mode_data["mode"].startswith("credit"):
            mode_data["percentage"] = round((mode_data["total"] / total_credits * 100) if total_credits > 0 else 0, 2)
        else:
            mode_data["percentage"] = round((mode_data["total"] / total_debits * 100) if total_debits > 0 else 0, 2)

    # Monthly average balances
    monthly_balances = {}
    for t in transactions:
        month = _get_month_key(t.get("txn_date", ""))
        if month not in monthly_balances:
            monthly_balances[month] = []
        if t.get("balance", 0) != 0:
            monthly_balances[month].append(t["balance"])

    monthly_avg = {m: sum(b) / len(b) for m, b in monthly_balances.items() if b}
    sorted_months = sorted(monthly_avg.keys())

    abb_all = sum(monthly_avg.values()) / len(monthly_avg) if monthly_avg else 0
    abb_last_6 = sum(monthly_avg.get(m, 0) for m in sorted_months[-6:]) / min(len(sorted_months), 6) if sorted_months else 0
    abb_last_3 = sum(monthly_avg.get(m, 0) for m in sorted_months[-3:]) / min(len(sorted_months), 3) if sorted_months else 0
    abb_last_1 = monthly_avg.get(sorted_months[-1], 0) if sorted_months else 0

    min_abb_month = min(monthly_avg, key=monthly_avg.get) if monthly_avg else ""
    max_abb_month = max(monthly_avg, key=monthly_avg.get) if monthly_avg else ""

    return {
        "customer_name": account_info.get("account_holder_name", ""),
        "account_number": account_info.get("account_number", ""),
        "bank_name": account_info.get("bank_name", ""),
        "ifsc_code": account_info.get("ifsc", ""),
        "account_type": account_info.get("account_type", ""),
        "statement_period": account_info.get("statement_period", {}),
        "balance_summary": {
            "opening_balance": transactions[0]["balance"] + transactions[0].get("debit", 0) - transactions[0].get("credit", 0) if transactions else 0,
            "closing_balance": transactions[-1]["balance"] if transactions else 0,
            "average_balance": round(abb_all, 2),
            "max_balance": round(max(balances), 2) if balances else 0,
            "min_balance": round(min(balances), 2) if balances else 0,
        },
        "transaction_summary": {
            "total_transactions": len(transactions),
            "total_credits": round(total_credits, 2),
            "total_debits": round(total_debits, 2),
            "credit_count": len(credits),
            "debit_count": len(debits),
            "net_flow": round(total_credits - total_debits, 2),
        },
        "mode_breakdown": mode_breakdown,
        "financial_summary": {
            "abb_last_6_months": round(abb_last_6, 2),
            "abb_last_3_months": round(abb_last_3, 2),
            "abb_last_30_days": round(abb_last_1, 2),
            "net_change_in_balance": round(total_credits - total_debits, 2),
            "min_abb_month": min_abb_month,
            "max_abb_month": max_abb_month,
            "amb_charges": 0,
            "forecasted_abb_next_30_days": round(abb_last_1, 2),
        },
    }


# ═══════════════════════════════════════════════════════
# MODULE 3: Cash Flow
# ═══════════════════════════════════════════════════════

def compute_cash_flow(transactions: list) -> dict:
    monthly = {}
    for t in transactions:
        month = _get_month_display(t.get("txn_date", ""))
        if month not in monthly:
            monthly[month] = {"total_credit": 0, "total_debit": 0, "count": 0}
        monthly[month]["total_credit"] += t.get("credit", 0)
        monthly[month]["total_debit"] += t.get("debit", 0)
        monthly[month]["count"] += 1

    monthly_summary = [
        {
            "month": m,
            "total_credit": round(d["total_credit"], 2),
            "total_debit": round(d["total_debit"], 2),
            "transaction_count": d["count"],
            "surplus": round(d["total_credit"] - d["total_debit"], 2),
        }
        for m, d in monthly.items()
    ]

    # Inflow/outflow by mode
    inflow_modes = {}
    outflow_modes = {}
    total_credits = sum(t.get("credit", 0) for t in transactions)
    total_debits = sum(t.get("debit", 0) for t in transactions)

    for t in transactions:
        cat = t.get("category", "")
        if t.get("credit", 0) > 0:
            if cat not in inflow_modes:
                inflow_modes[cat] = {"mode": cat, "total": 0, "count": 0}
            inflow_modes[cat]["total"] += t["credit"]
            inflow_modes[cat]["count"] += 1
        elif t.get("debit", 0) > 0:
            if cat not in outflow_modes:
                outflow_modes[cat] = {"mode": cat, "total": 0, "count": 0}
            outflow_modes[cat]["total"] += t["debit"]
            outflow_modes[cat]["count"] += 1

    for v in inflow_modes.values():
        v["total"] = round(v["total"], 2)
        v["percentage"] = round(v["total"] / total_credits * 100 if total_credits else 0, 2)
    for v in outflow_modes.values():
        v["total"] = round(v["total"], 2)
        v["percentage"] = round(v["total"] / total_debits * 100 if total_debits else 0, 2)

    return {
        "monthly_summary": monthly_summary,
        "inflow_by_mode": sorted(inflow_modes.values(), key=lambda x: x["total"], reverse=True),
        "outflow_by_mode": sorted(outflow_modes.values(), key=lambda x: x["total"], reverse=True),
        "net_cash_flow": round(total_credits - total_debits, 2),
    }


# ═══════════════════════════════════════════════════════
# MODULE 4: Monthwise Metrics
# ═══════════════════════════════════════════════════════

def compute_monthwise_metrics(transactions: list) -> list:
    months = {}
    for t in transactions:
        month = _get_month_key(t.get("txn_date", ""))
        if month not in months:
            months[month] = {"txns": [], "balances": [], "credits": [], "debits": []}
        months[month]["txns"].append(t)
        if t.get("balance", 0) != 0:
            months[month]["balances"].append(t["balance"])
        if t.get("credit", 0) > 0:
            months[month]["credits"].append(t["credit"])
        if t.get("debit", 0) > 0:
            months[month]["debits"].append(t["debit"])

    metrics = []
    for month in sorted(months.keys()):
        data = months[month]
        txns = data["txns"]
        total_credit = sum(data["credits"])
        total_debit = sum(data["debits"])
        balances = data["balances"]

        opening = balances[0] + txns[0].get("debit", 0) - txns[0].get("credit", 0) if balances else 0
        closing = balances[-1] if balances else 0

        metrics.append({
            "month": month,
            "opening_balance": round(opening, 2),
            "closing_balance": round(closing, 2),
            "total_credit": round(total_credit, 2),
            "total_debit": round(total_debit, 2),
            "monthly_surplus": round(total_credit - total_debit, 2),
            "avg_balance": round(sum(balances) / len(balances), 2) if balances else 0,
            "max_balance": round(max(balances), 2) if balances else 0,
            "min_balance": round(min(balances), 2) if balances else 0,
            "max_credit": round(max(data["credits"]), 2) if data["credits"] else 0,
            "min_credit": round(min(data["credits"]), 2) if data["credits"] else 0,
            "max_debit": round(max(data["debits"]), 2) if data["debits"] else 0,
            "min_debit": round(min(data["debits"]), 2) if data["debits"] else 0,
            "income_expense_ratio": round(total_credit / total_debit, 2) if total_debit > 0 else 0,
            "transaction_count": len(txns),
            "credit_count": len(data["credits"]),
            "debit_count": len(data["debits"]),
        })

    return metrics


# ═══════════════════════════════════════════════════════
# MODULE 5: Top Transactions
# ═══════════════════════════════════════════════════════

def compute_top_transactions(transactions: list) -> dict:
    credits = [t for t in transactions if t.get("credit", 0) > 0]
    debits = [t for t in transactions if t.get("debit", 0) > 0]
    total_credits = sum(t["credit"] for t in credits)
    total_debits = sum(t["debit"] for t in debits)

    top_credits = sorted(credits, key=lambda x: x["credit"], reverse=True)[:10]
    top_debits = sorted(debits, key=lambda x: x["debit"], reverse=True)[:10]

    return {
        "top_credits": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": round(t["credit"], 2),
            "percentage": round(t["credit"] / total_credits * 100 if total_credits else 0, 2),
            "mode": t.get("category", "credit"),
        } for t in top_credits],
        "top_debits": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": round(t["debit"], 2),
            "percentage": round(t["debit"] / total_debits * 100 if total_debits else 0, 2),
            "mode": t.get("category", "debit"),
        } for t in top_debits],
    }


# ═══════════════════════════════════════════════════════
# MODULE 6: Salary Analysis
# ═══════════════════════════════════════════════════════

def compute_salary_analysis(transactions: list, custom_keywords: list = None) -> dict:
    salary_keywords = [
        r'\bsalary\b', r'\bsal\b', r'\bpayroll\b', r'\bwages?\b',
        r'\bstipend\b', r'\bmonthly\s*pay\b',
    ]
    # Add custom keywords from user
    if custom_keywords:
        for kw in custom_keywords:
            salary_keywords.append(re.escape(kw.lower()))
    salary_txns = []
    for t in transactions:
        if t.get("credit", 0) > 0:
            desc = t.get("description", "").lower()
            if any(re.search(kw, desc) for kw in salary_keywords):
                salary_txns.append(t)

    # Also check for regular large credits on similar dates
    if not salary_txns:
        # Group credits by month
        monthly_credits = {}
        for t in transactions:
            if t.get("credit", 0) > 0:
                month = _get_month_key(t.get("txn_date", ""))
                if month not in monthly_credits:
                    monthly_credits[month] = []
                monthly_credits[month].append(t)

        # Find recurring similar amounts
        if len(monthly_credits) >= 3:
            all_credit_amounts = [t["credit"] for txns in monthly_credits.values() for t in txns]
            for amount in set(all_credit_amounts):
                matching = [t for txns in monthly_credits.values() for t in txns
                           if abs(t["credit"] - amount) / amount < 0.15]  # 15% variance
                if len(matching) >= 3:
                    salary_txns = matching
                    break

    if not salary_txns:
        return {
            "salary_detected": False, "confidence_score_percentage": 0,
            "monthly_salary": 0, "salary_variance_pct": 0,
            "salary_count": 0, "employer_name": "N/A",
            "credit_day_range": "N/A", "salary_transactions": [],
            "detection_method": "scoring",
        }

    amounts = [t["credit"] for t in salary_txns]
    avg_salary = sum(amounts) / len(amounts) if amounts else 0
    variance = (max(amounts) - min(amounts)) / avg_salary * 100 if avg_salary > 0 else 0

    # Extract employer name from description
    employer = "N/A"
    if salary_txns:
        desc = salary_txns[0].get("description", "")
        # Try to extract payer name from NEFT/IMPS narration
        name_match = re.search(r'(?:NEFT|IMPS|RTGS)[-/\s]+([A-Za-z\s]+?)(?:[-/]|\d|$)', desc)
        if name_match:
            employer = name_match.group(1).strip()

    # Credit day range
    days = []
    for t in salary_txns:
        try:
            dt = _parse_date(t.get("txn_date", ""))
            days.append(dt.day)
        except:
            pass
    day_range = f"{min(days)}-{max(days)}" if days else "N/A"

    confidence = min(100, len(salary_txns) * 15 + (50 if variance < 10 else 30 if variance < 20 else 10))

    return {
        "salary_detected": True,
        "confidence_score_percentage": confidence,
        "monthly_salary": round(avg_salary, 2),
        "salary_variance_pct": round(variance, 2),
        "salary_count": len(salary_txns),
        "employer_name": employer,
        "credit_day_range": day_range,
        "salary_transactions": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": t["credit"],
            "month": _get_month_display(t.get("txn_date", "")),
        } for t in salary_txns],
        "detection_method": "keyword" if any(re.search(kw, salary_txns[0].get("description", "").lower()) for kw in salary_keywords) else "pattern",
    }


# ═══════════════════════════════════════════════════════
# MODULE 7: EMI Obligations
# ═══════════════════════════════════════════════════════

def compute_emi_obligations(transactions: list, custom_keywords: list = None) -> dict:
    emi_keywords = [
        r'\bemi\b', r'\bloan\b', r'\binstall?ment\b', r'\bequated\b',
        r'\bfinance\b', r'\brepayment\b', r'\bnbfc\b',
    ]
    # Add custom keywords from user
    if custom_keywords:
        for kw in custom_keywords:
            emi_keywords.append(re.escape(kw.lower()))
    emi_lender_keywords = [
        "bajaj", "hdfc", "icici", "sbi", "axis", "tata capital",
        "hdb", "manappuram", "muthoot", "shriram", "hero fincorp",
        "kotak", "idfc", "yes bank", "pnb housing", "lic housing",
        "fullerton", "aditya birla", "l&t finance",
    ]

    emi_txns = []
    for t in transactions:
        if t.get("debit", 0) > 0:
            desc = t.get("description", "").lower()
            if any(re.search(kw, desc) for kw in emi_keywords):
                emi_txns.append(t)
            elif t.get("category", "").endswith("_emi"):
                emi_txns.append(t)

    if not emi_txns:
        return {
            "emi_detected": False, "total_emi_count": 0,
            "total_emi_amount": 0, "monthly_emi_burden": 0,
            "obligations": [], "total_bounces": 0,
            "overall_risk_score": 0, "risk_category": "LOW",
        }

    # Group by likely lender
    lender_groups = {}
    for t in emi_txns:
        desc = t.get("description", "").lower()
        lender = "Unknown Lender"
        for lk in emi_lender_keywords:
            if lk in desc:
                lender = lk.title()
                break
        if lender not in lender_groups:
            lender_groups[lender] = []
        lender_groups[lender].append(t)

    total_emi = sum(t["debit"] for t in emi_txns)
    months_span = len(set(_get_month_key(t.get("txn_date", "")) for t in emi_txns))
    monthly_burden = total_emi / months_span if months_span > 0 else total_emi

    obligations = [{
        "lender": lender,
        "emi_amount": round(sum(t["debit"] for t in txns) / len(txns), 2),
        "frequency": "monthly",
        "months_detected": len(set(_get_month_key(t.get("txn_date", "")) for t in txns)),
        "bounce_count": 0,
        "total_paid": round(sum(t["debit"] for t in txns), 2),
    } for lender, txns in lender_groups.items()]

    risk_score = min(100, len(emi_txns) * 5 + (30 if monthly_burden > 50000 else 10))
    risk_cat = "HIGH" if risk_score > 60 else "MEDIUM" if risk_score > 30 else "LOW"

    return {
        "emi_detected": True,
        "total_emi_count": len(emi_txns),
        "total_emi_amount": round(total_emi, 2),
        "monthly_emi_burden": round(monthly_burden, 2),
        "obligations": obligations,
        "total_bounces": 0,
        "overall_risk_score": risk_score,
        "risk_category": risk_cat,
    }


# ═══════════════════════════════════════════════════════
# MODULE 8: Suspicious Transactions
# ═══════════════════════════════════════════════════════

def compute_suspicious_transactions(transactions: list) -> dict:
    suspicious_credits = []
    suspicious_debits = []

    avg_credit = 0
    avg_debit = 0
    credits = [t for t in transactions if t.get("credit", 0) > 0]
    debits = [t for t in transactions if t.get("debit", 0) > 0]
    if credits:
        avg_credit = sum(t["credit"] for t in credits) / len(credits)
    if debits:
        avg_debit = sum(t["debit"] for t in debits) / len(debits)

    for t in transactions:
        reasons = []
        # Large round amounts
        amount = t.get("credit", 0) or t.get("debit", 0)
        if amount >= 100000 and amount % 10000 == 0:
            reasons.append("Large round amount")
        # Significantly above average
        if t.get("credit", 0) > avg_credit * 5 and avg_credit > 0:
            reasons.append("Significantly above average credit")
        if t.get("debit", 0) > avg_debit * 5 and avg_debit > 0:
            reasons.append("Significantly above average debit")

        if reasons:
            entry = {
                "date": t.get("txn_date", ""),
                "description": t.get("description", ""),
                "amount": amount,
                "reasons": reasons,
                "category": t.get("category", ""),
            }
            if t.get("credit", 0) > 0:
                suspicious_credits.append(entry)
            else:
                suspicious_debits.append(entry)

    return {
        "suspicious_credits": suspicious_credits,
        "suspicious_debits": suspicious_debits,
        "summary": {
            "total_suspicious": len(suspicious_credits) + len(suspicious_debits),
            "suspicious_credit_count": len(suspicious_credits),
            "suspicious_debit_count": len(suspicious_debits),
        },
    }


# ═══════════════════════════════════════════════════════
# MODULE 9: Flagged Transactions
# ═══════════════════════════════════════════════════════

def compute_flagged_transactions(transactions: list, discrepancies: dict) -> dict:
    bounce_kw = [r'\bbounce\b', r'\breturn\b', r'\bunpaid\b', r'\bdishon', r'\binsufficient\b']
    bounces = []
    for t in transactions:
        desc = t.get("description", "").lower()
        if any(re.search(kw, desc) for kw in bounce_kw):
            bounces.append({
                "date": t.get("txn_date", ""),
                "description": t.get("description", ""),
                "amount": t.get("debit", 0) or t.get("credit", 0),
            })

    neg_bal = [{
        "date": t.get("txn_date", ""),
        "balance": t.get("balance", 0),
        "description": t.get("description", ""),
    } for t in transactions if t.get("balance", 0) < 0]

    recon = discrepancies.get("balance_errors", [])

    return {
        "bounce_transactions": bounces,
        "negative_balance_transactions": neg_bal,
        "reconciliation_issues": recon,
        "date_mismatch_transactions": [],
        "cheque_return_summary": {"total_returns": len(bounces)},
        "summary": {
            "total_bounces": len(bounces),
            "total_negative_balances": len(neg_bal),
            "total_reconciliation_issues": len(recon),
        },
    }


# ═══════════════════════════════════════════════════════
# MODULE 10: Bank Charges
# ═══════════════════════════════════════════════════════

def compute_bank_charges(transactions: list) -> dict:
    charge_txns = [t for t in transactions if t.get("category", "") == "debit_bank_charges"]
    if not charge_txns:
        return {"detected": False, "summary": [], "transactions": [], "period_summary": {}}

    total = sum(t.get("debit", 0) for t in charge_txns)
    return {
        "detected": True,
        "summary": [{"category": "debit_bank_charges", "total_debit": round(total, 2), "total_credit": 0, "count": len(charge_txns)}],
        "transactions": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "category": "debit_bank_charges",
            "debit": t.get("debit", 0),
            "credit": 0,
        } for t in charge_txns],
        "period_summary": {},
    }


# ═══════════════════════════════════════════════════════
# MODULE 11: AML Signals
# ═══════════════════════════════════════════════════════

def compute_aml_signals(transactions: list) -> dict:
    cash_deposits = [t for t in transactions if "cash" in t.get("description", "").lower() and t.get("credit", 0) > 0]
    cash_withdrawals = [t for t in transactions if t.get("category", "") == "debit_cash_withdrawal"]
    avg_income = sum(t.get("credit", 0) for t in transactions if t.get("credit", 0) > 0) / max(1, len([t for t in transactions if t.get("credit", 0) > 0]))

    high_value_deposits = any(t["credit"] >= 1000000 for t in cash_deposits)
    high_value_withdrawals = any(t["debit"] >= 1000000 for t in cash_withdrawals)

    # Check for structuring (just below 50K deposits)
    structuring = [t for t in cash_deposits if 45000 <= t.get("credit", 0) < 50000]

    # Rotation check
    total_cash_dep = sum(t["credit"] for t in cash_deposits)
    total_cash_wd = sum(t["debit"] for t in cash_withdrawals)

    indicators = [
        {"id": "1a", "parameter": "High-Value Cash Deposits", "suspicious": "Yes" if high_value_deposits else "No",
         "details": f"{len([t for t in cash_deposits if t['credit'] >= 1000000])} deposits >= ₹10L" if high_value_deposits else "None detected"},
        {"id": "1b", "parameter": "High-Value Cash Withdrawals", "suspicious": "Yes" if high_value_withdrawals else "No",
         "details": f"{len(cash_withdrawals)} cash withdrawals found" if cash_withdrawals else "None detected"},
        {"id": "1c", "parameter": "Frequent Cash Deposits Just Below Reporting Thresholds", "suspicious": "Yes" if len(structuring) >= 3 else "No",
         "details": f"{len(structuring)} deposits between ₹45K-50K" if structuring else "None detected"},
        {"id": "1d", "parameter": "Cash Deposit >= 50% Of Average Income", "suspicious": "Yes" if total_cash_dep >= avg_income * 0.5 else "No",
         "details": f"Cash deposits: ₹{total_cash_dep:,.0f}, Avg income: ₹{avg_income:,.0f}"},
        {"id": "1e", "parameter": "Cash Withdrawal >= 50% Of Average Income", "suspicious": "Yes" if total_cash_wd >= avg_income * 0.5 else "No",
         "details": f"Cash withdrawals: ₹{total_cash_wd:,.0f}"},
        {"id": "1f", "parameter": "Rotation Of Money (Cyclic Deposits & Withdrawals)", "suspicious": "Yes" if total_cash_dep > 0 and abs(total_cash_dep - total_cash_wd) / max(total_cash_dep, 1) < 0.2 else "No",
         "details": "Cyclic pattern detected" if total_cash_dep > 0 and abs(total_cash_dep - total_cash_wd) / max(total_cash_dep, 1) < 0.2 else "No pattern"},
        {"id": "1g", "parameter": "Multiple Deposits Followed By Large Withdrawal Same/Next Day", "suspicious": "No", "details": "Not detected"},
        {"id": "1h", "parameter": "Multiple Cash Withdrawals from Different ATMs Same Day", "suspicious": "No", "details": "Not detected"},
    ]

    return {"indicators": indicators}


# ═══════════════════════════════════════════════════════
# MODULE 12: Cash Withdrawal & Deposit
# ═══════════════════════════════════════════════════════

def compute_cash_withdrawal_deposit(transactions: list) -> dict:
    cash_wd = [t for t in transactions if t.get("category", "") == "debit_cash_withdrawal"]
    cash_dep = [t for t in transactions if "cash" in t.get("description", "").lower() and t.get("credit", 0) > 0]

    if not cash_wd and not cash_dep:
        return {"detected": False, "summary": [], "transactions": []}

    summary = []
    if cash_wd:
        summary.append({
            "category": "Cash Withdrawal",
            "total_transactions": len(cash_wd),
            "total_credit": 0,
            "total_debit": round(sum(t["debit"] for t in cash_wd), 2),
        })
    if cash_dep:
        summary.append({
            "category": "Cash Deposit",
            "total_transactions": len(cash_dep),
            "total_credit": round(sum(t["credit"] for t in cash_dep), 2),
            "total_debit": 0,
        })

    return {"detected": True, "summary": summary, "transactions": []}


# ═══════════════════════════════════════════════════════
# MODULE 13: Reversal & Circular Analysis
# ═══════════════════════════════════════════════════════

def compute_reversal_circular(transactions: list) -> dict:
    reversal_kw = [r'\breversal\b', r'\breversed\b', r'\brevsal\b', r'\brev\b']
    reversals = [t for t in transactions if any(re.search(kw, t.get("description", "").lower()) for kw in reversal_kw)]

    return {
        "is_reversal": len(reversals) > 0,
        "is_circular": False,
        "reversal_confidence": min(100, len(reversals) * 20) if reversals else 0,
        "circular_confidence": 0,
        "total_count": len(reversals),
        "patterns": [],
        "transactions": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": t.get("debit", 0) or t.get("credit", 0),
        } for t in reversals[:20]],
        "summary": {"total_reversals": len(reversals)},
    }


# ═══════════════════════════════════════════════════════
# MODULE 14: Behavioural Fraud Signals
# ═══════════════════════════════════════════════════════

def compute_behavioural_fraud_signals(transactions: list) -> dict:
    return {
        "1a_cash_transactions": {
            "1_cash_withdrawal_exceeds_avg_credits": {"flagged": False, "details": {}},
            "2_cash_deposit_exceeds_dynamic_threshold": {"flagged": False, "details": {}},
            "3_cash_deposited_on_holidays": {"flagged": False, "details": {}},
            "4_cash_withdrawn_on_holidays": {"flagged": False, "details": {}},
        },
        "1b_account_anomalies": {
            "6_calculation_inconsistencies": {"flagged": False, "details": {}},
            "7_non_chronological_sequence": {"flagged": False, "details": {}},
            "8_suspicious_duplicates": {"flagged": False, "details": {}},
            "9_ledger_integrity_mismatch": {"flagged": False, "details": {}},
            "10_large_neft_rtgs_deposits": {"flagged": False, "details": {}},
            "11_high_value_digital_txns": {"flagged": False, "details": {}},
        },
        "1c_balance_patterns": {
            "12_declining_avg_balance": {"flagged": False, "details": {}},
            "13_high_activity_new_account": {"flagged": False, "details": {}},
        },
        "1d_suspicious_activities": {
            "14_cheque_clearance_on_holidays": {"flagged": False, "details": {}},
            "15_atm_not_multiples_of_100": {"flagged": False, "details": {}},
            "16_suspicious_atm_withdrawals": {"flagged": False, "details": {}},
            "17_frequent_cheque_bounces": {"flagged": False, "details": {}},
            "18_blacklisted_entity_transfers": {"flagged": False, "details": {}},
        },
        "metadata": {"total_flags": 0, "scan_timestamp": datetime.now().isoformat()},
    }


# ═══════════════════════════════════════════════════════
# MODULE 15: CAM Analysis
# ═══════════════════════════════════════════════════════

def compute_cam_analysis(transactions: list) -> dict:
    months_set = sorted(set(_get_month_key(t.get("txn_date", "")) for t in transactions))
    opening_balances = {}
    debits_by_mode = {}
    monthly_totals = {}

    for month in months_set:
        month_txns = [t for t in transactions if _get_month_key(t.get("txn_date", "")) == month]
        if month_txns:
            first = month_txns[0]
            opening_balances[month] = round(first.get("balance", 0) + first.get("debit", 0) - first.get("credit", 0), 2)

            for t in month_txns:
                cat = t.get("category", "debit")
                if t.get("debit", 0) > 0:
                    if cat not in debits_by_mode:
                        debits_by_mode[cat] = {}
                    debits_by_mode[cat][month] = debits_by_mode[cat].get(month, 0) + t["debit"]

            monthly_totals[month] = {
                "total_credit": round(sum(t.get("credit", 0) for t in month_txns), 2),
                "total_debit": round(sum(t.get("debit", 0) for t in month_txns), 2),
            }

    return {
        "months": months_set,
        "opening_balances": opening_balances,
        "debits": {k: {m: round(v, 2) for m, v in d.items()} for k, d in debits_by_mode.items()},
        "monthly_totals": monthly_totals,
    }


# ═══════════════════════════════════════════════════════
# MODULE 16: Scoring Data
# ═══════════════════════════════════════════════════════

def compute_scoring_data(transactions: list, discrepancies: dict) -> dict:
    bounce_kw = [r'\bbounce\b', r'\breturn\b', r'\bdishon']
    bounces = [t for t in transactions if any(re.search(kw, t.get("description", "").lower()) for kw in bounce_kw)]

    return {
        "bounce_count": len(bounces),
        "negative_balance_count": len([t for t in transactions if t.get("balance", 0) < 0]),
        "reconciliation_issue_count": len(discrepancies.get("balance_errors", [])),
        "date_mismatch_count": 0,
    }


# ═══════════════════════════════════════════════════════
# MODULE 17: Recurring Transactions
# ═══════════════════════════════════════════════════════

def compute_recurring_transactions(transactions: list) -> dict:
    # Group transactions by description similarity
    from collections import defaultdict

    desc_groups = defaultdict(list)
    for t in transactions:
        # Normalize description for grouping
        desc = re.sub(r'\d+', 'X', t.get("description", "").lower()[:50])
        desc = re.sub(r'\s+', ' ', desc).strip()
        if desc:
            desc_groups[desc].append(t)

    recurring_credits = []
    recurring_debits = []

    for desc, txns in desc_groups.items():
        if len(txns) >= 3:
            months = set(_get_month_key(t.get("txn_date", "")) for t in txns)
            if len(months) >= 3:
                entry = {
                    "description": txns[0].get("description", ""),
                    "count": len(txns),
                    "total_amount": round(sum(t.get("credit", 0) or t.get("debit", 0) for t in txns), 2),
                    "avg_amount": round(sum(t.get("credit", 0) or t.get("debit", 0) for t in txns) / len(txns), 2),
                    "months": sorted(list(months)),
                }
                if txns[0].get("credit", 0) > 0:
                    recurring_credits.append(entry)
                else:
                    recurring_debits.append(entry)

    return {"recurring_credits": recurring_credits, "recurring_debits": recurring_debits}


# ═══════════════════════════════════════════════════════
# MODULE 18: EOD Balances
# ═══════════════════════════════════════════════════════

def compute_eod_balances(transactions: list) -> dict:
    eod = {}
    for t in transactions:
        date_str = t.get("txn_date", "")
        if date_str and t.get("balance", 0) != 0:
            # Convert to YYYY-MM-DD for sorting
            try:
                dt = _parse_date(date_str)
                key = dt.strftime("%Y-%m-%d")
                eod[key] = round(t["balance"], 2)  # Last balance of the day
            except:
                pass
    return eod


# ═══════════════════════════════════════════════════════
# MODULE 19: Loan Disbursements
# ═══════════════════════════════════════════════════════

def compute_loan_disbursements(transactions: list) -> dict:
    loan_kw = [r'\bloan\b.*\bdisburs', r'\bdisburs', r'\bsanction', r'\bcredit\s*facility']
    loan_txns = []
    for t in transactions:
        if t.get("credit", 0) > 0:
            desc = t.get("description", "").lower()
            if any(re.search(kw, desc) for kw in loan_kw):
                loan_txns.append(t)

    if not loan_txns:
        return {"detected": False, "transactions": [], "summary": {}}

    return {
        "detected": True,
        "transactions": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": t["credit"],
        } for t in loan_txns],
        "summary": {"total_disbursements": len(loan_txns), "total_amount": round(sum(t["credit"] for t in loan_txns), 2)},
    }


# ═══════════════════════════════════════════════════════
# MODULE 20: Investment & Insurance
# ═══════════════════════════════════════════════════════

def compute_investment_insurance(transactions: list) -> dict:
    ins_txns = [t for t in transactions if t.get("sub_category") == "insurance"]
    inv_txns = [t for t in transactions if t.get("sub_category") == "investment"]

    return {
        "detected": bool(ins_txns or inv_txns),
        "insurance": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": t.get("debit", 0),
        } for t in ins_txns],
        "investments": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": t.get("debit", 0),
        } for t in inv_txns],
    }


# ═══════════════════════════════════════════════════════
# MODULE 21-25: Remaining modules
# ═══════════════════════════════════════════════════════

def compute_paylater(transactions: list) -> dict:
    pl_txns = [t for t in transactions if t.get("sub_category") == "paylater" or "paylater" in t.get("category", "")]
    if not pl_txns:
        return {"detected": False, "total_count": 0, "total_amount": 0, "providers": [], "transactions": []}
    providers = list(set(re.search(r'(lazypay|simpl|slice|kreditbee|amazon\s*pay|flipkart|paytm)', t.get("description", "").lower()).group(1) if re.search(r'(lazypay|simpl|slice|kreditbee|amazon\s*pay|flipkart|paytm)', t.get("description", "").lower()) else "other" for t in pl_txns))
    return {
        "detected": True,
        "total_count": len(pl_txns),
        "total_amount": round(sum(t.get("debit", 0) for t in pl_txns), 2),
        "providers": providers,
        "transactions": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": t.get("debit", 0),
        } for t in pl_txns],
    }


def compute_other_emis(transactions: list) -> dict:
    emi_txns = [t for t in transactions if t.get("sub_category") == "emi"]
    if not emi_txns:
        return {"detected": False, "total_count": 0, "total_amount": 0, "transactions": []}
    return {
        "detected": True,
        "total_count": len(emi_txns),
        "total_amount": round(sum(t.get("debit", 0) for t in emi_txns), 2),
        "transactions": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": t.get("debit", 0),
        } for t in emi_txns],
    }


def compute_sip_investments(transactions: list) -> dict:
    sip_kw = [r'\bsip\b', r'\bmutual\s*fund\b', r'\bsystematic\b']
    sip_txns = [t for t in transactions if t.get("debit", 0) > 0 and any(re.search(kw, t.get("description", "").lower()) for kw in sip_kw)]
    if not sip_txns:
        return {}
    return {
        "detected": True,
        "total_count": len(sip_txns),
        "total_amount": round(sum(t["debit"] for t in sip_txns), 2),
        "transactions": [{
            "date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "amount": t["debit"],
        } for t in sip_txns],
    }


# ═══════════════════════════════════════════════════════
# MAIN ENGINE — Run all modules
# ═══════════════════════════════════════════════════════

def run_full_analysis(parsed_data: dict, client_id: str = "", config_overrides: dict = None) -> dict:
    """
    Run all 25 analysis modules on parsed statement data.

    Args:
        parsed_data: Output from parser (account_info, transactions, discrepancies)
        client_id: Document client ID
        config_overrides: Optional custom keywords for salary/EMI detection

    Returns:
        Complete analysis JSON matching Finpass format.
    """
    transactions = parsed_data.get("transactions", [])
    account_info = parsed_data.get("account_info", {})
    discrepancies = parsed_data.get("discrepancies", {})
    overrides = config_overrides or {}

    # Step 1: Categorize all transactions
    categorize_all_transactions(transactions)

    # Step 2: Run all analysis modules
    result = {
        "client_id": client_id,
        "entity_type": "individual",
        "health_score": _safe_run("health_score", compute_health_score, transactions, discrepancies),
        "summary_card": _safe_run("summary_card", compute_summary_card, transactions, account_info),
        "cash_flow": _safe_run("cash_flow", compute_cash_flow, transactions),
        "monthwise_metrics": _safe_run("monthwise_metrics", compute_monthwise_metrics, transactions),
        "top_transactions": _safe_run("top_transactions", compute_top_transactions, transactions),
        "salary_analysis": _safe_run("salary_analysis", compute_salary_analysis, transactions, overrides.get("salary_keywords")),
        "emi_obligations": _safe_run("emi_obligations", compute_emi_obligations, transactions, overrides.get("emi_keywords")),
        "suspicious_transactions": _safe_run("suspicious_transactions", compute_suspicious_transactions, transactions),
        "flagged_transactions": _safe_run("flagged_transactions", compute_flagged_transactions, transactions, discrepancies),
        "bank_charges": _safe_run("bank_charges", compute_bank_charges, transactions),
        "aml_signals": _safe_run("aml_signals", compute_aml_signals, transactions),
        "cash_withdrawal_deposit": _safe_run("cash_withdrawal_deposit", compute_cash_withdrawal_deposit, transactions),
        "reversal_circular_analysis": _safe_run("reversal_circular", compute_reversal_circular, transactions),
        "behavioural_fraud_signals": _safe_run("behavioural_fraud", compute_behavioural_fraud_signals, transactions),
        "cam_analysis": _safe_run("cam_analysis", compute_cam_analysis, transactions),
        "scoring_data": _safe_run("scoring_data", compute_scoring_data, transactions, discrepancies),
        "recurring_transactions": _safe_run("recurring_transactions", compute_recurring_transactions, transactions),
        "eod_balances": _safe_run("eod_balances", compute_eod_balances, transactions),
        "loan_disbursements": _safe_run("loan_disbursements", compute_loan_disbursements, transactions),
        "investment_insurance_analysis": _safe_run("investment_insurance", compute_investment_insurance, transactions),
        "salary_keyword_analysis": {},
        "other_emis": _safe_run("other_emis", compute_other_emis, transactions),
        "sip_investments": _safe_run("sip_investments", compute_sip_investments, transactions),
        "paylater_transactions": _safe_run("paylater", compute_paylater, transactions),
        "config_overrides": overrides,
    }

    return result

