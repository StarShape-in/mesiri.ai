import { useState, useEffect } from 'react'
import {
  LayoutDashboard,
  Building2,
  Building,
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
  Boxes,
  Activity,
  Landmark,
  PieChart,
  ArrowLeftRight,
  Store,
  Tags,
  SlidersHorizontal,
  Warehouse,
  ShoppingBag,
  Truck,
  Layers,
  ChevronRight,
  ChevronDown,
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
  useSidebar,
} from '@/components/ui/sidebar'
import { useAuth } from '@/lib/AuthContext'
import { useAllowedScopes, useScope } from '@/lib/ScopeContext'
import { logout } from '@/lib/api'
import type { ScopeKind } from '@/lib/scope-types'
import { cn } from '@/lib/utils'

type NavItem = {
  title: string
  url: string
  icon: React.ElementType
  requiredScope?: ScopeKind
  requiredRole?: string
}

type NavCategory = {
  title: string
  icon: React.ElementType
  color: string
  bgColor: string
  activeBg: string
  activeText: string
  items: NavItem[]
  requiredRole?: string
}

const OPERATIONS_CATEGORY: NavCategory = {
  title: 'Operations',
  icon: Activity,
  color: 'text-amber-500 dark:text-amber-400',
  bgColor: 'bg-amber-500/10 dark:bg-amber-500/20',
  activeBg: 'bg-amber-500/15 dark:bg-amber-500/25',
  activeText: 'text-amber-700 dark:text-amber-300 font-semibold',
  items: [
    { title: 'Overview', url: '/operations/overview', icon: LayoutDashboard },
    { title: 'Timeline', url: '/operations/timeline', icon: History },
    { title: 'Field Reports', url: '/operations/field-reports', icon: ClipboardList },
    { title: 'Gallery', url: '/operations/gallery', icon: ImageIcon },
    { title: 'Analytics', url: '/operations/analytics', icon: BarChart3 },
  ],
}

const FINANCE_CATEGORY: NavCategory = {
  title: 'Finance',
  icon: Landmark,
  color: 'text-emerald-500 dark:text-emerald-400',
  bgColor: 'bg-emerald-500/10 dark:bg-emerald-500/20',
  activeBg: 'bg-emerald-500/15 dark:bg-emerald-500/25',
  activeText: 'text-emerald-700 dark:text-emerald-300 font-semibold',
  items: [
    { title: 'Overview', url: '/finance/overview', icon: PieChart },
    { title: 'Expenses', url: '/finance/expenses', icon: DollarSign },
    { title: 'Accounts', url: '/finance/accounts', icon: Landmark },
    { title: 'Transactions', url: '/finance/transactions', icon: ArrowLeftRight },
    { title: 'Petty Cash', url: '/finance/petty-cash', icon: Wallet },
    { title: 'Vendors', url: '/finance/vendors', icon: Store },
    { title: 'Categories', url: '/finance/categories', icon: Tags },
    { title: 'Reports', url: '/finance/reports', icon: FileText },
    { title: 'Settings', url: '/finance/settings', icon: SlidersHorizontal },
  ],
}

const MATERIALS_CATEGORY: NavCategory = {
  title: 'Materials',
  icon: Boxes,
  color: 'text-indigo-500 dark:text-indigo-400',
  bgColor: 'bg-indigo-500/10 dark:bg-indigo-500/20',
  activeBg: 'bg-indigo-500/15 dark:bg-indigo-500/25',
  activeText: 'text-indigo-700 dark:text-indigo-300 font-semibold',
  items: [
    { title: 'Overview', url: '/materials/overview', icon: Boxes },
    { title: 'Inventory', url: '/materials/inventory', icon: Warehouse },
    { title: 'Purchases', url: '/materials/purchases', icon: ShoppingBag },
    { title: 'Suppliers', url: '/materials/suppliers', icon: Truck },
    { title: 'Categories', url: '/materials/categories', icon: Layers },
  ],
}

const ROOT_MANAGEMENT_ITEMS: NavItem[] = [
  { title: 'Projects & Sites', url: '/projects', icon: Building2, requiredRole: 'ADMIN' },
  { title: 'Users', url: '/users', icon: Users, requiredRole: 'ADMIN' },
  { title: 'Company', url: '/company', icon: Building, requiredRole: 'ADMIN' },
]

function CollapsibleNavCategory({
  category,
  getUrlWithScope,
  pathname,
  allowedScopes,
  userRole,
}: {
  category: NavCategory
  getUrlWithScope: (url: string) => string
  pathname: string
  allowedScopes: ScopeKind[]
  userRole?: string
}) {
  const { state } = useSidebar()
  const isCollapsedMode = state === 'collapsed'

  const filteredItems = category.items.filter(
    (item) =>
      (!item.requiredScope || allowedScopes.includes(item.requiredScope)) &&
      (!item.requiredRole || userRole === item.requiredRole)
  )

  const isChildActive = filteredItems.some(
    (item) => pathname === item.url || (item.url === '/materials/overview' && pathname === '/materials')
  )

  const [isOpen, setIsOpen] = useState(isChildActive)

  useEffect(() => {
    if (isChildActive) {
      setIsOpen(true)
    }
  }, [pathname, isChildActive])

  if (filteredItems.length === 0) return null

  const IconComp = category.icon

  return (
    <SidebarMenuItem>
      {/* Category Toggle Header */}
      <SidebarMenuButton
        onClick={() => setIsOpen((prev) => !prev)}
        tooltip={category.title}
        className={cn(
          'w-full flex items-center justify-between group/cat-btn font-medium transition-colors',
          isChildActive && 'bg-accent/40 font-semibold'
        )}
      >
        <div className="flex items-center gap-2 min-w-0">
          <div className={cn('p-1 rounded-md transition-colors shrink-0', category.bgColor)}>
            <IconComp className={cn('size-4', category.color)} />
          </div>
          <span className="truncate group-data-[collapsible=icon]:hidden">{category.title}</span>
        </div>
        <div className="flex items-center gap-1 group-data-[collapsible=icon]:hidden">
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
            {filteredItems.length}
          </span>
          {isOpen ? (
            <ChevronDown className="size-3.5 text-muted-foreground transition-transform duration-200" />
          ) : (
            <ChevronRight className="size-3.5 text-muted-foreground transition-transform duration-200" />
          )}
        </div>
      </SidebarMenuButton>

      {/* Submenu Items (Shown when expanded or when not in icon-collapsed mode) */}
      {isOpen && !isCollapsedMode && (
        <div className="ml-3.5 pl-2.5 border-l border-sidebar-border/60 my-1 flex flex-col gap-0.5 group-data-[collapsible=icon]:hidden">
          {filteredItems.map((item) => {
            const ItemIcon = item.icon
            const targetUrl = getUrlWithScope(item.url)
            const isActive =
              pathname === item.url ||
              (item.url === '/operations/overview' && pathname === '/overview') ||
              (item.url === '/materials/overview' && pathname === '/materials')

            return (
              <NavLink
                key={item.title}
                to={targetUrl}
                className={({ isActive: isLinkActive }) =>
                  cn(
                    'flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs transition-all duration-150',
                    isLinkActive || isActive
                      ? cn(category.activeBg, category.activeText, 'shadow-2xs')
                      : 'text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent/60'
                  )
                }
              >
                <ItemIcon className={cn('size-3.5 shrink-0 opacity-80', (isActive || pathname === item.url) && category.color)} />
                <span className="truncate">{item.title}</span>
              </NavLink>
            )
          })}
        </div>
      )}
    </SidebarMenuItem>
  )
}

export function AppSidebar() {
  const { me } = useAuth()
  const allowed = useAllowedScopes()
  const { scope } = useScope()
  const location = useLocation()

  const getUrlWithScope = (baseUrl: string) => {
    const isOperational = !['/projects', '/users', '/company'].includes(baseUrl)
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

  const visibleManagementItems = ROOT_MANAGEMENT_ITEMS.filter(
    (item) =>
      (!item.requiredScope || allowed.includes(item.requiredScope)) &&
      (!item.requiredRole || me?.role === item.requiredRole)
  )

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border bg-sidebar/95 backdrop-blur-xs">
      <SidebarHeader>
        <div className="flex items-center justify-between px-2 py-2 border-b border-sidebar-border/50 pb-2.5">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="size-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-bold text-sm shadow-sm shrink-0">
              M
            </div>
            <div className="flex flex-col min-w-0 group-data-[collapsible=icon]:hidden">
              <span className="font-semibold text-sm truncate leading-tight">
                {me?.organization_name ?? 'Mesiri'}
              </span>
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">
                Enterprise App
              </span>
            </div>
          </div>
          {showBackButton && (
            <Link
              to={location.pathname.startsWith('/users/') ? '/users' : '/projects'}
              className="text-muted-foreground hover:text-foreground transition-colors group-data-[collapsible=icon]:hidden size-7 flex items-center justify-center hover:bg-muted rounded-md"
              title="Back"
            >
              <ArrowLeft className="size-4" />
            </Link>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent className="px-1.5 py-1">
        {/* Main Dashboard Section */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[11px] font-medium tracking-wider text-muted-foreground/80 uppercase">
            Main
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Dashboard">
                  <NavLink
                    to={getUrlWithScope('/overview')}
                    end
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2 w-full font-medium transition-colors',
                        isActive && 'bg-blue-500/15 text-blue-700 dark:text-blue-300 font-semibold'
                      )
                    }
                  >
                    <div className="p-1 rounded-md bg-blue-500/10 dark:bg-blue-500/20 text-blue-500 shrink-0">
                      <LayoutDashboard className="size-4" />
                    </div>
                    <span>Dashboard</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Modules Section */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[11px] font-medium tracking-wider text-muted-foreground/80 uppercase">
            Modules
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              <CollapsibleNavCategory
                category={OPERATIONS_CATEGORY}
                getUrlWithScope={getUrlWithScope}
                pathname={location.pathname}
                allowedScopes={allowed}
                userRole={me?.role}
              />
              <CollapsibleNavCategory
                category={FINANCE_CATEGORY}
                getUrlWithScope={getUrlWithScope}
                pathname={location.pathname}
                allowedScopes={allowed}
                userRole={me?.role}
              />
              <CollapsibleNavCategory
                category={MATERIALS_CATEGORY}
                getUrlWithScope={getUrlWithScope}
                pathname={location.pathname}
                allowedScopes={allowed}
                userRole={me?.role}
              />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Management & Administration */}
        {visibleManagementItems.length > 0 && (
          <SidebarGroup>
            <SidebarGroupLabel className="text-[11px] font-medium tracking-wider text-muted-foreground/80 uppercase">
              Management
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {visibleManagementItems.map((item) => {
                  const ItemIcon = item.icon
                  return (
                    <SidebarMenuItem key={item.title}>
                      <SidebarMenuButton asChild tooltip={item.title}>
                        <NavLink
                          to={getUrlWithScope(item.url)}
                          className={({ isActive }) =>
                            cn(
                              'flex items-center gap-2 w-full transition-colors',
                              isActive && 'bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 font-semibold'
                            )
                          }
                        >
                          <div className="p-1 rounded-md bg-cyan-500/10 dark:bg-cyan-500/20 text-cyan-500 shrink-0">
                            <ItemIcon className="size-4" />
                          </div>
                          <span>{item.title}</span>
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border/50 p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={() => logout().then(() => window.location.assign('/login'))}
              tooltip="Log out"
              className="hover:bg-destructive/10 hover:text-destructive transition-colors"
            >
              <LogOut className="size-4 text-muted-foreground group-hover:text-destructive" />
              <span>Log out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
