import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { RefreshCw, AlertCircle, MessageSquare, Send, FlaskConical, Cpu, Zap } from 'lucide-react';
import { api } from './api';
import { type Organization, type OrgUser, type SimulateResponse, ROUTED_VIA_LABELS } from './systemGraphShared';

const TestMessage = () => {
  const location = useLocation();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [orgId, setOrgId] = useState('');
  const [userId, setUserId] = useState('');
  const [testText, setTestText] = useState('');
  const [sending, setSending] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulateResponse | null>(null);

  useEffect(() => {
    api
      .get<Organization[]>('/admin/organizations')
      .then((res) => setOrgs(res.data))
      .catch(() => setOrgs([]));
  }, []);

  useEffect(() => {
    const prefill = (location.state as { prefill?: string } | null)?.prefill;
    if (prefill) {
      setTestText(prefill);
      setResult(null);
      setTestError(null);
    }
  }, [location.state]);

  useEffect(() => {
    if (!orgId) {
      setUsers([]);
      setUserId('');
      return;
    }
    api
      .get<OrgUser[]>(`/admin/organizations/${orgId}/users`)
      .then((res) => setUsers(res.data))
      .catch(() => setUsers([]));
  }, [orgId]);

  const sendTest = () => {
    if (!orgId || !userId || !testText.trim()) return;
    setSending(true);
    setTestError(null);
    setResult(null);
    api
      .post<SimulateResponse>('/admin/system-graph/simulate', {
        organization_id: orgId,
        user_id: userId,
        text: testText,
      })
      .then((res) => setResult(res.data))
      .catch((err) => setTestError(err.response?.data?.detail || 'Simulation failed'))
      .finally(() => setSending(false));
  };

  const selectedUser = users.find((u) => u.id === userId);
  const canSend = !!orgId && !!userId && !!selectedUser?.whatsapp_number && !!testText.trim() && !sending;

  return (
    <div className="animate-fade-in" style={{ maxWidth: '1100px' }}>
      <header style={{ marginBottom: 'var(--space-6)' }}>
        <h1>Send a test message</h1>
        <p className="subtitle">
          Runs the real AI pipeline as the chosen user and shows the reply. Test mode — the reply is captured, not sent to WhatsApp, and nothing is saved.
        </p>
      </header>

      <div id="test-panel" className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
          <FlaskConical size={18} style={{ color: 'var(--primary)' }} />
          <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>Message details</h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
          <div className="form-group">
            <label>Organization</label>
            <select className="form-input" value={orgId} onChange={(e) => setOrgId(e.target.value)}>
              <option value="">Select organization…</option>
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Run as user</label>
            <select className="form-input" value={userId} onChange={(e) => setUserId(e.target.value)} disabled={!orgId}>
              <option value="">Select user…</option>
              {users.map((u) => (
                <option key={u.id} value={u.id} disabled={!u.whatsapp_number}>
                  {(u.full_name || u.email || u.id) + (u.whatsapp_number ? '' : ' (no WhatsApp number)')}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label>Message</label>
          <textarea
            className="form-input"
            rows={2}
            placeholder='e.g. "50 bags of cement arrived"'
            value={testText}
            onChange={(e) => setTestText(e.target.value)}
          />
        </div>

        <button className="btn-primary" onClick={sendTest} disabled={!canSend}>
          {sending ? <RefreshCw size={16} className="spin" /> : <Send size={16} />} {sending ? 'Running…' : 'Send test'}
        </button>

        {testError && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--danger, #d33)', marginTop: 'var(--space-4)', fontSize: '13px' }}>
            <AlertCircle size={16} /> {testError}
          </div>
        )}

        {result && (
          <div style={{ marginTop: 'var(--space-5)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)', flexWrap: 'wrap' }}>
              <MessageSquare size={15} style={{ color: 'var(--primary)' }} />
              <span style={{ fontWeight: 600, fontSize: '13px' }}>Assistant reply</span>
              <span
                className={`badge ${result.routed_via === 'ai_pipeline' ? 'badge-info' : 'badge-success'}`}
                style={{ fontSize: '10px' }}
              >
                {result.routed_via === 'ai_pipeline' ? <Cpu size={11} style={{ marginRight: 4 }} /> : <Zap size={11} style={{ marginRight: 4 }} />}
                {ROUTED_VIA_LABELS[result.routed_via] || result.routed_via}
              </span>
            </div>
            {result.replies.length ? (
              result.replies.map((r, i) => (
                <div key={i} style={{ whiteSpace: 'pre-wrap', background: 'var(--neutral-50, #fafafa)', border: '1px solid var(--neutral-200, #e5e5e5)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-3)', fontSize: '13px', marginBottom: '8px' }}>
                  {r}
                </div>
              ))
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--neutral-500)' }}>(no reply produced)</div>
            )}

            {result.routed_via !== 'ai_pipeline' ? (
              <div style={{ marginTop: 'var(--space-4)', fontSize: '12px', color: 'var(--neutral-500)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Zap size={13} /> Deterministic reply — no AI model was involved, zero cost.
              </div>
            ) : (
            <div style={{ marginTop: 'var(--space-4)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                <Cpu size={14} style={{ color: 'var(--neutral-500)' }} />
                <span style={{ fontWeight: 600, fontSize: '13px' }}>AI providers used</span>
              </div>
              {(() => {
                const executions = result.understanding?.provider_executions ?? [];
                if (executions.length === 0) {
                  return <div style={{ fontSize: '12px', color: 'var(--neutral-500)', fontStyle: 'italic' }}>No AI provider calls executed.</div>;
                }
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', background: 'var(--neutral-50, #fafafa)', border: '1px solid var(--neutral-200, #e5e5e5)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-3)' }}>
                    {executions.map((p, i) => (
                      <div
                        key={i}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          borderBottom: i < executions.length - 1 ? '1px solid var(--neutral-200, #e5e5e5)' : 'none',
                          paddingBottom: i < executions.length - 1 ? 'var(--space-2)' : 0,
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--neutral-800, #333)' }}>{p.provider}</span>
                            <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>({p.operation})</span>
                          </div>
                          {p.model && (
                            <div style={{ fontSize: '11px', color: 'var(--neutral-500)', marginTop: '2px', fontFamily: 'monospace' }}>{p.model}</div>
                          )}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                          <span className={`badge ${p.succeeded ? 'badge-success' : 'badge-error'}`} style={{ fontSize: '10px', padding: '1px 6px' }}>
                            {p.succeeded ? 'Success' : p.error_code || 'Fail'}
                          </span>
                          {p.latency_ms !== null && (
                            <span style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--neutral-500)' }}>{p.latency_ms.toFixed(0)}ms</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
            )}

            {result.routed_via === 'ai_pipeline' && (
              <details style={{ marginTop: 'var(--space-3)' }}>
                <summary style={{ cursor: 'pointer', fontSize: '13px', fontWeight: 500, color: 'var(--neutral-600)' }}>How it was routed</summary>
                <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 12px', margin: '10px 0 0', fontSize: '13px' }}>
                  <dt style={{ color: 'var(--neutral-500)' }}>Understood as</dt>
                  <dd style={{ margin: 0, fontFamily: 'monospace' }}>{result.understanding?.semantic_type || '—'}</dd>
                  <dt style={{ color: 'var(--neutral-500)' }}>Canonical event</dt>
                  <dd style={{ margin: 0, fontFamily: 'monospace' }}>{result.canonical_event?.event_type || '—'}</dd>
                  <dt style={{ color: 'var(--neutral-500)' }}>Planner decision</dt>
                  <dd style={{ margin: 0, fontFamily: 'monospace' }}>{result.planner_decision?.decision_type || '—'}</dd>
                  <dt style={{ color: 'var(--neutral-500)' }}>Workflow</dt>
                  <dd style={{ margin: 0, fontFamily: 'monospace' }}>
                    {result.workflow_run ? `${result.workflow_run.workflow_key} (${result.workflow_run.status})` : '—'}
                  </dd>
                </dl>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TestMessage;
