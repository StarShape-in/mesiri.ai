/**
 * Post-login landing. Routes by role:
 *   Driver           → driver home
 *   Operator / Admin → operator home
 * (This screen only renders when logged in — see the guard in _layout.tsx.)
 */
import DriverHomeScreen from '@/screens/driver/HomeScreen';
import OperatorHomeScreen from '@/screens/operator/HomeScreen';
import { useAuth } from '@/lib/auth-context';
import { DriverLiveTracking } from '@/lib/DriverLiveTracking';

export default function Index() {
  const { role } = useAuth();
  if (role === 'Driver') {
    return (
      <>
        <DriverHomeScreen />
        <DriverLiveTracking />
      </>
    );
  }
  return <OperatorHomeScreen />;
}
