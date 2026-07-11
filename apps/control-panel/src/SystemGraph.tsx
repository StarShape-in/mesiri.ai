import { useCallback, useEffect, useId, useRef, useState } from 'react';
import {
  RefreshCw,
  GitBranch,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Play,
  MessageSquare,
  CheckCircle2,
  Circle,
  Send,
  FlaskConical,
  Cpu,
} from 'lucide-react';
import mermaid from 'mermaid';
import { api } from './api';

interface StageNode {
  id: string;
  label: string;
  description: string | null;
}
interface PipelineStage {
  key: string;
  title: string;
  summary: string;
  nodes: StageNode[];
}
interface WorkflowGraphInfo {
  workflow_key: string;
  title: string;
  implemented: boolean;
  canonical_event: string | null;
  semantic_type: string | null;
  required_fields: string[];
  required_field_labels: string[];
  node_names: string[];
  example_messages: string[];
  mermaid: string | null;
}
interface SystemGraphResponse {
  mermaid: string;
  stages: PipelineStage[];
  workflows: WorkflowGraphInfo[];
}

interface Organization {
  id: string;
  name: string;
}
interface OrgUser {
  id: string;
  full_name: string | null;
  email: string | null;
  role: string | null;
  whatsapp_number: string | null;
}
interface ProviderExecution {
  provider: string;
  operation: string;
  model: string | null;
  latency_ms: number | null;
  succeeded: boolean;
  error_code: string | null;
}
interface SimulateResponse {
  dry_run: boolean;
  ran_as_wa_id: string;
  replies: string[];
  understanding: {
    semantic_type?: string;
    transcript?: string;
    translated_text?: string;
    provider_executions?: ProviderExecution[];
  } | null;
  resolved_context: unknown | null;
  canonical_event: { event_type?: string } | null;
  planner_decision: { decision_type?: string; workflow_key?: string } | null;
  workflow_run: { status?: string; workflow_key?: string } | null;
}

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'strict',
  flowchart: { curve: 'basis', htmlLabels: true },
});

/** Renders one Mermaid source string into an <svg>, showing parse errors inline. */
function MermaidDiagram({ source }: { source: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rawId = useId();
  const id = `mmd-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    mermaid
      .render(id, source)
      .then(({ svg }) => {
        if (!cancelled && containerRef.current) containerRef.current.innerHTML = svg;
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || 'Failed to render diagram');
      });
    return () => {
      cancelled = true;
    };
  }, [id, source]);

  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--danger, #d33)', fontSize: '13px' }}>
        <AlertCircle size={14} /> {error}
      </div>
    );
  }
  return <div ref={containerRef} style={{ overflowX: 'auto' }} />;
}

const chipStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '4px 10px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--neutral-200, #e5e5e5)',
  background: 'var(--neutral-50, #fafafa)',
  fontSize: '12px',
  cursor: 'pointer',
  color: 'var(--neutral-700, #444)',
};

const SystemGraph = () => {
  const [data, setData] = useState<SystemGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [showMap, setShowMap] = useState(false);

  // --- Test harness state ---
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [orgId, setOrgId] = useState('');
  const [userId, setUserId] = useState('');
  const [testText, setTestText] = useState('');
  const [sending, setSending] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulateResponse | null>(null);

  const fetchGraph = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .get<SystemGraphResponse>('/admin/system-graph')
      .then((res) => setData({ ...res.data, stages: res.data.stages ?? [], workflows: res.data.workflows ?? [] }))
      .catch((err) => setError(err.response?.data?.detail || 'Failed to load system graph'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchGraph();
    api
      .get<Organization[]>('/admin/organizations')
      .then((res) => setOrgs(res.data))
      .catch(() => setOrgs([]));
  }, [fetchGraph]);

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

  const toggle = (key: string) => setExpanded((e) => ({ ...e, [key]: !e[key] }));

  const tryExample = (msg: string) => {
    setTestText(msg);
    setResult(null);
    setTestError(null);
    document.getElementById('test-panel')?.scrollIntoView({ behavior: 'smooth' });
  };

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
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 'var(--space-6)' }}>
        <div>
          <h1>System Graph</h1>
          <p className="subtitle">
            How the WhatsApp assistant reacts to every message — generated live from the routing tables, and testable end-to-end.
          </p>
        </div>
        <button className="btn-secondary" onClick={fetchGraph} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : undefined} /> Refresh
        </button>
      </header>

      {error && (
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--danger, #d33)', marginBottom: 'var(--space-6)' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {loading && !data ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>Loading live system map…</div>
      ) : data ? (
        <>
          {/* --- Pipeline stages --- */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
            {data.stages.map((stage) => (
              <div key={stage.key} className="card">
                <h2 style={{ fontSize: '15px', fontWeight: 600, margin: 0, marginBottom: 'var(--space-2)' }}>{stage.title}</h2>
                <p style={{ fontSize: '12px', color: 'var(--neutral-500)', margin: 0, marginBottom: 'var(--space-3)' }}>{stage.summary}</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {stage.nodes.map((n) => (
                    <div key={n.id} style={{ fontSize: '12px' }}>
                      <span style={{ fontWeight: 500, color: 'var(--neutral-800, #333)' }}>{n.label}</span>
                      {n.description && <span style={{ color: 'var(--neutral-500)' }}> — {n.description}</span>}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* --- Overview diagram (collapsible) --- */}
          <div className="card" style={{ marginBottom: 'var(--space-8)' }}>
            <button
              onClick={() => setShowMap((s) => !s)}
              style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '15px', fontWeight: 600, padding: 0, color: 'var(--neutral-900)' }}
            >
              {showMap ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
              <GitBranch size={16} style={{ color: 'var(--primary)' }} /> Full pipeline diagram
            </button>
            {showMap && (
              <div style={{ marginTop: 'var(--space-4)' }}>
                <MermaidDiagram source={data.mermaid} />
              </div>
            )}
          </div>

          {/* --- Workflows --- */}
          <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: 'var(--space-4)' }}>Workflows</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 'var(--space-5)', marginBottom: 'var(--space-10)' }}>
            {data.workflows.map((wf) => {
              const open = !!expanded[wf.workflow_key];
              return (
                <div key={wf.workflow_key} className="card">
                  <div
                    onClick={() => toggle(wf.workflow_key)}
                    style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--neutral-900)' }}>{wf.title}</div>
                        <div style={{ fontFamily: 'monospace', fontSize: '11px', color: 'var(--neutral-500)' }}>{wf.workflow_key}</div>
                      </div>
                    </div>
                    <span className={`badge ${wf.implemented ? 'badge-success' : 'badge-warning'}`}>
                      {wf.implemented ? <CheckCircle2 size={12} style={{ marginRight: 4 }} /> : <Circle size={12} style={{ marginRight: 4 }} />}
                      {wf.implemented ? 'Built' : 'Not built yet'}
                    </span>
                  </div>

                  {/* Example chips are always visible — the most useful bit */}
                  {wf.example_messages.length > 0 && (
                    <div style={{ marginTop: 'var(--space-3)', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {wf.example_messages.map((msg) => (
                        <span
                          key={msg}
                          style={chipStyle}
                          onClick={(e) => {
                            e.stopPropagation();
                            tryExample(msg);
                          }}
                          title="Load into the test panel"
                        >
                          <Play size={11} /> {msg}
                        </span>
                      ))}
                    </div>
                  )}

                  {open && (
                    <div style={{ marginTop: 'var(--space-4)', borderTop: '1px solid var(--neutral-100, #eee)', paddingTop: 'var(--space-4)', fontSize: '13px' }}>
                      <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 12px', margin: 0 }}>
                        <dt style={{ color: 'var(--neutral-500)' }}>Canonical event</dt>
                        <dd style={{ margin: 0, fontFamily: 'monospace' }}>{wf.canonical_event || '—'}</dd>
                        <dt style={{ color: 'var(--neutral-500)' }}>Semantic type</dt>
                        <dd style={{ margin: 0, fontFamily: 'monospace' }}>{wf.semantic_type || '—'}</dd>
                        <dt style={{ color: 'var(--neutral-500)' }}>Required fields</dt>
                        <dd style={{ margin: 0 }}>{wf.required_field_labels.length ? wf.required_field_labels.join(', ') : 'none'}</dd>
                        {wf.node_names.length > 0 && (
                          <>
                            <dt style={{ color: 'var(--neutral-500)' }}>Graph nodes</dt>
                            <dd style={{ margin: 0, fontFamily: 'monospace' }}>{wf.node_names.join(' → ')}</dd>
                          </>
                        )}
                      </dl>
                      {wf.mermaid && (
                        <div style={{ marginTop: 'var(--space-3)' }}>
                          <MermaidDiagram source={wf.mermaid} />
                        </div>
                      )}
                      {!wf.implemented && (
                        <p style={{ color: 'var(--neutral-500)', marginTop: 'var(--space-3)', marginBottom: 0 }}>
                          This intent is understood but routes to a "not supported yet" reply until the workflow is added.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* --- Test harness --- */}
          <div id="test-panel" className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
              <FlaskConical size={18} style={{ color: 'var(--primary)' }} />
              <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>Send a test message</h2>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: 0, marginBottom: 'var(--space-4)' }}>
              Runs the real AI pipeline as the chosen user and shows the reply. Test mode — the reply is captured, not sent to WhatsApp, and nothing is saved.
            </p>

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
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                  <MessageSquare size={15} style={{ color: 'var(--primary)' }} />
                  <span style={{ fontWeight: 600, fontSize: '13px' }}>Assistant reply</span>
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
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
};

export default SystemGraph;
