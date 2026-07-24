import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw, ChevronDown, ChevronRight, Check, RotateCcw, Code, Cpu } from 'lucide-react';
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
  acknowledged_at: string | null;
  project_id: string | null;
  project_name: string | null;
  site_id: string | null;
  site_name: string | null;
  workflow_instance_id: string | null;
  workflow_key: string | null;
  workflow_phase: string | null;
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
  project_id: string | null;
  project_name: string | null;
  site_id: string | null;
  site_name: string | null;
  workflow_instance_id: string | null;
  workflow_key: string | null;
  workflow_phase: string | null;
}

interface StageContextEntry {
  stage: string;
  succeeded: boolean;
  created_at: string;
  stage_payload: Record<string, unknown> | null;
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
// Messages from the same sender within this gap are treated as one
// conversation session — a heuristic grouping (no schema change) that sits
// alongside the precise workflow_instance_id bracket below.
const SESSION_GAP_MS = 30 * 60 * 1000;

interface MessageSession {
  key: string;
  sender_wa_id: string;
  messages: InboundMessageSummary[]; // newest-first, same order as the source list
}

// `messages` is newest-first. Runs of consecutive same-sender messages
// within SESSION_GAP_MS become one session — if another sender's messages
// interleave in time, that naturally splits the run, which is the desired
// behavior for a heuristic grounded in actual timestamps.
function groupIntoSessions(messages: InboundMessageSummary[]): MessageSession[] {
  const sessions: MessageSession[] = [];
  for (const m of messages) {
    const last = sessions[sessions.length - 1];
    if (last && last.sender_wa_id === m.sender_wa_id) {
      const lastMsg = last.messages[last.messages.length - 1];
      const gapMs = new Date(lastMsg.received_at).getTime() - new Date(m.received_at).getTime();
      if (gapMs <= SESSION_GAP_MS) {
        last.messages.push(m);
        continue;
      }
    }
    sessions.push({ key: `${m.sender_wa_id}-${m.id}`, sender_wa_id: m.sender_wa_id, messages: [m] });
  }
  return sessions;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay === 1) return 'yesterday';
  return date.toLocaleDateString();
}

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

  if (loading) return <div style={{ padding: 'var(--space-2) 0', color: 'var(--neutral-500)', fontSize: '13px' }}>Loading trace…</div>;
  if (!trace || trace.length === 0) {
    return <div style={{ padding: 'var(--space-2) 0', color: 'var(--neutral-500)', fontSize: '13px' }}>No pipeline trace recorded.</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, paddingLeft: '8px', paddingTop: '4px', position: 'relative' }}>
      {trace.map((entry, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            gap: 'var(--space-3)',
            position: 'relative',
            paddingBottom: i < trace.length - 1 ? 'var(--space-4)' : 0
          }}
        >
          {/* Vertical line connector */}
          {i < trace.length - 1 && (
            <div
              style={{
                position: 'absolute',
                left: '7px',
                top: '16px',
                bottom: 0,
                width: '2px',
                backgroundColor: 'var(--neutral-200)',
                zIndex: 1
              }}
            />
          )}
          
          {/* Node marker */}
          <div
            style={{
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              backgroundColor: entry.succeeded ? 'var(--success-soft)' : 'var(--error-soft)',
              border: `2px solid ${entry.succeeded ? 'var(--success)' : 'var(--error)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 2,
              fontSize: '9px',
              fontWeight: 'bold',
              color: entry.succeeded ? 'var(--success)' : 'var(--error)'
            }}
          >
            {entry.succeeded ? '✓' : '✗'}
          </div>

          <div style={{ flex: 1, marginTop: '-2px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--neutral-800)' }}>
                {entry.stage}
              </span>
              {entry.duration_ms !== null && (
                <span style={{ fontSize: '11px', color: 'var(--neutral-400)', fontFamily: 'monospace' }}>
                  {entry.duration_ms}ms
                </span>
              )}
            </div>
            {entry.error_message && (
              <div style={{ fontSize: '12px', color: 'var(--error)', marginTop: '4px', backgroundColor: 'var(--error-soft)', padding: '6px 10px', borderRadius: 'var(--radius-xs)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                {entry.error_code}: {entry.error_message}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

const ContextPanel = ({ correlationId }: { correlationId: string }) => {
  const [context, setContext] = useState<StageContextEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [openStage, setOpenStage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<StageContextEntry[]>(`/admin/logs/messages/${correlationId}/context`)
      .then((res) => {
        if (!cancelled) setContext(res.data);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [correlationId]);

  if (loading) return <div style={{ padding: 'var(--space-2) 0', color: 'var(--neutral-500)', fontSize: '13px' }}>Loading context…</div>;
  if (!context || context.length === 0) {
    return <div style={{ padding: 'var(--space-2) 0', color: 'var(--neutral-500)', fontSize: '13px' }}>No AI context recorded.</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
      {context
        .filter((entry) => entry.stage_payload !== null)
        .map((entry, i) => {
          const isOpen = openStage === `${entry.stage}-${i}`;
          return (
            <div key={i} style={{ border: '1px solid var(--neutral-200)', borderRadius: 'var(--radius-xs)', overflow: 'hidden' }}>
              <button
                type="button"
                onClick={() => setOpenStage(isOpen ? null : `${entry.stage}-${i}`)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--space-2) var(--space-3)', border: 'none', background: 'none', cursor: 'pointer', outline: 'none' }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: '12px', fontWeight: 500, color: 'var(--neutral-800)' }}>
                  {entry.stage}
                  <span className={`badge ${entry.succeeded ? 'badge-success' : 'badge-error'}`} style={{ fontSize: '9px', padding: '1px 6px' }}>
                    {entry.succeeded ? 'ok' : 'failed'}
                  </span>
                </span>
                <ChevronDown size={13} style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
              </button>
              {isOpen && (
                <div style={{ borderTop: '1px solid var(--neutral-200)', padding: 'var(--space-3)', backgroundColor: 'var(--neutral-900)', color: 'var(--neutral-200)', overflowX: 'auto' }}>
                  <pre style={{ margin: 0, fontSize: '11px', fontFamily: 'monospace', lineHeight: '1.5' }}>
                    {JSON.stringify(entry.stage_payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
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
        
        {/* Chat Visualizer Flow */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)', padding: 'var(--space-4)', boxShadow: '0 1px 2px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', borderBottom: '1px solid var(--neutral-100)', paddingBottom: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
            Conversation Flow
          </div>

          {/* User Message Bubble */}
          <div style={{ display: 'flex', flexDirection: 'column', alignSelf: 'flex-start', maxWidth: '85%', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--neutral-500)', marginLeft: '8px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              USER ({detail.normalized_message?.sender?.profile_name || detail.sender_wa_id})
              {detail.message_type === 'audio' && (
                <span style={{ backgroundColor: 'var(--info-soft)', color: 'var(--info)', fontSize: '9px', padding: '1px 6px', borderRadius: '4px', textTransform: 'uppercase', fontWeight: 600 }}>
                  🗣 Voice Transcribed
                </span>
              )}
            </span>
            <div style={{ backgroundColor: 'var(--neutral-100)', border: '1px solid var(--neutral-200)', borderRadius: '8px 8px 8px 0', padding: '10px 14px', fontSize: '13px', color: 'var(--neutral-800)', whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
              {detail.body_text || <em style={{ color: 'var(--neutral-400)' }}>[Media message or no text]</em>}
            </div>
            <span style={{ fontSize: '10px', color: 'var(--neutral-400)', alignSelf: 'flex-start', marginLeft: '4px' }}>
              {new Date(detail.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>

          {/* Assistant Reply Bubble */}
          {detail.assistant_reply ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignSelf: 'flex-end', maxWidth: '85%', gap: '4px', marginTop: 'var(--space-2)' }}>
              <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--neutral-500)', marginRight: '8px', alignSelf: 'flex-end' }}>
                ASSISTANT
              </span>
              <div style={{ backgroundColor: 'var(--primary-soft)', border: '1px solid var(--neutral-200)', borderRadius: '8px 8px 0 8px', padding: '10px 14px', fontSize: '13px', color: 'var(--neutral-800)', whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
                {detail.assistant_reply}
              </div>
              <span style={{ fontSize: '10px', color: 'var(--neutral-400)', alignSelf: 'flex-end', marginRight: '4px' }}>
                {detail.processed_at ? new Date(detail.processed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
              </span>
            </div>
          ) : (
            detail.processing_status === 'completed' && (
              <div style={{ alignSelf: 'flex-end', fontSize: '12px', color: 'var(--neutral-400)', fontStyle: 'italic', marginTop: 'var(--space-2)' }}>
                No reply was triggered for this message.
              </div>
            )
          )}
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

          {/* Resolved Context Display */}
          <div style={{ borderTop: '1px solid var(--neutral-100)', borderBottom: '1px solid var(--neutral-100)', padding: 'var(--space-3) 0', margin: 'var(--space-3) 0', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-400)' }}>
              Resolved Context
            </div>
            {detail.project_name ? (
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--neutral-800)' }}>
                  📁 {detail.project_name}
                </div>
                {detail.site_name && (
                  <div style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: '2px', paddingLeft: '18px' }}>
                    📍 {detail.site_name}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--neutral-400)' }}>
                Unmapped (No project/site resolved)
              </div>
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

        {/* AI Context (platform-admin only — full per-stage payloads) */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', marginBottom: 'var(--space-2)' }}>
            AI Context
          </div>
          <ContextPanel correlationId={message.correlation_id} />
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
  const [providerFilter, setProviderFilter] = useState('');
  const [live, setLive] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const messagesRef = useRef<InboundMessageSummary[]>([]);
  messagesRef.current = messages;

  // KPI Calculations
  const completedCount = messages.filter(m => m.processing_status === 'completed').length;
  const successRate = messages.length ? Math.round((completedCount / messages.length) * 100) : 100;
  const unacknowledgedCount = messages.filter(m => m.processing_status === 'failed' && !m.acknowledged_at).length;
  
  const completedMessages = messages.filter(m => m.processing_status === 'completed' && m.processed_at);
  const totalLatency = completedMessages.reduce((sum, m) => {
    const lat = new Date(m.processed_at!).getTime() - new Date(m.received_at).getTime();
    return sum + (lat > 0 ? lat : 0);
  }, 0);
  const avgLatency = completedMessages.length ? Math.round(totalLatency / completedMessages.length) : 0;

  const sessions = groupIntoSessions(messages);

  const loadHistory = useCallback(() => {
    setLoading(true);
    api
      .get<InboundMessageList>('/admin/logs/messages', {
        params: {
          wa_id: waIdFilter || undefined,
          status: statusFilter || undefined,
          provider: providerFilter || undefined,
          limit: 50,
        },
      })
      .then((res) => setMessages(res.data.items || []))
      .finally(() => setLoading(false));
  }, [waIdFilter, statusFilter, providerFilter]);

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
            provider: providerFilter || undefined,
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
  }, [live, waIdFilter, statusFilter, providerFilter]);

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

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 180px 180px auto', gap: 'var(--space-4)', marginBottom: 'var(--space-6)', backgroundColor: '#ffffff', border: '1px solid var(--neutral-200)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-4)', alignItems: 'flex-start' }}>
        
        {/* WhatsApp number filter */}
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--neutral-500)', display: 'block', marginBottom: '6px' }}>WhatsApp Number</label>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <input
              type="text"
              className="form-input"
              placeholder="919000000000"
              value={waIdFilter}
              onChange={(e) => setWaIdFilter(e.target.value)}
              style={{ flex: 1 }}
            />
            {waIdFilter && (
              <button 
                type="button" 
                className="btn-secondary" 
                onClick={() => setWaIdFilter('')}
                style={{ padding: '0 var(--space-3)', height: '36px' }}
              >
                Clear
              </button>
            )}
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            {KNOWN_NUMBERS.map((n) => (
              <button
                key={n.wa_id}
                type="button"
                className={`badge ${waIdFilter === n.wa_id ? 'badge-info' : 'badge-warning'}`}
                style={{ border: 'none', cursor: 'pointer', fontSize: '10px', padding: '2px 8px' }}
                onClick={() => setWaIdFilter(waIdFilter === n.wa_id ? '' : n.wa_id)}
              >
                {n.label}
              </button>
            ))}
          </div>
        </div>

        {/* Status filter */}
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--neutral-500)', display: 'block', marginBottom: '6px' }}>Status</label>
          <select 
            className="form-input" 
            value={statusFilter} 
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ width: '100%', height: '36px' }}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        {/* AI Provider filter */}
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--neutral-500)', display: 'block', marginBottom: '6px' }}>AI Provider</label>
          <select 
            className="form-input" 
            value={providerFilter} 
            onChange={(e) => setProviderFilter(e.target.value)}
            style={{ width: '100%', height: '36px' }}
          >
            <option value="">All Providers</option>
            <option value="gemini">Gemini</option>
            <option value="deepseek">DeepSeek</option>
            <option value="sarvam">Sarvam</option>
          </select>
        </div>

        {/* Live tail checkbox */}
        <div style={{ display: 'flex', alignItems: 'center', height: '100%', paddingTop: '28px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: '13px', color: 'var(--neutral-600)', cursor: 'pointer', userSelect: 'none' }}>
            <input 
              type="checkbox" 
              checked={live} 
              onChange={(e) => setLive(e.target.checked)} 
              style={{ cursor: 'pointer' }}
            />
            Live (5s poll)
          </label>
        </div>

      </div>

      {/* KPI Cards Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid var(--neutral-200)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--neutral-500)' }}>Ingress Messages</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--neutral-900)', marginTop: '4px' }}>{messages.length}</div>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid var(--neutral-200)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--neutral-500)' }}>Success Rate</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--neutral-900)', marginTop: '4px' }}>{successRate}%</div>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid var(--neutral-200)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--neutral-500)' }}>Avg Response Latency</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--neutral-900)', marginTop: '4px' }}>
            {avgLatency === 0 ? '—' : avgLatency < 1000 ? `${avgLatency}ms` : `${(avgLatency / 1000).toFixed(1)}s`}
          </div>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid var(--neutral-200)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--neutral-500)' }}>Triage Required</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: unacknowledgedCount > 0 ? 'var(--error)' : 'var(--neutral-900)', marginTop: '4px' }}>{unacknowledgedCount}</div>
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th style={{ width: 24 }} />
              <th>Time</th>
              <th>From</th>
              <th>Type</th>
              <th>Project/Site</th>
              <th>Message</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>Loading…</td></tr>
            ) : messages.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>No messages yet.</td></tr>
            ) : (
              sessions.map((session) => (
                <Fragment key={session.key}>
                  <tr>
                    <td colSpan={7} style={{ padding: '10px 12px', backgroundColor: 'var(--neutral-50)', borderTop: '1px solid var(--neutral-200)', borderBottom: '1px solid var(--neutral-200)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: '11px', fontWeight: 600, color: 'var(--neutral-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        <span>{session.sender_wa_id}</span>
                        <span style={{ fontWeight: 400, textTransform: 'none', color: 'var(--neutral-400)' }}>
                          {session.messages.length} message{session.messages.length === 1 ? '' : 's'} · {formatRelativeTime(session.messages[session.messages.length - 1].received_at)} – {formatRelativeTime(session.messages[0].received_at)}
                        </span>
                      </div>
                    </td>
                  </tr>
                  {session.messages.map((m, i) => {
                    const prev = session.messages[i - 1];
                    const next = session.messages[i + 1];
                    const inWorkflow = !!m.workflow_instance_id;
                    const startsBracket = inWorkflow && prev?.workflow_instance_id !== m.workflow_instance_id;
                    const continuesBracket = inWorkflow && next?.workflow_instance_id === m.workflow_instance_id;
                    return (
                      <Fragment key={m.id}>
                        <tr
                          style={{ cursor: 'pointer' }}
                          onClick={() => setExpandedId(expandedId === m.correlation_id ? null : m.correlation_id)}
                        >
                          <td style={{ position: 'relative' }}>
                            {inWorkflow && (
                              <div
                                title={[m.workflow_key, m.workflow_phase].filter(Boolean).join(' · ') || 'workflow interaction'}
                                style={{
                                  position: 'absolute',
                                  left: 2,
                                  top: 0,
                                  bottom: continuesBracket ? '-1px' : '50%',
                                  width: '3px',
                                  backgroundColor: 'var(--info)',
                                  borderRadius: '2px',
                                }}
                              />
                            )}
                            {expandedId === m.correlation_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </td>
                          <td>
                            <div style={{ fontSize: '13px', color: 'var(--neutral-800)', fontWeight: 500 }}>{formatRelativeTime(m.received_at)}</div>
                            <div style={{ fontSize: '11px', color: 'var(--neutral-400)', fontFamily: 'monospace', marginTop: '2px' }}>
                              {new Date(m.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </div>
                          </td>
                          <td>{m.sender_wa_id}</td>
                          <td>
                            {m.message_type}
                            {m.message_type === 'audio' && ' 🗣'}
                          </td>
                          <td>
                            {m.project_name ? (
                              <div>
                                <div style={{ fontSize: '13px', color: 'var(--neutral-800)', fontWeight: 500 }}>{m.project_name}</div>
                                {m.site_name && (
                                  <div style={{ fontSize: '11px', color: 'var(--neutral-400)', marginTop: '2px' }}>
                                    {m.site_name}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span style={{ fontSize: '11px', color: 'var(--neutral-400)', fontStyle: 'italic' }}>Unmapped</span>
                            )}
                          </td>
                          <td style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {startsBracket && (
                              <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--info)', textTransform: 'uppercase', letterSpacing: '0.03em', marginRight: '6px' }}>
                                {m.workflow_key || 'workflow'}
                              </span>
                            )}
                            {m.body_preview || <em style={{ color: 'var(--neutral-400)' }}>no text</em>}
                          </td>
                          <td>
                            <span className={`badge ${statusBadgeClass(m.processing_status)}`}>{m.processing_status}</span>
                          </td>
                        </tr>
                        {expandedId === m.correlation_id && (
                          <tr>
                            <td colSpan={7} style={{ padding: 0 }}>
                              <LogDetailPanel message={m} onUpdate={loadHistory} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
