/** Route: /trip/navigate — live map to the delivery stop; auto-detects arrival (InTransit -> AtDelivery). */
import LiveNavigationScreen from '@/screens/driver/LiveNavigationScreen';

export default function NavigateRoute() {
  return <LiveNavigationScreen />;
}
