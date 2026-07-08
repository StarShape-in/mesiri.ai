import React, { useCallback } from 'react';
import { View, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuth } from '../../app/_layout';
import { useTheme, useStyles } from '../../src/theme';
import { SectionHeader } from '../ui/SectionHeader';
import { EmptyState } from '../ui/EmptyState';
import { ProjectHealthCard } from '../features/ProjectHealthCard';
import { useProjects } from '../../hooks/useProjects';

export function ProjectsManagementScreen() {
  const { user } = useAuth();
  const router = useRouter();
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  // Live, tenant-scoped projects (GET /projects).
  const { projects, isLoading, refetch } = useProjects();

  const canCreateProject = user?.capabilities?.includes('projects.create');

  // Refetch when returning to this screen (e.g. after creating a project).
  useFocusEffect(
    useCallback(() => {
      refetch();
    }, [refetch])
  );

  const handleProjectSelect = (project: { id: string }) => {
    router.push(`/projects/${project.id}`);
  };

  return (
    <ScrollView 
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      refreshControl={<RefreshControl refreshing={isLoading} onRefresh={refetch} />}
    >
      <View style={styles.section}>
        <SectionHeader
          title="Projects"
          count={projects.length}
          actionLabel={canCreateProject ? "+ New Project" : undefined}
          onActionPress={canCreateProject ? () => router.push('/projects/new') : undefined}
        />

        {projects.length === 0 ? (
          <EmptyState
            message="No projects yet. Create your first project to start tracking daily site activity."
          />
        ) : (
          <View style={styles.listContainer}>
            {projects.map(project => (
              <ProjectHealthCard
                key={project.id}
                name={project.name}
                location={project.location}
                status={project.status}
                statusLabel={project.statusLabel}
                progress={project.progress}
                reportingRatio={project.reportingRatio}
                openIssues={project.openIssues}
                onPress={() => handleProjectSelect(project)}
              />
            ))}
          </View>
        )}
      </View>
      <View style={{ height: 60 }} />
    </ScrollView>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.backgroundApp,
  },
  contentContainer: {
    paddingHorizontal: theme.spacing.space4,
    paddingTop: theme.spacing.space6,
    paddingBottom: 80,
    maxWidth: 520,
    marginHorizontal: 'auto',
    width: '100%',
  },
  section: {
    marginBottom: 24,
  },
  listContainer: {
    gap: 12,
  },
});
