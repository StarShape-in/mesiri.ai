import { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, RefreshCw, Cpu } from 'lucide-react';
import { api } from './api';

interface Provider {
  id: string;
  name: string;
  model: string | null;
  configured: boolean;
  key_preview: string | null;
}

interface CheckResult {
  ok: boolean;
  error: string | null;
  latency_ms: number | null;
}

export default function Providers() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, CheckResult>>({});

  const fetchProviders = () => {
    setLoading(true);
    api
      .get<Provider[]>('/admin/providers')
      .then((res) => setProviders(res.data))
      .catch((err) => console.error('Failed to fetch providers', err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  const runCheck = (id: string) => {
    setChecking((prev) => ({ ...prev, [id]: true }));
    api
      .post<CheckResult>(`/admin/providers/${id}/check`)
      .then((res) => setResults((prev) => ({ ...prev, [id]: res.data })))
      .catch((err) =>
        setResults((prev) => ({
          ...prev,
          [id]: { ok: false, error: err.response?.data?.detail || 'Check failed', latency_ms: null },
        }))
      )
      .finally(() => setChecking((prev) => ({ ...prev, [id]: false })));
  };

  return (
    <div className="animate-fade-in" style={{ maxWidth: '900px' }}>
      <header style={{ marginBottom: 'var(--space-6)' }}>
        <h1>AI Providers</h1>
        <p className="subtitle">API keys used by the WhatsApp assistant, and whether they're working right now.</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 'var(--space-4)' }}>
        {loading ? (
          <div style={{ color: 'var(--neutral-500)' }}>Loading providers…</div>
        ) : (
          providers.map((p) => {
            const result = results[p.id];
            return (
              <div className="card" key={p.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <Cpu size={16} />
                      <h2 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>{p.name}</h2>
                    </div>
                    {p.model && (
                      <div style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: 4 }}>{p.model}</div>
                    )}
                  </div>
                  <span className={`badge ${p.configured ? 'badge-info' : 'badge-warning'}`}>
                    {p.configured ? 'Configured' : 'Not set'}
                  </span>
                </div>

                <div
                  style={{
                    fontFamily: 'monospace',
                    fontSize: '13px',
                    color: 'var(--neutral-600)',
                    backgroundColor: 'var(--neutral-50)',
                    padding: 'var(--space-2)',
                    borderRadius: 'var(--radius-sm)',
                    marginBottom: 'var(--space-3)',
                  }}
                >
                  {p.key_preview ?? 'no key configured'}
                </div>

                <button
                  className="btn-secondary"
                  disabled={!p.configured || checking[p.id]}
                  onClick={() => runCheck(p.id)}
                  style={{ width: '100%', marginBottom: result ? 'var(--space-3)' : 0 }}
                >
                  {checking[p.id] ? (
                    <>
                      <RefreshCw size={14} className="spin" /> Checking…
                    </>
                  ) : (
                    'Check now'
                  )}
                </button>

                {result && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-2)',
                      fontSize: '13px',
                      color: result.ok ? 'var(--success)' : 'var(--error)',
                    }}
                  >
                    {result.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                    {result.ok
                      ? `Working (${result.latency_ms?.toFixed(0)} ms)`
                      : result.error || 'Not working'}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
