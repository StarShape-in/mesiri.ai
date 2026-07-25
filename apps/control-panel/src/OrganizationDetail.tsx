import { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, Cloud, Server, Trash2, X } from 'lucide-react';
import { api } from './api';

interface Organization {
  id: string;
  name: string;
  deployment_type: string;
  db_route: string;
  status: string;
  created_at: string;
}

interface ProjectAccessGrant {
  project_id: string;
  project_name: string;
  site_access: string;
}

interface OrgUser {
  id: string;
  email: string | null;
  full_name: string | null;
  role: string | null;
  status?: string;
  whatsapp_number: string | null;
  access_mode: string;
  project_access: ProjectAccessGrant[];
}

interface TimelineEntry {
  id: string;
  project_id: string | null;
  site_id: string | null;
  event_type: string;
  summary: string;
  occurred_at: string;
}

type Tab = 'users' | 'activity';

const statusBadgeClass = (status: string) =>
  status === 'active' || status === 'Active' ? 'badge-success' : 'badge-warning';

export default function OrganizationDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [org, setOrg] = useState<Organization | null>(null);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [tab, setTab] = useState<Tab>('users');
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      api.get<Organization>(`/admin/organizations/${id}`),
      api.get<OrgUser[]>(`/admin/organizations/${id}/users`),
      api.get<{ items: TimelineEntry[]; total: number }>(`/admin/organizations/${id}/timeline`),
    ])
      .then(([orgRes, usersRes, timelineRes]) => {
        setOrg(orgRes.data);
        setUsers(usersRes.data);
        setTimeline(timelineRes.data.items);
      })
      .catch((err) => setError(err.response?.data?.detail || 'Failed to load organization'))
      .finally(() => setLoading(false));
  }, [id]);

  const executeDelete = () => {
    if (!org) return;
    setDeleting(true);
    setError(null);
    api
      .delete(`/admin/organizations/${org.id}`)
      .then(() => navigate('/organizations'))
      .catch((err) => {
        setError(err.response?.data?.detail || 'Failed to delete organization');
        setDeleting(false);
        setShowDeleteModal(false);
      });
  };

  const handleUpdateUserStatus = (user: OrgUser, newStatus: string) => {
    if (!id) return;
    setUpdatingUserId(user.id);
    setError(null);
    api
      .patch<OrgUser>(`/admin/organizations/${id}/users/${user.id}/status`, { status: newStatus })
      .then((res) => {
        setUsers((prev) =>
          prev.map((u) => (u.id === user.id ? { ...u, status: res.data.status || newStatus } : u))
        );
      })
      .catch((err) => setError(err.response?.data?.detail || 'Failed to update user status'))
      .finally(() => setUpdatingUserId(null));
  };

  const handleForceDeleteUser = (user: OrgUser) => {
    if (!id) return;
    const confirmed = window.confirm(
      `FORCE DELETE "${user.full_name || user.email || user.id}"?\n\nThis will unbind user ownership on historical records and PERMANENTLY delete the account. This cannot be undone.`
    );
    if (!confirmed) return;

    setDeletingUserId(user.id);
    setError(null);
    api
      .delete(`/admin/organizations/${id}/users/${user.id}?force=true`)
      .then(() => setUsers((prev) => prev.filter((u) => u.id !== user.id)))
      .catch((err) => setError(err.response?.data?.detail || 'Failed to force delete user'))
      .finally(() => setDeletingUserId(null));
  };

  const handleDeleteUser = (user: OrgUser) => {
    if (!id) return;
    const confirmed = window.confirm(
      `Remove ${user.full_name || user.email || user.id} from this organization?`
    );
    if (!confirmed) return;

    setDeletingUserId(user.id);
    setError(null);
    api
      .delete(`/admin/organizations/${id}/users/${user.id}`)
      .then(() => setUsers((prev) => prev.filter((u) => u.id !== user.id)))
      .catch((err) => {
        if (err.response?.status === 409) {
          const detail = err.response?.data?.detail || 'User owns historical records.';
          const choice = window.confirm(
            `${detail}\n\nClick OK to DEACTIVATE account (recommended).\nClick CANCEL to choice Force Delete.`
          );
          if (choice) {
            handleUpdateUserStatus(user, 'Inactive');
          } else {
            handleForceDeleteUser(user);
          }
          return;
        }
        setError(err.response?.data?.detail || 'Failed to remove user');
      })
      .finally(() => setDeletingUserId(null));
  };

  if (loading) {
    return <div className="animate-fade-in" style={{ maxWidth: '1200px', color: 'var(--neutral-500)' }}>Loading…</div>;
  }

  if (error && !org) {
    return (
      <div className="animate-fade-in" style={{ maxWidth: '1200px' }}>
        <Link to="/organizations" className="btn-secondary" style={{ display: 'inline-flex', marginBottom: 'var(--space-6)' }}>
          <ArrowLeft size={16} /> Back to Organizations
        </Link>
        <p style={{ color: 'var(--error)' }}>{error}</p>
      </div>
    );
  }

  if (!org) return null;

  return (
    <div className="animate-fade-in" style={{ maxWidth: '1200px' }}>
      <Link to="/organizations" className="btn-secondary" style={{ display: 'inline-flex', marginBottom: 'var(--space-6)' }}>
        <ArrowLeft size={16} /> Back to Organizations
      </Link>

      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 'var(--space-6)' }}>
        <div>
          <h1>{org.name}</h1>
          <p className="subtitle">
            <span className={`badge ${org.deployment_type === 'SaaS' ? 'badge-info' : 'badge-warning'}`} style={{ marginRight: 8 }}>
              {org.deployment_type === 'SaaS' ? <Cloud size={12} style={{ marginRight: 4 }} /> : <Server size={12} style={{ marginRight: 4 }} />}
              {org.deployment_type}
            </span>
            <span className={`badge ${statusBadgeClass(org.status)}`}>{org.status}</span>
          </p>
        </div>
        <button
          className="btn-secondary"
          style={{ color: 'var(--error)', borderColor: 'var(--error)' }}
          onClick={() => setShowDeleteModal(true)}
          disabled={deleting}
        >
          <Trash2 size={16} /> Delete Tenant
        </button>
      </header>

      {error && <p style={{ color: 'var(--error)', marginBottom: 'var(--space-4)' }}>{error}</p>}

      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>Database Route</div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px' }}>{org.db_route}</div>
          </div>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>Created</div>
            <div style={{ fontSize: '13px' }}>{new Date(org.created_at).toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>Users</div>
            <div style={{ fontSize: '13px' }}>{users.length}</div>
          </div>
        </div>
      </div>

      <nav style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-strong)' }}>
        {(['users', 'activity'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: tab === t ? '2px solid var(--primary)' : '2px solid transparent',
              padding: 'var(--space-3) var(--space-2)',
              fontWeight: 500,
              fontSize: '14px',
              color: tab === t ? 'var(--neutral-900)' : 'var(--neutral-500)',
              cursor: 'pointer',
            }}
          >
            {t === 'users' ? 'Users & Roles' : 'Activity'}
          </button>
        ))}
      </nav>

      {tab === 'users' && (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>WhatsApp</th>
                <th>Project &amp; Site Access</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>No users in this organization.</td></tr>
              ) : (
                users.map((u) => {
                  const isInactive = (u.status || 'Active').toLowerCase() === 'inactive';
                  return (
                    <tr key={u.id}>
                      <td style={{ fontWeight: 500, color: 'var(--neutral-900)' }}>{u.full_name || '—'}</td>
                      <td>{u.email || '—'}</td>
                      <td style={{ textTransform: 'capitalize' }}>{(u.role || '').toLowerCase()}</td>
                      <td>
                        <span className={`badge ${statusBadgeClass(u.status || 'Active')}`}>
                          {u.status || 'Active'}
                        </span>
                      </td>
                      <td style={{ fontSize: '13px', color: 'var(--neutral-500)' }}>{u.whatsapp_number || 'Not mapped'}</td>
                      <td style={{ fontSize: '13px' }}>
                        {u.access_mode === 'all_projects' ? (
                          <span className="badge badge-info">All Projects</span>
                        ) : u.project_access.length === 0 ? (
                          <span style={{ color: 'var(--neutral-500)' }}>No projects assigned</span>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            {u.project_access.map((grant) => (
                              <div key={grant.project_id}>
                                <span style={{ fontWeight: 500 }}>{grant.project_name}</span>
                                <span style={{ color: 'var(--neutral-500)' }}> — {grant.site_access}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          style={{
                            background: 'none',
                            border: 'none',
                            color: isInactive ? 'var(--primary)' : 'var(--neutral-600)',
                            fontWeight: 500,
                            cursor: 'pointer',
                            fontSize: '13px',
                            marginRight: '12px',
                          }}
                          onClick={() => handleUpdateUserStatus(u, isInactive ? 'Active' : 'Inactive')}
                          disabled={updatingUserId === u.id}
                        >
                          {updatingUserId === u.id ? 'Updating…' : isInactive ? 'Reactivate' : 'Deactivate'}
                        </button>
                        <button
                          style={{ background: 'none', border: 'none', color: 'var(--error)', fontWeight: 500, cursor: 'pointer', fontSize: '13px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                          onClick={() => handleDeleteUser(u)}
                          disabled={deletingUserId === u.id}
                        >
                          <X size={13} /> {deletingUserId === u.id ? 'Removing…' : 'Remove'}
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'activity' && (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Event</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {timeline.length === 0 ? (
                <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>No activity recorded yet.</td></tr>
              ) : (
                timeline.map((entry) => (
                  <tr key={entry.id}>
                    <td style={{ fontSize: '13px', color: 'var(--neutral-500)', whiteSpace: 'nowrap' }}>
                      {new Date(entry.occurred_at).toLocaleString()}
                    </td>
                    <td><span className="badge badge-info">{entry.event_type}</span></td>
                    <td>{entry.summary}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {showDeleteModal && (
        <DeleteOrgModal
          orgName={org.name}
          isOpen={showDeleteModal}
          deleting={deleting}
          onClose={() => setShowDeleteModal(false)}
          onConfirm={executeDelete}
        />
      )}
    </div>
  );
}

interface DeleteOrgModalProps {
  orgName: string;
  isOpen: boolean;
  deleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

function DeleteOrgModal({ orgName, isOpen, deleting, onClose, onConfirm }: DeleteOrgModalProps) {
  const [typedName, setTypedName] = useState('');

  if (!isOpen) return null;

  const isConfirmed = typedName.trim() === orgName.trim();

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(14, 17, 22, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '16px',
      }}
      onClick={onClose}
    >
      <div
        className="animate-fade-in"
        style={{
          background: 'var(--surface-primary, #FFFFFF)',
          border: '1px solid var(--border-default, #E5E7EB)',
          borderRadius: 'var(--radius-md, 12px)',
          padding: '24px',
          maxWidth: '480px',
          width: '100%',
          boxShadow: 'var(--shadow-overlay, 0 20px 48px rgba(16,24,40,0.18))',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', marginBottom: '16px' }}>
          <div
            style={{
              padding: '10px',
              borderRadius: '50%',
              background: 'var(--error-soft, #FEE2E2)',
              color: 'var(--error, #EF4444)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <AlertTriangle size={22} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: 'var(--neutral-900)' }}>
              Delete Tenant Organization?
            </h3>
            <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--neutral-500)' }}>
              This action <strong style={{ color: 'var(--error)' }}>cannot be undone</strong>.
            </p>
          </div>
        </div>

        <div
          style={{
            background: 'var(--surface-secondary, #F3F4F6)',
            borderRadius: '8px',
            padding: '12px 14px',
            marginBottom: '16px',
            fontSize: '13px',
            color: 'var(--neutral-700)',
            lineHeight: 1.5,
          }}
        >
          Deleting <strong>"{orgName}"</strong> will permanently purge:
          <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
            <li>All user accounts, roles & access policies</li>
            <li>All projects, job sites & assigned memberships</li>
            <li>All money accounts, expenses & transaction ledgers</li>
            <li>All material catalogues, receipts & movement logs</li>
            <li>All timeline activity & message logs</li>
          </ul>
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label
            htmlFor="confirm-org-name"
            style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px', color: 'var(--neutral-700)' }}
          >
            Type <code style={{ background: '#E5E7EB', padding: '2px 6px', borderRadius: '4px' }}>{orgName}</code> to confirm:
          </label>
          <input
            id="confirm-org-name"
            type="text"
            className="form-input"
            style={{ width: '100%', boxSizing: 'border-box' }}
            placeholder={orgName}
            value={typedName}
            onChange={(e) => setTypedName(e.target.value)}
            disabled={deleting}
            autoFocus
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={deleting}
          >
            Cancel
          </button>
          <button
            type="button"
            style={{
              background: isConfirmed ? 'var(--error)' : 'var(--neutral-300)',
              color: 'var(--white)',
              border: 'none',
              borderRadius: 'var(--radius-sm, 8px)',
              padding: '8px 16px',
              fontWeight: 500,
              fontSize: '14px',
              cursor: isConfirmed && !deleting ? 'pointer' : 'not-allowed',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
            onClick={onConfirm}
            disabled={!isConfirmed || deleting}
          >
            <Trash2 size={15} /> {deleting ? 'Deleting…' : 'Permanently Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}
