import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from './api';

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    login(email, password)
      .then(() => navigate('/logs'))
      .catch((err) => {
        setError(err.response?.data?.detail || 'Login failed');
      })
      .finally(() => setSubmitting(false));
  };

  return (
    <div
      className="animate-fade-in"
      style={{
        maxWidth: '360px',
        margin: '10vh auto',
        padding: 'var(--space-8)',
      }}
    >
      <header style={{ marginBottom: 'var(--space-6)', textAlign: 'center' }}>
        <h1>Mesiri Control</h1>
        <p className="subtitle">Platform admin sign-in</p>
      </header>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Email</label>
          <input
            required
            type="email"
            className="form-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Password</label>
          <input
            required
            type="password"
            className="form-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && (
          <p style={{ color: 'var(--error)', fontSize: '13px', marginBottom: 'var(--space-4)' }}>
            {error}
          </p>
        )}

        <button type="submit" className="btn-primary" disabled={submitting} style={{ width: '100%' }}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
