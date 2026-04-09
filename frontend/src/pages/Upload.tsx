import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, FileText, Lock, CheckCircle, AlertCircle, Loader, Shield, BarChart3, Search, Settings, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../api'

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState<any>(null)
  const [dragOver, setDragOver] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [salaryKeywords, setSalaryKeywords] = useState('')
  const [emiKeywords, setEmiKeywords] = useState('')
  const [bankOverride, setBankOverride] = useState('')
  const [nameOverride, setNameOverride] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const handleFile = (f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase()
    const allowed = ['pdf', 'xlsx', 'xls', 'csv', 'txt']
    if (!ext || !allowed.includes(ext)) {
      setError(`Unsupported file type: .${ext}. Supported: ${allowed.join(', ')}`)
      return
    }
    if (f.size > 50 * 1024 * 1024) {
      setError('File too large. Maximum: 50MB')
      return
    }
    setFile(f)
    setError('')
    setSuccess(null)
    // Auto-show password field for PDFs
    if (ext === 'pdf') setShowPassword(true)
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0])
  }, [])

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError('')
    setProgress(10)

    const progressInterval = setInterval(() => {
      setProgress(p => Math.min(p + Math.random() * 15, 85))
    }, 500)

    try {
      const advancedOptions = showAdvanced ? {
        salary_keywords: salaryKeywords ? salaryKeywords.split(',').map(s => s.trim()).filter(Boolean) : undefined,
        emi_keywords: emiKeywords ? emiKeywords.split(',').map(s => s.trim()).filter(Boolean) : undefined,
        bank_override: bankOverride || undefined,
        name_override: nameOverride || undefined,
      } : undefined
      const result = await api.upload(file, password || undefined, advancedOptions)
      clearInterval(progressInterval)
      setProgress(100)
      setSuccess(result)
      setTimeout(() => {
        navigate(`/analysis/${result.client_id}`)
      }, 1500)
    } catch (err: any) {
      clearInterval(progressInterval)
      setProgress(0)
      setError(err.message || 'Upload failed. Please try again.')
    }
    setUploading(false)
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Upload Bank Statement</h2>
          <p>Upload a statement to analyze transactions, cash flow, and more</p>
        </div>
      </div>

      <div className="page-body">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 28, alignItems: 'start' }}>
          {/* Left: Upload Area */}
          <div className="animate-fade-in">
            {/* Drop Zone */}
            {!success ? (
              <>
                <div
                  className={`upload-zone ${dragOver ? 'dragover' : ''}`}
                  onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={onDrop}
                  onClick={() => inputRef.current?.click()}
                >
                  <input ref={inputRef} type="file" hidden
                    accept=".pdf,.xlsx,.xls,.csv,.txt"
                    onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />

                  <div className="upload-icon">
                    <Upload size={28} />
                  </div>

                  {file ? (
                    <>
                      <h3 style={{ color: 'var(--accent-primary-light)' }}>
                        <FileText size={18} style={{ display: 'inline', verticalAlign: -3, marginRight: 6 }} />
                        {file.name}
                      </h3>
                      <p>{(file.size / 1024).toFixed(1)} KB • {file.type || file.name.split('.').pop()?.toUpperCase()}</p>
                      <p style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 12 }}>Click or drag to change file</p>
                    </>
                  ) : (
                    <>
                      <h3>Drop your bank statement here</h3>
                      <p>or click to browse files</p>
                      <div className="file-types">
                        {['PDF', 'XLSX', 'XLS', 'CSV', 'TXT'].map(t => (
                          <span key={t} className="file-type-badge">.{t}</span>
                        ))}
                      </div>
                    </>
                  )}
                </div>

                {/* Password Field */}
                {showPassword && (
                  <div className="password-group animate-fade-in" style={{ marginTop: 16 }}>
                    <Lock size={18} className="lock-icon" />
                    <div style={{ flex: 1 }}>
                      <label className="form-label" style={{ marginBottom: 4 }}>PDF Password (if protected)</label>
                      <input className="form-input" type="password" placeholder="Enter password (e.g. DOB: 01011990)"
                        value={password} onChange={e => setPassword(e.target.value)} />
                    </div>
                  </div>
                )}

                {/* Advanced Options */}
                {file && !uploading && (
                  <div style={{ marginTop: 16 }} className="animate-fade-in">
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ width: '100%', justifyContent: 'space-between', padding: '10px 14px', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-sm)' }}
                      onClick={() => setShowAdvanced(!showAdvanced)}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Settings size={14} />
                        Advanced Options
                      </span>
                      {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    {showAdvanced && (
                      <div className="card animate-fade-in" style={{ marginTop: 8, padding: 16 }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                          <div>
                            <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>Override Bank Name</label>
                            <select className="form-input" value={bankOverride} onChange={e => setBankOverride(e.target.value)}
                              style={{ fontSize: 12, padding: '8px 10px' }}>
                              <option value="">Auto-detect</option>
                              <option value="sbi">State Bank of India</option>
                              <option value="hdfc">HDFC Bank</option>
                              <option value="icici">ICICI Bank</option>
                              <option value="axis">Axis Bank</option>
                              <option value="kotak">Kotak Mahindra Bank</option>
                              <option value="bob">Bank of Baroda</option>
                              <option value="pnb">Punjab National Bank</option>
                              <option value="canara">Canara Bank</option>
                              <option value="union">Union Bank</option>
                              <option value="yes_bank">Yes Bank</option>
                              <option value="idfc">IDFC First Bank</option>
                              <option value="indusind">IndusInd Bank</option>
                              <option value="federal">Federal Bank</option>
                            </select>
                          </div>
                          <div>
                            <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>Override Account Holder</label>
                            <input className="form-input" type="text" placeholder="e.g. JOHN DOE"
                              value={nameOverride} onChange={e => setNameOverride(e.target.value)}
                              style={{ fontSize: 12, padding: '8px 10px' }} />
                          </div>
                        </div>

                        <div style={{ marginBottom: 12 }}>
                          <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                            Custom Salary Keywords <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(comma separated)</span>
                          </label>
                          <input className="form-input" type="text"
                            placeholder="e.g. SALARY, WIPRO, INFOSYS, PAY, WAGES"
                            value={salaryKeywords} onChange={e => setSalaryKeywords(e.target.value)}
                            style={{ fontSize: 12, padding: '8px 10px' }} />
                          <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                            Add company names or keywords to improve salary detection accuracy
                          </p>
                        </div>

                        <div>
                          <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                            Custom EMI Keywords <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(comma separated)</span>
                          </label>
                          <input className="form-input" type="text"
                            placeholder="e.g. HDFC LTD, BAJAJ, HOME LOAN, CAR LOAN"
                            value={emiKeywords} onChange={e => setEmiKeywords(e.target.value)}
                            style={{ fontSize: 12, padding: '8px 10px' }} />
                          <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                            Add loan provider names to improve EMI/obligation detection
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Error */}
                {error && (
                  <div className="toast-error animate-fade-in" style={{ position: 'relative', top: 'auto', right: 'auto', marginTop: 16, borderRadius: 'var(--radius-sm)' }}>
                    <AlertCircle size={16} />
                    {error}
                  </div>
                )}

                {/* Upload Progress */}
                {uploading && (
                  <div style={{ marginTop: 20 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
                      <span><Loader size={14} style={{ display: 'inline', verticalAlign: -2, marginRight: 6, animation: 'spin 1s linear infinite' }} />Analyzing statement...</span>
                      <span>{Math.round(progress)}%</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${progress}%` }} />
                    </div>
                    <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                      Extracting transactions, categorizing, and running 25 analysis modules...
                    </p>
                  </div>
                )}

                {/* Upload Button */}
                <button className="btn btn-primary" style={{ marginTop: 20, width: '100%', justifyContent: 'center', padding: '14px 24px', fontSize: 14 }}
                  disabled={!file || uploading}
                  onClick={handleUpload}>
                  {uploading ? <><Loader size={16} style={{ animation: 'spin 1s linear infinite' }} /> Processing...</>
                    : <><Upload size={16} /> Analyze Statement</>}
                </button>
              </>
            ) : (
              /* Success State */
              <div className="card animate-fade-in" style={{ textAlign: 'center', padding: 48 }}>
                <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--success-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px', color: 'var(--success)' }}>
                  <CheckCircle size={32} />
                </div>
                <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Analysis Complete!</h3>
                <p style={{ color: 'var(--text-secondary)', marginBottom: 4 }}>{success.filename}</p>
                <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                  {success.transaction_count} transactions analyzed • Bank: {success.bank_name}
                </p>
                <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 16 }}>Redirecting to analysis...</p>
              </div>
            )}
          </div>

          {/* Right: Info Panels */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <InfoPanel icon={<BarChart3 size={18} />} title="What We Analyse"
              items={['Transaction Data & Categorization', 'Cash Flow & Monthly Metrics', 'Salary Detection & EMI Tracking', 'Suspicious & AML Signals', 'Health Score & Risk Assessment']} />
            <InfoPanel icon={<Search size={18} />} title="How It\'s Used"
              items={['Credit & Loan Assessment', 'Income Verification for ITR', 'Audit & Risk Management', 'Forensic Accounting', 'Client Advisory']} />
            <InfoPanel icon={<Shield size={18} />} title="Security & Privacy"
              items={['100% Local Processing', 'No Data Sent to Third Parties', 'Files Processed In-Memory', 'Self-Hosted Solution', 'Zero External API Calls']} />
          </div>
        </div>
      </div>
    </>
  )
}

function InfoPanel({ icon, title, items }: { icon: React.ReactNode; title: string; items: string[] }) {
  return (
    <div className="card" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, color: 'var(--accent-primary-light)' }}>
        {icon}
        <span style={{ fontSize: 13, fontWeight: 600 }}>{title}</span>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((item, i) => (
          <li key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent-primary)', flexShrink: 0 }} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
