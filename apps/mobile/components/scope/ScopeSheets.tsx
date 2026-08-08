import React from 'react';
import { Modal, View, Text, StyleSheet, TouchableOpacity, Pressable, ScrollView, SafeAreaView } from 'react-native';
import { Check } from 'lucide-react-native';
import { ProjectItem, SiteItem, AppScope } from './scope.types';
import { useTheme, useStyles } from '../../src/theme';

type ProjectScopeSheetProps = {
  visible: boolean;
  onClose: () => void;
  projects: ProjectItem[];
  currentScope: AppScope;
  onSelectPortfolio: () => void;
  onSelectProject: (project: ProjectItem) => void;
};

export function ProjectScopeSheet({ visible, onClose, projects, currentScope, onSelectPortfolio, onSelectProject }: ProjectScopeSheetProps) {
  const isPortfolio = currentScope.mode === 'portfolio';
  const { theme } = useTheme();
  const styles = useStyles(createStyles);
  
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <Pressable style={styles.backdrop} onPress={onClose} />
        <SafeAreaView style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>PROJECTS</Text>
          </View>
          <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
            
            {/* All Projects Option */}
            <TouchableOpacity 
              style={[styles.row, isPortfolio && styles.activeRow]} 
              onPress={() => { onSelectPortfolio(); onClose(); }}
            >
              <Text style={[styles.rowText, isPortfolio && styles.activeText]}>All Projects</Text>
              {isPortfolio && <Check size={20} color={theme.components.scopeControlActiveForeground} strokeWidth={2.5} />}
            </TouchableOpacity>
            
            {/* Project List */}
            {projects.map((project) => {
              const isActive = (currentScope.mode === 'project' || currentScope.mode === 'site') && currentScope.projectId === project.id;
              return (
                <TouchableOpacity 
                  key={project.id}
                  style={[styles.row, isActive && styles.activeRow]} 
                  onPress={() => { onSelectProject(project); onClose(); }}
                >
                  <Text style={[styles.rowText, isActive && styles.activeText]} numberOfLines={1}>
                    {project.name}
                  </Text>
                  {isActive && <Check size={20} color={theme.components.scopeControlActiveForeground} strokeWidth={2.5} />}
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

type SiteScopeSheetProps = {
  visible: boolean;
  onClose: () => void;
  sites: SiteItem[];
  currentScope: AppScope;
  onSelectAllSites: () => void;
  onSelectSite: (site: SiteItem) => void;
};

export function SiteScopeSheet({ visible, onClose, sites, currentScope, onSelectAllSites, onSelectSite }: SiteScopeSheetProps) {
  const isAllSites = currentScope.mode === 'project';
  const { theme } = useTheme();
  const styles = useStyles(createStyles);
  
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <Pressable style={styles.backdrop} onPress={onClose} />
        <SafeAreaView style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>SITES</Text>
          </View>
          
          {sites.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No sites available for this project.</Text>
            </View>
          ) : (
            <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
              
              {/* All Sites Option */}
              <TouchableOpacity 
                style={[styles.row, isAllSites && styles.activeRow]} 
                onPress={() => { onSelectAllSites(); onClose(); }}
              >
                <Text style={[styles.rowText, isAllSites && styles.activeText]}>All Sites</Text>
                {isAllSites && <Check size={20} color={theme.components.scopeControlActiveForeground} strokeWidth={2.5} />}
              </TouchableOpacity>
              
              {/* Site List */}
              {sites.map((site) => {
                const isActive = currentScope.mode === 'site' && currentScope.siteId === site.id;
                return (
                  <TouchableOpacity 
                    key={site.id}
                    style={[styles.row, isActive && styles.activeRow]} 
                    onPress={() => { onSelectSite(site); onClose(); }}
                  >
                    <Text style={[styles.rowText, isActive && styles.activeText]} numberOfLines={1}>
                    {site.name}
                    </Text>
                    {isActive && <Check size={20} color={theme.components.scopeControlActiveForeground} strokeWidth={2.5} />}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          )}
        </SafeAreaView>
      </View>
    </Modal>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: theme.components.scopeSheetOverlay,
  },
  sheet: {
    backgroundColor: theme.colors.backgroundSurface,
    borderTopLeftRadius: theme.radius.xl, // 20 roughly
    borderTopRightRadius: theme.radius.xl,
    maxHeight: '80%',
    paddingBottom: 24, // extra padding for bottom safe area
  },
  header: {
    padding: 20,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderSubtle,
  },
  title: {
    fontSize: 12,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textMuted,
    letterSpacing: 0.5,
  },
  list: {
    maxHeight: 400,
  },
  listContent: {
    padding: theme.spacing.space4,
    gap: theme.spacing.space2,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: theme.spacing.space4,
    borderRadius: theme.radius.lg,
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  activeRow: {
    backgroundColor: theme.components.scopeControlActiveBackground,
    borderColor: theme.components.scopeControlBorder,
  },
  rowText: {
    fontSize: theme.typography.sizeMd, // 16
    color: theme.colors.textPrimary,
    fontWeight: theme.typography.weightMedium,
    flex: 1,
    marginRight: 12,
  },
  activeText: {
    fontWeight: theme.typography.weightBold,
  },
  emptyContainer: {
    padding: 32,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 15,
    color: theme.colors.textMuted,
  }
});
