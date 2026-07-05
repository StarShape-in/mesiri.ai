import { House, GitCommitVertical, Sparkles, ChartNoAxesColumnIncreasing, HardHat } from 'lucide-react-native';

export type NavItemConfig = {
  id: string;
  label: string;
  href: string;
  icon: any;
  isAction?: boolean;
};

export const NAVIGATION_CONFIG: NavItemConfig[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    href: '/', // Maps to /app/(app)/index
    icon: House,
  },
  {
    id: 'timeline',
    label: 'Timeline',
    href: '/timeline',
    icon: GitCommitVertical,
  },
  {
    id: 'ai',
    label: 'Mesiri AI',
    href: '#ai', // Not a real route, triggers action
    icon: Sparkles,
    isAction: true,
  },
  {
    id: 'analytics',
    label: 'Analytics',
    href: '/analytics',
    icon: ChartNoAxesColumnIncreasing,
  },
  {
    id: 'field',
    label: 'Field',
    href: '/field',
    icon: HardHat,
  },
];
