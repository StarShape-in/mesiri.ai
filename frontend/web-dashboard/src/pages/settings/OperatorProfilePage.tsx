import { useEffect, useState, useCallback } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { 
  User, 
  Mail, 
  Phone, 
  Shield, 
  Save, 
  RefreshCw, 
  Building2, 
  KeyRound, 
  Lock, 
  CheckCircle2, 
  AlertCircle, 
  Sliders, 
  Check, 
  RotateCcw, 
  Clock, 
  ShieldCheck, 
  Award, 
  Bell, 
  Laptop, 
  Smartphone, 
  Globe, 
  LogOut,
  IdCard,
  MapPin
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import { authService } from '@/services/authService';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';

// Active sessions interface & data
interface LoginSession {
  id: string;
  device: string;
  browser: string;
  ip: string;
  location: string;
  lastActive: string;
  isCurrent: boolean;
  type: 'desktop' | 'mobile';
}

const INITIAL_SESSIONS: LoginSession[] = [
  { id: 'sess_1', device: 'Windows PC (Chrome)', browser: 'Chrome 126.0', ip: '185.220.101.42', location: 'Riyadh, SA', lastActive: 'Active now', isCurrent: true, type: 'desktop' },
  { id: 'sess_2', device: 'iPhone 15 Pro (Safari)', browser: 'Mobile Safari 17.4', ip: '94.201.18.99', location: 'Jeddah, SA', lastActive: '2 hours ago', isCurrent: false, type: 'mobile' },
  { id: 'sess_3', device: 'MacBook Pro (Firefox)', browser: 'Firefox 127.0', ip: '213.166.138.10', location: 'Dammam, SA', lastActive: 'Yesterday at 18:40', isCurrent: false, type: 'desktop' },
];

export default function OperatorProfilePage() {
  const { data: user, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authService.getMe,
  });

  const [activeTab, setActiveTab] = useState<'identity' | 'security' | 'notifications' | 'preferences'>('identity');
  const [isEditing, setIsEditing] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [sessions, setSessions] = useState<LoginSession[]>(INITIAL_SESSIONS);

  // Profile Form state
  const [form, setForm] = useState({ 
    firstName: '', 
    lastName: '', 
    email: '', 
    phone: '',
    iqamaNumber: '1092837465',
    department: 'Fleet Operations',
    operatingHub: 'Riyadh Logistics Hub',
    timezone: 'Asia/Riyadh (GMT+3)'
  });

  // Password change state
  const [pwd, setPwd] = useState({ current: '', next: '', confirm: '' });
  const [pwdMsg, setPwdMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Notification Toggles
  const [notifications, setNotifications] = useState({
    criticalDelays: true,
    documentExpiry: true,
    creditLimits: true,
    dailyDigest: true,
  });

  // Preferences
  const [preferences, setPreferences] = useState({
    landingPage: '/dashboard',
    compactView: false,
  });

  useEffect(() => {
    if (user) {
      const [firstName = '', ...rest] = (user.name || '').split(' ');
      setForm((prev) => ({
        ...prev,
        firstName,
        lastName: rest.join(' '),
        email: user.email || '',
        phone: user.phone || '',
      }));
    }
  }, [user]);

  const setFormField = (field: keyof typeof form, value: string) => {
    setForm((p) => ({ ...p, [field]: value }));
  };

  const saveMutation = useMutation({
    mutationFn: () =>
      authService.updateMe({
        name: `${form.firstName} ${form.lastName}`.trim(),
        email: form.email || undefined,
        phone: form.phone || undefined,
      }),
    onSuccess: () => { 
      setIsEditing(false); 
      setSaveError(''); 
      setSaveSuccess(true);
      refetch(); 
      setTimeout(() => setSaveSuccess(false), 4000);
    },
    onError: (err: any) => setSaveError(err?.response?.data?.error?.message || 'Failed to update profile settings.'),
  });

  const pwdMutation = useMutation({
    mutationFn: () => authService.changePassword(pwd.current, pwd.next),
    onSuccess: () => { 
      setPwdMsg({ ok: true, text: 'Password successfully updated!' }); 
      setPwd({ current: '', next: '', confirm: '' }); 
      setTimeout(() => setPwdMsg(null), 5000);
    },
    onError: (err: any) => setPwdMsg({ ok: false, text: err?.response?.data?.error?.message || 'Failed to update password.' }),
  });

  const handleSaveProfile = useCallback(() => {
    setSaveError('');
    if (!form.firstName.trim()) {
      setSaveError('First name is required.');
      return;
    }
    saveMutation.mutate();
  }, [form.firstName, saveMutation]);

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPwdMsg(null);
    if (!pwd.current) return setPwdMsg({ ok: false, text: 'Current password is required.' });
    if (pwd.next.length < 8) return setPwdMsg({ ok: false, text: 'New password must be at least 8 characters long.' });
    if (pwd.next !== pwd.confirm) return setPwdMsg({ ok: false, text: 'New passwords do not match.' });
    pwdMutation.mutate();
  };

  const handleRevokeSession = (sessionId: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
  };

  const initials = `${form.firstName[0] ?? ''}${form.lastName[0] ?? ''}`.toUpperCase() || (user?.username?.[0]?.toUpperCase() ?? 'OP');
  const roleTitle = user?.role ? (user.role.charAt(0).toUpperCase() + user.role.slice(1)) : 'Fleet Dispatcher';

  const getPasswordStrength = (pass: string) => {
    if (!pass) return { score: 0, label: 'None', color: 'bg-slate-200' };
    let score = 0;
    if (pass.length >= 8) score += 1;
    if (/[A-Z]/.test(pass)) score += 1;
    if (/[0-9]/.test(pass)) score += 1;
    if (/[^A-Za-z0-9]/.test(pass)) score += 1;

    if (score <= 1) return { score: 25, label: 'Weak', color: 'bg-rose-500' };
    if (score === 2) return { score: 50, label: 'Fair', color: 'bg-amber-500' };
    if (score === 3) return { score: 75, label: 'Good', color: 'bg-blue-500' };
    return { score: 100, label: 'Strong', color: 'bg-emerald-500' };
  };

  const pwdStrength = getPasswordStrength(pwd.next);

  return (
    <DashboardLayout active="Settings" title="Operator Profile">
      <div className="px-4 sm:px-6 pb-6 space-y-5 animate-fade-in max-w-[1250px] mx-auto w-full">

        {/* ── Minimalist Header ───────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
              Operator Profile
            </h1>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Manage personal identity, security credentials, active sessions, and system preferences
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
              className="h-8 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-[#E8450F]' : 'text-slate-500'}`} />
              Refresh
            </Button>

            {isEditing ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { setIsEditing(false); setSaveError(''); refetch(); }}
                  className="h-8 gap-1.5 text-xs text-slate-500 hover:text-slate-900"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Cancel
                </Button>

                <Button
                  size="sm"
                  onClick={handleSaveProfile}
                  disabled={saveMutation.isPending}
                  className="h-8 gap-1.5 text-xs bg-[#E8450F] hover:bg-[#d03d0c] text-white font-bold shadow-xs px-4"
                >
                  <Save className="w-3.5 h-3.5" /> {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                onClick={() => setIsEditing(true)}
                disabled={isLoading}
                className="h-8 gap-1.5 text-xs bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-white text-white dark:text-slate-900 font-bold shadow-xs px-4"
              >
                <User className="w-3.5 h-3.5" /> Edit Profile
              </Button>
            )}
          </div>
        </div>

        {/* ── Status Messages ────────────────────────────────────────────── */}
        {saveError && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-xs font-semibold text-rose-700 dark:text-rose-400 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
            <span>{saveError}</span>
          </div>
        )}

        {saveSuccess && (
          <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span>Profile settings successfully saved.</span>
          </div>
        )}

        {/* ── Clean Flat Profile Summary Card ─────────────────────────────── */}
        <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs p-5">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            
            {/* Avatar & User Details */}
            <div className="flex items-center gap-4">
              <div className="relative shrink-0">
                <div className="w-14 h-14 rounded-xl bg-slate-900 dark:bg-slate-800 flex items-center justify-center text-white text-xl font-bold border border-slate-200 dark:border-slate-700 shadow-2xs">
                  {initials}
                </div>
                <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-white dark:border-slate-900" title="Active"></span>
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                    {form.firstName} {form.lastName}
                  </h2>
                  <Badge variant="outline" className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 text-[10px] font-semibold">
                    {roleTitle}
                  </Badge>
                </div>

                <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2 mt-0.5">
                  <span>{form.email || user?.email || 'No email provided'}</span>
                  <span>•</span>
                  <span className="font-mono text-slate-400">ID: OP-{user?.username?.toUpperCase() || 'SYS'}</span>
                </p>
              </div>
            </div>

            {/* Clean Key Stats Pills */}
            <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
              <div className="bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-700/80 px-3 py-1.5 rounded-lg text-center flex-1 sm:flex-none">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Access Level</div>
                <div className="text-xs font-mono font-bold text-slate-800 dark:text-slate-200">Tier 1 Admin</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-700/80 px-3 py-1.5 rounded-lg text-center flex-1 sm:flex-none">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Security</div>
                <div className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">2FA Active</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-700/80 px-3 py-1.5 rounded-lg text-center flex-1 sm:flex-none">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Location</div>
                <div className="text-xs font-mono font-bold text-slate-800 dark:text-slate-200">Riyadh</div>
              </div>
            </div>

          </div>
        </Card>

        {/* ── Crisp Tabbed Workspace ───────────────────────────────────────── */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full space-y-4">
          <TabsList className="bg-slate-100 dark:bg-slate-800/80 p-1 rounded-lg grid grid-cols-2 sm:grid-cols-4 w-full border border-slate-200/60 dark:border-slate-700">
            <TabsTrigger 
              value="identity" 
              className="text-xs font-semibold gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-slate-100 data-[state=active]:shadow-2xs rounded-md"
            >
              <User className="w-3.5 h-3.5 text-slate-500" />
              <span>Personal Details</span>
            </TabsTrigger>

            <TabsTrigger 
              value="security" 
              className="text-xs font-semibold gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-slate-100 data-[state=active]:shadow-2xs rounded-md"
            >
              <Shield className="w-3.5 h-3.5 text-slate-500" />
              <span>Security & 2FA</span>
            </TabsTrigger>

            <TabsTrigger 
              value="notifications" 
              className="text-xs font-semibold gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-slate-100 data-[state=active]:shadow-2xs rounded-md"
            >
              <Bell className="w-3.5 h-3.5 text-slate-500" />
              <span>Notifications</span>
            </TabsTrigger>

            <TabsTrigger 
              value="preferences" 
              className="text-xs font-semibold gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-slate-100 data-[state=active]:shadow-2xs rounded-md"
            >
              <Sliders className="w-3.5 h-3.5 text-slate-500" />
              <span>Preferences</span>
            </TabsTrigger>
          </TabsList>

          {/* ── TAB 1: Personal Details ────────────────────────────────────── */}
          <TabsContent value="identity" className="m-0">
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
                      Personal Credentials & Assignment
                    </CardTitle>
                    <CardDescription className="text-xs text-slate-500">
                      Official operator contact information and regional logistics assignment.
                    </CardDescription>
                  </div>

                  {!isEditing && (
                    <Button variant="outline" size="sm" onClick={() => setIsEditing(true)} className="h-7 text-xs font-semibold border-slate-200">
                      Edit
                    </Button>
                  )}
                </div>
              </CardHeader>

              <CardContent className="p-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  
                  <div className="space-y-1.5">
                    <Label htmlFor="firstName" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      First Name <span className="text-rose-500">*</span>
                    </Label>
                    <Input
                      id="firstName"
                      value={form.firstName}
                      onChange={(e) => setFormField('firstName', e.target.value)}
                      disabled={!isEditing}
                      placeholder="First Name"
                      className="h-9 text-xs border-slate-200 dark:border-slate-800 disabled:bg-slate-50 dark:disabled:bg-slate-800/40 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="lastName" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Last Name
                    </Label>
                    <Input
                      id="lastName"
                      value={form.lastName}
                      onChange={(e) => setFormField('lastName', e.target.value)}
                      disabled={!isEditing}
                      placeholder="Last Name"
                      className="h-9 text-xs border-slate-200 dark:border-slate-800 disabled:bg-slate-50 dark:disabled:bg-slate-800/40 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="email" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Work Email
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      value={form.email}
                      onChange={(e) => setFormField('email', e.target.value)}
                      disabled={!isEditing}
                      placeholder="operator@mercon.sa"
                      className="h-9 text-xs border-slate-200 dark:border-slate-800 disabled:bg-slate-50 dark:disabled:bg-slate-800/40 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="phone" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Phone Number
                    </Label>
                    <Input
                      id="phone"
                      value={form.phone}
                      onChange={(e) => setFormField('phone', e.target.value)}
                      disabled={!isEditing}
                      placeholder="+966 50 000 0000"
                      className="h-9 text-xs border-slate-200 dark:border-slate-800 disabled:bg-slate-50 dark:disabled:bg-slate-800/40 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="iqama" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Saudi Iqama / National ID Reference
                    </Label>
                    <Input
                      id="iqama"
                      value={form.iqamaNumber}
                      onChange={(e) => setFormField('iqamaNumber', e.target.value)}
                      disabled={!isEditing}
                      className="h-9 text-xs font-mono border-slate-200 dark:border-slate-800 disabled:bg-slate-50 dark:disabled:bg-slate-800/40 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="hub" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Logistics Hub Location
                    </Label>
                    <Input
                      id="hub"
                      value={form.operatingHub}
                      onChange={(e) => setFormField('operatingHub', e.target.value)}
                      disabled={!isEditing}
                      className="h-9 text-xs border-slate-200 dark:border-slate-800 disabled:bg-slate-50 dark:disabled:bg-slate-800/40 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="department" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Department
                    </Label>
                    <Input
                      id="department"
                      value={form.department}
                      onChange={(e) => setFormField('department', e.target.value)}
                      disabled={!isEditing}
                      className="h-9 text-xs border-slate-200 dark:border-slate-800 disabled:bg-slate-50 dark:disabled:bg-slate-800/40 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="timezone" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Timezone
                    </Label>
                    <Input
                      id="timezone"
                      value={form.timezone}
                      onChange={(e) => setFormField('timezone', e.target.value)}
                      disabled={!isEditing}
                      className="h-9 text-xs border-slate-200 dark:border-slate-800 disabled:bg-slate-50 dark:disabled:bg-slate-800/40 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                    />
                  </div>

                </div>
              </CardContent>

              {isEditing && (
                <CardFooter className="border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 p-3 flex justify-end gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setIsEditing(false)} className="text-xs h-8">
                    Cancel
                  </Button>
                  <Button size="sm" onClick={handleSaveProfile} disabled={saveMutation.isPending} className="text-xs h-8 bg-[#E8450F] text-white font-bold">
                    Save Changes
                  </Button>
                </CardFooter>
              )}
            </Card>
          </TabsContent>

          {/* ── TAB 2: Security & 2FA ───────────────────────────────────────── */}
          <TabsContent value="security" className="m-0 space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
              
              {/* Password Form */}
              <Card className="lg:col-span-3 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
                <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
                    Change Account Password
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Update password for accessing system dispatch controls.
                  </CardDescription>
                </CardHeader>

                <form onSubmit={handlePasswordSubmit}>
                  <CardContent className="p-5 space-y-3.5">
                    
                    {pwdMsg && (
                      <div className={cn(
                        'p-2.5 rounded-lg text-xs font-medium flex items-center gap-2 border',
                        pwdMsg.ok 
                          ? 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800' 
                          : 'bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-800'
                      )}>
                        {pwdMsg.ok ? <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" /> : <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />}
                        <span>{pwdMsg.text}</span>
                      </div>
                    )}

                    <div className="space-y-1.5">
                      <Label htmlFor="current_pwd" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                        Current Password
                      </Label>
                      <Input
                        id="current_pwd"
                        type="password"
                        placeholder="••••••••••••"
                        value={pwd.current}
                        onChange={(e) => setPwd((p) => ({ ...p, current: e.target.value }))}
                        className="h-9 text-xs border-slate-200 dark:border-slate-800 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="next_pwd" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                          New Password
                        </Label>
                        {pwd.next && (
                          <span className="text-[10px] font-semibold text-slate-500">
                            Strength: <span className="font-bold text-slate-900 dark:text-slate-100">{pwdStrength.label}</span>
                          </span>
                        )}
                      </div>
                      <Input
                        id="next_pwd"
                        type="password"
                        placeholder="At least 8 characters"
                        value={pwd.next}
                        onChange={(e) => setPwd((p) => ({ ...p, next: e.target.value }))}
                        className="h-9 text-xs border-slate-200 dark:border-slate-800 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                      />
                      
                      {pwd.next && (
                        <div className="w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1">
                          <div className={cn('h-full transition-all duration-300', pwdStrength.color)} style={{ width: `${pwdStrength.score}%` }} />
                        </div>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="confirm_pwd" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                        Confirm New Password
                      </Label>
                      <Input
                        id="confirm_pwd"
                        type="password"
                        placeholder="Re-enter new password"
                        value={pwd.confirm}
                        onChange={(e) => setPwd((p) => ({ ...p, confirm: e.target.value }))}
                        className="h-9 text-xs border-slate-200 dark:border-slate-800 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F]"
                      />
                    </div>

                  </CardContent>

                  <CardFooter className="border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 p-3 flex justify-end">
                    <Button
                      type="submit"
                      disabled={pwdMutation.isPending}
                      className="h-8 text-xs bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-bold px-4 rounded-md focus-visible:ring-[#E8450F]/20"
                    >
                      {pwdMutation.isPending ? 'Updating...' : 'Update Password'}
                    </Button>
                  </CardFooter>
                </form>
              </Card>

              {/* Security Audit */}
              <div className="lg:col-span-2 space-y-4">
                <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
                  <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                    <CardTitle className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                      Security Audit Summary
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-2.5">
                    
                    <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                      <div>
                        <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">Two-Factor Authentication</div>
                        <div className="text-[10px] text-slate-400">MFA token active</div>
                      </div>
                      <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 font-mono text-[10px] font-semibold">
                        ACTIVE
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                      <div>
                        <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">Current Session IP</div>
                        <div className="text-[10px] text-slate-400 font-mono">185.220.101.42 (Riyadh, SA)</div>
                      </div>
                      <Badge variant="outline" className="text-[10px] font-mono border-slate-200">
                        TRUSTED
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                      <div>
                        <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">Token Expiry</div>
                        <div className="text-[10px] text-slate-400">24h token life</div>
                      </div>
                      <span className="text-[10px] font-mono font-bold text-slate-600 dark:text-slate-400">
                        23h left
                      </span>
                    </div>

                  </CardContent>
                </Card>
              </div>

            </div>

            {/* Active Sessions Ledger */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs overflow-hidden">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
                    Authorized Login Sessions
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Active browser and mobile sessions logged into your account.
                  </CardDescription>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono text-slate-500 border-slate-200">
                  {sessions.length} Active
                </Badge>
              </CardHeader>

              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {sessions.map((sess) => (
                  <div key={sess.id} className="p-3.5 flex items-center justify-between hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-400 shrink-0">
                        {sess.type === 'mobile' ? <Smartphone className="w-4 h-4 text-slate-600" /> : <Laptop className="w-4 h-4 text-slate-600" />}
                      </div>

                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">{sess.device}</span>
                          {sess.isCurrent && (
                            <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[9px] font-bold">
                              THIS DEVICE
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-0.5 font-mono">
                          <span>{sess.ip}</span>
                          <span>•</span>
                          <span>{sess.location}</span>
                          <span>•</span>
                          <span>{sess.lastActive}</span>
                        </div>
                      </div>
                    </div>

                    {!sess.isCurrent && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRevokeSession(sess.id)}
                        className="h-7 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/30 gap-1 font-medium"
                      >
                        Revoke
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </TabsContent>

          {/* ── TAB 3: Notifications ───────────────────────────────────────── */}
          <TabsContent value="notifications" className="m-0">
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Notification Alert Preferences
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Select which events trigger automated email and system alerts.
                </CardDescription>
              </CardHeader>

              <CardContent className="p-5 space-y-3">
                
                <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div>
                    <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">Critical Fleet Delays</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Alerts when trips exceed SLA tolerance limits (+30 mins)</div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setNotifications((n) => ({ ...n, criticalDelays: !n.criticalDelays }))}
                    className={cn(
                      'h-7 text-[11px] font-semibold min-w-[80px] rounded-md transition-all',
                      notifications.criticalDelays ? 'bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900' : 'text-slate-400'
                    )}
                  >
                    {notifications.criticalDelays ? 'ENABLED' : 'OFF'}
                  </Button>
                </div>

                <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div>
                    <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">Saudi MOT & Document Expirations</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Notifications when permits enter 30-day expiry window</div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setNotifications((n) => ({ ...n, documentExpiry: !n.documentExpiry }))}
                    className={cn(
                      'h-7 text-[11px] font-semibold min-w-[80px] rounded-md transition-all',
                      notifications.documentExpiry ? 'bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900' : 'text-slate-400'
                    )}
                  >
                    {notifications.documentExpiry ? 'ENABLED' : 'OFF'}
                  </Button>
                </div>

                <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div>
                    <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">Customer Credit Exposure Warnings</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Alerts when corporate accounts reach 85% credit capacity</div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setNotifications((n) => ({ ...n, creditLimits: !n.creditLimits }))}
                    className={cn(
                      'h-7 text-[11px] font-semibold min-w-[80px] rounded-md transition-all',
                      notifications.creditLimits ? 'bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900' : 'text-slate-400'
                    )}
                  >
                    {notifications.creditLimits ? 'ENABLED' : 'OFF'}
                  </Button>
                </div>

                <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div>
                    <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">Daily Morning Operations Digest</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Daily summary email of trips, fleet metrics, and active revenue</div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setNotifications((n) => ({ ...n, dailyDigest: !n.dailyDigest }))}
                    className={cn(
                      'h-7 text-[11px] font-semibold min-w-[80px] rounded-md transition-all',
                      notifications.dailyDigest ? 'bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900' : 'text-slate-400'
                    )}
                  >
                    {notifications.dailyDigest ? 'ENABLED' : 'OFF'}
                  </Button>
                </div>

              </CardContent>
            </Card>
          </TabsContent>

          {/* ── TAB 4: Preferences ─────────────────────────────────────────── */}
          <TabsContent value="preferences" className="m-0 space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              
              {/* System Role */}
              <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
                <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
                    System Role & Privileges
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Assigned access level and granted operational scopes.
                  </CardDescription>
                </CardHeader>

                <CardContent className="p-5 space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Username</Label>
                      <Input value={user?.username || 'operator'} disabled className="h-8 font-mono text-xs bg-slate-50 dark:bg-slate-800/40" />
                    </div>

                    <div className="space-y-1">
                      <Label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Role</Label>
                      <Input value={user?.role || 'Admin'} disabled className="h-8 font-mono font-bold text-xs bg-slate-50 dark:bg-slate-800/40 text-slate-900 dark:text-slate-100" />
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">Granted System Scopes</div>
                    <div className="flex flex-wrap gap-1.5">
                      {[
                        'Trip Dispatch Write',
                        'Vehicle Ledger Read',
                        'Driver Management Write',
                        'Rate Card Authoring',
                        'Invoice Approval',
                        'System Audit Logs'
                      ].map((perm) => (
                        <Badge key={perm} variant="outline" className="bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[10px] font-medium py-0.5 px-2 rounded border-slate-200 dark:border-slate-700">
                          <Check className="w-3 h-3 text-emerald-500 mr-1" /> {perm}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Startup Page & Density */}
              <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
                <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
                    Startup & View Settings
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Customize your personal view and landing page preferences.
                  </CardDescription>
                </CardHeader>

                <CardContent className="p-5 space-y-4">
                  
                  <div className="space-y-1.5">
                    <Label htmlFor="landingPage" className="text-xs font-medium text-slate-700 dark:text-slate-300">
                      Default Startup Page
                    </Label>
                    <Select value={preferences.landingPage} onValueChange={(v) => setPreferences((p) => ({ ...p, landingPage: v }))}>
                      <SelectTrigger className="h-9 text-xs border-slate-200 dark:border-slate-800">
                        <SelectValue placeholder="Select startup page" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="/dashboard" className="text-xs">📊 Dashboard</SelectItem>
                        <SelectItem value="/trips" className="text-xs">🚚 Trips Control Center</SelectItem>
                        <SelectItem value="/vehicles" className="text-xs">🚛 Vehicle Fleet Ledger</SelectItem>
                        <SelectItem value="/drivers" className="text-xs">👤 Driver Roster</SelectItem>
                        <SelectItem value="/documents" className="text-xs">🛡️ Documents Center</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                    <div>
                      <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">Compact Data Mode</div>
                      <div className="text-[10px] text-slate-400">Higher data row density across tables</div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPreferences((p) => ({ ...p, compactView: !p.compactView }))}
                      className={cn(
                        'h-7 text-[11px] font-semibold min-w-[80px] rounded-md transition-all',
                        preferences.compactView ? 'bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900' : 'text-slate-400'
                      )}
                    >
                      {preferences.compactView ? 'ENABLED' : 'OFF'}
                    </Button>
                  </div>

                </CardContent>
              </Card>

            </div>
          </TabsContent>

        </Tabs>

      </div>
    </DashboardLayout>
  );
}
