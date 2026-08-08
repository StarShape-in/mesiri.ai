import { useState } from 'react';
import { X } from 'lucide-react';
import { api } from './api';

const ROLES = ['ADMIN', 'PROJECT_MANAGER', 'SITE_ENGINEER', 'FINANCE'];

const ROLE_LABELS: Record<string, string> = {
  ADMIN: 'Admin',
  PROJECT_MANAGER: 'Project manager',
  SITE_ENGINEER: 'Site engineer',
  FINANCE: 'Finance',
};

interface Props {
  orgId: string;
  orgName: string;
  onClose: () => void;
  onCreated: () => void;
}

export default function AddUserDialog({ orgId, orgName, onClose, onCreated }: Props) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('SITE_ENGINEER');
  const [whatsapp, setWhatsapp] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = fullName.trim() && email.trim() && password && !saving;

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.post(`/admin/organizations/${orgId}/users`, {
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        role,
        whatsapp_number: whatsapp.trim() || null,
      });
      onCreated();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not add the user. Nothing was created.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        padding: 'var(--space-6)',
        zIndex: 50,
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{ maxWidth: '520px', width: '100%', maxHeight: '85vh', overflowY: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            marginBottom: 'var(--space-4)',
          }}
        >
          <div>
            <h2 style={{ fontSize: '17px', margin: 0 }}>Add user</h2>
            <p style={{ fontSize: '13px', color: 'var(--neutral-500)', margin: '2px 0 0' }}>
              to {orgName}
            </p>
          </div>
          <button
            style={{ background: 'none', border: 'none', cursor: 'pointer' }}
            onClick={onClose}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <p style={{ color: 'var(--error)', fontSize: '13px', marginBottom: 'var(--space-3)' }}>
            {error}
          </p>
        )}

        <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: 4 }}>
          Full name
        </label>
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          style={{ width: '100%', marginBottom: 'var(--space-3)', padding: '8px' }}
        />

        <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: 4 }}>
          Email
        </label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="name@company.com"
          style={{ width: '100%', marginBottom: 4, padding: '8px' }}
        />
        <p style={{ fontSize: '12px', color: 'var(--neutral-500)', margin: '0 0 var(--space-3)' }}>
          Used to sign in to the dashboard. Must be unique across all organizations.
        </p>

        <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: 4 }}>
          Temporary password
        </label>
        <input
          type="text"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ width: '100%', marginBottom: 4, padding: '8px' }}
        />
        <p style={{ fontSize: '12px', color: 'var(--neutral-500)', margin: '0 0 var(--space-3)' }}>
          Shown as plain text on purpose — you need to pass it on. Ask them to change it after
          their first sign-in.
        </p>

        <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: 4 }}>
          Role
        </label>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          style={{ width: '100%', marginBottom: 'var(--space-3)', padding: '8px' }}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r] || r}
            </option>
          ))}
        </select>

        <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: 4 }}>
          WhatsApp number <span style={{ fontWeight: 400, color: 'var(--neutral-500)' }}>(optional)</span>
        </label>
        <input
          value={whatsapp}
          onChange={(e) => setWhatsapp(e.target.value)}
          placeholder="919876543210"
          style={{ width: '100%', marginBottom: 4, padding: '8px' }}
        />
        <p style={{ fontSize: '12px', color: 'var(--neutral-500)', margin: '0 0 var(--space-4)' }}>
          Setting this links the number to them straight away — they can message the assistant as
          soon as they're added. You can add it later instead.
        </p>

        <div
          style={{
            background: 'var(--neutral-100)',
            borderRadius: 'var(--radius)',
            padding: '10px 12px',
            fontSize: '12px',
            color: 'var(--neutral-600)',
            marginBottom: 'var(--space-4)',
          }}
        >
          {role === 'ADMIN'
            ? 'Admins reach every project in the organization automatically.'
            : 'They start with no project access. Use "Edit access" afterwards to assign projects and sites.'}
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 'var(--space-2)',
            borderTop: '1px solid var(--border-strong)',
            paddingTop: 'var(--space-4)',
          }}
        >
          <button className="btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button className="btn-primary" onClick={submit} disabled={!canSubmit}>
            {saving ? 'Adding…' : 'Add user'}
          </button>
        </div>
      </div>
    </div>
  );
}
