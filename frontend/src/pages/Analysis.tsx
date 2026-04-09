import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, RefreshCw, Download, FileText, User, Building, CreditCard, Calendar,
  TrendingUp, TrendingDown, DollarSign, Activity, Shield, AlertTriangle,
  CheckCircle, XCircle, Search, ChevronDown, ChevronUp, Banknote, Landmark, Eye, Sparkles, Loader2, Settings
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend, AreaChart, Area
} from 'recharts'
import { api } from '../api'

const COLORS = ['#2a5cb5', '#e8722a', '#0d9668', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#be185d', '#16a34a', '#9333ea']
const fmt = (n: number) => '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 })
const fmtDec = (n: number) => '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 2 })

const TAB_NAMES = ['Overview', 'Transactions', 'Salary', 'EMI & Obligations', 'Suspicious', 'Top Transactions', 'Bank Charges', 'AI Insights']

export default function AnalysisPage() {
  const { clientId } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState(0)
  const [analysis, setAnalysis] = useState<any>(null)
  const [statement, setStatement] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    if (!clientId) return
    setLoading(true)
    try {
      const [a, s] = await Promise.all([api.getAnalysisJson(clientId), api.getStatementResult(clientId)])
      setAnalysis(a)
      setStatement(s)
    } catch (e: any) { setError(e.message || 'Failed to load analysis') }
    setLoading(false)
  }

  useEffect(() => { load() }, [clientId])

  if (loading) return <div className="loading-overlay" style={{ minHeight: '80vh' }}><div className="spinner" style={{ width: 40, height: 40 }} /><span>Loading analysis...</span></div>
  if (error) return <div className="page-body"><div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--danger)' }}><AlertTriangle size={32} /><h3 style={{ marginTop: 12 }}>{error}</h3><button className="btn btn-ghost" style={{ marginTop: 16 }} onClick={() => navigate('/')}>Go Back</button></div></div>
  if (!analysis || !statement) return null

  const sc = analysis.summary_card || {}
  const bs = sc.balance_summary || {}
  const ts = sc.transaction_summary || {}
  const fs = sc.financial_summary || {}
  const ai = statement.account_info || {}
  const hs = analysis.health_score || {}

  return (
    <>
      {/* Header Banner */}
      <div className="page-header" style={{ flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-ghost btn-icon" onClick={() => navigate('/')}><ArrowLeft size={18} /></button>
          <div>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              Bank Statement Analysis
              <span className="badge badge-info" style={{ fontSize: 10 }}>Individual</span>
            </h2>
            <p style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <span><User size={12} style={{ display: 'inline', verticalAlign: -2 }} /> {sc.customer_name || ai.account_holder_name || 'N/A'}</span>
              {ai.statement_period?.from && <span><Calendar size={12} style={{ display: 'inline', verticalAlign: -2 }} /> {ai.statement_period.from} → {ai.statement_period.to}</span>}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCw size={14} /></button>
          <button className="btn btn-ghost btn-sm" onClick={() => {
            window.open(`${import.meta.env.DEV ? 'http://localhost:8000' : ''}/api/v1/export/pdf/${clientId}`, '_blank')
          }}><Download size={14} /> PDF</button>
          <button className="btn btn-primary btn-sm" onClick={() => {
            window.open(`${import.meta.env.DEV ? 'http://localhost:8000' : ''}/api/v1/export/excel/${clientId}`, '_blank')
          }}><FileText size={14} /> Excel</button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ paddingLeft: 32 }}>
        {TAB_NAMES.map((name, i) => (
          <button key={i} className={`tab ${tab === i ? 'active' : ''}`} onClick={() => setTab(i)}>{name}</button>
        ))}
      </div>

      <div className="page-body" style={{ paddingTop: 0 }}>
        {tab === 0 && <OverviewTab analysis={analysis} statement={statement} sc={sc} bs={bs} ts={ts} fs={fs} ai={ai} hs={hs} />}
        {tab === 1 && <TransactionTab transactions={statement.transactions || []} />}
        {tab === 2 && <SalaryTab data={analysis.salary_analysis || {}} />}
        {tab === 3 && <EMITab data={analysis.emi_obligations || {}} />}
        {tab === 4 && <SuspiciousTab data={analysis.suspicious_transactions || {}} aml={analysis.aml_signals || {}} />}
        {tab === 5 && <TopTransactionsTab data={analysis.top_transactions || {}} />}
        {tab === 6 && <BankChargesTab data={analysis.bank_charges || {}} />}
        {tab === 7 && <AIInsightsTab data={analysis.ai_insights || {}} clientId={clientId || ''} onRefresh={load} />}
      </div>
    </>
  )
}

/* ═══════════════════════════════════════════════════════
   TAB 1: OVERVIEW
   ═══════════════════════════════════════════════════════ */
function OverviewTab({ analysis, statement, sc, bs, ts, fs, ai, hs }: any) {
  const cashFlow = analysis.cash_flow || {}
  const monthlyData = (cashFlow.monthly_summary || []).map((m: any) => ({
    month: m.month, credit: m.total_credit, debit: m.total_debit, surplus: m.surplus
  }))

  const inflowModes = (cashFlow.inflow_by_mode || []).slice(0, 6)
  const outflowModes = (cashFlow.outflow_by_mode || []).slice(0, 8)

  return (
    <div className="animate-fade-in">
      {/* Account Profile + Health Score */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px', gap: 16, marginBottom: 20 }}>
        <div className="card">
          <div className="card-title">Account Profile</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            <ProfileItem icon={<User size={14} />} label="Account Holder" value={sc.customer_name || ai.account_holder_name || 'N/A'} />
            <ProfileItem icon={<Landmark size={14} />} label="Bank" value={(sc.bank_name || ai.bank_name || '').toUpperCase()} />
            <ProfileItem icon={<CreditCard size={14} />} label="Account No." value={sc.account_number || ai.account_number || 'N/A'} />
            <ProfileItem icon={<Building size={14} />} label="IFSC" value={sc.ifsc_code || ai.ifsc || 'N/A'} />
            <ProfileItem icon={<Calendar size={14} />} label="Period" value={`${ai.statement_period?.from || ''} → ${ai.statement_period?.to || ''}`} />
          </div>
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div className="health-score-circle" style={{
            background: hs.score >= 80 ? 'rgba(16,185,129,0.1)' : hs.score >= 50 ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)',
            border: `3px solid ${hs.score >= 80 ? '#10b981' : hs.score >= 50 ? '#f59e0b' : '#ef4444'}`
          }}>
            <div className="score-value" style={{ color: hs.score >= 80 ? '#10b981' : hs.score >= 50 ? '#f59e0b' : '#ef4444' }}>{hs.score || 0}</div>
            <div className="score-label" style={{ color: hs.score >= 80 ? '#10b981' : hs.score >= 50 ? '#f59e0b' : '#ef4444' }}>{hs.rating || 'N/A'}</div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, textAlign: 'center' }}>Health Score</div>
        </div>
      </div>

      {/* Balance / Transaction / Key Indicator Cards */}
      <div className="grid-3" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title">Balance Summary</div>
          <SummaryRow label="Opening Balance" value={fmtDec(bs.opening_balance || 0)} />
          <SummaryRow label="Closing Balance" value={fmtDec(bs.closing_balance || 0)} />
          <SummaryRow label="Average Balance" value={fmtDec(bs.average_balance || 0)} />
          <SummaryRow label="Max Balance" value={fmtDec(bs.max_balance || 0)} color="var(--success)" />
          <SummaryRow label="Min Balance" value={fmtDec(bs.min_balance || 0)} color="var(--warning)" />
        </div>
        <div className="card">
          <div className="card-title">Transaction Summary</div>
          <SummaryRow label="Total Transactions" value={ts.total_transactions || 0} />
          <SummaryRow label="Total Credits" value={fmtDec(ts.total_credits || 0)} color="var(--success)" />
          <SummaryRow label="Total Debits" value={fmtDec(ts.total_debits || 0)} color="var(--danger)" />
          <SummaryRow label="Credit Count" value={ts.credit_count || 0} />
          <SummaryRow label="Debit Count" value={ts.debit_count || 0} />
          <SummaryRow label="Net Flow" value={fmtDec(ts.net_flow || 0)} color={ts.net_flow >= 0 ? 'var(--success)' : 'var(--danger)'} />
        </div>
        <div className="card">
          <div className="card-title">Average Bank Balance</div>
          <SummaryRow label="ABB (Last 30 Days)" value={fmt(fs.abb_last_30_days || 0)} />
          <SummaryRow label="ABB (Last 3 Months)" value={fmt(fs.abb_last_3_months || 0)} />
          <SummaryRow label="ABB (Last 6 Months)" value={fmt(fs.abb_last_6_months || 0)} />
          <SummaryRow label="Peak Month" value={fs.max_abb_month || 'N/A'} />
          <SummaryRow label="Trough Month" value={fs.min_abb_month || 'N/A'} />
          <SummaryRow label="Net Change" value={fmtDec(fs.net_change_in_balance || 0)} color={fs.net_change_in_balance >= 0 ? 'var(--success)' : 'var(--danger)'} />
        </div>
      </div>

      {/* Cash Flow Chart */}
      {monthlyData.length > 0 && (
        <div className="chart-container" style={{ marginBottom: 20 }}>
          <div className="chart-title">Monthly Cash Flow</div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={monthlyData} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fill: '#4a5568', fontSize: 11 }} />
              <YAxis tick={{ fill: '#4a5568', fontSize: 11 }} tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}K`} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12, color: '#1a2b50', boxShadow: '0 4px 12px rgba(26,43,80,0.08)' }}
                formatter={(v: number) => [fmtDec(v), '']} />
              <Bar dataKey="credit" fill="#0d9668" name="Inflow" radius={[4, 4, 0, 0]} />
              <Bar dataKey="debit" fill="#dc2626" name="Outflow" radius={[4, 4, 0, 0]} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Surplus/Deficit Area */}
      {monthlyData.length > 0 && (
        <div className="chart-container" style={{ marginBottom: 20 }}>
          <div className="chart-title">Monthly Surplus / Deficit</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={monthlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fill: '#4a5568', fontSize: 11 }} />
              <YAxis tick={{ fill: '#4a5568', fontSize: 11 }} tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}K`} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12, color: '#1a2b50', boxShadow: '0 4px 12px rgba(26,43,80,0.08)' }}
                formatter={(v: number) => [fmtDec(v), 'Surplus']} />
              <Area type="monotone" dataKey="surplus" stroke="#2a5cb5" fill="rgba(42,92,181,0.12)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Inflow / Outflow Breakdown */}
      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title">Inflow by Mode</div>
          {inflowModes.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {inflowModes.map((m: any, i: number) => (
                <ModeBar key={i} mode={m.mode} total={m.total} count={m.count} pct={m.percentage} color="#10b981" />
              ))}
            </div>
          ) : <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 12 }}>No inflow data</div>}
        </div>
        <div className="card">
          <div className="card-title">Outflow by Mode</div>
          {outflowModes.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {outflowModes.map((m: any, i: number) => (
                <ModeBar key={i} mode={m.mode} total={m.total} count={m.count} pct={m.percentage} color="#ef4444" />
              ))}
            </div>
          ) : <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 12 }}>No outflow data</div>}
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   TAB 2: TRANSACTIONS
   ═══════════════════════════════════════════════════════ */
function TransactionTab({ transactions }: { transactions: any[] }) {
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [page, setPage] = useState(0)
  const perPage = 50

  const filtered = transactions.filter(t => {
    if (search && !t.description?.toLowerCase().includes(search.toLowerCase())) return false
    if (typeFilter === 'credit' && !t.credit) return false
    if (typeFilter === 'debit' && !t.debit) return false
    return true
  })

  const paged = filtered.slice(page * perPage, (page + 1) * perPage)
  const totalPages = Math.ceil(filtered.length / perPage)

  return (
    <div className="animate-fade-in">
      <div className="filters-bar">
        <div className="search-bar" style={{ flex: 1, maxWidth: 400 }}>
          <Search size={16} />
          <input placeholder="Search transactions..." value={search} onChange={e => { setSearch(e.target.value); setPage(0) }} />
        </div>
        <select className="form-input" style={{ width: 'auto' }} value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(0) }}>
          <option value="">All Types</option>
          <option value="credit">Credits Only</option>
          <option value="debit">Debits Only</option>
        </select>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{filtered.length} transactions</span>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Date</th>
              <th>Description</th>
              <th>Category</th>
              <th style={{ textAlign: 'right' }}>Debit</th>
              <th style={{ textAlign: 'right' }}>Credit</th>
              <th style={{ textAlign: 'right' }}>Balance</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((t: any, i: number) => (
              <tr key={i}>
                <td style={{ color: 'var(--text-muted)' }}>{t.sr_no}</td>
                <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, whiteSpace: 'nowrap' }}>{t.txn_date}</td>
                <td className="txn-description" title={t.description}>{t.description}</td>
                <td><span className={`mode-badge ${t.category?.startsWith('credit') ? 'credit' : 'debit'}`}>{(t.category || '').replace(/_/g, ' ').slice(0, 20)}</span></td>
                <td style={{ textAlign: 'right' }}>{t.debit ? <span className="amount debit">{fmtDec(t.debit)}</span> : '—'}</td>
                <td style={{ textAlign: 'right' }}>{t.credit ? <span className="amount credit">{fmtDec(t.credit)}</span> : '—'}</td>
                <td style={{ textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: 12 }}>{fmtDec(t.balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <button className="btn btn-ghost btn-sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous</button>
          <span style={{ padding: '6px 12px', fontSize: 12, color: 'var(--text-muted)' }}>Page {page + 1} of {totalPages}</span>
          <button className="btn btn-ghost btn-sm" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next</button>
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   TAB 3: SALARY ANALYSIS
   ═══════════════════════════════════════════════════════ */
function SalaryTab({ data }: { data: any }) {
  const detected = data.salary_detected
  const salaryTxns = data.salary_transactions || []

  return (
    <div className="animate-fade-in">
      {/* Summary Stats */}
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <StatCard label="Monthly Salary" value={detected ? fmt(data.monthly_salary || 0) : '—'} icon={<DollarSign size={18} />} color="#10b981" />
        <StatCard label="Salary Payments" value={data.salary_count || 0} icon={<Activity size={18} />} color="#2a5cb5" />
        <StatCard label="Credit Day Range" value={data.credit_day_range || 'N/A'} icon={<Calendar size={18} />} color="#f59e0b" />
        <StatCard label="Confidence" value={`${data.confidence_score_percentage || 0}%`} icon={<Shield size={18} />} color="#3b82f6" />
      </div>

      {/* Detection Status */}
      <div className="card" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
        {detected ? (
          <>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--success-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--success)' }}>
              <CheckCircle size={20} />
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--success)' }}>Salary Detected</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Employer: {data.employer_name || 'N/A'} • Method: {data.detection_method} • Variance: {data.salary_variance_pct?.toFixed(1)}%
              </div>
            </div>
          </>
        ) : (
          <>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--warning-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--warning)' }}>
              <AlertTriangle size={20} />
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--warning)' }}>No Salary Detected</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No regular salary pattern found in transactions.</div>
            </div>
          </>
        )}
      </div>

      {/* Salary Transactions Table */}
      {salaryTxns.length > 0 && (
        <div className="table-container">
          <table>
            <thead><tr><th>Date</th><th>Description</th><th>Month</th><th style={{ textAlign: 'right' }}>Amount</th></tr></thead>
            <tbody>
              {salaryTxns.map((t: any, i: number) => (
                <tr key={i}>
                  <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>{t.date}</td>
                  <td className="txn-description">{t.description}</td>
                  <td><span className="badge badge-info">{t.month}</span></td>
                  <td style={{ textAlign: 'right' }}><span className="amount credit">{fmtDec(t.amount)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   TAB 4: EMI & OBLIGATIONS
   ═══════════════════════════════════════════════════════ */
function EMITab({ data }: { data: any }) {
  const obligations = data.obligations || []

  return (
    <div className="animate-fade-in">
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <StatCard label="Monthly Burden" value={data.monthly_emi_burden ? fmt(data.monthly_emi_burden) : '—'} icon={<DollarSign size={18} />} color="#ef4444" />
        <StatCard label="Total EMIs" value={data.total_emi_count || 0} icon={<Activity size={18} />} color="#2a5cb5" />
        <StatCard label="Total Bounces" value={data.total_bounces || 0} icon={<AlertTriangle size={18} />} color="#f59e0b" />
        <StatCard label="Risk Score" value={`${data.overall_risk_score || 0}`} icon={<Shield size={18} />} color={data.risk_category === 'HIGH' ? '#ef4444' : data.risk_category === 'MEDIUM' ? '#f59e0b' : '#10b981'} />
      </div>

      <div className="card" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
        {data.emi_detected ? (
          <>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--info-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--info)' }}><CreditCard size={20} /></div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>EMI Obligations Detected</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Risk Category: <span className={`badge ${data.risk_category === 'HIGH' ? 'badge-danger' : data.risk_category === 'MEDIUM' ? 'badge-warning' : 'badge-success'}`}>{data.risk_category}</span>
                {' '}• Total: {fmtDec(data.total_emi_amount || 0)}
              </div>
            </div>
          </>
        ) : (
          <>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--success-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--success)' }}><CheckCircle size={20} /></div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--success)' }}>No EMI Obligations</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No recurring EMI payments detected.</div>
            </div>
          </>
        )}
      </div>

      {obligations.length > 0 && (
        <div className="table-container">
          <table>
            <thead><tr><th>Lender</th><th>EMI Amount</th><th>Frequency</th><th>Months</th><th>Bounces</th><th>Total Paid</th></tr></thead>
            <tbody>
              {obligations.map((o: any, i: number) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{o.lender}</td>
                  <td><span className="amount debit">{fmtDec(o.emi_amount)}</span></td>
                  <td><span className="badge badge-neutral">{o.frequency}</span></td>
                  <td>{o.months_detected}</td>
                  <td>{o.bounce_count > 0 ? <span className="badge badge-danger">{o.bounce_count}</span> : <span className="badge badge-success">0</span>}</td>
                  <td><span className="amount neutral">{fmtDec(o.total_paid)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   TAB 5: SUSPICIOUS & AML
   ═══════════════════════════════════════════════════════ */
function SuspiciousTab({ data, aml }: { data: any; aml: any }) {
  const summary = data.summary || {}
  const indicators = aml.indicators || []
  const suspCredits = data.suspicious_credits || []
  const suspDebits = data.suspicious_debits || []

  return (
    <div className="animate-fade-in">
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <StatCard label="Total Suspicious" value={summary.total_suspicious || 0} icon={<AlertTriangle size={18} />} color="#ef4444" />
        <StatCard label="Suspicious Credits" value={summary.suspicious_credit_count || 0} icon={<TrendingUp size={18} />} color="#f59e0b" />
        <StatCard label="Suspicious Debits" value={summary.suspicious_debit_count || 0} icon={<TrendingDown size={18} />} color="#f59e0b" />
      </div>

      {/* Status */}
      <div className="card" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
        {(summary.total_suspicious || 0) === 0 ? (
          <>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--success-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--success)' }}><Shield size={20} /></div>
            <div><div style={{ fontWeight: 600, color: 'var(--success)' }}>All Clear</div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No suspicious transactions detected.</div></div>
          </>
        ) : (
          <>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--danger-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--danger)' }}><AlertTriangle size={20} /></div>
            <div><div style={{ fontWeight: 600, color: 'var(--danger)' }}>Alerts Found</div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{summary.total_suspicious} suspicious transactions identified.</div></div>
          </>
        )}
      </div>

      {/* AML Indicators */}
      {indicators.length > 0 && (
        <div className="card" style={{ marginBottom: 20, padding: 0 }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>🔍 AML Signal Check</span>
          </div>
          {indicators.map((ind: any, i: number) => (
            <div key={i} className="aml-row">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: "'JetBrains Mono'" }}>{ind.id}</span>
                <span style={{ fontSize: 13 }}>{ind.parameter}</span>
              </div>
              <span className={`aml-status ${ind.suspicious === 'Yes' ? 'suspicious' : 'safe'}`}>
                {ind.suspicious === 'Yes' ? <><XCircle size={14} /> Suspicious</> : <><CheckCircle size={14} /> Clear</>}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Suspicious Tables */}
      {suspCredits.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title" style={{ color: 'var(--warning)' }}>Suspicious Credits</div>
          {suspCredits.map((t: any, i: number) => (
            <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div><div style={{ fontSize: 13, fontWeight: 500 }}>{t.description?.slice(0, 60)}</div><div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t.date} • {t.reasons?.join(', ')}</div></div>
              <span className="amount credit" style={{ whiteSpace: 'nowrap' }}>{fmtDec(t.amount)}</span>
            </div>
          ))}
        </div>
      )}
      {suspDebits.length > 0 && (
        <div className="card">
          <div className="card-title" style={{ color: 'var(--warning)' }}>Suspicious Debits</div>
          {suspDebits.map((t: any, i: number) => (
            <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div><div style={{ fontSize: 13, fontWeight: 500 }}>{t.description?.slice(0, 60)}</div><div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t.date} • {t.reasons?.join(', ')}</div></div>
              <span className="amount debit" style={{ whiteSpace: 'nowrap' }}>{fmtDec(t.amount)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   TAB 6: TOP TRANSACTIONS
   ═══════════════════════════════════════════════════════ */
function TopTransactionsTab({ data }: { data: any }) {
  const topCredits = data.top_credits || []
  const topDebits = data.top_debits || []

  const TxnRow = ({ t, i, type }: { t: any; i: number; type: 'credit' | 'debit' }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid var(--border-light)' }}>
      <span style={{ width: 22, minWidth: 22, height: 22, borderRadius: '50%', background: type === 'credit' ? 'var(--success-bg)' : 'var(--danger-bg)', color: type === 'credit' ? 'var(--success)' : 'var(--danger)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700 }}>{i + 1}</span>
      <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
        <div style={{ fontWeight: 500, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.description}>{t.description}</div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{t.date} • {t.mode?.replace(/_/g, ' ')}</div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0, minWidth: 90 }}>
        <div className={`amount ${type}`} style={{ fontSize: 13 }}>{fmtDec(t.amount)}</div>
        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>{t.percentage}%</div>
      </div>
    </div>
  )

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-title" style={{ color: 'var(--success)' }}>
            <TrendingUp size={14} style={{ display: 'inline', verticalAlign: -2, marginRight: 6 }} />
            Top Credits (by Value)
          </div>
          {topCredits.length === 0 ? <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 12 }}>No credit transactions</div> :
            topCredits.map((t: any, i: number) => <TxnRow key={i} t={t} i={i} type="credit" />)}
        </div>

        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-title" style={{ color: 'var(--danger)' }}>
            <TrendingDown size={14} style={{ display: 'inline', verticalAlign: -2, marginRight: 6 }} />
            Top Debits (by Value)
          </div>
          {topDebits.length === 0 ? <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 12 }}>No debit transactions</div> :
            topDebits.map((t: any, i: number) => <TxnRow key={i} t={t} i={i} type="debit" />)}
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   TAB 7: BANK CHARGES
   ═══════════════════════════════════════════════════════ */
function BankChargesTab({ data }: { data: any }) {
  const detected = data.detected
  const summary = data.summary || []
  const txns = data.transactions || []
  const totalCharges = summary.reduce((s: number, item: any) => s + (item.total_debit || 0), 0)

  return (
    <div className="animate-fade-in">
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <StatCard label="Status" value={detected ? 'Found' : 'None'} icon={<Banknote size={18} />} color={detected ? '#f59e0b' : '#10b981'} />
        <StatCard label="Total Charges" value={detected ? fmtDec(totalCharges) : '₹0'} icon={<DollarSign size={18} />} color="#ef4444" />
        <StatCard label="Charge Transactions" value={txns.length} icon={<Activity size={18} />} color="#2a5cb5" />
      </div>

      {detected ? (
        <>
          {summary.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-title">Charge Summary</div>
              {summary.map((s: any, i: number) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-light)' }}>
                  <span style={{ fontSize: 13 }}>{s.category?.replace(/_/g, ' ')}</span>
                  <div style={{ display: 'flex', gap: 16 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{s.count} txns</span>
                    <span className="amount debit">{fmtDec(s.total_debit)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {txns.length > 0 && (
            <div className="table-container">
              <table>
                <thead><tr><th>Date</th><th>Description</th><th>Category</th><th style={{ textAlign: 'right' }}>Amount</th></tr></thead>
                <tbody>
                  {txns.map((t: any, i: number) => (
                    <tr key={i}>
                      <td style={{ fontFamily: "'JetBrains Mono'", fontSize: 12 }}>{t.date}</td>
                      <td className="txn-description">{t.description}</td>
                      <td><span className="badge badge-neutral">{t.category?.replace(/_/g, ' ')}</span></td>
                      <td style={{ textAlign: 'right' }}><span className="amount debit">{fmtDec(t.debit)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: 40 }}>
          <CheckCircle size={32} style={{ color: 'var(--success)', marginBottom: 12 }} />
          <h3 style={{ fontWeight: 600, color: 'var(--success)' }}>No Bank Charges Detected</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>No charges, penalties, or fees found in the statement.</p>
        </div>
      )}
    </div>
  )
}


/* ═══════════════════════════════════════════════════════
   TAB 8: AI INSIGHTS (Groq-powered)
   ═══════════════════════════════════════════════════════ */
function AIInsightsTab({ data, clientId, onRefresh }: { data: any; clientId: string; onRefresh: () => void }) {
  const [reanalyzing, setReanalyzing] = useState(false)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const navigate = useNavigate()
  const hasData = data && data.executive_summary && data.executive_summary !== 'AI insights unavailable'

  async function handleReanalyze() {
    setReanalyzing(true)
    setMsg(null)
    try {
      const result = await api.reanalyzeWithAI(clientId)
      setMsg({ type: 'success', text: result.message || 'AI analysis complete!' })
      onRefresh()
    } catch (e: any) {
      setMsg({ type: 'error', text: e.message || 'Failed' })
    }
    setReanalyzing(false)
  }

  if (!hasData) {
    return (
      <div className="animate-fade-in">
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <Sparkles size={36} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
          <h3 style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>AI Insights Not Available</h3>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 450, margin: '0 auto 20px' }}>
            Add your Groq API key in Settings, then click below to run AI analysis on this statement.
          </p>
          {msg && (
            <div style={{ padding: '10px 16px', borderRadius: 8, marginBottom: 16, background: msg.type === 'success' ? 'var(--success-bg)' : '#fee2e2', color: msg.type === 'success' ? 'var(--success)' : '#dc2626', fontSize: 13, fontWeight: 500, maxWidth: 450, margin: '0 auto 16px' }}>
              {msg.text}
            </div>
          )}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
            <button onClick={handleReanalyze} disabled={reanalyzing} className="btn btn-primary" style={{ padding: '10px 24px', fontSize: 13 }}>
              {reanalyzing ? <><Loader2 size={14} className="spin" /> Analyzing...</> : <><Sparkles size={14} /> Run AI Analysis</>}
            </button>
            <button onClick={() => navigate('/settings')} className="btn" style={{ padding: '10px 20px', fontSize: 13, background: 'var(--bg-tertiary)', border: '1px solid var(--border-light)', borderRadius: 8, cursor: 'pointer', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Settings size={14} /> API Settings
            </button>
          </div>
        </div>
      </div>
    )
  }

  const healthColor = data.cashflow_health === 'healthy' ? 'var(--success)' :
    data.cashflow_health === 'moderate' ? '#f59e0b' : 'var(--danger)'

  return (
    <div className="animate-fade-in">
      {/* AI Banner */}
      <div className="card" style={{ background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e3a5f 100%)', color: 'white', marginBottom: 20, border: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div style={{ width: 40, height: 40, borderRadius: 12, background: 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Sparkles size={20} />
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.3px' }}>AI-Powered Financial Analysis</div>
            <div style={{ fontSize: 11, opacity: 0.7 }}>Powered by Groq LLM • llama-3.3-70b</div>
          </div>
          {data.cashflow_health && (
            <div style={{ marginLeft: 'auto', padding: '6px 16px', borderRadius: 20, background: `${healthColor}25`, color: healthColor, fontSize: 12, fontWeight: 700, textTransform: 'uppercase', border: `1px solid ${healthColor}40` }}>
              {data.cashflow_health}
            </div>
          )}
        </div>
        <p style={{ fontSize: 14, lineHeight: 1.7, opacity: 0.95 }}>{data.executive_summary}</p>
        {data.savings_rate_estimate && (
          <div style={{ marginTop: 12, padding: '8px 14px', background: 'rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}>
            💰 Estimated Savings Rate: <strong>{data.savings_rate_estimate}</strong>
          </div>
        )}
      </div>

      {/* Income & Spending Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {data.income_assessment && (
          <div className="card">
            <div className="card-title" style={{ color: 'var(--success)' }}>
              <TrendingUp size={14} style={{ display: 'inline', verticalAlign: -2, marginRight: 6 }} />
              Income Assessment
            </div>
            <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-secondary)' }}>{data.income_assessment}</p>
          </div>
        )}
        {data.spending_pattern && (
          <div className="card">
            <div className="card-title" style={{ color: '#f59e0b' }}>
              <TrendingDown size={14} style={{ display: 'inline', verticalAlign: -2, marginRight: 6 }} />
              Spending Patterns
            </div>
            <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-secondary)' }}>{data.spending_pattern}</p>
          </div>
        )}
      </div>

      {/* Risk Flags */}
      {data.risk_flags && data.risk_flags.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title" style={{ color: 'var(--danger)' }}>
            <AlertTriangle size={14} style={{ display: 'inline', verticalAlign: -2, marginRight: 6 }} />
            Risk Flags
          </div>
          {data.risk_flags.map((flag: string, i: number) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 0', borderBottom: i < data.risk_flags.length - 1 ? '1px solid var(--border-light)' : 'none' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)', marginTop: 6, flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{flag}</span>
            </div>
          ))}
        </div>
      )}

      {/* Recommendations */}
      {data.recommendations && data.recommendations.length > 0 && (
        <div className="card">
          <div className="card-title" style={{ color: 'var(--accent-primary-light)' }}>
            <CheckCircle size={14} style={{ display: 'inline', verticalAlign: -2, marginRight: 6 }} />
            Recommendations
          </div>
          {data.recommendations.map((rec: string, i: number) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 0', borderBottom: i < data.recommendations.length - 1 ? '1px solid var(--border-light)' : 'none' }}>
              <span style={{ width: 22, minWidth: 22, height: 22, borderRadius: '50%', background: 'var(--accent-primary-bg)', color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700 }}>{i + 1}</span>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{rec}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


/* ═══════════════════════════════════════════════════════
   SHARED COMPONENTS
   ═══════════════════════════════════════════════════════ */

function ProfileItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0' }}>
      <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
      <div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{value || 'N/A'}</div>
      </div>
    </div>
  )
}

function SummaryRow({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border-light)' }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 600, fontFamily: typeof value === 'string' && value.includes('₹') ? "'JetBrains Mono', monospace" : 'inherit', color: color || 'var(--text-primary)' }}>{value}</span>
    </div>
  )
}

function StatCard({ label, value, icon, color }: { label: string; value: string | number; icon: React.ReactNode; color: string }) {
  return (
    <div className="stat-card">
      <div className="stat-icon" style={{ background: `${color}15`, color }}>{icon}</div>
      <div className="stat-value" style={{ fontSize: typeof value === 'string' && value.length > 10 ? 18 : 28 }}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function ModeBar({ mode, total, count, pct, color }: { mode: string; total: number; count: number; pct: number; color: string }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
        <span style={{ color: 'var(--text-secondary)' }}>{mode.replace(/_/g, ' ')}</span>
        <span style={{ fontFamily: "'JetBrains Mono'", fontWeight: 600, color }}>{fmt(total)} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>({count})</span></span>
      </div>
      <div style={{ height: 6, background: 'var(--bg-tertiary)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: color, borderRadius: 3, transition: 'width 0.5s ease' }} />
      </div>
    </div>
  )
}
