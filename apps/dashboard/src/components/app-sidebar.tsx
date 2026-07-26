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
  Bot,
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
  items: NavItem[]
  requiredRole?: string
}

const OPERATIONS_CATEGORY: NavCategory = {
  title: 'Operations',
  icon: Activity,
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
  items: [
    { title: 'Overview', url: '/finance/overview', icon: PieChart },
    { title: 'Expenses', url: '/finance/expenses', icon: DollarSign },
    { title: 'Accounts', url: '/finance/accounts', icon: Landmark },
    { title: 'WhatsApp Automations', url: '/finance/whatsapp', icon: Bot },
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
          'w-full flex items-center justify-between font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/80 rounded-md px-2 py-1.5 text-xs transition-colors',
          isChildActive && 'bg-slate-100 dark:bg-slate-800 font-semibold text-slate-900 dark:text-white'
        )}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <IconComp className="size-4 text-slate-600 dark:text-slate-400 shrink-0" />
          <span className="truncate group-data-[collapsible=icon]:hidden">{category.title}</span>
        </div>
        <div className="flex items-center gap-1.5 group-data-[collapsible=icon]:hidden">
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200/60 dark:border-slate-700/60">
            {filteredItems.length}
          </span>
          {isOpen ? (
            <ChevronDown className="size-3.5 text-slate-400 transition-transform duration-200" />
          ) : (
            <ChevronRight className="size-3.5 text-slate-400 transition-transform duration-200" />
          )}
        </div>
      </SidebarMenuButton>

      {/* Submenu Items */}
      {isOpen && !isCollapsedMode && (
        <div className="ml-3 pl-2.5 border-l border-slate-200 dark:border-slate-800 my-0.5 flex flex-col gap-0.5 group-data-[collapsible=icon]:hidden">
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
                    'flex items-center gap-2 px-2 py-1.5 rounded-md text-xs font-medium transition-all duration-150',
                    isLinkActive || isActive
                      ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100/70 dark:hover:bg-slate-800/50'
                  )
                }
              >
                <ItemIcon className="size-3.5 shrink-0 text-slate-500 dark:text-slate-400" />
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
    <Sidebar collapsible="icon" className="border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950">
      <SidebarHeader>
        <div className="flex items-center justify-between px-2.5 py-2 border-b border-slate-200/80 dark:border-slate-800/80">
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="size-7 rounded-md bg-blue-600 text-white flex items-center justify-center font-bold text-xs shadow-xs shrink-0">
              M
            </div>
            <div className="flex flex-col min-w-0 group-data-[collapsible=icon]:hidden">
              <span className="font-semibold text-xs truncate leading-tight text-slate-900 dark:text-slate-100">
                {me?.organization_name ?? 'Mesiri'}
              </span>
              <span className="text-[9px] text-slate-500 dark:text-slate-400 uppercase tracking-wider font-medium">
                Enterprise App
              </span>
            </div>
          </div>
          {showBackButton && (
            <Link
              to={location.pathname.startsWith('/users/') ? '/users' : '/projects'}
              className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors group-data-[collapsible=icon]:hidden size-6 flex items-center justify-center hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md"
              title="Back"
            >
              <ArrowLeft className="size-3.5" />
            </Link>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent className="px-1.5 py-1 gap-1">
        {/* Core Operations Section */}
        <SidebarGroup className="p-1 py-0.5">
          <SidebarGroupLabel className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider text-blue-600 dark:text-blue-400 uppercase whitespace-nowrap px-1.5 h-6">
            <span className="size-1.5 rounded-full bg-blue-600 shrink-0" />
            <span>Core Operations</span>
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-0.5">
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Dashboard">
                  <NavLink
                    to={getUrlWithScope('/overview')}
                    end
                    className={({ isActive }) =>
                      cn(
                        'flex items-center justify-between w-full px-2 py-1.5 rounded-md text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-colors',
                        isActive && 'bg-slate-100 dark:bg-slate-800 font-semibold text-slate-900 dark:text-white'
                      )
                    }
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <LayoutDashboard className="size-4 text-slate-600 dark:text-slate-400 shrink-0" />
                      <span className="truncate">Dashboard</span>
                    </div>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <CollapsibleNavCategory
                category={OPERATIONS_CATEGORY}
                getUrlWithScope={getUrlWithScope}
                pathname={location.pathname}
                allowedScopes={allowed}
                userRole={me?.role}
              />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Financial Management Section */}
        <SidebarGroup className="p-1 py-0.5">
          <SidebarGroupLabel className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider text-emerald-600 dark:text-emerald-400 uppercase whitespace-nowrap px-1.5 h-6">
            <span className="size-1.5 rounded-full bg-emerald-600 shrink-0" />
            <span>Financial Management</span>
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-0.5">
              <CollapsibleNavCategory
                category={FINANCE_CATEGORY}
                getUrlWithScope={getUrlWithScope}
                pathname={location.pathname}
                allowedScopes={allowed}
                userRole={me?.role}
              />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Business & Materials Section */}
        <SidebarGroup className="p-1 py-0.5">
          <SidebarGroupLabel className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider text-purple-600 dark:text-purple-400 uppercase whitespace-nowrap px-1.5 h-6">
            <span className="size-1.5 rounded-full bg-purple-600 shrink-0" />
            <span>Business Operations</span>
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-0.5">
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

        {/* Management & Admin Section */}
        {visibleManagementItems.length > 0 && (
          <SidebarGroup className="p-1 py-0.5">
            <SidebarGroupLabel className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider text-cyan-600 dark:text-cyan-400 uppercase whitespace-nowrap px-1.5 h-6">
              <span className="size-1.5 rounded-full bg-cyan-600 shrink-0" />
              <span>Management & Admin</span>
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu className="gap-0.5">
                {visibleManagementItems.map((item) => {
                  const ItemIcon = item.icon
                  return (
                    <SidebarMenuItem key={item.title}>
                      <SidebarMenuButton asChild tooltip={item.title}>
                        <NavLink
                          to={getUrlWithScope(item.url)}
                          className={({ isActive }) =>
                            cn(
                              'flex items-center justify-between w-full px-2 py-1.5 rounded-md text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-colors',
                              isActive && 'bg-slate-100 dark:bg-slate-800 font-semibold text-slate-900 dark:text-white'
                            )
                          }
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <ItemIcon className="size-4 text-slate-600 dark:text-slate-400 shrink-0" />
                            <span className="truncate">{item.title}</span>
                          </div>
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

      <SidebarFooter className="border-t border-slate-200 dark:border-slate-800 p-1.5">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={() => logout().then(() => window.location.assign('/login'))}
              tooltip="Log out"
              className="hover:bg-red-50 dark:hover:bg-red-950/50 text-slate-700 dark:text-slate-300 hover:text-red-600 dark:hover:text-red-400 transition-colors rounded-md px-2 py-1.5 text-xs"
            >
              <LogOut className="size-4 text-slate-500 shrink-0" />
              <span className="font-medium">Log out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
