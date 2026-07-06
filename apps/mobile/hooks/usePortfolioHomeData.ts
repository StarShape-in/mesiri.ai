import { useState, useEffect } from 'react';
import { StatusType } from '../components/ui/StatusBadge';
import { AttentionSeverity } from '../components/features/AttentionItem';
import { ReportingStatusType } from '../components/features/ReportingStatusRow';
import { FileWarning, Banknote, HardHat, TrendingDown, Clock } from 'lucide-react-native';

export type PortfolioData = {
  aiBrief: string | null;
  attentionItems: Array<{
    id: string;
    title: string;
    context: string;
    detail?: string;
    severity: AttentionSeverity;
    route: string;
  }>;
  snapshotMetrics: Array<{
    label: string;
    value: string | number;
    highlight?: boolean;
    route?: string;
  }> | null;
  projects: Array<{
    id: string;
    name: string;
    location: string;
    status: StatusType;
    statusLabel: string;
    progress: number;
    reportingRatio: string;
    openIssues: number;
  }>;
  recentActivity: Array<{
    id: string;
    title: string;
    context: string;
    timeLabel: string;
    iconName: string; // Will map to Lucide icon in component
    route: string;
  }>;
  reportingStatus: Array<{
    id: string;
    title: string;
    subtitle: string;
    status: ReportingStatusType;
    contextMessage?: string;
    timeLabel?: string;
    route: string;
  }>;
};

// CONCEPTUAL QUERY HOOK
// In production, this will use React Query and fetch based on the global scope context
export function usePortfolioHomeData() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // Simulated fetch
    const fetch = async () => {
      try {
        await new Promise((resolve) => setTimeout(resolve, 600));
        
        setData({
          aiBrief: "Skyline Towers is falling behind schedule due to concrete delays. 3 active sites have not submitted their DPRs today. Expenses across the portfolio are tracking 4% above the monthly threshold.",
          attentionItems: [
            {
              id: 'a1',
              severity: 'critical',
              title: 'Project has not submitted DPR today.',
              context: 'Skyline Towers • All Sites',
              detail: 'Required by 6:00 PM',
              route: '/reports/missing',
            },
            {
              id: 'a2',
              severity: 'warning',
              title: 'Concrete work delayed by 3 days.',
              context: 'Green Valley • Tower 1',
              detail: 'Pending material delivery',
              route: '/issues/123',
            },
          ],
          snapshotMetrics: [
            { label: 'Active Projects', value: '12', route: '/projects' },
            { label: 'Active Sites', value: '28', route: '/sites' },
            { label: 'Reporting Today', value: '83%', highlight: true, route: '/reports' },
            { label: 'Expenses', value: '₹2.4L', route: '/expenses' },
            { label: 'Open Issues', value: '14', route: '/issues' },
            { label: 'Workforce', value: '436', route: '/team' },
          ],
          projects: [
            {
              id: 'p1',
              name: 'Skyline Towers',
              location: 'North Zone',
              status: 'critical',
              statusLabel: 'Critical',
              progress: 68,
              reportingRatio: '2 / 5 Sites',
              openIssues: 3,
            },
            {
              id: 'p2',
              name: 'Green Valley',
              location: 'East Zone',
              status: 'warning',
              statusLabel: 'At Risk',
              progress: 42,
              reportingRatio: '1 / 1 Sites',
              openIssues: 1,
            },
            {
              id: 'p3',
              name: 'Metro Heights',
              location: 'South Zone',
              status: 'success',
              statusLabel: 'On Track',
              progress: 89,
              reportingRatio: '3 / 3 Sites',
              openIssues: 0,
            }
          ],
          recentActivity: [
            {
              id: 'act1',
              title: 'Critical issue created',
              context: 'Skyline Towers • Block A',
              timeLabel: '2h ago',
              iconName: 'FileWarning',
              route: '/issues/402',
            },
            {
              id: 'act2',
              title: 'Large expense recorded',
              context: 'Metro Heights • Site 2',
              timeLabel: '4h ago',
              iconName: 'Banknote',
              route: '/expenses/99',
            },
          ],
          reportingStatus: [
            {
              id: 'rep1',
              title: 'Skyline Towers',
              subtitle: 'Block A',
              status: 'missing',
              contextMessage: 'Missing Today',
              route: '/reports/missing/1',
            },
            {
              id: 'rep2',
              title: 'Green Valley',
              subtitle: 'Tower 2',
              status: 'incomplete',
              contextMessage: 'Missing workforce details',
              route: '/reports/edit/2',
            },
            {
              id: 'rep3',
              title: 'Metro Heights',
              subtitle: 'Site 1',
              status: 'complete',
              timeLabel: 'Generated 24 min ago',
              route: '/reports/view/3',
            }
          ],
        });
        setIsLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to load portfolio data'));
        setIsLoading(false);
      }
    };
    
    fetch();
  }, []);

  return { data, isLoading, error };
}

export function getIconByName(name: string) {
  switch (name) {
    case 'FileWarning': return FileWarning;
    case 'Banknote': return Banknote;
    case 'HardHat': return HardHat;
    case 'TrendingDown': return TrendingDown;
    default: return Clock;
  }
}
