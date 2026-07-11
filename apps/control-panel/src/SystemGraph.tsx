import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { RefreshCw, GitBranch, Workflow, AlertCircle } from 'lucide-react';
import mermaid from 'mermaid';
import { api } from './api';

interface WorkflowGraphInfo {
  workflow_key: string;
  implemented: boolean;
  mermaid: string | null;
}

interface SystemGraphResponse {
  mermaid: string;
  workflows: WorkflowGraphInfo[];
}

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'strict',
  flowchart: { curve: 'basis', htmlLabels: true },
});

/**
 * Renders one Mermaid source string into an <svg>. Mermaid is async and needs a
 * unique id per render, so we key off a stable useId and re-render whenever the
 * source changes. Parse failures are shown inline rather than crashing the page.
 */
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
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
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

const SystemGraph = () => {
  const [data, setData] = useState<SystemGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .get<SystemGraphResponse>('/admin/system-graph')
      .then((res) => setData(res.data))
      .catch((err) => {
        console.error('Failed to fetch system graph', err);
        setError(err.response?.data?.detail || 'Failed to load system graph');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  return (
    <div className="animate-fade-in" style={{ maxWidth: '1200px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 'var(--space-6)' }}>
        <div>
          <h1>System Graph</h1>
          <p className="subtitle">
            How the WhatsApp assistant reacts to every message — generated live from the routing tables and workflow graphs.
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
          <div className="card" style={{ marginBottom: 'var(--space-8)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
              <GitBranch size={18} style={{ color: 'var(--primary)' }} />
              <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>End-to-end pipeline</h2>
            </div>
            <MermaidDiagram source={data.mermaid} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <Workflow size={18} style={{ color: 'var(--neutral-600)' }} />
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>Individual workflows</h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-6)' }}>
            {data.workflows.map((wf) => (
              <div key={wf.workflow_key} className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                  <span style={{ fontFamily: 'monospace', fontSize: '13px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                    {wf.workflow_key}
                  </span>
                  <span className={`badge ${wf.implemented ? 'badge-success' : 'badge-warning'}`}>
                    {wf.implemented ? 'Built' : 'Not built yet'}
                  </span>
                </div>
                {wf.mermaid ? (
                  <MermaidDiagram source={wf.mermaid} />
                ) : (
                  <div style={{ fontSize: '13px', color: 'var(--neutral-500)' }}>
                    {wf.implemented
                      ? 'Graph drawing unavailable (LangGraph not installed in this environment).'
                      : 'This intent is understood but routes to a "not supported yet" reply until the workflow is added.'}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
};

export default SystemGraph;
