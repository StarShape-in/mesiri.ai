import { LayoutDashboard, Building2, LogOut, Users, ArrowLeft } from 'lucide-react'
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
import { useAllowedScopes } from '@/lib/ScopeContext'
import { logout } from '@/lib/api'
import type { ScopeKind } from '@/lib/scope-types'

type NavItem = {
  title: string
  url: string
  icon: typeof LayoutDashboard
  /** Omit to show at every scope the user can reach; set to restrict a nav
   * entry to scopes where it makes sense (e.g. cross-project views only
   * make sense in Portfolio scope). */
  requiredScope?: ScopeKind
  requiredRole?: string
}

const NAV_ITEMS: NavItem[] = [
  { title: 'Overview', url: '/', icon: LayoutDashboard },
  { title: 'Projects & Sites', url: '/projects', icon: Building2, requiredRole: 'ADMIN' },
  { title: 'Users', url: '/users', icon: Users, requiredRole: 'ADMIN' },
]

export function AppSidebar() {
  const { me } = useAuth()
  const allowed = useAllowedScopes()

  const visibleItems = NAV_ITEMS.filter(
    (item) =>
      (!item.requiredScope || allowed.includes(item.requiredScope)) &&
      (!item.requiredRole || me?.role === item.requiredRole)
  )

  const location = useLocation()
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
                    <NavLink to={item.url} end>
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
