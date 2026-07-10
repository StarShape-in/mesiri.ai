import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw, ChevronDown, ChevronRight, Check, RotateCcw, Code, Cpu, MessageSquare, Bot } from 'lucide-react';
import { api } from './api';

interface InboundMessageSummary {
  id: string;
  correlation_id: string;
  sender_wa_id: string;
  message_type: string;
  body_preview: string;
  processing_status: string;
  error_code: string | null;
  received_at: string;
  processed_at: string | null;
  assistant_reply: string | null;
}

interface InboundMessageList {
  items: InboundMessageSummary[];
  total: number | null;
}

interface InboundMessageDetail {
  id: string;
  correlation_id: string;
  sender_wa_id: string;
  message_type: string;
  body_text: string | null;
  raw_payload: any;
  normalized_message: any;
  media_object_key: string | null;
  processing_status: string;
  error_code: string | null;
  received_at: string;
  processed_at: string | null;
  raw_payload_captured: boolean;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  retry_of_id: string | null;
  assistant_reply: string | null;
}

interface ProviderExecutionEntry {
  stage: string;
  provider: string;
  operation: string;
  model: string | null;
  latency_ms: number | null;
  succeeded: boolean;
  error_code: string | null;
  created_at: string;
}

interface JourneyTraceEntry {
  stage: string;
  succeeded: boolean;
  duration_ms: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
}

const POLL_INTERVAL_MS = 5000;
const MAX_ROWS = 200;

// Known WhatsApp numbers used for testing the assistant, offered as a quick
// filter so you don't have to retype them. wa_id has no "+" or spaces.
const KNOWN_NUMBERS = [{ label: '+91 8904034938', wa_id: '918904034938' }];

const statusBadgeClass = (status: string) => {
  if (status === 'completed') return 'badge-success';
  if (status === 'failed') return 'badge-error';
  return 'badge-warning'; // pending
};

const TracePanel = ({ correlationId }: { correlationId: string }) => {
  const [trace, setTrace] = useState<JourneyTraceEntry[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<JourneyTraceEntry[]>(`/admin/logs/messages/${correlationId}/trace`)
      .then((res) => {
        if (!cancelled) setTrace(res.data);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [correlationId]);

  if (loading) return <div style={{ padding: 'var(--space-4)', color: 'var(--neutral-500)' }}>Loading trace…</div>;
  if (!trace || trace.length === 0) {
    return <div style={{ padding: 'var(--space-4)', color: 'var(--neutral-500)' }}>No pipeline trace recorded for this message.</div>;
  }

  return (
    <div style={{ padding: 'var(--space-4)', backgroundColor: 'var(--neutral-50)' }}>
      {trace.map((entry, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 'var(--space-3)',
            padding: 'var(--space-2) 0',
            borderBottom: i < trace.length - 1 ? '1px solid var(--neutral-200)' : 'none',
          }}
        >
          <span>{entry.succeeded ? '✅' : '❌'}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 500, fontSize: '13px' }}>{entry.stage}</div>
            {entry.error_message && (
              <div style={{ fontSize: '12px', color: 'var(--error)' }}>
                {entry.error_code}: {entry.error_message}
              </div>
            )}
          </div>
          {entry.duration_ms !== null && (
            <span style={{ fontSize: '12px', color: 'var(--neutral-500)', fontFamily: 'monospace' }}>
              {entry.duration_ms}ms
            </span>
          )}
        </div>
      ))}
    </div>
  );
};

const LogDetailPanel = ({
  message,
  onUpdate,
}: {
  message: InboundMessageSummary;
  onUpdate: () => void;
}) => {
  const [detail, setDetail] = useState<InboundMessageDetail | null>(null);
  const [providers, setProviders] = useState<ProviderExecutionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showPayload, setShowPayload] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchDetails = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get<InboundMessageDetail>(`/admin/logs/messages/${message.id}`),
      api.get<ProviderExecutionEntry[]>(`/admin/logs/messages/${message.correlation_id}/providers`),
    ])
      .then(([detailRes, providersRes]) => {
        setDetail(detailRes.data);
        setProviders(providersRes.data);
      })
      .catch((err) => {
        console.error('Failed to fetch message details', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [message.id, message.correlation_id]);

  useEffect(() => {
    fetchDetails();
  }, [fetchDetails]);

  const handleAcknowledge = () => {
    setActionLoading(true);
    api
      .post(`/admin/logs/messages/${message.id}/acknowledge`)
      .then(() => {
        fetchDetails();
        onUpdate();
      })
      .catch((err) => {
        alert(err.response?.data?.detail || 'Failed to acknowledge message');
      })
      .finally(() => {
        setActionLoading(false);
      });
  };

  const handleRetry = () => {
    setActionLoading(true);
    api
      .post(`/admin/logs/messages/${message.id}/retry`)
      .then((res) => {
        alert(`Retry triggered! New Correlation ID: ${res.data.correlation_id}`);
        fetchDetails();
        onUpdate();
      })
      .catch((err) => {
        alert(err.response?.data?.detail || 'Failed to retry message');
      })
      .finally(() => {
        setActionLoading(false);
      });
  };

  if (loading) {
    return <div style={{ padding: 'var(--space-4)', color: 'var(--neutral-500)' }}>Loading details…</div>;
  }

  if (!detail) {
    return <div style={{ padding: 'var(--space-4)', color: 'var(--neutral-500)' }}>Failed to load message details.</div>;
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 'var(--space-6)', padding: 'var(--space-5)', backgroundColor: 'var(--neutral-50)', borderBottom: '1px solid var(--neutral-200)' }}>
      {/* Left column - Content */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        
        {/* Inbound Message */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)', padding: 'var(--space-4)', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', marginBottom: 'var(--space-3)' }}>
            <MessageSquare size={13} />
            Inbound Message ({detail.message_type})
            {detail.normalized_message?.sender?.profile_name && (
              <span style={{ marginLeft: 'auto', textTransform: 'none', color: 'var(--neutral-400)', fontWeight: 500 }}>
                Sent by: {detail.normalized_message.sender.profile_name}
              </span>
            )}
          </div>
          <div style={{ fontSize: '13px', color: 'var(--neutral-800)', whiteSpace: 'pre-wrap', fontFamily: 'var(--font-sans)', lineHeight: '1.6' }}>
            {detail.body_text || <em style={{ color: 'var(--neutral-400)' }}>no text content</em>}
          </div>
        </div>

        {/* Assistant Reply */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)', padding: 'var(--space-4)', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', marginBottom: 'var(--space-3)' }}>
            <Bot size={13} />
            Assistant Reply
          </div>
          <div style={{ fontSize: '13px', color: 'var(--neutral-800)', whiteSpace: 'pre-wrap', fontFamily: 'var(--font-sans)', lineHeight: '1.6' }}>
            {detail.assistant_reply || <em style={{ color: 'var(--neutral-400)' }}>no reply sent or pending</em>}
          </div>
        </div>

        {/* Raw Payload Section */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)', overflow: 'hidden' }}>
          <button 
            type="button"
            onClick={() => setShowPayload(!showPayload)}
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--space-3) var(--space-4)', border: 'none', background: 'none', cursor: 'pointer', outline: 'none' }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)' }}>
              <Code size={13} />
              Raw Webhook Payload
            </span>
            <ChevronDown size={14} style={{ transform: showPayload ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', border: 'none', background: 'none' }} />
          </button>
          {showPayload && (
            <div style={{ borderTop: '1px solid var(--neutral-200)', padding: 'var(--space-4)', backgroundColor: 'var(--neutral-900)', color: 'var(--neutral-200)', overflowX: 'auto' }}>
              <pre style={{ margin: 0, fontSize: '12px', fontFamily: 'monospace', lineHeight: '1.5' }}>
                {JSON.stringify(detail.raw_payload, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>

      {/* Right column - Execution & Actions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        
        {/* Actions & Triage */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', marginBottom: 'var(--space-3)' }}>
            Status & Triage
          </div>
          
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
            <span className={`badge ${detail.processing_status === 'completed' ? 'badge-success' : detail.processing_status === 'failed' ? 'badge-error' : 'badge-warning'}`}>
              {detail.processing_status}
            </span>
            {detail.acknowledged_at && (
              <span className="badge badge-success" style={{ backgroundColor: 'var(--success-soft)', color: 'var(--success)' }}>
                Acknowledged
              </span>
            )}
            {detail.retry_of_id && (
              <span className="badge badge-info" style={{ backgroundColor: 'var(--info-soft)', color: 'var(--info)' }}>
                Retry attempt
              </span>
            )}
          </div>

          {detail.acknowledged_at && (
            <div style={{ fontSize: '12px', color: 'var(--neutral-500)', marginBottom: 'var(--space-3)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Check size={12} /> Acknowledged by {detail.acknowledged_by || 'admin'} at {new Date(detail.acknowledged_at).toLocaleString()}
            </div>
          )}

          {detail.processing_status === 'failed' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              {!detail.acknowledged_at && (
                <button 
                  className="btn-secondary" 
                  disabled={actionLoading}
                  onClick={handleAcknowledge}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  <Check size={14} style={{ marginRight: '6px' }} /> Mark as Acknowledged
                </button>
              )}
              <button 
                className="btn-primary" 
                disabled={actionLoading}
                onClick={handleRetry}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <RotateCcw size={14} style={{ marginRight: '6px' }} /> Retry Message
              </button>
            </div>
          )}
        </div>

        {/* AI Providers Execution Metrics */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', marginBottom: 'var(--space-3)' }}>
            AI Providers Metrics
          </div>
          {providers.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--neutral-400)', fontStyle: 'italic' }}>No AI provider calls executed.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {providers.map((p, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: i < providers.length - 1 ? '1px solid var(--neutral-100)' : 'none', paddingBottom: i < providers.length - 1 ? 'var(--space-2)' : 0 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <Cpu size={12} color="var(--neutral-500)" />
                      <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--neutral-800)' }}>{p.provider}</span>
                      <span style={{ fontSize: '11px', color: 'var(--neutral-400)' }}>({p.operation})</span>
                    </div>
                    {p.model && (
                      <div style={{ fontSize: '11px', color: 'var(--neutral-500)', marginTop: '2px', fontFamily: 'monospace' }}>
                        {p.model}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 'var(--space-1)' }}>
                    <span className={`badge ${p.succeeded ? 'badge-success' : 'badge-error'}`} style={{ fontSize: '10px', padding: '1px 6px' }}>
                      {p.succeeded ? 'Success' : p.error_code || 'Fail'}
                    </span>
                    {p.latency_ms !== null && (
                      <span style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--neutral-500)' }}>
                        {p.latency_ms.toFixed(0)}ms
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pipeline Journey Trace */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', marginBottom: 'var(--space-2)' }}>
            Pipeline Trace
          </div>
          <TracePanel correlationId={message.correlation_id} />
        </div>
      </div>
    </div>
  );
};

export default function Logs() {
  const [messages, setMessages] = useState<InboundMessageSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [waIdFilter, setWaIdFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [live, setLive] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const messagesRef = useRef<InboundMessageSummary[]>([]);
  messagesRef.current = messages;

  const loadHistory = useCallback(() => {
    setLoading(true);
    api
      .get<InboundMessageList>('/admin/logs/messages', {
        params: {
          wa_id: waIdFilter || undefined,
          status: statusFilter || undefined,
          limit: 50,
        },
      })
      .then((res) => setMessages(res.data.items || []))
      .finally(() => setLoading(false));
  }, [waIdFilter, statusFilter]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Live polling: cursor-based on the newest row currently held, not OFFSET —
  // immune to new inserts shifting a page window, and dedupes by id.
  useEffect(() => {
    if (!live) return;

    const interval = setInterval(() => {
      const current = messagesRef.current;
      const newest = current[0];
      api
        .get<InboundMessageList>('/admin/logs/messages', {
          params: {
            wa_id: waIdFilter || undefined,
            status: statusFilter || undefined,
            since_received_at: newest?.received_at,
            since_id: newest?.id,
            limit: 50,
          },
        })
        .then((res) => {
          const items = res.data.items || [];
          if (items.length === 0) return;
          setMessages((prev) => {
            const seen = new Set(prev.map((m) => m.id));
            const fresh = items.filter((m) => !seen.has(m.id));
            if (fresh.length === 0) return prev;
            // API returns live-cursor results oldest-first; prepend newest-first.
            return [...fresh.reverse(), ...prev].slice(0, MAX_ROWS);
          });
        })
        .catch(() => {
          // A transient poll failure shouldn't stop future polls (or trip
          // the auth interceptor's redirect more than once) — the interval
          // will simply try again next tick.
        });
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [live, waIdFilter, statusFilter]);

  return (
    <div className="animate-fade-in" style={{ maxWidth: '1200px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 'var(--space-6)' }}>
        <div>
          <h1>WhatsApp Assistant Logs</h1>
          <p className="subtitle">Inbound messages and their pipeline traces.</p>
        </div>
        <button className="btn-secondary" onClick={loadHistory}>
          <RefreshCw size={14} /> Refresh
        </button>
      </header>

      <div style={{ display: 'flex', gap: 'var(--space-4)', marginBottom: 'var(--space-4)', alignItems: 'flex-end' }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label>WhatsApp number</label>
          <input
            type="text"
            className="form-input"
            placeholder="919000000000"
            value={waIdFilter}
            onChange={(e) => setWaIdFilter(e.target.value)}
          />
          <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            {KNOWN_NUMBERS.map((n) => (
              <button
                key={n.wa_id}
                type="button"
                className={`badge ${waIdFilter === n.wa_id ? 'badge-info' : 'badge-warning'}`}
                style={{ border: 'none', cursor: 'pointer' }}
                onClick={() => setWaIdFilter(waIdFilter === n.wa_id ? '' : n.wa_id)}
              >
                {n.label}
              </button>
            ))}
          </div>
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label>Status</label>
          <select className="form-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: '13px', color: 'var(--neutral-600)', marginBottom: '2px' }}>
          <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} />
          Live (poll every 5s)
        </label>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th style={{ width: 24 }} />
              <th>Time</th>
              <th>From</th>
              <th>Type</th>
              <th>Message</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>Loading…</td></tr>
            ) : messages.length === 0 ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>No messages yet.</td></tr>
            ) : (
              messages.map((m) => (
                <Fragment key={m.id}>
                  <tr
                    style={{ cursor: 'pointer' }}
                    onClick={() => setExpandedId(expandedId === m.correlation_id ? null : m.correlation_id)}
                  >
                    <td>{expandedId === m.correlation_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '12px', color: 'var(--neutral-500)' }}>
                      {new Date(m.received_at).toLocaleString()}
                    </td>
                    <td>{m.sender_wa_id}</td>
                    <td>{m.message_type}</td>
                    <td style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {m.body_preview || <em style={{ color: 'var(--neutral-400)' }}>no text</em>}
                    </td>
                    <td>
                      <span className={`badge ${statusBadgeClass(m.processing_status)}`}>{m.processing_status}</span>
                    </td>
                  </tr>
                  {expandedId === m.correlation_id && (
                    <tr>
                      <td colSpan={6} style={{ padding: 0 }}>
                        <LogDetailPanel message={m} onUpdate={loadHistory} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
