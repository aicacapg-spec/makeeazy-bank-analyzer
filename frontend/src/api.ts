const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

export const api = {
  async upload(file: File, password?: string, advancedOptions?: any) {
    const formData = new FormData();
    formData.append('file', file);
    if (password) formData.append('password', password);
    if (advancedOptions) formData.append('advanced_options', JSON.stringify(advancedOptions));
    const res = await fetch(`${API_BASE}/api/v1/upload`, { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async getDocuments(params?: { status?: string; search?: string }) {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.search) qs.set('search', params.search);
    const res = await fetch(`${API_BASE}/api/v1/documents?${qs}`);
    return res.json();
  },

  async getDocument(clientId: string) {
    const res = await fetch(`${API_BASE}/api/v1/documents/${clientId}`);
    return res.json();
  },

  async deleteDocument(clientId: string) {
    const res = await fetch(`${API_BASE}/api/v1/documents/${clientId}`, { method: 'DELETE' });
    return res.json();
  },

  async getStatementResult(clientId: string) {
    const res = await fetch(`${API_BASE}/api/v1/statement-result/${clientId}`);
    return res.json();
  },

  async getAnalysisJson(clientId: string) {
    const res = await fetch(`${API_BASE}/api/v1/analysis-json/${clientId}`);
    return res.json();
  },

  async getSupportedBanks() {
    const res = await fetch(`${API_BASE}/api/v1/supported-banks`);
    return res.json();
  },

  async getApiStatus() {
    const res = await fetch(`${API_BASE}/api/v1/settings/api-status`);
    return res.json();
  },

  async saveApiKey(keys: { groq_api_key?: string; gemini_api_key?: string }) {
    const res = await fetch(`${API_BASE}/api/v1/settings/save-api-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(keys),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Save failed' }));
      throw new Error(err.detail || 'Save failed');
    }
    return res.json();
  },

  async reanalyzeWithAI(clientId: string) {
    const res = await fetch(`${API_BASE}/api/v1/settings/reanalyze-ai/${clientId}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Re-analysis failed' }));
      throw new Error(err.detail || 'Re-analysis failed');
    }
    return res.json();
  },
};
