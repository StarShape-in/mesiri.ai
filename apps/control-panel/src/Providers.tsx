import { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, RefreshCw, Cpu, ShieldAlert, Key } from 'lucide-react';
import { api } from './api';

interface Provider {
  id: string;
  name: string;
  model: string | null;
  configured: boolean;
  key_preview: string | null;
  source: string;
  base_url?: string | null;
}

interface CheckResult {
  ok: boolean;
  error: string | null;
  latency_ms: number | null;
}

interface CapabilityRouting {
  provider_id: string;
  model: string;
}

interface AIConfig {
  routing: Record<string, CapabilityRouting>;
  secrets: Record<string, { api_key: string | null; base_url: string | null }>;
}

export default function Providers() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, CheckResult>>({});

  // Routing Configuration State
  const [routing, setRouting] = useState<Record<string, CapabilityRouting>>({
    voice: { provider_id: 'sarvam', model: 'saaras:v2.5' },
    extraction: { provider_id: 'gemini', model: 'gemini-2.5-flash' },
    vision: { provider_id: 'gemini', model: 'gemini-2.5-flash' },
    translation: { provider_id: 'gemini', model: 'gemini-2.5-flash' },
  });

  const [secretsInput, setSecretsInput] = useState<Record<string, { api_key: string; base_url: string }>>({
    gemini: { api_key: '', base_url: '' },
    deepseek: { api_key: '', base_url: '' },
    sarvam: { api_key: '', base_url: '' },
  });

  const [customModels, setCustomModels] = useState<Record<string, string>>({
    voice: '',
    extraction: '',
    vision: '',
    translation: '',
  });

  const [isCustomModel, setIsCustomModel] = useState<Record<string, boolean>>({
    voice: false,
    extraction: false,
    vision: false,
    translation: false,
  });

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const fetchProvidersAndConfig = async () => {
    setLoading(true);
    try {
      // Fetch provider list status
      const providersRes = await api.get<Provider[]>('/admin/providers');
      setProviders(providersRes.data);

      // Fetch active routing and secrets configs
      const configRes = await api.get<AIConfig>('/admin/providers/config');
      const { routing: dbRouting, secrets: dbSecrets } = configRes.data;

      // Update routing state
      setRouting(dbRouting);

      // Update secrets input placeholders/values
      const newSecretsInput = { ...secretsInput };
      Object.keys(dbSecrets).forEach((pid) => {
        newSecretsInput[pid] = {
          api_key: dbSecrets[pid].api_key || '',
          base_url: dbSecrets[pid].base_url || '',
        };
      });
      setSecretsInput(newSecretsInput);

      // Detect if model is custom (not in predefined list)
      const predefined: Record<string, string[]> = {
        voice: ['saaras:v2.5'],
        extraction: ['gemini-2.5-flash', 'deepseek-chat'],
        vision: ['gemini-2.5-flash'],
        translation: ['gemini-2.5-flash'],
      };

      const newIsCustom: Record<string, boolean> = {};
      const newCustomModels: Record<string, string> = {};

      Object.keys(dbRouting).forEach((cap) => {
        const model = dbRouting[cap].model;
        const list = predefined[cap] || [];
        if (model && !list.includes(model) && model !== 'fake') {
          newIsCustom[cap] = true;
          newCustomModels[cap] = model;
        } else {
          newIsCustom[cap] = false;
          newCustomModels[cap] = '';
        }
      });
      setIsCustomModel(newIsCustom);
      setCustomModels(newCustomModels);

    } catch (err) {
      console.error('Failed to load configurations', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProvidersAndConfig();
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

  const handleRoutingChange = (capability: string, providerId: string) => {
    // Pick default model for selected provider
    let model = 'fake';
    if (providerId === 'gemini') model = 'gemini-2.5-flash';
    else if (providerId === 'deepseek') model = 'deepseek-chat';
    else if (providerId === 'sarvam') model = 'saaras:v2.5';

    setRouting((prev) => ({
      ...prev,
      [capability]: { provider_id: providerId, model },
    }));
    setIsCustomModel((prev) => ({ ...prev, [capability]: false }));
  };

  const handleModelChange = (capability: string, model: string) => {
    if (model === 'custom') {
      setIsCustomModel((prev) => ({ ...prev, [capability]: true }));
    } else {
      setIsCustomModel((prev) => ({ ...prev, [capability]: false }));
      setRouting((prev) => ({
        ...prev,
        [capability]: { ...prev[capability], model },
      }));
    }
  };

  const handleApplyConfig = (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    // Build payload
    const finalRouting = { ...routing };
    Object.keys(isCustomModel).forEach((cap) => {
      if (isCustomModel[cap]) {
        finalRouting[cap].model = customModels[cap];
      }
    });

    const payload = {
      routing: finalRouting,
      secrets: secretsInput,
    };

    api
      .put('/admin/providers/config', payload)
      .then(() => {
        setSaveSuccess(true);
        fetchProvidersAndConfig();
      })
      .catch((err) => {
        setSaveError(err.response?.data?.detail || 'Failed to apply configuration');
      })
      .finally(() => setSaving(false));
  };

  if (loading) {
    return <div style={{ color: 'var(--neutral-500)', padding: 'var(--space-8)' }}>Loading configurations…</div>;
  }

  return (
    <div className="animate-fade-in" style={{ maxWidth: '1000px', paddingBottom: 'var(--space-12)' }}>
      <header style={{ marginBottom: 'var(--space-6)' }}>
        <h1>AI Routing & Providers</h1>
        <p className="subtitle">Dynamically route AI capabilities to specific models and configure credentials.</p>
      </header>

      {saveSuccess && (
        <div style={{
          backgroundColor: 'rgba(126, 217, 87, 0.1)',
          border: '1px solid var(--primary)',
          color: 'var(--neutral-900)',
          padding: 'var(--space-4)',
          borderRadius: 'var(--radius-md)',
          marginBottom: 'var(--space-6)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)'
        }}>
          <CheckCircle2 size={20} style={{ color: 'var(--primary)' }} />
          <div>
            <strong style={{ fontWeight: 600 }}>Configuration deployed!</strong> Change was applied instantly and cached in Redis.
          </div>
        </div>
      )}

      {saveError && (
        <div style={{
          backgroundColor: 'var(--error-soft)',
          border: '1px solid var(--error)',
          color: 'var(--neutral-900)',
          padding: 'var(--space-4)',
          borderRadius: 'var(--radius-md)',
          marginBottom: 'var(--space-6)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)'
        }}>
          <ShieldAlert size={20} style={{ color: 'var(--error)' }} />
          <div>
            <strong style={{ fontWeight: 600 }}>Deployment failed:</strong> {saveError}
          </div>
        </div>
      )}

      <form onSubmit={handleApplyConfig}>
        {/* SECTION 1: AI ROUTING CONFIGURATION */}
        <section style={{ marginBottom: 'var(--space-8)' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Cpu size={20} /> AI Capability Routing
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--space-4)' }}>
            {/* Capability: Voice */}
            <div className="card" style={{ padding: 'var(--space-4)' }}>
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: 'var(--space-3)', color: 'var(--neutral-800)' }}>
                Voice / STT
              </div>
              <div className="form-group" style={{ marginBottom: 'var(--space-3)' }}>
                <label>Provider</label>
                <select
                  className="form-input"
                  value={routing.voice.provider_id}
                  onChange={(e) => handleRoutingChange('voice', e.target.value)}
                >
                  <option value="sarvam">Sarvam</option>
                  <option value="fake">Fake (Mock data)</option>
                </select>
              </div>

              {routing.voice.provider_id !== 'fake' && (
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label>Model</label>
                  <select
                    className="form-input"
                    value={isCustomModel.voice ? 'custom' : routing.voice.model}
                    onChange={(e) => handleModelChange('voice', e.target.value)}
                  >
                    <option value="saaras:v2.5">saaras:v2.5</option>
                    <option value="custom">Custom model...</option>
                  </select>
                  {isCustomModel.voice && (
                    <input
                      type="text"
                      className="form-input"
                      style={{ marginTop: 'var(--space-2)' }}
                      placeholder="e.g. saaras:v3"
                      value={customModels.voice}
                      onChange={(e) => setCustomModels({ ...customModels, voice: e.target.value })}
                      required
                    />
                  )}
                </div>
              )}
            </div>

            {/* Capability: Extraction */}
            <div className="card" style={{ padding: 'var(--space-4)' }}>
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: 'var(--space-3)', color: 'var(--neutral-800)' }}>
                Structured Extraction
              </div>
              <div className="form-group" style={{ marginBottom: 'var(--space-3)' }}>
                <label>Provider</label>
                <select
                  className="form-input"
                  value={routing.extraction.provider_id}
                  onChange={(e) => handleRoutingChange('extraction', e.target.value)}
                >
                  <option value="gemini">Gemini</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="fake">Fake (Mock data)</option>
                </select>
              </div>

              {routing.extraction.provider_id !== 'fake' && (
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label>Model</label>
                  <select
                    className="form-input"
                    value={isCustomModel.extraction ? 'custom' : routing.extraction.model}
                    onChange={(e) => handleModelChange('extraction', e.target.value)}
                  >
                    {routing.extraction.provider_id === 'gemini' && (
                      <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                    )}
                    {routing.extraction.provider_id === 'deepseek' && (
                      <option value="deepseek-chat">deepseek-chat</option>
                    )}
                    <option value="custom">Custom model...</option>
                  </select>
                  {isCustomModel.extraction && (
                    <input
                      type="text"
                      className="form-input"
                      style={{ marginTop: 'var(--space-2)' }}
                      placeholder="e.g. gemini-1.5-pro"
                      value={customModels.extraction}
                      onChange={(e) => setCustomModels({ ...customModels, extraction: e.target.value })}
                      required
                    />
                  )}
                </div>
              )}
            </div>

            {/* Capability: Vision */}
            <div className="card" style={{ padding: 'var(--space-4)' }}>
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: 'var(--space-3)', color: 'var(--neutral-800)' }}>
                Vision / Image Analysis
              </div>
              <div className="form-group" style={{ marginBottom: 'var(--space-3)' }}>
                <label>Provider</label>
                <select
                  className="form-input"
                  value={routing.vision.provider_id}
                  onChange={(e) => handleRoutingChange('vision', e.target.value)}
                >
                  <option value="gemini">Gemini</option>
                  <option value="fake">Fake (Mock data)</option>
                </select>
              </div>

              {routing.vision.provider_id !== 'fake' && (
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label>Model</label>
                  <select
                    className="form-input"
                    value={isCustomModel.vision ? 'custom' : routing.vision.model}
                    onChange={(e) => handleModelChange('vision', e.target.value)}
                  >
                    <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                    <option value="custom">Custom model...</option>
                  </select>
                  {isCustomModel.vision && (
                    <input
                      type="text"
                      className="form-input"
                      style={{ marginTop: 'var(--space-2)' }}
                      placeholder="e.g. gemini-1.5-pro"
                      value={customModels.vision}
                      onChange={(e) => setCustomModels({ ...customModels, vision: e.target.value })}
                      required
                    />
                  )}
                </div>
              )}
            </div>

            {/* Capability: Translation */}
            <div className="card" style={{ padding: 'var(--space-4)' }}>
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: 'var(--space-3)', color: 'var(--neutral-800)' }}>
                Translation
              </div>
              <div className="form-group" style={{ marginBottom: 'var(--space-3)' }}>
                <label>Provider</label>
                <select
                  className="form-input"
                  value={routing.translation.provider_id}
                  onChange={(e) => handleRoutingChange('translation', e.target.value)}
                >
                  <option value="gemini">Gemini</option>
                  <option value="fake">Fake (Mock data)</option>
                </select>
              </div>

              {routing.translation.provider_id !== 'fake' && (
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label>Model</label>
                  <select
                    className="form-input"
                    value={isCustomModel.translation ? 'custom' : routing.translation.model}
                    onChange={(e) => handleModelChange('translation', e.target.value)}
                  >
                    <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                    <option value="custom">Custom model...</option>
                  </select>
                  {isCustomModel.translation && (
                    <input
                      type="text"
                      className="form-input"
                      style={{ marginTop: 'var(--space-2)' }}
                      placeholder="e.g. gemini-1.5-pro"
                      value={customModels.translation}
                      onChange={(e) => setCustomModels({ ...customModels, translation: e.target.value })}
                      required
                    />
                  )}
                </div>
              )}
            </div>
          </div>
        </section>

        {/* SECTION 2: PROVIDER API KEYS */}
        <section style={{ marginBottom: 'var(--space-8)' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Key size={20} /> Provider API Credentials
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-6)' }}>
            {providers.map((p) => {
              const result = results[p.id];
              return (
                <div className="card" key={p.id}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
                    <div>
                      <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>{p.name}</h3>
                      <div style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: 4 }}>
                        Configured via: <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{p.source}</span>
                      </div>
                    </div>
                    <span className={`badge ${p.configured ? 'badge-info' : 'badge-warning'}`}>
                      {p.configured ? 'Active' : 'Not set'}
                    </span>
                  </div>

                  <div className="form-group" style={{ marginBottom: 'var(--space-3)' }}>
                    <label>API Key</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder={p.key_preview ? `${p.key_preview} (unchanged)` : 'Enter API Key'}
                      value={secretsInput[p.id]?.api_key || ''}
                      onChange={(e) => setSecretsInput({
                        ...secretsInput,
                        [p.id]: { ...secretsInput[p.id], api_key: e.target.value }
                      })}
                    />
                  </div>

                  {p.id === 'deepseek' && (
                    <div className="form-group" style={{ marginBottom: 'var(--space-4)' }}>
                      <label>API Base URL</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="https://api.deepseek.com"
                        value={secretsInput.deepseek?.base_url || ''}
                        onChange={(e) => setSecretsInput({
                          ...secretsInput,
                          deepseek: { ...secretsInput.deepseek, base_url: e.target.value }
                        })}
                      />
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-4)' }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={!p.configured || checking[p.id]}
                      onClick={() => runCheck(p.id)}
                      style={{ flex: 1 }}
                    >
                      {checking[p.id] ? (
                        <>
                          <RefreshCw size={14} className="spin" /> Checking…
                        </>
                      ) : (
                        'Test Health'
                      )}
                    </button>
                  </div>

                  {result && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                        fontSize: '13px',
                        color: result.ok ? 'var(--success)' : 'var(--error)',
                        marginTop: 'var(--space-3)'
                      }}
                    >
                      {result.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                      {result.ok
                        ? `Working (${result.latency_ms?.toFixed(0)} ms)`
                        : result.error || 'Health check failed'}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* SUBMIT FOOTER */}
        <div style={{
          borderTop: '1px solid var(--neutral-200)',
          paddingTop: 'var(--space-6)',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 'var(--space-4)'
        }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={fetchProvidersAndConfig}
            disabled={saving}
          >
            Reset
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={saving}
          >
            {saving ? 'Applying & Deploying...' : 'Apply & Deploy AI Routing'}
          </button>
        </div>
      </form>
    </div>
  );
}
