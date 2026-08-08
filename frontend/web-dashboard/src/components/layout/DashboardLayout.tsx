import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

interface DashboardLayoutProps {
  active: string;
  title: string;
  breadcrumb?: string;
  pageTitle?: React.ReactNode;
  pageSub?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

export default function DashboardLayout({
  active,
  title,
  breadcrumb,
  pageTitle,
  pageSub,
  actions,
  children,
}: DashboardLayoutProps) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Close the mobile drawer whenever the route changes
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  // Lock body scroll while the mobile drawer is open
  useEffect(() => {
    if (!sidebarOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, [sidebarOpen]);

  // Escape closes the drawer
  useEffect(() => {
    if (!sidebarOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSidebarOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [sidebarOpen]);

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-white">
      <Sidebar active={active} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex flex-col flex-1 min-w-0 bg-white">
        <Header title={title} breadcrumb={breadcrumb} onMenuClick={() => setSidebarOpen(true)} />
        <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0 relative pt-4 sm:pt-6 bg-white">
          {children}
        </div>
      </div>
    </div>
  );
}
