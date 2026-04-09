from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# --- Upload / Document schemas ---

class DocumentUploadResponse(BaseModel):
    doc_id: str
    client_id: str
    filename: str
    status: str
    message: str


class DocumentListItem(BaseModel):
    id: int
    doc_id: str
    client_id: str
    filename: str
    file_type: str
    file_size: int
    bank_name: str
    account_holder_name: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentListItem]
    status_counts: Dict[str, int]


# --- Account Info ---

class StatementPeriod(BaseModel):
    from_date: str = ""
    to_date: str = ""


class AccountInfo(BaseModel):
    bank_name: str = ""
    account_holder_name: str = ""
    account_number: str = ""
    address: str = ""
    ifsc: str = ""
    micr_code: str = ""
    customer_id: str = ""
    email: str = ""
    phone: str = ""
    account_type: str = ""
    account_open_date: str = ""
    branch_name: str = ""
    statement_period: StatementPeriod = StatementPeriod()


# --- Transaction ---

class Transaction(BaseModel):
    sr_no: int = 0
    txn_date: str = ""
    value_date: str = ""
    reference_no: str = ""
    description: str = ""
    txn_type: str = ""  # Dr. or Cr.
    credit: float = 0.0
    debit: float = 0.0
    balance: float = 0.0
    category: str = ""  # assigned by categorizer
    sub_category: str = ""


# --- Statement Result (Raw Extraction) ---

class StatementResult(BaseModel):
    doc_id: str
    client_id: str
    status: str
    account_info: AccountInfo
    transactions: List[Transaction]
    total_transactions: int = 0
    mismatched_sequence_date: List[Any] = []
    negative_balance: List[Any] = []
    discrepancies: Dict[str, Any] = {}


# --- Analysis JSON (all 25 sections) ---

class BalanceSummary(BaseModel):
    opening_balance: float = 0.0
    closing_balance: float = 0.0
    average_balance: float = 0.0
    max_balance: float = 0.0
    min_balance: float = 0.0


class TransactionSummary(BaseModel):
    total_transactions: int = 0
    total_credits: float = 0.0
    total_debits: float = 0.0
    credit_count: int = 0
    debit_count: int = 0
    net_flow: float = 0.0


class ModeBreakdownItem(BaseModel):
    mode: str = ""
    total: float = 0.0
    count: int = 0
    percentage: float = 0.0


class FinancialSummary(BaseModel):
    abb_last_6_months: float = 0.0
    abb_last_3_months: float = 0.0
    abb_last_30_days: float = 0.0
    net_change_in_balance: float = 0.0
    min_abb_month: str = ""
    max_abb_month: str = ""
    amb_charges: float = 0.0
    forecasted_abb_next_30_days: float = 0.0


class SummaryCard(BaseModel):
    customer_name: str = ""
    account_number: str = ""
    bank_name: str = ""
    ifsc_code: str = ""
    account_type: str = ""
    statement_period: StatementPeriod = StatementPeriod()
    balance_summary: BalanceSummary = BalanceSummary()
    transaction_summary: TransactionSummary = TransactionSummary()
    mode_breakdown: Dict[str, ModeBreakdownItem] = {}
    financial_summary: FinancialSummary = FinancialSummary()


class HealthScore(BaseModel):
    score: int = 100
    rating: str = "Excellent"
    rating_description: str = ""
    total_penalties: int = 0
    breakdown: Dict[str, Any] = {}
    details: Dict[str, Any] = {}


class MonthlyCashFlow(BaseModel):
    month: str = ""
    total_credit: float = 0.0
    total_debit: float = 0.0
    transaction_count: int = 0
    surplus: float = 0.0


class CashFlow(BaseModel):
    monthly_summary: List[MonthlyCashFlow] = []
    inflow_by_mode: List[ModeBreakdownItem] = []
    outflow_by_mode: List[ModeBreakdownItem] = []
    net_cash_flow: float = 0.0


class MonthwiseMetric(BaseModel):
    month: str = ""
    opening_balance: float = 0.0
    closing_balance: float = 0.0
    total_credit: float = 0.0
    total_debit: float = 0.0
    monthly_surplus: float = 0.0
    avg_balance: float = 0.0
    max_balance: float = 0.0
    min_balance: float = 0.0
    max_credit: float = 0.0
    min_credit: float = 0.0
    max_debit: float = 0.0
    min_debit: float = 0.0
    income_expense_ratio: float = 0.0
    transaction_count: int = 0
    credit_count: int = 0
    debit_count: int = 0


class TopTransaction(BaseModel):
    date: str = ""
    description: str = ""
    amount: float = 0.0
    percentage: float = 0.0
    mode: str = ""


class TopTransactions(BaseModel):
    top_credits: List[TopTransaction] = []
    top_debits: List[TopTransaction] = []


class SalaryAnalysis(BaseModel):
    salary_detected: bool = False
    confidence_score_percentage: float = 0.0
    monthly_salary: float = 0.0
    salary_variance_pct: float = 0.0
    salary_count: int = 0
    employer_name: str = "N/A"
    credit_day_range: str = "N/A"
    salary_transactions: List[Dict[str, Any]] = []
    detection_method: str = "scoring"


class EMIObligation(BaseModel):
    lender: str = ""
    emi_amount: float = 0.0
    frequency: str = ""
    months_detected: int = 0
    bounce_count: int = 0
    total_paid: float = 0.0


class EMIOblications(BaseModel):
    emi_detected: bool = False
    total_emi_count: int = 0
    total_emi_amount: float = 0.0
    monthly_emi_burden: float = 0.0
    obligations: List[EMIObligation] = []
    total_bounces: int = 0
    overall_risk_score: float = 0.0
    risk_category: str = "LOW"


class SuspiciousTransactions(BaseModel):
    suspicious_credits: List[Dict[str, Any]] = []
    suspicious_debits: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}


class FlaggedTransactions(BaseModel):
    bounce_transactions: List[Dict[str, Any]] = []
    negative_balance_transactions: List[Dict[str, Any]] = []
    reconciliation_issues: List[Dict[str, Any]] = []
    cheque_return_summary: Dict[str, Any] = {}
    summary: Dict[str, Any] = {}


class AMLIndicator(BaseModel):
    id: str = ""
    parameter: str = ""
    suspicious: str = "No"
    details: str = ""


class AMLSignals(BaseModel):
    indicators: List[AMLIndicator] = []


class FullAnalysisJSON(BaseModel):
    """Complete analysis output matching all 25 Finpass sections."""
    client_id: str = ""
    entity_type: str = "individual"
    health_score: HealthScore = HealthScore()
    summary_card: SummaryCard = SummaryCard()
    cash_flow: CashFlow = CashFlow()
    monthwise_metrics: List[MonthwiseMetric] = []
    top_transactions: TopTransactions = TopTransactions()
    salary_analysis: SalaryAnalysis = SalaryAnalysis()
    emi_obligations: EMIOblications = EMIOblications()
    suspicious_transactions: SuspiciousTransactions = SuspiciousTransactions()
    flagged_transactions: FlaggedTransactions = FlaggedTransactions()
    bank_charges: Dict[str, Any] = {}
    aml_signals: AMLSignals = AMLSignals()
    cash_withdrawal_deposit: Dict[str, Any] = {}
    reversal_circular_analysis: Dict[str, Any] = {}
    behavioural_fraud_signals: Dict[str, Any] = {}
    cam_analysis: Dict[str, Any] = {}
    scoring_data: Dict[str, Any] = {}
    recurring_transactions: Dict[str, Any] = {}
    eod_balances: Dict[str, float] = {}
    loan_disbursements: Dict[str, Any] = {}
    investment_insurance_analysis: Dict[str, Any] = {}
    salary_keyword_analysis: Dict[str, Any] = {}
    other_emis: Dict[str, Any] = {}
    sip_investments: Dict[str, Any] = {}
    paylater_transactions: Dict[str, Any] = {}
