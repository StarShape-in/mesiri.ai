import {
  LayoutDashboard,
  Building2,
  LogOut,
  Users,
  ArrowLeft,
  History,
  BarChart3,
  Image as ImageIcon,
  FileText,
  ClipboardList,
  DollarSign,
  Wallet,
} from 'lucide-react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { useAuth } from '@/lib/AuthContext'
import { useAllowedScopes, useScope } from '@/lib/ScopeContext'
import { logout } from '@/lib/api'
import type { ScopeKind } from '@/lib/scope-types'

type NavItem = {
  title: string
  url: string
  icon: any
  requiredScope?: ScopeKind
  requiredRole?: string
}

const NAV_ITEMS: NavItem[] = [
  { title: 'Overview', url: '/overview', icon: LayoutDashboard },
  { title: 'Timeline', url: '/timeline', icon: History },
  { title: 'Analytics', url: '/analytics', icon: BarChart3 },
  { title: 'Gallery', url: '/gallery', icon: ImageIcon },
  { title: 'Reports', url: '/reports', icon: FileText },
  { title: 'Field Reports', url: '/field-reports', icon: ClipboardList },
  { title: 'Expenses', url: '/expenses', icon: DollarSign },
  { title: 'Petty Cash', url: '/petty-cash', icon: Wallet },
  { title: 'Projects & Sites', url: '/projects', icon: Building2, requiredRole: 'ADMIN' },
  { title: 'Users', url: '/users', icon: Users, requiredRole: 'ADMIN' },
]

export function AppSidebar() {
  const { me } = useAuth()
  const allowed = useAllowedScopes()
  const { scope } = useScope()
  const location = useLocation()

  const visibleItems = NAV_ITEMS.filter(
    (item) =>
      (!item.requiredScope || allowed.includes(item.requiredScope)) &&
      (!item.requiredRole || me?.role === item.requiredRole)
  )

  const getUrlWithScope = (baseUrl: string) => {
    const isOperational = !['/projects', '/users'].includes(baseUrl)
    if (!isOperational) return baseUrl

    const params = new URLSearchParams()
    if (scope.mode === 'project' || scope.mode === 'site') {
      params.set('project', scope.projectId)
    }
    if (scope.mode === 'site') {
      params.set('site', scope.siteId)
    }
    const qs = params.toString()
    return qs ? `${baseUrl}?${qs}` : baseUrl
  }

  const showBackButton = location.pathname.startsWith('/projects/') || location.pathname.startsWith('/users/')

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center justify-between px-2 py-1.5">
          <div className="flex items-center gap-2">
            <Building2 className="size-5" />
            <span className="font-semibold group-data-[collapsible=icon]:hidden">
              {me?.organization_name ?? 'Mesiri'}
            </span>
          </div>
          {showBackButton && (
            <Link
              to={location.pathname.startsWith('/users/') ? '/users' : '/projects'}
              className="text-muted-foreground hover:text-foreground transition-colors group-data-[collapsible=icon]:hidden size-7 flex items-center justify-center hover:bg-muted rounded"
              title="Back"
            >
              <ArrowLeft className="size-4" />
            </Link>
          )}
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Dashboard</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {visibleItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <NavLink to={getUrlWithScope(item.url)} end={item.url === '/overview'}>
                      <item.icon />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={() => logout().then(() => window.location.assign('/login'))} tooltip="Log out">
              <LogOut />
              <span>Log out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
