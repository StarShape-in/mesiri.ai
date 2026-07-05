import React from 'react';
import { View, StyleSheet, ScrollView, RefreshControl, Text } from 'react-native';
import { usePortfolioHomeData, getIconByName } from '../../hooks/usePortfolioHomeData';
import { useProjects } from '../../hooks/useProjects';
import { AIDailyBrief } from '../features/AIDailyBrief';
import { AttentionItem } from '../features/AttentionItem';
import { DarkMetricPanel } from '../features/DarkMetricPanel';
import { ProjectHealthCard } from '../features/ProjectHealthCard';
import { ActivityItem } from '../features/ActivityItem';
import { ReportingStatusRow } from '../features/ReportingStatusRow';
import { SectionHeader } from '../ui/SectionHeader';
import { EmptyState } from '../ui/EmptyState';
import { useScope } from '../../state/ScopeProvider';
import { AlertCircle } from 'lucide-react-native';

export function PortfolioHomeScreen() {
  const { data, isLoading, error } = usePortfolioHomeData();
  // Projects are live; the remaining dashboard widgets are still placeholder
  // data until their endpoints exist.
  const { projects } = useProjects();
  const { setProjectScope } = useScope();

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <AlertCircle size={32} color="#DC2626" style={{ marginBottom: 12 }} />
        <Text style={styles.errorText}>Unable to load portfolio data.</Text>
      </View>
    );
  }

  if (isLoading || !data) {
    return (
      <View style={styles.container}>
        <View style={styles.skeletonBlock} />
        <View style={[styles.skeletonBlock, { height: 120 }]} />
        <View style={[styles.skeletonBlock, { height: 200, borderRadius: 20, backgroundColor: '#E5E5E5' }]} />
      </View>
    );
  }

  return (
    <ScrollView 
      style={styles.container} 
      contentContainerStyle={styles.contentContainer}
      refreshControl={<RefreshControl refreshing={isLoading} onRefresh={() => {}} />}
    >
      {/* 1. AI DAILY BRIEF */}
      {data.aiBrief && (
        <View style={styles.section}>
          <AIDailyBrief brief={data.aiBrief} />
        </View>
      )}

      {/* 2. ATTENTION REQUIRED */}
      <View style={styles.section}>
        <SectionHeader title="Attention Required" count={data.attentionItems.length} />
        {data.attentionItems.length === 0 ? (
          <EmptyState message="No critical items require attention." />
        ) : (
          <View style={styles.listContainer}>
            {data.attentionItems.map((item) => (
              <AttentionItem
                key={item.id}
                title={item.title}
                context={item.context}
                detail={item.detail}
                severity={item.severity}
                onPress={() => console.log('Navigate to', item.route)}
              />
            ))}
          </View>
        )}
      </View>

      {/* 3. PORTFOLIO SNAPSHOT (DARK COMPONENT) */}
      <View style={styles.section}>
        <DarkMetricPanel 
          title="Portfolio Snapshot"
          subtitle="Today"
          metrics={data.snapshotMetrics || []}
        />
      </View>

      {/* 4. PROJECTS */}
      <View style={styles.section}>
        <SectionHeader title="Projects" count={projects.length} actionLabel="View All" onActionPress={() => {}} />
        {projects.length === 0 ? (
          <EmptyState message="No active projects available." />
        ) : (
          <View>
            {projects.map((project) => (
              <ProjectHealthCard
                key={project.id}
                name={project.name}
                location={project.location}
                status={project.status}
                statusLabel={project.statusLabel}
                progress={project.progress}
                reportingRatio={project.reportingRatio}
                openIssues={project.openIssues}
                onPress={() => {
                  setProjectScope({ id: project.id, name: project.name });
                }}
              />
            ))}
          </View>
        )}
      </View>

      {/* 5. RECENT ACTIVITY */}
      <View style={styles.section}>
        <SectionHeader title="Recent Activity" actionLabel="View Timeline" onActionPress={() => {}} />
        {data.recentActivity.length === 0 ? (
          <EmptyState message="No recent activity to show." />
        ) : (
          <View style={styles.listContainer}>
            {data.recentActivity.map((activity) => (
              <ActivityItem
                key={activity.id}
                title={activity.title}
                context={activity.context}
                timeLabel={activity.timeLabel}
                Icon={getIconByName(activity.iconName)}
                onPress={() => console.log('Navigate to', activity.route)}
              />
            ))}
          </View>
        )}
      </View>

      {/* 6. REPORTING STATUS / LATEST DPRs */}
      <View style={styles.section}>
        <SectionHeader title="Reporting Status" actionLabel="View DPRs" onActionPress={() => {}} />
        {data.reportingStatus.length === 0 ? (
          <EmptyState message="No reporting status available." />
        ) : (
          <View style={styles.listContainer}>
            {data.reportingStatus.map((report) => (
              <ReportingStatusRow
                key={report.id}
                title={report.title}
                subtitle={report.subtitle}
                status={report.status}
                contextMessage={report.contextMessage}
                timeLabel={report.timeLabel}
                onPress={() => console.log('Navigate to', report.route)}
              />
            ))}
          </View>
        )}
      </View>
      
      {/* Extra space at bottom to ensure scrolling over absolute tabs */}
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FAFAFB',
  },
  contentContainer: {
    paddingHorizontal: 16,
    paddingTop: 24,
    paddingBottom: 80, // Space for Bottom Navigation
    maxWidth: 520,
    marginHorizontal: 'auto',
    width: '100%',
  },
  section: {
    marginBottom: 28,
  },
  listContainer: {
    gap: 12,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errorText: {
    fontSize: 14,
    color: '#737373',
  },
  skeletonBlock: {
    backgroundColor: '#F0F0F0',
    height: 80,
    borderRadius: 14,
    marginBottom: 24,
    marginHorizontal: 16,
    marginTop: 24,
  }
});
