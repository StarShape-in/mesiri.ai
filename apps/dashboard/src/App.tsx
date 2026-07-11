import { Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/components/app-layout'
import Login from '@/pages/Login'
import Overview from '@/pages/Overview'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Overview />} />
      </Route>
    </Routes>
  )
}
