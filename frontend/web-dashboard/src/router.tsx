import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { authStore } from '@/store/authStore';
import FullPageSpinner from '@/components/ui/FullPageSpinner';
import RequireRole from '@/components/auth/RequireRole';

/* ─── Auth pages (eager — small, always needed) ──────────────────────────── */
import LoginPage         from '@/pages/auth/LoginPage';
import ForgotPasswordPage from '@/pages/auth/ForgotPasswordPage';

/* ─── Protected pages (lazy) ────────────────────────────────────────────── */
const DashboardPage           = lazy(() => import('@/pages/dashboard/DashboardPage'));
const NotificationsPage       = lazy(() => import('@/pages/notifications/NotificationsPage'));

// Trips
const TripListPage            = lazy(() => import('@/pages/trips/TripListPage'));
const TripDetailsPage         = lazy(() => import('@/pages/trips/TripDetailsPage'));
const CreateTripPage          = lazy(() => import('@/pages/trips/CreateTripPage'));
const EditTripPage            = lazy(() => import('@/pages/trips/EditTripPage'));
const TripTrackingPage        = lazy(() => import('@/pages/trips/TripTrackingPage'));
const TripCompletionPage      = lazy(() => import('@/pages/trips/TripCompletionPage'));

// Drivers
const DriverListPage          = lazy(() => import('@/pages/drivers/DriverListPage'));
const DriverDetailsPage       = lazy(() => import('@/pages/drivers/DriverDetailsPage'));
const AddDriverPage           = lazy(() => import('@/pages/drivers/AddDriverPage'));
const EditDriverPage          = lazy(() => import('@/pages/drivers/EditDriverPage'));
const DriverDocumentsPage     = lazy(() => import('@/pages/drivers/DriverDocumentsPage'));

// Vehicles
const VehicleListPage         = lazy(() => import('@/pages/vehicles/VehicleListPage'));
const VehicleDetailsPage      = lazy(() => import('@/pages/vehicles/VehicleDetailsPage'));
const AddVehiclePage          = lazy(() => import('@/pages/vehicles/AddVehiclePage'));
const EditVehiclePage         = lazy(() => import('@/pages/vehicles/EditVehiclePage'));
const VehicleDocumentsPage    = lazy(() => import('@/pages/vehicles/VehicleDocumentsPage'));
const MaintenanceListPage     = lazy(() => import('@/pages/maintenance/MaintenanceListPage'));
const MaintenanceDetailsPage  = lazy(() => import('@/pages/maintenance/MaintenanceDetailsPage'));

// Customers
const CustomerListPage        = lazy(() => import('@/pages/customers/CustomerListPage'));
const CustomerDetailsPage     = lazy(() => import('@/pages/customers/CustomerDetailsPage'));
const AddCustomerPage         = lazy(() => import('@/pages/customers/AddCustomerPage'));
const EditCustomerPage        = lazy(() => import('@/pages/customers/EditCustomerPage'));
const CustomerContractsPage   = lazy(() => import('@/pages/customers/CustomerContractsPage'));

// Rate Cards (static/mock for now)
const RateCardListPage        = lazy(() => import('@/pages/rate-cards/RateCardListPage'));
const CreateRateCardPage      = lazy(() => import('@/pages/rate-cards/CreateRateCardPage'));
const RateCardDetailsPage     = lazy(() => import('@/pages/rate-cards/RateCardDetailsPage'));
const EditRateCardPage        = lazy(() => import('@/pages/rate-cards/EditRateCardPage'));
const RateCardDocsPage        = lazy(() => import('@/pages/rate-cards/RateCardDocsPage'));

// Invoices
const InvoiceListPage         = lazy(() => import('@/pages/invoices/InvoiceListPage'));
const InvoiceDetailsPage      = lazy(() => import('@/pages/invoices/InvoiceDetailsPage'));
const InvoicePrintTemplate    = lazy(() => import('@/pages/invoices/InvoicePrintTemplate'));
const CreateInvoicePage       = lazy(() => import('@/pages/invoices/CreateInvoicePage'));
const PaymentStatusPage       = lazy(() => import('@/pages/invoices/PaymentStatusPage'));

// Documents
const DocumentsCenterPage     = lazy(() => import('@/pages/documents/DocumentsCenterPage'));
const ExpiryManagementPage    = lazy(() => import('@/pages/documents/ExpiryManagementPage'));

// Reports
const ReportsDashboardPage    = lazy(() => import('@/pages/reports/ReportsDashboardPage'));
const FleetPerformancePage    = lazy(() => import('@/pages/reports/FleetPerformancePage'));
const RevenueReportsPage      = lazy(() => import('@/pages/reports/RevenueReportsPage'));
const DriverPerformancePage   = lazy(() => import('@/pages/reports/DriverPerformancePage'));
const CustomReportPage        = lazy(() => import('@/pages/reports/CustomReportPage'));
const DelayReportPage         = lazy(() => import('@/pages/reports/DelayReportPage'));

// Settings
const OperatorProfilePage     = lazy(() => import('@/pages/settings/OperatorProfilePage'));
const SettingsPage            = lazy(() => import('@/pages/settings/SettingsPage'));
const UserManagementPage      = lazy(() => import('@/pages/settings/UserManagementPage'));

/* ─── Protected Route wrapper ────────────────────────────────────────────── */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!authStore.isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

/* ─── App Router ─────────────────────────────────────────────────────────── */
export default function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<FullPageSpinner />}>
        <Routes>
          {/* ── Auth (public) ──────────────────────────────────── */}
          <Route path="/login"           element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />

          {/* ── Protected ────────────────────────────────────── */}
          <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />

          {/* Trips */}
          <Route path="/trips"                    element={<ProtectedRoute><TripListPage /></ProtectedRoute>} />
          <Route path="/trips/new"                element={<ProtectedRoute><CreateTripPage /></ProtectedRoute>} />
          <Route path="/trips/:id"                element={<ProtectedRoute><TripDetailsPage /></ProtectedRoute>} />
          <Route path="/trips/:id/edit"           element={<ProtectedRoute><EditTripPage /></ProtectedRoute>} />
          <Route path="/trips/:id/track"          element={<ProtectedRoute><TripTrackingPage /></ProtectedRoute>} />
          <Route path="/trips/:id/completion"     element={<ProtectedRoute><TripCompletionPage /></ProtectedRoute>} />

          {/* Drivers */}
          <Route path="/drivers"                  element={<ProtectedRoute><DriverListPage /></ProtectedRoute>} />
          <Route path="/drivers/new"              element={<ProtectedRoute><AddDriverPage /></ProtectedRoute>} />
          <Route path="/drivers/:id"              element={<ProtectedRoute><DriverDetailsPage /></ProtectedRoute>} />
          <Route path="/drivers/:id/edit"         element={<ProtectedRoute><EditDriverPage /></ProtectedRoute>} />
          <Route path="/drivers/:id/documents"    element={<ProtectedRoute><DriverDocumentsPage /></ProtectedRoute>} />

          {/* Vehicles */}
          <Route path="/vehicles"                 element={<ProtectedRoute><VehicleListPage /></ProtectedRoute>} />
          <Route path="/vehicles/new"             element={<ProtectedRoute><AddVehiclePage /></ProtectedRoute>} />
          <Route path="/vehicles/:id"             element={<ProtectedRoute><VehicleDetailsPage /></ProtectedRoute>} />
          <Route path="/vehicles/:id/edit"        element={<ProtectedRoute><EditVehiclePage /></ProtectedRoute>} />
          <Route path="/vehicles/:id/documents"   element={<ProtectedRoute><VehicleDocumentsPage /></ProtectedRoute>} />
          <Route path="/maintenance"              element={<ProtectedRoute><MaintenanceListPage /></ProtectedRoute>} />
          <Route path="/maintenance/:id"          element={<ProtectedRoute><MaintenanceDetailsPage /></ProtectedRoute>} />

          {/* Customers */}
          <Route path="/customers"                element={<ProtectedRoute><CustomerListPage /></ProtectedRoute>} />
          <Route path="/customers/new"            element={<ProtectedRoute><AddCustomerPage /></ProtectedRoute>} />
          <Route path="/customers/:id"            element={<ProtectedRoute><CustomerDetailsPage /></ProtectedRoute>} />
          <Route path="/customers/:id/edit"       element={<ProtectedRoute><EditCustomerPage /></ProtectedRoute>} />
          <Route path="/customers/:id/contracts"  element={<ProtectedRoute><CustomerContractsPage /></ProtectedRoute>} />

          {/* Rate Cards */}
          <Route path="/rate-cards"               element={<ProtectedRoute><RateCardListPage /></ProtectedRoute>} />
          <Route path="/rate-cards/new"           element={<ProtectedRoute><CreateRateCardPage /></ProtectedRoute>} />
          <Route path="/rate-cards/:id"            element={<ProtectedRoute><RateCardDetailsPage /></ProtectedRoute>} />
          <Route path="/rate-cards/:id/edit"      element={<ProtectedRoute><EditRateCardPage /></ProtectedRoute>} />
          <Route path="/rate-cards/:id/documents" element={<ProtectedRoute><RateCardDocsPage /></ProtectedRoute>} />

          {/* Invoices */}
          <Route path="/invoices"                 element={<ProtectedRoute><InvoiceListPage /></ProtectedRoute>} />
          <Route path="/invoices/new"             element={<ProtectedRoute><CreateInvoicePage /></ProtectedRoute>} />
          <Route path="/invoices/:id"             element={<ProtectedRoute><InvoiceDetailsPage /></ProtectedRoute>} />
          <Route path="/invoices/:id/print"       element={<ProtectedRoute><InvoicePrintTemplate /></ProtectedRoute>} />
          <Route path="/invoices/:id/payment"     element={<ProtectedRoute><PaymentStatusPage /></ProtectedRoute>} />

          {/* Documents */}
          <Route path="/documents"                element={<ProtectedRoute><DocumentsCenterPage /></ProtectedRoute>} />
          <Route path="/documents/expiry"         element={<ProtectedRoute><ExpiryManagementPage /></ProtectedRoute>} />

          {/* Reports */}
          <Route path="/reports"                  element={<ProtectedRoute><ReportsDashboardPage /></ProtectedRoute>} />
          <Route path="/reports/custom"           element={<ProtectedRoute><CustomReportPage /></ProtectedRoute>} />
          <Route path="/reports/fleet"            element={<ProtectedRoute><FleetPerformancePage /></ProtectedRoute>} />
          <Route path="/reports/revenue"          element={<ProtectedRoute><RevenueReportsPage /></ProtectedRoute>} />
          <Route path="/reports/drivers"          element={<ProtectedRoute><DriverPerformancePage /></ProtectedRoute>} />
          <Route path="/reports/delays"           element={<ProtectedRoute><DelayReportPage /></ProtectedRoute>} />

          {/* Settings */}
          <Route path="/settings"                 element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          <Route path="/settings/profile"         element={<ProtectedRoute><OperatorProfilePage /></ProtectedRoute>} />
          <Route path="/settings/users"           element={<ProtectedRoute><RequireRole roles={['Admin', 'Operator']}><UserManagementPage /></RequireRole></ProtectedRoute>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
