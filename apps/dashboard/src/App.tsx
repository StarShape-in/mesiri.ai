import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AppLayout } from '@/components/app-layout'
import Login from '@/pages/Login'
import Overview from '@/pages/Overview'
import Users from '@/pages/Users'
import UserDetails from '@/pages/UserDetails'
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
        <Route path="users" element={<Users />} />
        <Route path="users/:id" element={<UserDetails />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:id" element={<ProjectDetails />} />
        <Route path="field-reports" element={<FieldReportsPage />} />
        <Route path="materials" element={<MaterialsPage />} />

        {/* Reusable Operational Shared Placeholders */}
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
