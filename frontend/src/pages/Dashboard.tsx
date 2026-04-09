import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, CheckCircle, Clock, AlertCircle, Upload, Eye, Trash2, Search, RefreshCw } from 'lucide-react'
import { api } from '../api'

interface Doc {
  id: number; doc_id: string; client_id: string; filename: string;
  file_type: string; file_size: number; bank_name: string;
  account_holder_name: string; status: string; error_message: string | null;
  created_at: string; completed_at: string | null;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) +
    ', ' + d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

const bankLabels: Record<string, string> = {
  hdfc: 'HDFC Bank', sbi: 'SBI', icici: 'ICICI Bank', axis: 'Axis Bank',
  kotak: 'Kotak', pnb: 'PNB', bob: 'Bank of Baroda', canara: 'Canara Bank',
  union: 'Union Bank', idbi: 'IDBI Bank', yes_bank: 'Yes Bank',
  indusind: 'IndusInd', federal: 'Federal Bank', bandhan: 'Bandhan Bank',
  idfc: 'IDFC First', rbl: 'RBL Bank', unknown: 'Unknown',
}

export default function Dashboard() {
  const [docs, setDocs] = useState<Doc[]>([])
  const [counts, setCounts] = useState({ total: 0, completed: 0, processing: 0, failed: 0 })
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.getDocuments({ search, status: statusFilter })
      setDocs(data.documents || [])
      setCounts(data.status_counts || { total: 0, completed: 0, processing: 0, failed: 0 })
    } catch { }
    setLoading(false)
  }

  useEffect(() => { load() }, [search, statusFilter])

  const handleDelete = async (clientId: string) => {
    if (!confirm('Delete this document?')) return
    await api.deleteDocument(clientId)
    load()
  }

  const statCards = [
    { icon: FileText, label: 'Total Documents', value: counts.total, color: '#2a5cb5', bg: 'rgba(42,92,181,0.1)' },
    { icon: CheckCircle, label: 'Completed', value: counts.completed, color: '#0d9668', bg: 'rgba(13,150,104,0.08)' },
    { icon: Clock, label: 'Processing', value: counts.processing, color: '#d97706', bg: 'rgba(217,119,6,0.08)' },
    { icon: AlertCircle, label: 'Failed', value: counts.failed, color: '#dc2626', bg: 'rgba(220,38,38,0.08)' },
  ]

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Bank Statement Analyser</h2>
          <p>Manage and analyze your bank statements</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </button>
          <Link to="/upload" className="btn btn-primary btn-sm">
            <Upload size={14} /> Upload New
          </Link>
        </div>
      </div>

      <div className="page-body">
        {/* Status Cards */}
        <div className="stats-grid animate-fade-in">
          {statCards.map((card, i) => (
            <div key={i} className="stat-card" style={{ animationDelay: `${i * 80}ms` }}>
              <div className="stat-icon" style={{ background: card.bg, color: card.color }}>
                <card.icon size={20} />
              </div>
              <div className="stat-value">{card.value}</div>
              <div className="stat-label">{card.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="filters-bar">
          <div className="search-bar" style={{ flex: 1, maxWidth: 400 }}>
            <Search />
            <input placeholder="Search by filename, account holder, bank..." value={search}
              onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="form-input" style={{ width: 'auto', minWidth: 140 }}
            value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">All Status</option>
            <option value="completed">Completed</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        {/* Table */}
        {loading ? (
          <div className="loading-overlay">
            <div className="spinner" />
            <span>Loading documents...</span>
          </div>
        ) : docs.length === 0 ? (
          <div className="empty-state">
            <FileText size={48} />
            <h3>No statements yet</h3>
            <p>Upload your first bank statement to get started.</p>
            <Link to="/upload" className="btn btn-primary" style={{ marginTop: 16 }}>
              <Upload size={14} /> Upload Statement
            </Link>
          </div>
        ) : (
          <div className="table-container animate-fade-in">
            <table>
              <thead>
                <tr>
                  <th>Statement</th>
                  <th>Bank</th>
                  <th>Account Holder</th>
                  <th>Uploaded</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {docs.map(doc => (
                  <tr key={doc.client_id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(232,114,42,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#e8722a', flexShrink: 0 }}>
                          <FileText size={16} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>{doc.filename}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{formatSize(doc.file_size)} • {doc.file_type.toUpperCase()}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-neutral">{bankLabels[doc.bank_name] || doc.bank_name || '—'}</span>
                    </td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{doc.account_holder_name || '—'}</td>
                    <td>
                      <div style={{ fontSize: 12 }}>{formatTime(doc.created_at)}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{timeAgo(doc.created_at)}</div>
                    </td>
                    <td>
                      <span className={`badge ${doc.status === 'completed' ? 'badge-success' : doc.status === 'processing' ? 'badge-warning' : doc.status === 'failed' ? 'badge-danger' : 'badge-neutral'}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {doc.status === 'completed' && (
                          <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/analysis/${doc.client_id}`)}>
                            <Eye size={14} /> View
                          </button>
                        )}
                        <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(doc.client_id)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
