import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert, Modal, Switch } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@mesiri/auth';
import { useTheme, useStyles } from '../../../src/theme';
import { userAccessService, UserDetails, UserAccessPolicy, ProjectAccess } from '../../../src/services/userAccessService';
import { useProjects } from '../../../hooks/useProjects';
import { UserSummaryHeader } from '../../../components/features/access/UserSummaryHeader';
import { AccessSummary } from '../../../components/features/access/AccessSummary';
import { ProjectAccessRow } from '../../../components/features/access/ProjectAccessRow';
import { StickyFormActions } from '../../../components/features/access/StickyFormActions';
import { ConfirmationDialog } from '../../../components/ui/ConfirmationDialog';

const ROLES = ["ADMIN", "PROJECT_MANAGER", "SITE_ENGINEER", "FINANCE"];

type SiteItem = { id: string; name: string };

export default function UserDetailsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const { projects } = useProjects();
  const [sitesCache, setSitesCache] = useState<Record<string, SiteItem[]>>({});

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [user, setUser] = useState<UserDetails | null>(null);

  // Access Draft State
  const [draftPolicy, setDraftPolicy] = useState<UserAccessPolicy | null>(null);

  // Modals
  const [roleSheetOpen, setRoleSheetOpen] = useState(false);
  const [siteSheetProject, setSiteSheetProject] = useState<string | null>(null);
  const [deactivateConfirmOpen, setDeactivateConfirmOpen] = useState(false);

  const fetchSitesForProject = useCallback(async (projectId: string) => {
    if (sitesCache[projectId]) return;
    try {
      const { data } = await api.get(`/projects/${projectId}/sites`);
      setSitesCache(prev => ({ ...prev, [projectId]: data }));
    } catch {
      setSitesCache(prev => ({ ...prev, [projectId]: [] }));
    }
  }, [sitesCache]);

  // Pre-fetch sites for all projects once they load
  useEffect(() => {
    projects.forEach(p => fetchSitesForProject(p.id));
  }, [projects]);

  useEffect(() => {
    if (id) fetchUser();
  }, [id]);

  const fetchUser = async () => {
    try {
      const data = await userAccessService.getUserDetails(id!);
      setUser(data);
      // Create deep copy for draft
      setDraftPolicy(JSON.parse(JSON.stringify(data.accessPolicy)));
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail || e?.message || 'Unknown error';
      Alert.alert(
        'Error',
        `Failed to load user details\n\nStatus: ${status || 'N/A'}\n${detail}`
      );
    } finally {
      setLoading(false);
    }
  };

  const hasUnsavedChanges = JSON.stringify(draftPolicy) !== JSON.stringify(user?.accessPolicy);

  const handleSave = async () => {
    if (!draftPolicy || !user) return;
    setSaving(true);
    try {
      await userAccessService.updateUserAccessPolicy(user.id, draftPolicy);
      setUser(prev => prev ? { ...prev, accessPolicy: JSON.parse(JSON.stringify(draftPolicy)) } : null);
      Alert.alert('Success', 'User access updated');
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to update access');
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    if (user) setDraftPolicy(JSON.parse(JSON.stringify(user.accessPolicy)));
  };

  const changeRole = async (role: string) => {
    if (!user) return;
    try {
      await userAccessService.updateUserRole(user.id, role);
      setUser({ ...user, role });
      setRoleSheetOpen(false);
    } catch (e) {
      Alert.alert('Error', 'Failed to change role');
    }
  };

  const deactivateUser = async () => {
    if (!user) return;
    try {
      await userAccessService.updateUserStatus(user.id, 'inactive');
      setUser({ ...user, status: 'inactive' });
      setDeactivateConfirmOpen(false);
    } catch (e) {
      Alert.alert('Error', 'Failed to deactivate user');
    }
  };

  const toggleAllProjects = (val: boolean) => {
    if (!draftPolicy) return;
    setDraftPolicy({ ...draftPolicy, mode: val ? 'all_projects' : 'custom_projects' });
  };

  const toggleProject = (projectId: string) => {
    if (!draftPolicy || draftPolicy.mode === 'all_projects') return;
    const existing = draftPolicy.projects || [];
    const hasProj = existing.some(p => p.projectId === projectId);
    
    if (hasProj) {
      setDraftPolicy({
        ...draftPolicy,
        projects: existing.filter(p => p.projectId !== projectId)
      });
    } else {
      setDraftPolicy({
        ...draftPolicy,
        projects: [...existing, { projectId, siteAccess: { mode: 'all_sites' } }]
      });
    }
  };

  const toggleSiteMode = (projectId: string, isAllSites: boolean) => {
    if (!draftPolicy) return;
    const projs = draftPolicy.projects || [];
    const newProjs = projs.map(p => {
      if (p.projectId === projectId) {
        return { ...p, siteAccess: { mode: isAllSites ? 'all_sites' as const : 'custom_sites' as const, siteIds: [] } };
      }
      return p;
    });
    setDraftPolicy({ ...draftPolicy, projects: newProjs });
  };

  const toggleSite = (projectId: string, siteId: string) => {
    if (!draftPolicy) return;
    const projs = draftPolicy.projects || [];
    const newProjs = projs.map(p => {
      if (p.projectId === projectId && p.siteAccess.mode === 'custom_sites') {
        const currentIds = p.siteAccess.siteIds || [];
        const hasSite = currentIds.includes(siteId);
        return {
          ...p,
          siteAccess: {
            ...p.siteAccess,
            siteIds: hasSite ? currentIds.filter(id => id !== siteId) : [...currentIds, siteId]
          }
        };
      }
      return p;
    });
    setDraftPolicy({ ...draftPolicy, projects: newProjs });
  };

  if (loading || !user || !draftPolicy) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color={theme.colors.actionPrimary} />
      </View>
    );
  }

  const projectCount = draftPolicy.mode === 'all_projects'
    ? projects.length
    : (draftPolicy.projects?.length || 0);

  let siteCount = 0;
  if (draftPolicy.mode === 'all_projects') {
    siteCount = Object.values(sitesCache).flat().length;
  } else {
    draftPolicy.projects?.forEach(p => {
      if (p.siteAccess.mode === 'all_sites') {
        siteCount += (sitesCache[p.projectId] || []).length;
      } else {
        siteCount += (p.siteAccess.siteIds?.length || 0);
      }
    });
  }

  const activeSiteProject = draftPolicy.projects?.find(p => p.projectId === siteSheetProject);

  return (
    <View style={styles.container}>
      <View style={styles.headerBar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={theme.colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>User Access</Text>
        <View style={{ width: 24 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* 1. USER SUMMARY */}
        <UserSummaryHeader 
          name={user.full_name} 
          role={user.role} 
          email={user.email}
          phone={user.whatsapp_number || undefined}
          status={user.status}
        />

        {/* 2. ROLE & ACCOUNT */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Role & Account</Text>
          <View style={styles.card}>
            <TouchableOpacity style={styles.row} onPress={() => setRoleSheetOpen(true)}>
              <Text style={styles.rowLabel}>Role</Text>
              <View style={styles.rowValueContainer}>
                <Text style={styles.rowValue}>{user.role.replace('_', ' ')}</Text>
                <Ionicons name="chevron-forward" size={16} color={theme.colors.textMuted} />
              </View>
            </TouchableOpacity>
            <View style={styles.divider} />
            <TouchableOpacity style={styles.row} onPress={() => setDeactivateConfirmOpen(true)}>
              <Text style={styles.rowLabel}>Account Status</Text>
              <View style={styles.rowValueContainer}>
                <Text style={[styles.rowValue, user.status === 'inactive' && { color: '#EF4444' }]}>
                  {user.status === 'active' ? 'Active' : 'Inactive'}
                </Text>
                <Ionicons name="chevron-forward" size={16} color={theme.colors.textMuted} />
              </View>
            </TouchableOpacity>
          </View>
        </View>

        {/* 3. ACCESS SUMMARY */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Access Summary</Text>
          <AccessSummary 
            projectCount={projectCount}
            siteCount={siteCount}
            accessType={draftPolicy.mode === 'all_projects' ? 'All Projects' : 'Custom Access'}
          />
        </View>

        {/* 4. PROJECT & SITE ACCESS */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Project & Site Access</Text>
          <Text style={styles.sectionSubtitle}>Control which projects and sites this user can access.</Text>
          
          <View style={styles.card}>
            <View style={styles.switchRow}>
              <View>
                <Text style={styles.rowLabel}>All Projects</Text>
                <Text style={styles.rowSubLabel}>Access every project permitted by policy</Text>
              </View>
              <Switch 
                value={draftPolicy.mode === 'all_projects'} 
                onValueChange={toggleAllProjects}
                trackColor={{ true: theme.colors.actionPrimary }}
              />
            </View>
            
            {draftPolicy.mode === 'custom_projects' && (
              <View style={styles.projectList}>
                <Text style={styles.listHeader}>CUSTOM PROJECTS</Text>
                {projects.map(proj => {
                  const projAccess = draftPolicy.projects?.find(p => p.projectId === proj.id);
                  const isSelected = !!projAccess;
                  let siteDesc = '';
                  if (isSelected) {
                    siteDesc = projAccess.siteAccess.mode === 'all_sites'
                      ? 'All Sites'
                      : `${projAccess.siteAccess.siteIds?.length || 0} Sites`;
                  }

                  return (
                    <ProjectAccessRow
                      key={proj.id}
                      projectName={proj.name}
                      isSelected={isSelected}
                      siteAccessSummary={siteDesc}
                      onToggle={() => toggleProject(proj.id)}
                      onOpenSiteAccess={() => {
                        fetchSitesForProject(proj.id);
                        setSiteSheetProject(proj.id);
                      }}
                    />
                  );
                })}
              </View>
            )}
          </View>
        </View>

        {/* 6. ADMIN ACTIONS */}
        <View style={[styles.section, { marginBottom: 120 }]}>
          <Text style={styles.sectionTitle}>Admin Actions</Text>
          <View style={styles.card}>
            <TouchableOpacity style={styles.dangerRow} onPress={() => setDeactivateConfirmOpen(true)}>
              <Text style={styles.dangerText}>Deactivate User</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>

      {/* Sticky Actions */}
      <StickyFormActions 
        visible={hasUnsavedChanges}
        onDiscard={handleDiscard}
        onSave={handleSave}
        isSaving={saving}
      />

      {/* ROLE SHEET */}
      <Modal visible={roleSheetOpen} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.bottomSheet}>
            <Text style={styles.sheetTitle}>Select Role</Text>
            {ROLES.map(r => (
              <TouchableOpacity key={r} style={styles.roleOption} onPress={() => changeRole(r)}>
                <Text style={[styles.roleText, user.role === r && styles.roleTextActive]}>
                  {r.replace('_', ' ')}
                </Text>
                {user.role === r && <Ionicons name="checkmark" size={20} color={theme.colors.actionPrimary} />}
              </TouchableOpacity>
            ))}
            <TouchableOpacity style={styles.sheetCloseButton} onPress={() => setRoleSheetOpen(false)}>
              <Text style={styles.sheetCloseText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* SITE ACCESS SHEET */}
      <Modal visible={!!siteSheetProject} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.bottomSheet, { height: '80%' }]}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Site Access</Text>
              <TouchableOpacity onPress={() => setSiteSheetProject(null)}>
                <Ionicons name="close" size={24} color={theme.colors.textSecondary} />
              </TouchableOpacity>
            </View>
            
            {activeSiteProject && (
              <ScrollView>
                <View style={styles.switchRow}>
                  <Text style={styles.rowLabel}>All Sites</Text>
                  <Switch 
                    value={activeSiteProject.siteAccess.mode === 'all_sites'} 
                    onValueChange={(val) => toggleSiteMode(activeSiteProject.projectId, val)}
                    trackColor={{ true: theme.colors.actionPrimary }}
                  />
                </View>

                {activeSiteProject.siteAccess.mode === 'custom_sites' && (
                  <View style={styles.siteList}>
                    {(sitesCache[activeSiteProject.projectId] || []).map(site => {
                      const isSelected = (activeSiteProject.siteAccess.siteIds || []).includes(site.id);
                      return (
                        <TouchableOpacity key={site.id} style={styles.siteRow} onPress={() => toggleSite(activeSiteProject.projectId, site.id)}>
                          <View style={[styles.checkbox, isSelected && styles.checkboxSelected]}>
                            {isSelected && <Ionicons name="checkmark" size={14} color="#FFF" />}
                          </View>
                          <Text style={styles.siteName}>{site.name}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}
              </ScrollView>
            )}
            
            <TouchableOpacity style={styles.doneButton} onPress={() => setSiteSheetProject(null)}>
              <Text style={styles.doneText}>Done</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <ConfirmationDialog 
        visible={deactivateConfirmOpen}
        title="Deactivate User"
        message="The user will lose access to Mesiri Daily until reactivated."
        confirmText="Deactivate"
        isDestructive
        onConfirm={deactivateUser}
        onCancel={() => setDeactivateConfirmOpen(false)}
      />
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.backgroundApp },
  centered: { justifyContent: 'center', alignItems: 'center' },
  headerBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: theme.spacing.space4, backgroundColor: theme.colors.backgroundSurface, borderBottomWidth: 1, borderBottomColor: theme.colors.borderDefault },
  backButton: { padding: theme.spacing.space1 },
  headerTitle: { fontSize: theme.typography.sizeLg, fontWeight: theme.typography.weightSemiBold, color: theme.colors.textPrimary },
  scrollContent: { padding: theme.spacing.space4, paddingBottom: 100 },
  section: { marginTop: theme.spacing.space6 },
  sectionTitle: { fontSize: theme.typography.sizeMd, fontWeight: theme.typography.weightSemiBold, color: theme.colors.textPrimary, marginBottom: theme.spacing.space2 },
  sectionSubtitle: { fontSize: theme.typography.sizeSm, color: theme.colors.textSecondary, marginBottom: theme.spacing.space3 },
  card: { backgroundColor: theme.colors.backgroundSurface, borderRadius: theme.radius.lg, borderWidth: 1, borderColor: theme.colors.borderDefault, overflow: 'hidden' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: theme.spacing.space4 },
  rowLabel: { fontSize: theme.typography.sizeMd, fontWeight: theme.typography.weightMedium, color: theme.colors.textPrimary },
  rowSubLabel: { fontSize: theme.typography.sizeSm, color: theme.colors.textSecondary, marginTop: 2 },
  rowValueContainer: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.space2 },
  rowValue: { fontSize: theme.typography.sizeMd, color: theme.colors.textSecondary },
  divider: { height: 1, backgroundColor: theme.colors.borderSubtle },
  dangerRow: { padding: theme.spacing.space4, alignItems: 'center' },
  dangerText: { color: '#EF4444', fontSize: theme.typography.sizeMd, fontWeight: theme.typography.weightMedium },
  switchRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: theme.spacing.space4, borderBottomWidth: 1, borderBottomColor: theme.colors.borderSubtle },
  projectList: { marginTop: theme.spacing.space2 },
  listHeader: { fontSize: 12, fontWeight: theme.typography.weightBold, color: theme.colors.textMuted, marginLeft: theme.spacing.space4, marginBottom: theme.spacing.space2 },
  
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  bottomSheet: { backgroundColor: theme.colors.backgroundSurface, borderTopLeftRadius: theme.radius.xl, borderTopRightRadius: theme.radius.xl, padding: theme.spacing.space6, paddingBottom: 40 },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.space4 },
  sheetTitle: { fontSize: theme.typography.sizeLg, fontWeight: theme.typography.weightSemiBold, color: theme.colors.textPrimary, marginBottom: theme.spacing.space4 },
  roleOption: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: theme.spacing.space4, borderBottomWidth: 1, borderBottomColor: theme.colors.borderSubtle },
  roleText: { fontSize: theme.typography.sizeMd, color: theme.colors.textPrimary },
  roleTextActive: { fontWeight: theme.typography.weightSemiBold, color: theme.colors.actionPrimary },
  sheetCloseButton: { marginTop: theme.spacing.space6, alignItems: 'center', paddingVertical: theme.spacing.space3, backgroundColor: theme.colors.backgroundSubtle, borderRadius: theme.radius.md },
  sheetCloseText: { fontSize: theme.typography.sizeMd, fontWeight: theme.typography.weightMedium, color: theme.colors.textSecondary },
  
  siteList: { marginTop: theme.spacing.space4 },
  siteRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.space3, paddingHorizontal: theme.spacing.space4, borderBottomWidth: 1, borderBottomColor: theme.colors.borderSubtle },
  checkbox: { width: 20, height: 20, borderRadius: theme.radius.xs, borderWidth: 2, borderColor: theme.colors.borderStrong, justifyContent: 'center', alignItems: 'center', marginRight: theme.spacing.space3 },
  checkboxSelected: { backgroundColor: theme.colors.actionPrimary, borderColor: theme.colors.actionPrimary },
  siteName: { fontSize: theme.typography.sizeMd, color: theme.colors.textPrimary },
  doneButton: { backgroundColor: theme.colors.actionPrimary, paddingVertical: theme.spacing.space4, borderRadius: theme.radius.md, alignItems: 'center', marginTop: theme.spacing.space6 },
  doneText: { color: theme.colors.actionPrimaryForeground, fontWeight: theme.typography.weightSemiBold, fontSize: theme.typography.sizeMd }
});
