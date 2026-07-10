import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
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
      .get<InboundMessageSummary[]>('/admin/logs/messages', {
        params: {
          wa_id: waIdFilter || undefined,
          status: statusFilter || undefined,
          limit: 50,
        },
      })
      .then((res) => setMessages(res.data))
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
        .get<InboundMessageSummary[]>('/admin/logs/messages', {
          params: {
            wa_id: waIdFilter || undefined,
            status: statusFilter || undefined,
            since_received_at: newest?.received_at,
            since_id: newest?.id,
            limit: 50,
          },
        })
        .then((res) => {
          if (res.data.length === 0) return;
          setMessages((prev) => {
            const seen = new Set(prev.map((m) => m.id));
            const fresh = res.data.filter((m) => !seen.has(m.id));
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
                      <td colSpan={6} style={{ padding: 'var(--space-4)', backgroundColor: 'var(--neutral-50)' }}>
                        {m.assistant_reply && (
                          <div style={{ marginBottom: 'var(--space-4)', padding: 'var(--space-4)', backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--neutral-200)' }}>
                            <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', marginBottom: 'var(--space-2)' }}>
                              Assistant Reply
                            </div>
                            <div style={{ fontSize: '13px', whiteSpace: 'pre-wrap', color: 'var(--neutral-800)', fontFamily: 'var(--font-sans)' }}>
                              {m.assistant_reply}
                            </div>
                          </div>
                        )}
                        <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--neutral-500)', marginBottom: 'var(--space-2)' }}>
                          Pipeline Trace
                        </div>
                        <TracePanel correlationId={m.correlation_id} />
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
