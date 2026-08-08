import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User, Lock, Eye, EyeOff, ArrowRight, Loader2, ShieldCheck, AlertCircle,
} from 'lucide-react';
import { authStore } from '@/store/authStore';
import { authService } from '@/services/authService';

/* Brand tokens */
const C = {
  orange: '#E8450F',
  orangeDark: '#CF3D0D',
  dark: '#1E1F28',
  sub: '#6E7285',
  border: '#ECEEF3',
  danger: '#F04438',
  success: '#12B76A',
};
const FONT = "'Inter Variable', Inter, system-ui, -apple-system, sans-serif";

const inputCls =
  'w-full h-12 pl-11 pr-4 rounded-xl bg-white text-[15px] text-[#1E1F28] border border-[#ECEEF3] outline-none ' +
  'transition-all duration-200 placeholder:text-[#9AA0AB] hover:border-[#DDE0E6] ' +
  'focus:border-[#E8450F] focus:ring-4 focus:ring-[#E8450F]/15';

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [remember, setRemember] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (authStore.isAuthenticated()) navigate('/', { replace: true });
  }, [navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await authService.login({ username: username.trim(), password });
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="relative min-h-screen w-full flex items-center justify-center lg:justify-end px-6 py-12 lg:pr-[9%] bg-cover bg-center"
      style={{
        fontFamily: FONT,
        color: C.dark,
        backgroundColor: '#F8F9FC',
        backgroundImage: 'url(/login-bg.png)',
      }}
    >
      {/* Logo pinned to the top-right of the page */}
      <img
        src="/mercon-logo.png"
        alt="MERCON Logistics"
        className="absolute top-6 right-6 lg:top-10 lg:right-12 h-12 lg:h-16 w-auto z-10"
      />

      <div className="w-full max-w-[400px] animate-fade-in flex flex-col items-center lg:-translate-y-4">
        <div className="text-center">
          <p className="text-sm font-semibold" style={{ color: C.orange }}>Welcome back</p>
          <h2 className="mt-4 text-[30px] sm:text-[40px] leading-[1.1] font-bold tracking-[-0.02em]">Sign in to your workspace</h2>
        </div>

        <div className="mt-6 w-full rounded-2xl border border-[#ECEEF3] bg-white/95 backdrop-blur-sm p-6 sm:p-8 shadow-[0_28px_70px_-24px_rgba(30,31,40,0.32)]">
          {error && (
            <div className="mb-5 flex items-start gap-2 rounded-xl px-3.5 py-3 text-sm font-medium"
              style={{ background: '#FEF3F2', color: C.danger, border: '1px solid #FEE4E2' }}>
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-[13px] font-medium mb-2" style={{ color: C.dark }}>Username</label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#9AA0AB]">
                  <User size={18} />
                </span>
                <input
                  type="text"
                  required
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={inputCls}
                  placeholder="admin"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-[13px] font-medium" style={{ color: C.dark }}>Password</label>
                <a href="/forgot-password" className="text-[13px] font-semibold hover:underline" style={{ color: C.orange }}>
                  Forgot password?
                </a>
              </div>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#9AA0AB]">
                  <Lock size={18} />
                </span>
                <input
                  type={showPw ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputCls + ' pr-11'}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((s) => !s)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[#9AA0AB] hover:text-[#6E7285] transition-colors"
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <label className="flex items-center gap-2.5 select-none cursor-pointer w-fit">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="w-[18px] h-[18px] rounded-[6px] accent-[#E8450F] cursor-pointer"
              />
              <span className="text-sm" style={{ color: C.sub }}>Keep me signed in</span>
            </label>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 rounded-xl text-white font-semibold text-[15px] flex items-center justify-center gap-2
                         transition-all duration-200 disabled:opacity-70 shadow-[0_6px_16px_-4px_rgba(232,69,15,0.4)]
                         hover:-translate-y-0.5 active:translate-y-0"
              style={{ backgroundColor: C.orange }}
              onMouseEnter={(e: React.MouseEvent<HTMLButtonElement>) => (e.currentTarget.style.backgroundColor = C.orangeDark)}
              onMouseLeave={(e: React.MouseEvent<HTMLButtonElement>) => (e.currentTarget.style.backgroundColor = C.orange)}
            >
              {isLoading ? <Loader2 size={20} className="animate-spin" /> : (<>Sign in<ArrowRight size={18} /></>)}
            </button>
          </form>

          <p className="mt-8 flex items-center justify-center gap-1.5 text-xs" style={{ color: C.sub }}>
            <ShieldCheck size={14} />
            Secure portal · © {new Date().getFullYear()} MERCON Logistics
          </p>
        </div>
      </div>
    </div>
  );
}
