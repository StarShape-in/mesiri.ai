import React, { useState } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { ChevronRight, ChevronDown } from 'lucide-react-native';
import { useScope } from '../../state/ScopeProvider';
import { ProjectScopeSheet, SiteScopeSheet } from './ScopeSheets';
import { ProjectItem, SiteItem } from './scope.types';
import { useTheme, useStyles } from '../../src/theme';

export type MesiriScopeBarProps = {
  projects: ProjectItem[];
  // Mapping of projectId to its sites
  sitesByProject: Record<string, SiteItem[]>;
};

export function MesiriScopeBar({ projects, sitesByProject }: MesiriScopeBarProps) {
  const { scope, setPortfolioScope, setProjectScope, setSiteScope } = useScope();
  const { theme } = useTheme();
  const styles = useStyles(createStyles);
  
  const [projectSheetVisible, setProjectSheetVisible] = useState(false);
  const [siteSheetVisible, setSiteSheetVisible] = useState(false);

  // Derive active sites for the current project context
  const activeProjectId = scope.mode === 'portfolio' ? null : scope.projectId;
  const activeSites = activeProjectId ? (sitesByProject[activeProjectId] || []) : [];

  const handleSelectPortfolio = () => {
    setPortfolioScope();
  };

  const handleSelectProject = (project: ProjectItem) => {
    setProjectScope(project);
  };

  const handleSelectAllSites = () => {
    if (scope.mode === 'site') {
      // Revert to project mode for the current project
      setProjectScope({ id: scope.projectId, name: scope.projectName });
    }
  };

  const handleSelectSite = (site: SiteItem) => {
    if (scope.mode !== 'portfolio') {
      setSiteScope(
        { id: scope.projectId, name: scope.projectName }, 
        site
      );
    }
  };

  return (
    <View style={styles.container}>
      {/* Portfolio Mode */}
      {scope.mode === 'portfolio' && (
        <Pressable 
          style={({ pressed }) => [styles.control, styles.controlWhite, pressed && styles.controlPressed]} 
          onPress={() => setProjectSheetVisible(true)}
          accessibilityRole="button"
          accessibilityLabel="Select project scope"
        >
          <Text style={styles.controlText} numberOfLines={1}>All Projects</Text>
          <ChevronDown size={14} color={theme.components.scopeControlChevron} strokeWidth={2.5} style={styles.chevron} />
        </Pressable>
      )}

      {/* Project Mode or Site Mode */}
      {scope.mode !== 'portfolio' && (
        <>
          <Pressable 
            style={({ pressed }) => [
              styles.control, 
              scope.mode === 'project' ? styles.controlLime : styles.controlWhite,
              { flexShrink: 1 },
              pressed && styles.controlPressed
            ]} 
            onPress={() => setProjectSheetVisible(true)}
            accessibilityRole="button"
            accessibilityLabel="Change selected project"
          >
            <Text style={styles.controlText} numberOfLines={1}>{scope.projectName}</Text>
          </Pressable>

          <ChevronRight size={16} color={theme.colors.textMuted} strokeWidth={2} />

          <Pressable 
            style={({ pressed }) => [
              styles.control, 
              scope.mode === 'site' ? styles.controlLime : styles.controlWhite,
              { flexShrink: 1 },
              pressed && styles.controlPressed
            ]} 
            onPress={() => setSiteSheetVisible(true)}
            accessibilityRole="button"
            accessibilityLabel="Change selected site"
          >
            <Text style={styles.controlText} numberOfLines={1}>
              {scope.mode === 'site' ? scope.siteName : 'All Sites'}
            </Text>
            <ChevronDown size={14} color={theme.components.scopeControlChevron} strokeWidth={2.5} style={styles.chevron} />
          </Pressable>
        </>
      )}

      <ProjectScopeSheet 
        visible={projectSheetVisible}
        onClose={() => setProjectSheetVisible(false)}
        projects={projects}
        currentScope={scope}
        onSelectPortfolio={handleSelectPortfolio}
        onSelectProject={handleSelectProject}
      />

      <SiteScopeSheet 
        visible={siteSheetVisible}
        onClose={() => setSiteSheetVisible(false)}
        sites={activeSites}
        currentScope={scope}
        onSelectAllSites={handleSelectAllSites}
        onSelectSite={handleSelectSite}
      />
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    height: 48,
    width: '100%',
    backgroundColor: theme.components.scopeControlBackground,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderSubtle,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.space4, // 16
    gap: 6,
  },
  control: {
    height: 36,
    paddingHorizontal: theme.spacing.space3, // 12
    borderWidth: 1.5,
    borderColor: theme.components.scopeControlBorder,
    borderRadius: theme.radius.md, // 10 is between md and lg, using md or a custom token
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  controlWhite: {
    backgroundColor: theme.components.scopeControlBackground,
  },
  controlLime: {
    backgroundColor: theme.components.scopeControlActiveBackground,
  },
  controlPressed: {
    transform: [{ scale: 0.97 }],
  },
  controlText: {
    fontSize: 13,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary, // Or scopeControlActiveForeground based on state
    flexShrink: 1,
  },
  chevron: {
    marginLeft: 6,
  },
});
