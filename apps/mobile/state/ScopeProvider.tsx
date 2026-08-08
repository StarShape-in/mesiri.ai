import React, { createContext, useContext, useState, useEffect } from 'react';
import * as SecureStore from 'expo-secure-store';
import { AppScope, ProjectItem, SiteItem } from '../components/scope/scope.types';

const SCOPE_STORAGE_KEY = 'mesiri_active_scope';

type ScopeContextType = {
  scope: AppScope;
  setPortfolioScope: () => void;
  setProjectScope: (project: ProjectItem) => void;
  setSiteScope: (project: ProjectItem, site: SiteItem) => void;
  isPortfolioMode: boolean;
  isProjectMode: boolean;
  isSiteMode: boolean;
};

const ScopeContext = createContext<ScopeContextType | null>(null);

export const useScope = () => {
  const context = useContext(ScopeContext);
  if (!context) {
    throw new Error('useScope must be used within a ScopeProvider');
  }
  return context;
};

export function ScopeProvider({ children }: { children: React.ReactNode }) {
  const [scope, setScopeState] = useState<AppScope>({ mode: 'portfolio' });

  // Load initial scope on mount
  useEffect(() => {
    async function loadPersistedScope() {
      try {
        const stored = await SecureStore.getItemAsync(SCOPE_STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored) as AppScope;
          // In a real implementation, you would validate here that the user 
          // still has access to parsed.projectId / parsed.siteId
          setScopeState(parsed);
        }
      } catch (e) {
        console.warn('Failed to load scope', e);
      }
    }
    loadPersistedScope();
  }, []);

  // Update state and persist
  const setScope = (newScope: AppScope) => {
    setScopeState(newScope);
    SecureStore.setItemAsync(SCOPE_STORAGE_KEY, JSON.stringify(newScope)).catch((e) => {
      console.warn('Failed to save scope', e);
    });
  };

  const setPortfolioScope = () => {
    setScope({ mode: 'portfolio' });
  };

  const setProjectScope = (project: ProjectItem) => {
    setScope({
      mode: 'project',
      projectId: project.id,
      projectName: project.name,
    });
  };

  const setSiteScope = (project: ProjectItem, site: SiteItem) => {
    setScope({
      mode: 'site',
      projectId: project.id,
      projectName: project.name,
      siteId: site.id,
      siteName: site.name,
    });
  };

  return (
    <ScopeContext.Provider
      value={{
        scope,
        setPortfolioScope,
        setProjectScope,
        setSiteScope,
        isPortfolioMode: scope.mode === 'portfolio',
        isProjectMode: scope.mode === 'project',
        isSiteMode: scope.mode === 'site',
      }}
    >
      {children}
    </ScopeContext.Provider>
  );
}
