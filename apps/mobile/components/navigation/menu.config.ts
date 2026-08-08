import { FolderKanban, Images, FileText, WalletCards, Settings, HelpCircle, Palette, LucideIcon, Boxes } from 'lucide-react-native';
import { Capability } from '../../app/_layout';

export type DrawerSectionId = 'management' | 'settings';

export type DrawerNavigationItem = {
  id: string;
  label: string;
  icon: LucideIcon;
  route: string;
  requiredCapability?: Capability;
  badgeSource?: string;
  section: DrawerSectionId;
};

export const drawerNavigationItems: DrawerNavigationItem[] = [
  // Primary Management
  {
    id: 'projects',
    label: 'Projects',
    icon: FolderKanban,
    route: '/projects',
    requiredCapability: 'projects.view',
    section: 'management',
  },
  {
    id: 'materials',
    label: 'Materials Log',
    icon: Boxes,
    route: '/field/materials',
    requiredCapability: 'projects.view',
    section: 'management',
  },
  {
    id: 'gallery',
    label: 'Gallery',
    icon: Images,
    route: '/gallery',
    requiredCapability: 'gallery.view',
    section: 'management',
  },
  {
    id: 'dprs',
    label: 'DPRs',
    icon: FileText,
    route: '/dprs',
    requiredCapability: 'dprs.view',
    section: 'management',
  },
  {
    id: 'expenses',
    label: 'Expenses & Petty Cash',
    icon: WalletCards,
    route: '/expenses',
    requiredCapability: 'expenses.view',
    section: 'management',
  },
  // Settings & Account
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    route: '/settings',
    section: 'settings',
  },
  {
    id: 'theme',
    label: 'Theme',
    icon: Palette,
    route: '/settings/theme',
    section: 'settings',
  },
  {
    id: 'help',
    label: 'Help & Support',
    icon: HelpCircle,
    route: '/support',
    section: 'settings',
  },
];
