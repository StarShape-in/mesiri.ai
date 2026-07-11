import { LayoutDashboard, Building2, LogOut } from 'lucide-react'
import { NavLink } from 'react-router-dom'
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
}

const NAV_ITEMS: NavItem[] = [{ title: 'Overview', url: '/', icon: LayoutDashboard }]

export function AppSidebar() {
  const { me } = useAuth()
  const allowed = useAllowedScopes()

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.requiredScope || allowed.includes(item.requiredScope)
  )

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1.5">
          <Building2 className="size-5" />
          <span className="font-semibold group-data-[collapsible=icon]:hidden">
            {me?.organization_name ?? 'Mesiri'}
          </span>
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
