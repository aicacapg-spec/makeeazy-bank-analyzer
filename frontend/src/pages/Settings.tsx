import { useState, useEffect } from 'react'
import { Key, ExternalLink, CheckCircle, XCircle, Loader2, Sparkles, Eye, EyeOff, Save, Trash2 } from 'lucide-react'
import { api } from '../api'

interface ApiStatus {
  groq: { configured: boolean; source: string; valid: boolean; key_preview: string }
  gemini: { configured: boolean; source: string; valid: boolean; key_preview: string }
}

export default function SettingsPage() {
  const [status, setStatus] = useState<ApiStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [groqKey, setGroqKey] = useState('')
  const [geminiKey, setGeminiKey] = useState('')
  const [showGroq, setShowGroq] = useState(false)
  const [showGemini, setShowGemini] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => { loadStatus() }, [])

  async function loadStatus() {
    setLoading(true)
    try {
      const s = await api.getApiStatus()
      setStatus(s)
    } catch { }
    setLoading(false)
  }

  async function handleSave(provider: 'groq' | 'gemini') {
    setSaving(true)
    setMessage(null)
    try {
      const keys = provider === 'groq'
        ? { groq_api_key: groqKey }
        : { gemini_api_key: geminiKey }
      await api.saveApiKey(keys)
      setMessage({ type: 'success', text: `${provider === 'groq' ? 'Groq' : 'Gemini'} API key saved and validated ✓` })
      if (provider === 'groq') setGroqKey('')
      else setGeminiKey('')
      await loadStatus()
    } catch (e: any) {
      setMessage({ type: 'error', text: e.message || 'Failed to save' })
    }
    setSaving(false)
  }

  async function handleClear(provider: 'groq' | 'gemini') {
    setSaving(true)
    setMessage(null)
    try {
      const keys = provider === 'groq'
        ? { groq_api_key: '' }
        : { gemini_api_key: '' }
      await api.saveApiKey(keys)
      setMessage({ type: 'success', text: `${provider === 'groq' ? 'Groq' : 'Gemini'} key cleared, using .env fallback` })
      await loadStatus()
    } catch (e: any) {
      setMessage({ type: 'error', text: e.message })
    }
    setSaving(false)
  }

  return (
    <>
      <div className="page-header">
        <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.5px' }}>
          <Key size={18} style={{ verticalAlign: -3, marginRight: 8, color: 'var(--accent-primary)' }} />
          API Settings
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
          Configure AI providers for enhanced bank statement analysis
        </p>
      </div>

      <div className="page-body">
        {/* Info Banner */}
        <div className="card" style={{ background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e3a5f 100%)', color: 'white', marginBottom: 24, border: 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 40, height: 40, borderRadius: 12, background: 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Sparkles size={20} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 700 }}>AI-Powered Analysis</div>
              <div style={{ fontSize: 12, opacity: 0.8, marginTop: 2 }}>
                Add your Groq API key to enable smart transaction categorization, financial insights, and accurate account detection. It's <strong>free</strong> to get a key.
              </div>
            </div>
          </div>
        </div>

        {/* Message */}
        {message && (
          <div style={{
            padding: '12px 16px', borderRadius: 8, marginBottom: 16,
            background: message.type === 'success' ? 'var(--success-bg)' : 'var(--danger-bg)',
            color: message.type === 'success' ? 'var(--success)' : 'var(--danger)',
            fontSize: 13, fontWeight: 500,
            border: `1px solid ${message.type === 'success' ? 'var(--success)' : 'var(--danger)'}20`
          }}>
            {message.type === 'success' ? <CheckCircle size={14} style={{ verticalAlign: -2, marginRight: 6 }} /> : <XCircle size={14} style={{ verticalAlign: -2, marginRight: 6 }} />}
            {message.text}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Groq Card */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>Groq API</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Primary AI provider • Fast inference</div>
              </div>
              {loading ? (
                <Loader2 size={16} className="spin" style={{ color: 'var(--text-muted)' }} />
              ) : status?.groq.configured ? (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 12,
                  background: status.groq.valid ? 'var(--success-bg)' : '#fef3c7',
                  color: status.groq.valid ? 'var(--success)' : '#d97706', fontSize: 11, fontWeight: 600
                }}>
                  {status.groq.valid ? <CheckCircle size={12} /> : <XCircle size={12} />}
                  {status.groq.valid ? 'Active' : 'Invalid'}
                </div>
              ) : (
                <div style={{ padding: '4px 10px', borderRadius: 12, background: '#fee2e2', color: '#dc2626', fontSize: 11, fontWeight: 600 }}>
                  Not Set
                </div>
              )}
            </div>

            {/* Current key preview */}
            {status?.groq.configured && (
              <div style={{ padding: '8px 12px', background: 'var(--bg-tertiary)', borderRadius: 6, marginBottom: 12, fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Current: </span>
                <code style={{ color: 'var(--text-secondary)' }}>{status.groq.key_preview}</code>
                <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>({status.groq.source})</span>
                {status.groq.source === 'user' && (
                  <button onClick={() => handleClear('groq')} style={{ marginLeft: 8, background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: 11 }}>
                    <Trash2 size={12} style={{ verticalAlign: -2 }} /> Clear
                  </button>
                )}
              </div>
            )}

            {/* Input */}
            <div style={{ position: 'relative', marginBottom: 12 }}>
              <input
                type={showGroq ? 'text' : 'password'}
                placeholder="gsk_..."
                value={groqKey}
                onChange={e => setGroqKey(e.target.value)}
                style={{
                  width: '100%', padding: '10px 40px 10px 12px', borderRadius: 8,
                  border: '1px solid var(--border-light)', background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)', fontSize: 13, outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
              <button onClick={() => setShowGroq(!showGroq)} style={{
                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer'
              }}>
                {showGroq ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => handleSave('groq')}
                disabled={!groqKey.trim() || saving}
                className="btn btn-primary"
                style={{ flex: 1, padding: '8px 16px', fontSize: 12, opacity: !groqKey.trim() ? 0.5 : 1 }}
              >
                {saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
                <span style={{ marginLeft: 6 }}>Save & Validate</span>
              </button>
              <a
                href="https://console.groq.com/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="btn"
                style={{
                  padding: '8px 16px', fontSize: 12, background: 'var(--bg-tertiary)',
                  color: 'var(--accent-primary)', border: '1px solid var(--border-light)',
                  textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4,
                  borderRadius: 8, cursor: 'pointer'
                }}
              >
                <ExternalLink size={12} /> Get Free Key
              </a>
            </div>
          </div>

          {/* Gemini Card */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>Gemini API</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Fallback provider • Google AI</div>
              </div>
              {loading ? (
                <Loader2 size={16} className="spin" style={{ color: 'var(--text-muted)' }} />
              ) : status?.gemini.configured ? (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 12,
                  background: status.gemini.valid ? 'var(--success-bg)' : '#fef3c7',
                  color: status.gemini.valid ? 'var(--success)' : '#d97706', fontSize: 11, fontWeight: 600
                }}>
                  {status.gemini.valid ? <CheckCircle size={12} /> : <XCircle size={12} />}
                  {status.gemini.valid ? 'Active' : 'Invalid'}
                </div>
              ) : (
                <div style={{ padding: '4px 10px', borderRadius: 12, background: '#fee2e2', color: '#dc2626', fontSize: 11, fontWeight: 600 }}>
                  Not Set
                </div>
              )}
            </div>

            {status?.gemini.configured && (
              <div style={{ padding: '8px 12px', background: 'var(--bg-tertiary)', borderRadius: 6, marginBottom: 12, fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Current: </span>
                <code style={{ color: 'var(--text-secondary)' }}>{status.gemini.key_preview}</code>
                <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>({status.gemini.source})</span>
                {status.gemini.source === 'user' && (
                  <button onClick={() => handleClear('gemini')} style={{ marginLeft: 8, background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: 11 }}>
                    <Trash2 size={12} style={{ verticalAlign: -2 }} /> Clear
                  </button>
                )}
              </div>
            )}

            <div style={{ position: 'relative', marginBottom: 12 }}>
              <input
                type={showGemini ? 'text' : 'password'}
                placeholder="AIza..."
                value={geminiKey}
                onChange={e => setGeminiKey(e.target.value)}
                style={{
                  width: '100%', padding: '10px 40px 10px 12px', borderRadius: 8,
                  border: '1px solid var(--border-light)', background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)', fontSize: 13, outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
              <button onClick={() => setShowGemini(!showGemini)} style={{
                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer'
              }}>
                {showGemini ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => handleSave('gemini')}
                disabled={!geminiKey.trim() || saving}
                className="btn btn-primary"
                style={{ flex: 1, padding: '8px 16px', fontSize: 12, opacity: !geminiKey.trim() ? 0.5 : 1 }}
              >
                {saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
                <span style={{ marginLeft: 6 }}>Save & Validate</span>
              </button>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="btn"
                style={{
                  padding: '8px 16px', fontSize: 12, background: 'var(--bg-tertiary)',
                  color: 'var(--accent-primary)', border: '1px solid var(--border-light)',
                  textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4,
                  borderRadius: 8, cursor: 'pointer'
                }}
              >
                <ExternalLink size={12} /> Get Free Key
              </a>
            </div>
          </div>
        </div>

        {/* How it works */}
        <div className="card" style={{ marginTop: 24 }}>
          <div className="card-title">How AI Enhancement Works</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginTop: 12 }}>
            <div style={{ textAlign: 'center', padding: 16 }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>🔍</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>Smart Detection</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                AI verifies bank name, account holder, and corrects any parsing errors
              </div>
            </div>
            <div style={{ textAlign: 'center', padding: 16 }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>📊</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>Categorization</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                Every transaction is categorized (salary, EMI, shopping, food, etc.) using AI
              </div>
            </div>
            <div style={{ textAlign: 'center', padding: 16 }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>💡</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>Financial Insights</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                Get AI-generated executive summary, risk flags, and recommendations
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
