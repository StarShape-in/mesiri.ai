import { useState, useEffect, useCallback } from 'react';
import { api } from '@mesiri/auth';
import { StatusType } from '../components/ui/StatusBadge';

export type Project = {
  id: string;
  name: string;
  location?: string;
  code?: string;
  client?: string;
  description?: string;
  status: StatusType;
  statusLabel: string;
  progress: number;
  openIssues: number;
  reportingRatio?: string;
};

// Live projects for the caller's organization (GET /projects).
export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchProjects = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/projects');
      setProjects(res.data);
      setError(null);
    } catch (err: any) {
      setError(err instanceof Error ? err : new Error('Failed to load projects'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return { projects, isLoading, error, refetch: fetchProjects };
}
