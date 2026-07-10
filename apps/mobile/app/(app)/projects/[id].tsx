import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Keyboard,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '@mesiri/auth';
import { ArrowLeft, Building2, MapPin, Plus, Target } from 'lucide-react-native';
import { useProjects } from '../../../hooks/useProjects';
import { useScope } from '../../../state/ScopeProvider';
import { useTheme, useStyles } from '../../../src/theme';
import { FormTextInput } from '../../../components/ui/FormTextInput';
import { StatusBadge } from '../../../components/ui/StatusBadge';

type SiteItem = {
  id: string;
  project_id?: string;
  name: string;
  status: string;
};

export default function ProjectDetailsRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { setProjectScope } = useScope();
  const { projects, isLoading, refetch } = useProjects();
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const project = useMemo(() => projects.find(item => item.id === id), [projects, id]);
  const [sites, setSites] = useState<SiteItem[]>([]);
  const [sitesLoading, setSitesLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [siteName, setSiteName] = useState('');
  const [siteError, setSiteError] = useState<string | null>(null);
  const [submittingSite, setSubmittingSite] = useState(false);

  const fetchSites = useCallback(async () => {
    if (!id) return;
    setSitesLoading(true);
    try {
      const { data } = await api.get(`/projects/${id}/sites`);
      setSites(data);
    } catch (error: any) {
      Alert.alert(
        'Unable to load sites',
        error?.response?.data?.detail || 'Please try again.'
      );
    } finally {
      setSitesLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchSites();
  }, [fetchSites]);

  const handleCreateSite = async () => {
    const name = siteName.trim();
    if (!name) {
      setSiteError('Site name is required');
      return;
    }
    if (!id) return;

    setSubmittingSite(true);
    try {
      await api.post(`/projects/${id}/sites`, { name });
      setSiteName('');
      setSiteError(null);
      setCreateOpen(false);
      await fetchSites();
      Alert.alert('Success', 'Site created');
    } catch (error: any) {
      Alert.alert(
        'Unable to create site',
        error?.response?.data?.detail || 'Please try again.'
      );
    } finally {
      setSubmittingSite(false);
    }
  };

  const openDashboard = () => {
    if (!project) return;
    setProjectScope({ id: project.id, name: project.name });
    router.replace('/');
  };

  if (isLoading) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color={theme.colors.actionPrimary} />
      </View>
    );
  }

  if (!project) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.iconButton}>
            <ArrowLeft size={24} color={theme.colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Project Details</Text>
          <View style={styles.headerSpacer} />
        </View>
        <View style={[styles.centered, styles.emptyPanel]}>
          <Text style={styles.emptyTitle}>Project not found</Text>
          <TouchableOpacity style={styles.secondaryButton} onPress={refetch}>
            <Text style={styles.secondaryButtonText}>Refresh</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconButton}>
          <ArrowLeft size={24} color={theme.colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Project Details</Text>
        <TouchableOpacity onPress={() => setCreateOpen(true)} style={styles.iconButton}>
          <Plus size={22} color={theme.colors.textPrimary} />
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
        <View style={styles.summaryCard}>
          <View style={styles.summaryHeader}>
            <View style={styles.projectIcon}>
              <Building2 size={22} color={theme.colors.actionPrimary} />
            </View>
            <View style={styles.summaryText}>
              <Text style={styles.projectName} selectable>{project.name}</Text>
              {project.code ? <Text style={styles.projectMeta} selectable>{project.code}</Text> : null}
            </View>
          </View>

          <View style={styles.statusRow}>
            <StatusBadge status={project.status} label={project.statusLabel} />
            <Text style={styles.progressText}>{project.progress}% complete</Text>
          </View>

          {project.location ? (
            <View style={styles.metaRow}>
              <MapPin size={16} color={theme.colors.textSecondary} />
              <Text style={styles.metaText} selectable>{project.location}</Text>
            </View>
          ) : null}

          {project.client ? (
            <View style={styles.metaRow}>
              <Target size={16} color={theme.colors.textSecondary} />
              <Text style={styles.metaText} selectable>{project.client}</Text>
            </View>
          ) : null}

          {project.description ? (
            <Text style={styles.description} selectable>{project.description}</Text>
          ) : null}
        </View>

        <View style={styles.actionsRow}>
          <TouchableOpacity style={styles.primaryButton} onPress={() => setCreateOpen(true)}>
            <Plus size={18} color={theme.colors.actionPrimaryForeground} />
            <Text style={styles.primaryButtonText}>Create Site</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondaryButton} onPress={openDashboard}>
            <Text style={styles.secondaryButtonText}>Open Dashboard</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Sites</Text>
          <Text style={styles.sectionCount}>{sites.length}</Text>
        </View>

        {sitesLoading ? (
          <View style={styles.loadingSites}>
            <ActivityIndicator color={theme.colors.actionPrimary} />
          </View>
        ) : sites.length === 0 ? (
          <View style={styles.emptySites}>
            <Text style={styles.emptyTitle}>No sites yet</Text>
            <Text style={styles.emptyCopy}>Create the first site for this project.</Text>
          </View>
        ) : (
          <View style={styles.siteList}>
            {sites.map(site => (
              <View key={site.id} style={styles.siteRow}>
                <View>
                  <Text style={styles.siteName} selectable>{site.name}</Text>
                  <Text style={styles.siteStatus} selectable>{site.status || 'active'}</Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>

      <Modal visible={createOpen} animationType="slide" transparent>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.keyboardAvoidingView}
        >
          <Pressable style={styles.modalOverlay} onPress={Keyboard.dismiss}>
            <Pressable style={styles.sheet} onPress={e => e.stopPropagation()}>
              <Text style={styles.sheetTitle}>Create Site</Text>
              <ScrollView
                showsVerticalScrollIndicator={false}
                keyboardShouldPersistTaps="handled"
                contentContainerStyle={styles.sheetFormScroll}
              >
                <FormTextInput
                  label="Site Name *"
                  placeholder="e.g. Tower A"
                  value={siteName}
                  onChangeText={text => {
                    setSiteName(text);
                    setSiteError(null);
                  }}
                  error={siteError || undefined}
                />
                <View style={styles.sheetActions}>
                  <TouchableOpacity
                    style={styles.secondaryButton}
                    onPress={() => {
                      setCreateOpen(false);
                      setSiteName('');
                      setSiteError(null);
                    }}
                    disabled={submittingSite}
                  >
                    <Text style={styles.secondaryButtonText}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.primaryButton, submittingSite && styles.disabledButton]}
                    onPress={handleCreateSite}
                    disabled={submittingSite}
                  >
                    <Text style={styles.primaryButtonText}>
                      {submittingSite ? 'Creating...' : 'Create'}
                    </Text>
                  </TouchableOpacity>
                </View>
              </ScrollView>
            </Pressable>
          </Pressable>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.backgroundApp,
  },
  centered: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  header: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    backgroundColor: theme.colors.backgroundSurface,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderSubtle,
  },
  iconButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerSpacer: {
    width: 40,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: 16,
    gap: 16,
    paddingBottom: 96,
    maxWidth: 620,
    marginHorizontal: 'auto',
    width: '100%',
  },
  summaryCard: {
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    borderRadius: theme.radius.lg,
    padding: 16,
    gap: 14,
  },
  summaryHeader: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
  },
  projectIcon: {
    width: 44,
    height: 44,
    borderRadius: theme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.backgroundSubtle,
  },
  summaryText: {
    flex: 1,
  },
  projectName: {
    fontSize: theme.typography.sizeLg,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  projectMeta: {
    marginTop: 2,
    color: theme.colors.textSecondary,
    fontSize: theme.typography.sizeSm,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  progressText: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.sizeSm,
    fontVariant: ['tabular-nums'],
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  metaText: {
    flex: 1,
    color: theme.colors.textSecondary,
    fontSize: theme.typography.sizeSm,
  },
  description: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.sizeSm,
    lineHeight: 20,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  primaryButton: {
    flex: 1,
    minHeight: 44,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.actionPrimary,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 14,
  },
  primaryButtonText: {
    color: theme.colors.actionPrimaryForeground,
    fontWeight: theme.typography.weightBold,
    fontSize: theme.typography.sizeSm,
  },
  secondaryButton: {
    flex: 1,
    minHeight: 44,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    backgroundColor: theme.colors.backgroundSurface,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  secondaryButtonText: {
    color: theme.colors.textPrimary,
    fontWeight: theme.typography.weightSemiBold,
    fontSize: theme.typography.sizeSm,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionTitle: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightBold,
  },
  sectionCount: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.sizeSm,
    fontVariant: ['tabular-nums'],
  },
  loadingSites: {
    padding: 24,
    alignItems: 'center',
  },
  emptyPanel: {
    flex: 1,
    padding: 24,
    gap: 16,
  },
  emptySites: {
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    borderRadius: theme.radius.lg,
    padding: 18,
    gap: 4,
  },
  emptyTitle: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightBold,
  },
  emptyCopy: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.sizeSm,
  },
  siteList: {
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    borderRadius: theme.radius.lg,
    overflow: 'hidden',
  },
  siteRow: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderSubtle,
  },
  siteName: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightSemiBold,
  },
  siteStatus: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.sizeSm,
    marginTop: 2,
    textTransform: 'capitalize',
  },
  keyboardAvoidingView: {
    flex: 1,
  },
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.45)',
  },
  sheet: {
    backgroundColor: theme.colors.backgroundSurface,
    borderTopLeftRadius: theme.radius.xl,
    borderTopRightRadius: theme.radius.xl,
    padding: 20,
    paddingBottom: 36,
    maxHeight: '90%',
  },
  sheetFormScroll: {
    gap: 16,
  },
  sheetTitle: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.sizeLg,
    fontWeight: theme.typography.weightBold,
  },
  sheetActions: {
    flexDirection: 'row',
    gap: 10,
  },
  disabledButton: {
    opacity: 0.6,
  },
});
