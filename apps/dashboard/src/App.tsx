import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AppLayout } from '@/components/app-layout'
import Login from '@/pages/Login'
import Overview from '@/pages/Overview'
import Users from '@/pages/Users'
import UserDetails from '@/pages/UserDetails'
import CompanyDetails from '@/pages/CompanyDetails'
import Projects from '@/pages/Projects'
import ProjectDetails from '@/pages/ProjectDetails'
import FieldReportsPage from '@/pages/FieldReportsPage'
import MaterialsPage from '@/pages/MaterialsPage'
import ExpensesPage from '@/pages/ExpensesPage'
import ReceiptsPage from '@/pages/ReceiptsPage'
import AccountsPage from '@/pages/AccountsPage'
import WhatsAppFinancePage from '@/pages/WhatsAppFinancePage'
import WhatsAppLabourPage from '@/pages/WhatsAppLabourPage'
import WorkersPage from '@/pages/WorkersPage'
import PettyCashPage from '@/pages/PettyCashPage'
import FinanceOverviewPage from '@/pages/FinanceOverviewPage'
import FinanceReportsPage from '@/pages/FinanceReportsPage'
import FinanceSettingsPage from '@/pages/FinanceSettingsPage'
import ExpenseDetailPage from '@/pages/ExpenseDetailPage'
import TransactionsPage from '@/pages/TransactionsPage'
import VendorsPage from '@/pages/VendorsPage'
import CategoriesPage from '@/pages/CategoriesPage'
import { OperationalPlaceholder } from '@/components/operational-placeholder'

import { ToastProvider } from '@/components/ui/toast-notification'

function IndexRedirect() {
  const location = useLocation()
  return <Navigate to={`/overview${location.search}`} replace />
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<AppLayout />}>
        <Route index element={<IndexRedirect />} />
        <Route path="overview" element={<Overview />} />
        <Route path="users" element={<Users />} />
        <Route path="users/:id" element={<UserDetails />} />
        <Route path="company" element={<CompanyDetails />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:id" element={<ProjectDetails />} />

        {/* Operations Section */}
        <Route path="operations" element={<IndexRedirect />} />
        <Route path="operations/overview" element={<Overview />} />
        <Route path="operations/timeline" element={<OperationalPlaceholder title="Operations Timeline" />} />
        <Route path="operations/field-reports" element={<FieldReportsPage />} />
        <Route path="operations/gallery" element={<OperationalPlaceholder title="Operations Gallery" />} />
        <Route path="operations/analytics" element={<OperationalPlaceholder title="Operations Analytics" />} />

        {/* Finance Section */}
        <Route path="finance" element={<Navigate to="/finance/expenses" replace />} />
        <Route path="finance/overview" element={<FinanceOverviewPage />} />
        <Route path="finance/expenses" element={<ExpensesPage />} />
        <Route path="finance/expenses/:id" element={<ExpenseDetailPage />} />
        <Route path="finance/receipts" element={<ReceiptsPage />} />
        <Route path="finance/accounts" element={<AccountsPage />} />
        <Route path="finance/whatsapp" element={<WhatsAppFinancePage />} />
        <Route path="whatsapp/finance" element={<WhatsAppFinancePage />} />
        <Route path="finance/transactions" element={<TransactionsPage />} />
        <Route path="finance/petty-cash" element={<PettyCashPage />} />
        <Route path="finance/vendors" element={<VendorsPage />} />
        <Route path="finance/categories" element={<CategoriesPage />} />
        <Route path="finance/reports" element={<FinanceReportsPage />} />
        <Route path="finance/settings" element={<FinanceSettingsPage />} />

        {/* Materials Section */}
        <Route path="materials" element={<MaterialsPage />} />
        <Route path="materials/overview" element={<MaterialsPage />} />
        <Route path="materials/inventory" element={<OperationalPlaceholder title="Material Inventory" />} />
        <Route path="materials/purchases" element={<OperationalPlaceholder title="Material Purchases" />} />
        <Route path="materials/suppliers" element={<OperationalPlaceholder title="Suppliers" />} />
        <Route path="materials/categories" element={<OperationalPlaceholder title="Material Categories" />} />

        {/* Labour & Workforce Section */}
        <Route path="labour" element={<Navigate to="/labour/attendance" replace />} />
        <Route path="labour/overview" element={<OperationalPlaceholder title="Labour Overview" />} />
        <Route path="labour/attendance" element={<OperationalPlaceholder title="Labour Attendance" />} />
        <Route path="labour/workers" element={<WorkersPage />} />
        <Route path="labour/whatsapp" element={<WhatsAppLabourPage />} />
        <Route path="whatsapp/labour" element={<WhatsAppLabourPage />} />
        <Route path="labour/reports" element={<OperationalPlaceholder title="Labour Reports" />} />
        <Route path="labour/settings" element={<OperationalPlaceholder title="Labour Settings" />} />

        {/* Legacy operational routes fallbacks */}
        <Route path="field-reports" element={<FieldReportsPage />} />
        <Route path="timeline" element={<OperationalPlaceholder title="Timeline" />} />
        <Route path="analytics" element={<OperationalPlaceholder title="Analytics" />} />
        <Route path="gallery" element={<OperationalPlaceholder title="Gallery" />} />
        <Route path="reports" element={<OperationalPlaceholder title="Reports" />} />
        <Route path="expenses" element={<ExpensesPage />} />
        <Route path="petty-cash" element={<PettyCashPage />} />
      </Route>
    </Routes>
    </ToastProvider>
  )
}
