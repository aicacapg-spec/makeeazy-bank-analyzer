import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, Eye, Trash2, Search, RefreshCw, Clock } from 'lucide-react'
import { api } from '../api'

export default function HistoryPage() {
  const [docs, setDocs] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.getDocuments({ search })
      setDocs(data.documents || [])
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [search])

  const handleDelete = async (clientId: string) => {
    if (!confirm('Delete this document and its analysis?')) return
    await api.deleteDocument(clientId)
    load()
  }

  const formatDate = (iso: string) => new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  const formatSize = (b: number) => b < 1048576 ? (b / 1024).toFixed(1) + ' KB' : (b / 1048576).toFixed(1) + ' MB'

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Upload History</h2>
          <p>View all previously uploaded and analyzed statements</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCw size={14} /> Refresh</button>
      </div>
      <div className="page-body">
        <div className="filters-bar">
          <div className="search-bar" style={{ flex: 1, maxWidth: 500 }}>
            <Search />
            <input placeholder="Search statements..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>

        {loading ? (
          <div className="loading-overlay"><div className="spinner" /><span>Loading...</span></div>
        ) : docs.length === 0 ? (
          <div className="empty-state">
            <Clock size={48} />
            <h3>No history yet</h3>
            <p>Uploaded statements will appear here.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 12 }}>
            {docs.map(doc => (
              <div key={doc.client_id} className="card animate-fade-in" style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px', cursor: doc.status === 'completed' ? 'pointer' : 'default' }}
                onClick={() => doc.status === 'completed' && navigate(`/analysis/${doc.client_id}`)}>
                <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(99,102,241,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-primary)', flexShrink: 0 }}>
                  <FileText size={20} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14 }}>{doc.filename}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 2 }}>
                    <span>{formatSize(doc.file_size)}</span>
                    {doc.bank_name && <span>• {doc.bank_name.toUpperCase()}</span>}
                    {doc.account_holder_name && <span>• {doc.account_holder_name}</span>}
                    <span>• {formatDate(doc.created_at)}</span>
                  </div>
                </div>
                <span className={`badge ${doc.status === 'completed' ? 'badge-success' : doc.status === 'processing' ? 'badge-warning' : 'badge-danger'}`}>
                  {doc.status}
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  {doc.status === 'completed' && (
                    <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); navigate(`/analysis/${doc.client_id}`) }}>
                      <Eye size={14} />
                    </button>
                  )}
                  <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); handleDelete(doc.client_id) }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
