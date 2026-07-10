import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { api } from './api';
import { useAuth } from './AuthContext';

interface PlatformUser {
  id: string;
  email: string;
  full_name: string;
  status: string;
  created_at: string | null;
}

const statusBadgeClass = (status: string) => (status === 'active' ? 'badge-success' : 'badge-warning');

export default function PlatformUsers() {
  const { me } = useAuth();
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editing, setEditing] = useState<PlatformUser | null>(null);

  const fetchUsers = () => {
    setLoading(true);
    api
      .get<PlatformUser[]>('/admin/platform-users')
      .then((res) => setUsers(res.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  return (
    <div className="animate-fade-in" style={{ maxWidth: '1000px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 'var(--space-6)' }}>
        <div>
          <h1>Superadmins</h1>
          <p className="subtitle">Platform admin accounts with access to this control panel.</p>
        </div>
        <button className="btn-primary" onClick={() => setIsAddOpen(true)}>
          <Plus size={16} /> Add Admin
        </button>
      </header>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Status</th>
              <th>Created</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>Loading…</td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--neutral-500)' }}>No platform admins yet.</td></tr>
            ) : (
              users.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 500, color: 'var(--neutral-900)' }}>
                    {u.full_name} {u.id === me?.user_id && <span style={{ color: 'var(--neutral-400)', fontWeight: 400 }}>(you)</span>}
                  </td>
                  <td>{u.email}</td>
                  <td><span className={`badge ${statusBadgeClass(u.status)}`}>{u.status}</span></td>
                  <td style={{ fontSize: '13px', color: 'var(--neutral-500)' }}>
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      style={{ background: 'none', border: 'none', color: 'var(--neutral-600)', fontWeight: 500, cursor: 'pointer', fontSize: '13px' }}
                      onClick={() => setEditing(u)}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {isAddOpen && (
        <AddAdminModal
          onClose={() => setIsAddOpen(false)}
          onCreated={() => {
            setIsAddOpen(false);
            fetchUsers();
          }}
        />
      )}

      {editing && (
        <EditAdminModal
          user={editing}
          isSelf={editing.id === me?.user_id}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            fetchUsers();
          }}
        />
      )}
    </div>
  );
}

function AddAdminModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    api
      .post('/admin/platform-users', { email, password, full_name: fullName })
      .then(onCreated)
      .catch((err) => setError(err.response?.data?.detail || 'Failed to create admin'))
      .finally(() => setSubmitting(false));
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2 style={{ marginBottom: 'var(--space-6)' }}>Add Platform Admin</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Full name</label>
            <input required type="text" className="form-input" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Email</label>
            <input required type="email" className="form-input" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input required type="password" minLength={8} className="form-input" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>

          {error && <p style={{ color: 'var(--error)', fontSize: '13px', marginBottom: 'var(--space-4)' }}>{error}</p>}

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create Admin'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EditAdminModal({
  user,
  isSelf,
  onClose,
  onSaved,
}: {
  user: PlatformUser;
  isSelf: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [fullName, setFullName] = useState(user.full_name);
  const [status, setStatus] = useState(user.status);
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const body: Record<string, string> = { full_name: fullName, status };
    if (newPassword) body.new_password = newPassword;

    api
      .patch(`/admin/platform-users/${user.id}`, body)
      .then(onSaved)
      .catch((err) => setError(err.response?.data?.detail || 'Failed to save changes'))
      .finally(() => setSubmitting(false));
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2 style={{ marginBottom: 'var(--space-6)' }}>Edit {user.email}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Full name</label>
            <input required type="text" className="form-input" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Status</label>
            <select
              className="form-input"
              value={status}
              disabled={isSelf}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="suspended">Suspended</option>
              <option value="invited">Invited</option>
            </select>
            {isSelf && (
              <p style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: 'var(--space-2)' }}>
                You can't change your own account's status.
              </p>
            )}
          </div>
          <div className="form-group">
            <label>New password (leave blank to keep current)</label>
            <input type="password" minLength={8} className="form-input" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          </div>

          {error && <p style={{ color: 'var(--error)', fontSize: '13px', marginBottom: 'var(--space-4)' }}>{error}</p>}

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
