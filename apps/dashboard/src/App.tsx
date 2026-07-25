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
import { OperationalPlaceholder } from '@/components/operational-placeholder'

function IndexRedirect() {
  const location = useLocation()
  return <Navigate to={`/overview${location.search}`} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<AppLayout />}>
        <Route index element={<IndexRedirect />} />
        <Route path="overview" element={<Overview />} />
        <Route path="company" element={<CompanyDetails />} />
        <Route path="users" element={<Users />} />
        <Route path="users/:id" element={<UserDetails />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:id" element={<ProjectDetails />} />

        {/* Operations Section */}
        <Route path="operations/overview" element={<Overview />} />
        <Route path="operations/timeline" element={<OperationalPlaceholder title="Timeline" />} />
        <Route path="operations/field-reports" element={<FieldReportsPage />} />
        <Route path="operations/gallery" element={<OperationalPlaceholder title="Gallery" />} />
        <Route path="operations/analytics" element={<OperationalPlaceholder title="Analytics" />} />

        {/* Finance Section */}
        <Route path="finance/overview" element={<OperationalPlaceholder title="Finance Overview" />} />
        <Route path="finance/expenses" element={<OperationalPlaceholder title="Expenses" />} />
        <Route path="finance/accounts" element={<OperationalPlaceholder title="Accounts" />} />
        <Route path="finance/transactions" element={<OperationalPlaceholder title="Transactions" />} />
        <Route path="finance/petty-cash" element={<OperationalPlaceholder title="Petty Cash" />} />
        <Route path="finance/vendors" element={<OperationalPlaceholder title="Vendors" />} />
        <Route path="finance/categories" element={<OperationalPlaceholder title="Finance Categories" />} />
        <Route path="finance/reports" element={<OperationalPlaceholder title="Finance Reports" />} />
        <Route path="finance/settings" element={<OperationalPlaceholder title="Finance Settings" />} />

        {/* Materials Section */}
        <Route path="materials" element={<MaterialsPage />} />
        <Route path="materials/overview" element={<MaterialsPage />} />
        <Route path="materials/inventory" element={<OperationalPlaceholder title="Material Inventory" />} />
        <Route path="materials/purchases" element={<OperationalPlaceholder title="Material Purchases" />} />
        <Route path="materials/suppliers" element={<OperationalPlaceholder title="Suppliers" />} />
        <Route path="materials/categories" element={<OperationalPlaceholder title="Material Categories" />} />

        {/* Legacy operational routes fallbacks */}
        <Route path="field-reports" element={<FieldReportsPage />} />
        <Route path="timeline" element={<OperationalPlaceholder title="Timeline" />} />
        <Route path="analytics" element={<OperationalPlaceholder title="Analytics" />} />
        <Route path="gallery" element={<OperationalPlaceholder title="Gallery" />} />
        <Route path="reports" element={<OperationalPlaceholder title="Reports" />} />
        <Route path="expenses" element={<OperationalPlaceholder title="Expenses" />} />
        <Route path="petty-cash" element={<OperationalPlaceholder title="Petty Cash" />} />
      </Route>
    </Routes>
  )
}
