import { useState, useRef, useEffect } from 'react';
import { 
  Bell, 
  ChevronDown, 
  User, 
  Settings, 
  LogOut, 
  Building2, 
  Plus, 
  LayoutDashboard, 
  Truck, 
  Users, 
  FileText, 
  PieChart,
  Receipt,
  Menu
} from 'lucide-react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { authStore } from '@/store/authStore';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface HeaderProps {
  title?: string;
  breadcrumb?: string;
  /** Opens the off-canvas sidebar — only rendered below lg */
  onMenuClick?: () => void;
}

export default function Header({ title, breadcrumb, onMenuClick }: HeaderProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const user = authStore.getUser();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const initials = user?.name ? user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'OP';
  const firstName = user?.name ? user.name.split(' ')[0] : 'Operator';

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    authStore.clearSession();
    navigate('/login');
  };

  const navRoutes = [
    { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, activeClass: 'bg-violet-600 text-white shadow-2xs', iconActive: 'text-white', iconInactive: 'text-violet-500', hoverClass: 'hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-950/30 dark:hover:text-violet-300' },
    { label: 'Trips',     path: '/trips',      icon: Truck,            activeClass: 'bg-indigo-600 text-white shadow-2xs', iconActive: 'text-white', iconInactive: 'text-indigo-500', hoverClass: 'hover:bg-indigo-50 hover:text-indigo-700 dark:hover:bg-indigo-950/30 dark:hover:text-indigo-300' },
    { label: 'Vehicles',  path: '/vehicles',   icon: Truck,            activeClass: 'bg-blue-600 text-white shadow-2xs',   iconActive: 'text-white', iconInactive: 'text-blue-500',   hoverClass: 'hover:bg-blue-50 hover:text-blue-700 dark:hover:bg-blue-950/30 dark:hover:text-blue-300' },
    { label: 'Drivers',   path: '/drivers',    icon: Users,            activeClass: 'bg-emerald-600 text-white shadow-2xs', iconActive: 'text-white', iconInactive: 'text-emerald-500', hoverClass: 'hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-950/30 dark:hover:text-emerald-300' },
    { label: 'Rate Cards',path: '/rate-cards', icon: FileText,         activeClass: 'bg-[#E8450F] text-white shadow-2xs',  iconActive: 'text-white', iconInactive: 'text-orange-500', hoverClass: 'hover:bg-orange-50 hover:text-orange-700 dark:hover:bg-orange-950/30 dark:hover:text-orange-300' },
    { label: 'Customers', path: '/customers',  icon: Building2,        activeClass: 'bg-cyan-600 text-white shadow-2xs',   iconActive: 'text-white', iconInactive: 'text-cyan-500',   hoverClass: 'hover:bg-cyan-50 hover:text-cyan-700 dark:hover:bg-cyan-950/30 dark:hover:text-cyan-300' },
    { label: 'Invoices',  path: '/invoices',   icon: Receipt,          activeClass: 'bg-amber-500 text-white shadow-2xs',  iconActive: 'text-white', iconInactive: 'text-amber-500',  hoverClass: 'hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-950/30 dark:hover:text-amber-300' },
    { label: 'Reports',   path: '/reports',    icon: PieChart,         activeClass: 'bg-rose-600 text-white shadow-2xs',   iconActive: 'text-white', iconInactive: 'text-rose-500',   hoverClass: 'hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/30 dark:hover:text-rose-300' },
  ];

  return (
    <div className="shrink-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-3 sm:px-4 lg:px-6 h-[56px] lg:h-[62px] flex items-center justify-between gap-2 sm:gap-4 relative z-20">

      {/* Mobile: hamburger + current page title (route pills live in the drawer) */}
      <div className="flex items-center gap-2.5 min-w-0 lg:hidden">
        <button
          onClick={onMenuClick}
          aria-label="Open navigation menu"
          className="p-2 -ml-1 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0"
        >
          <Menu size={20} />
        </button>
        <div className="min-w-0">
          <p className="text-sm font-extrabold text-slate-900 dark:text-slate-100 truncate leading-tight">
            {title || 'MERCON'}
          </p>
          {breadcrumb && (
            <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate leading-tight">{breadcrumb}</p>
          )}
        </div>
      </div>

      {/* Center-Left: Horizontal Route Navigation Hub (lg and up) */}
      <div
        className="hidden lg:flex items-center gap-3 min-w-0 overflow-x-auto scrollbar-none"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >

        {/* HORIZONTAL ROUTE PILL BAR */}
        <div className="bg-white dark:bg-slate-800/80 p-1.5 rounded-xl flex items-center gap-1.5 border border-slate-200/80 dark:border-slate-700 shrink-0">
          {navRoutes.map((route) => {
            const isActive = location.pathname === route.path || (route.path !== '/dashboard' && location.pathname.startsWith(route.path));
            const Icon = route.icon;
            
            return (
              <Link
                key={route.path}
                to={route.path}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  isActive 
                    ? route.activeClass
                    : `text-slate-500 dark:text-slate-400 ${route.hoverClass}`
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? route.iconActive : route.iconInactive}`} />
                <span>{route.label}</span>
              </Link>
            );
          })}

          {/* Quick Create Dropdown Pill */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button 
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:border-[#E8450F] transition-all shadow-2xs ml-1"
                title="Quick Create Action"
              >
                <Plus className="w-3.5 h-3.5 text-[#E8450F]" />
                <span>New</span>
                <ChevronDown className="w-3 h-3 text-slate-400" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52 p-1.5 shadow-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl">
              <DropdownMenuLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
                Quick Create Workflows
              </DropdownMenuLabel>
              <DropdownMenuItem onClick={() => navigate('/trips/new')} className="cursor-pointer text-xs font-semibold py-1.5 px-2 rounded-md">
                <Truck className="w-3.5 h-3.5 mr-2 text-indigo-600" /> New Dispatch Trip
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/vehicles/new')} className="cursor-pointer text-xs font-semibold py-1.5 px-2 rounded-md">
                <Truck className="w-3.5 h-3.5 mr-2 text-blue-600" /> Register Vehicle
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/drivers/new')} className="cursor-pointer text-xs font-semibold py-1.5 px-2 rounded-md">
                <Users className="w-3.5 h-3.5 mr-2 text-emerald-600" /> Onboard Driver
              </DropdownMenuItem>
              <DropdownMenuSeparator className="my-1 bg-slate-200/50 dark:bg-slate-800" />
              <DropdownMenuItem onClick={() => navigate('/rate-cards/new')} className="cursor-pointer text-xs font-semibold py-1.5 px-2 rounded-md">
                <FileText className="w-3.5 h-3.5 mr-2 text-[#E8450F]" /> Create Rate Card
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/invoices/new')} className="cursor-pointer text-xs font-semibold py-1.5 px-2 rounded-md">
                <Receipt className="w-3.5 h-3.5 mr-2 text-purple-600" /> Generate Invoice
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

        </div>

      </div>

      {/* Right Side Controls */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">

        {/* Quick Create — mobile only (the desktop one lives in the pill bar) */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="lg:hidden w-8.5 h-8.5 rounded-xl bg-[#E8450F] text-white flex items-center justify-center transition-colors hover:bg-[#C7380A] shadow-2xs"
              aria-label="Quick create"
            >
              <Plus className="w-4 h-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52 p-1.5 shadow-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl">
            <DropdownMenuLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
              Quick Create Workflows
            </DropdownMenuLabel>
            <DropdownMenuItem onClick={() => navigate('/trips/new')} className="cursor-pointer text-xs font-semibold py-2 px-2 rounded-md">
              <Truck className="w-3.5 h-3.5 mr-2 text-indigo-600" /> New Dispatch Trip
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate('/vehicles/new')} className="cursor-pointer text-xs font-semibold py-2 px-2 rounded-md">
              <Truck className="w-3.5 h-3.5 mr-2 text-blue-600" /> Register Vehicle
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate('/drivers/new')} className="cursor-pointer text-xs font-semibold py-2 px-2 rounded-md">
              <Users className="w-3.5 h-3.5 mr-2 text-emerald-600" /> Onboard Driver
            </DropdownMenuItem>
            <DropdownMenuSeparator className="my-1 bg-slate-200/50 dark:bg-slate-800" />
            <DropdownMenuItem onClick={() => navigate('/rate-cards/new')} className="cursor-pointer text-xs font-semibold py-2 px-2 rounded-md">
              <FileText className="w-3.5 h-3.5 mr-2 text-[#E8450F]" /> Create Rate Card
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate('/invoices/new')} className="cursor-pointer text-xs font-semibold py-2 px-2 rounded-md">
              <Receipt className="w-3.5 h-3.5 mr-2 text-purple-600" /> Generate Invoice
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Notifications trigger */}
        <Link to="/notifications" className="relative group">
          <div className="w-8.5 h-8.5 rounded-xl bg-white dark:bg-slate-800 hover:bg-slate-100/50 dark:hover:bg-slate-700 flex items-center justify-center transition-colors border border-slate-200 dark:border-slate-700">
            <Bell size={15} className="text-slate-600 dark:text-slate-300" />
          </div>
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-[#E8450F] text-white text-[9px] font-extrabold flex items-center justify-center shadow-2xs">
            5
          </span>
        </Link>

        {/* User profile dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button 
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-white dark:bg-slate-800 hover:bg-slate-100/50 dark:hover:bg-slate-700 transition-colors border border-slate-200 dark:border-slate-700"
          >
            <div className="w-5.5 h-5.5 rounded-full bg-[#E8450F] flex items-center justify-center text-white text-[9px] font-black select-none">
              {initials}
            </div>
            <span className="hidden sm:inline text-xs font-bold text-slate-800 dark:text-slate-200 max-w-[80px] truncate">{firstName}</span>
            <ChevronDown size={12} className={`text-slate-400 transition-transform duration-200 ${dropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-1.5 w-48 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-lg py-1.5 animate-fade-in origin-top-right z-50">
              <div className="px-4 py-2 border-b border-slate-200/60 dark:border-slate-800">
                <p className="text-xs font-extrabold text-slate-900 dark:text-slate-100 truncate">{user?.name || 'Mohammed Al-Harbi'}</p>
                <p className="text-[10px] text-slate-500 truncate">{user?.role || 'Operator'}</p>
              </div>
              
              <Link 
                to="/settings/profile" 
                onClick={() => setDropdownOpen(false)}
                className="flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100/50 dark:hover:bg-slate-800 transition-colors"
              >
                <User size={14} className="text-slate-400" />
                My Profile
              </Link>
              
              <Link 
                to="/settings" 
                onClick={() => setDropdownOpen(false)}
                className="flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100/50 dark:hover:bg-slate-800 transition-colors"
              >
                <Settings size={14} className="text-slate-400" />
                Settings
              </Link>

              <div className="border-t border-slate-200/60 dark:border-slate-800 mt-1.5 pt-1.5">
                <button 
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-bold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20 transition-colors"
                >
                  <LogOut size={14} />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
