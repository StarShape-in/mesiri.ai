import { House, FolderKanban, Sparkles, GitCommitVertical, HardHat } from 'lucide-react-native';

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
    id: 'projects',
    label: 'Projects',
    href: '/projects',
    icon: FolderKanban,
  },
  {
    id: 'ai',
    label: 'Ask Mesiri',
    href: '#ai', // Not a real route, triggers action
    icon: Sparkles,
    isAction: true,
  },
  {
    id: 'timeline',
    label: 'Timeline',
    href: '/timeline',
    icon: GitCommitVertical,
  },
  {
    id: 'field',
    label: 'Field',
    href: '/field',
    icon: HardHat,
  },
];
