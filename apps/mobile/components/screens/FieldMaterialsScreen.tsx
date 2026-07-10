import React, { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet, Text, Pressable, ScrollView, RefreshControl, Modal, TextInput, ActivityIndicator, FlatList, KeyboardAvoidingView, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useScope } from '../../state/ScopeProvider';
import { useStyles, useTheme } from '../../src/theme';
import { api } from '@mesiri/auth';
import { useProjects } from '../../hooks/useProjects';
import { MaterialInflowsList } from '../features/materials/MaterialInflowsList';
import { MaterialOutflowsList } from '../features/materials/MaterialOutflowsList';
import { MaterialInventoryList } from '../features/materials/MaterialInventoryList';
import { MaterialsFilterBar } from '../features/materials/MaterialsFilterBar';

type SelectionType = 'project' | 'site' | 'unit' | null;

const COMMON_UNITS = ['bags', 'kg', 'tons', 'cum', 'sqft', 'ltr', 'pieces', 'rolls', 'boxes'];

export function FieldMaterialsScreen() {
  const { scope } = useScope();
  const styles = useStyles(createStyles);
  const { theme } = useTheme();
  const { projects } = useProjects();

  const [activeTab, setActiveTab] = useState<'inflows' | 'outflows' | 'inventory'>('inflows');
  
  // Local state for search query and date filters
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState<string | undefined>(undefined);
  const [dateTo, setDateTo] = useState<string | undefined>(undefined);
  
  // Refresh tracking
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Form State
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [formType, setFormType] = useState<'inflow' | 'outflow' | null>(null);

  // Form fields
  const [formProjectId, setFormProjectId] = useState('');
  const [formProjectName, setFormProjectName] = useState('');
  const [formSiteId, setFormSiteId] = useState('');
  const [formSiteName, setFormSiteName] = useState('');
  const [formMaterialName, setFormMaterialName] = useState('');
  const [formQuantity, setFormQuantity] = useState('');
  const [formUnit, setFormUnit] = useState('bags');
  const [formSupplier, setFormSupplier] = useState('');
  const [formWorkItem, setFormWorkItem] = useState('');
  const [formOccurredDate, setFormOccurredDate] = useState('');
  
  const [formSites, setFormSites] = useState<{ id: string; name: string }[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // Selection Picker (rendered as an in-modal overlay, not a stacked native Modal)
  const [pickerType, setPickerType] = useState<SelectionType>(null);
  const [customUnitInput, setCustomUnitInput] = useState('');

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    setRefreshTrigger((prev) => prev + 1);
  }, []);

  const onRefreshComplete = useCallback(() => {
    setIsRefreshing(false);
  }, []);

  // Fetch sites when selected project changes
  useEffect(() => {
    let active = true;
    if (formProjectId) {
      api.get(`/projects/${formProjectId}/sites`)
        .then((res) => {
          if (active) setFormSites(res.data || []);
        })
        .catch(() => {
          if (active) setFormSites([]);
        });
    } else {
      setFormSites([]);
    }
    return () => {
      active = false;
    };
  }, [formProjectId]);

  // Refresh when scope context or active tab transitions
  useEffect(() => {
    handleRefresh();
  }, [scope, activeTab, handleRefresh]);

  const projectId = scope.mode !== 'portfolio' ? scope.projectId : undefined;
  const siteId = scope.mode === 'site' ? scope.siteId : undefined;

  const scopeText =
    scope.mode === 'portfolio'
      ? 'All Projects Portfolio'
      : scope.mode === 'project'
      ? scope.projectName
      : `${scope.projectName} • ${scope.siteName}`;

  const openForm = (type: 'inflow' | 'outflow') => {
    setFormType(type);
    setFormMaterialName('');
    setFormQuantity('');
    setFormUnit('bags');
    setFormSupplier('');
    setFormWorkItem('');
    setFormOccurredDate(new Date().toISOString().split('T')[0]);
    setCustomUnitInput('');
    setPickerType(null);

    if (scope.mode !== 'portfolio' && scope.projectId) {
      setFormProjectId(scope.projectId);
      setFormProjectName(scope.projectName);
      if (scope.mode === 'site' && scope.siteId) {
        setFormSiteId(scope.siteId);
        setFormSiteName(scope.siteName);
      } else {
        setFormSiteId('');
        setFormSiteName('');
      }
    } else {
      setFormProjectId('');
      setFormProjectName('');
      setFormSiteId('');
      setFormSiteName('');
    }
    setIsFormOpen(true);
  };

  const handleFabPress = () => {
    if (activeTab === 'inflows') {
      openForm('inflow');
    } else if (activeTab === 'outflows') {
      openForm('outflow');
    } else if (activeTab === 'inventory') {
      openForm('inflow'); // Add new inventory items via inflow receipts
    }
  };

  const handleFormSubmit = async () => {
    if (!formProjectId) {
      alert('Please select a project');
      return;
    }
    if (!formMaterialName.trim()) {
      alert('Please enter a material name');
      return;
    }
    if (!formQuantity || isNaN(Number(formQuantity)) || Number(formQuantity) <= 0) {
      alert('Please enter a valid quantity');
      return;
    }
    if (!formUnit.trim()) {
      alert('Please enter a unit');
      return;
    }
    if (!formOccurredDate.trim()) {
      alert('Please enter date (YYYY-MM-DD)');
      return;
    }

    setSubmitting(true);
    try {
      if (formType === 'inflow') {
        await api.post('/materials/inflows', {
          project_id: formProjectId,
          site_id: formSiteId || null,
          material_name: formMaterialName.trim(),
          quantity: Number(formQuantity),
          unit: formUnit.trim(),
          supplier: formSupplier.trim() || null,
          occurred_date: formOccurredDate.trim(),
        });
      } else {
        await api.post('/materials/outflows', {
          project_id: formProjectId,
          site_id: formSiteId || null,
          material_name: formMaterialName.trim(),
          quantity: Number(formQuantity),
          unit: formUnit.trim(),
          work_item: formWorkItem.trim() || null,
          occurred_date: formOccurredDate.trim(),
        });
      }
      setIsFormOpen(false);
      handleRefresh();
      alert('Material recorded successfully!');
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to record material');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={styles.container}>
      {/* Scope Header */}
      <View style={styles.headerContainer}>
        <Text style={styles.headerTitle}>Materials Log</Text>
        <Text style={styles.headerSubtitle}>{scopeText}</Text>
      </View>

      {/* Tab Segmented Control */}
      <View style={styles.tabContainer}>
        {(['inflows', 'outflows', 'inventory'] as const).map((tab) => (
          <Pressable
            key={tab}
            style={[
              styles.tabButton,
              activeTab === tab && styles.activeTabButton
            ]}
            onPress={() => setActiveTab(tab)}
            accessibilityRole="tab"
            accessibilityState={{ selected: activeTab === tab }}
          >
            <Text
              style={[
                styles.tabText,
                activeTab === tab && styles.activeTabText
              ]}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* Reusable Filter Bar */}
      <MaterialsFilterBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        dateFrom={dateFrom}
        onDateFromChange={setDateFrom}
        dateTo={dateTo}
        onDateToChange={setDateTo}
        showDateFilters={activeTab !== 'inventory'}
      />

      {/* Scrollable Lists */}
      <ScrollView
        style={styles.scrollContainer}
        contentContainerStyle={styles.contentContainer}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor={theme.colors.textPrimary}
          />
        }
      >
        {activeTab === 'inflows' && (
          <MaterialInflowsList
            projectId={projectId}
            siteId={siteId}
            searchQuery={searchQuery}
            dateFrom={dateFrom}
            dateTo={dateTo}
            refreshTrigger={refreshTrigger}
            onRefreshComplete={onRefreshComplete}
          />
        )}
        {activeTab === 'outflows' && (
          <MaterialOutflowsList
            projectId={projectId}
            siteId={siteId}
            searchQuery={searchQuery}
            dateFrom={dateFrom}
            dateTo={dateTo}
            refreshTrigger={refreshTrigger}
            onRefreshComplete={onRefreshComplete}
          />
        )}
        {activeTab === 'inventory' && (
          <MaterialInventoryList
            projectId={projectId}
            siteId={siteId}
            searchQuery={searchQuery}
            refreshTrigger={refreshTrigger}
            onRefreshComplete={onRefreshComplete}
          />
        )}
      </ScrollView>

      {/* Floating Action Button */}
      <Pressable
        style={styles.fab}
        onPress={handleFabPress}
        accessibilityRole="button"
        accessibilityLabel="Add materials log entry"
      >
        <Ionicons name="add" size={24} color={theme.colors.actionPrimaryForeground} />
      </Pressable>

      {/* FORM DIALOG MODAL */}
      <Modal
        visible={isFormOpen}
        animationType="slide"
        transparent={true}
        onRequestClose={() => (pickerType !== null ? setPickerType(null) : setIsFormOpen(false))}
      >
        <KeyboardAvoidingView
          style={styles.formOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={styles.formCard}>
            <View style={styles.formHeader}>
              <Text style={styles.formTitle}>
                {activeTab === 'inventory'
                  ? 'Add Inventory Item'
                  : formType === 'inflow'
                  ? 'Receive Material (Inflow)'
                  : 'Use Material (Outflow)'}
              </Text>
              <Pressable onPress={() => setIsFormOpen(false)}>
                <Ionicons name="close" size={24} color={theme.colors.textSecondary} />
              </Pressable>
            </View>

            <ScrollView contentContainerStyle={{ paddingBottom: 24 }} keyboardShouldPersistTaps="handled">
              {/* Project Picker */}
              <View style={styles.formGroup}>
                <Text style={styles.label}>Project</Text>
                <Pressable
                  style={[styles.inputButton, scope.mode !== 'portfolio' && styles.inputDisabled]}
                  onPress={() => scope.mode === 'portfolio' && setPickerType('project')}
                  disabled={scope.mode !== 'portfolio'}
                >
                  <Text style={[styles.inputButtonText, !formProjectId && styles.placeholderText]}>
                    {formProjectName || 'Select Project'}
                  </Text>
                  {scope.mode === 'portfolio' && <Ionicons name="chevron-down" size={16} color={theme.colors.textSecondary} />}
                </Pressable>
              </View>

              {/* Site Picker — locked (by app scope) or not yet eligible (no project chosen) */}
              {(() => {
                const siteLockedByScope = scope.mode === 'site';
                const siteNeedsProjectFirst = !siteLockedByScope && !formProjectId;
                const siteSelectable = !siteLockedByScope && !siteNeedsProjectFirst;
                return (
                  <View style={styles.formGroup}>
                    <Text style={styles.label}>Site (Optional)</Text>
                    <Pressable
                      style={[styles.inputButton, !siteSelectable && styles.inputDisabled]}
                      onPress={() => siteSelectable && setPickerType('site')}
                      disabled={!siteSelectable}
                    >
                      <Text style={[styles.inputButtonText, !formSiteId && styles.placeholderText]}>
                        {formSiteName ||
                          (siteNeedsProjectFirst ? 'Select a project first' : 'Select Site (All Sites)')}
                      </Text>
                      {siteSelectable && <Ionicons name="chevron-down" size={16} color={theme.colors.textSecondary} />}
                    </Pressable>
                  </View>
                );
              })()}

              {/* Material Name */}
              <View style={styles.formGroup}>
                <Text style={styles.label}>Material Name</Text>
                <TextInput
                  style={styles.textInput}
                  value={formMaterialName}
                  onChangeText={setFormMaterialName}
                  placeholder="e.g. Cement, Steel, Sand"
                  placeholderTextColor={theme.colors.textMuted}
                />
              </View>

              {/* Quantity & Unit Row */}
              <View style={styles.formRow}>
                <View style={[styles.formGroup, { flex: 1 }]}>
                  <Text style={styles.label}>Quantity</Text>
                  <TextInput
                    style={styles.textInput}
                    value={formQuantity}
                    onChangeText={setFormQuantity}
                    placeholder="e.g. 50"
                    placeholderTextColor={theme.colors.textMuted}
                    keyboardType="numeric"
                  />
                </View>
                <View style={[styles.formGroup, { flex: 1 }]}>
                  <Text style={styles.label}>Unit</Text>
                  <Pressable style={styles.inputButton} onPress={() => setPickerType('unit')}>
                    <Text style={[styles.inputButtonText, !formUnit && styles.placeholderText]}>
                      {formUnit || 'Select unit'}
                    </Text>
                    <Ionicons name="chevron-down" size={16} color={theme.colors.textSecondary} />
                  </Pressable>
                </View>
              </View>

              {/* Date */}
              <View style={styles.formGroup}>
                <Text style={styles.label}>Date</Text>
                <TextInput
                  style={styles.textInput}
                  value={formOccurredDate}
                  onChangeText={setFormOccurredDate}
                  placeholder="YYYY-MM-DD"
                  placeholderTextColor={theme.colors.textMuted}
                />
              </View>

              {/* Inflow Only Fields: Supplier */}
              {formType === 'inflow' && (
                <View style={styles.formGroup}>
                  <Text style={styles.label}>Supplier (Optional)</Text>
                  <TextInput
                    style={styles.textInput}
                    value={formSupplier}
                    onChangeText={setFormSupplier}
                    placeholder="e.g. UltraTech Cement"
                    placeholderTextColor={theme.colors.textMuted}
                  />
                </View>
              )}

              {/* Outflow Only Fields: Work Item */}
              {formType === 'outflow' && (
                <View style={styles.formGroup}>
                  <Text style={styles.label}>Work Item / Task (Optional)</Text>
                  <TextInput
                    style={styles.textInput}
                    value={formWorkItem}
                    onChangeText={setFormWorkItem}
                    placeholder="e.g. Foundation columns casting"
                    placeholderTextColor={theme.colors.textMuted}
                  />
                </View>
              )}

              <Pressable style={styles.submitButton} onPress={handleFormSubmit} disabled={submitting}>
                {submitting ? (
                  <ActivityIndicator color={theme.colors.actionPrimaryForeground} />
                ) : (
                  <Text style={styles.submitButtonText}>Submit Record</Text>
                )}
              </Pressable>
            </ScrollView>
          </View>

          {/* SELECTION OVERLAY (PROJECT / SITE / UNIT) — rendered inside the same Modal
              rather than a second stacked native Modal, which was leaving the touch
              responder chain stuck after the picker closed. */}
          {pickerType !== null && (
            <View style={styles.pickerOverlay}>
              <View style={styles.pickerCard}>
                <View style={styles.pickerHeader}>
                  <Text style={styles.pickerTitle}>
                    {pickerType === 'project' ? 'Select Project' : pickerType === 'site' ? 'Select Site' : 'Select Unit'}
                  </Text>
                  <Pressable onPress={() => setPickerType(null)}>
                    <Ionicons name="close" size={20} color={theme.colors.textSecondary} />
                  </Pressable>
                </View>

                {pickerType === 'project' && (
                  <FlatList
                    data={projects}
                    keyExtractor={(item) => item.id}
                    renderItem={({ item }) => (
                      <Pressable
                        style={styles.pickerItem}
                        onPress={() => {
                          setFormProjectId(item.id);
                          setFormProjectName(item.name);
                          setFormSiteId('');
                          setFormSiteName('');
                          setPickerType(null);
                        }}
                      >
                        <Text style={styles.pickerItemText}>{item.name}</Text>
                      </Pressable>
                    )}
                    ListEmptyComponent={<Text style={styles.pickerEmptyText}>No projects found</Text>}
                  />
                )}

                {pickerType === 'site' && (
                  <FlatList
                    data={[{ id: '', name: 'All Sites (Project-level)' }, ...formSites]}
                    keyExtractor={(item, index) => item.id || String(index)}
                    renderItem={({ item }) => (
                      <Pressable
                        style={styles.pickerItem}
                        onPress={() => {
                          setFormSiteId(item.id);
                          setFormSiteName(item.id ? item.name : '');
                          setPickerType(null);
                        }}
                      >
                        <Text style={styles.pickerItemText}>{item.name}</Text>
                      </Pressable>
                    )}
                    ListEmptyComponent={<Text style={styles.pickerEmptyText}>No sites found for this project</Text>}
                  />
                )}

                {pickerType === 'unit' && (
                  <>
                    <FlatList
                      data={COMMON_UNITS}
                      keyExtractor={(item) => item}
                      renderItem={({ item }) => (
                        <Pressable
                          style={styles.pickerItem}
                          onPress={() => {
                            setFormUnit(item);
                            setPickerType(null);
                          }}
                        >
                          <Text style={styles.pickerItemText}>{item}</Text>
                        </Pressable>
                      )}
                    />
                    <View style={styles.customUnitRow}>
                      <TextInput
                        style={[styles.textInput, { flex: 1 }]}
                        value={customUnitInput}
                        onChangeText={setCustomUnitInput}
                        placeholder="Add custom unit"
                        placeholderTextColor={theme.colors.textMuted}
                        autoCapitalize="none"
                      />
                      <Pressable
                        style={styles.customUnitAddButton}
                        onPress={() => {
                          const trimmed = customUnitInput.trim();
                          if (!trimmed) return;
                          setFormUnit(trimmed);
                          setCustomUnitInput('');
                          setPickerType(null);
                        }}
                      >
                        <Text style={styles.customUnitAddButtonText}>Add</Text>
                      </Pressable>
                    </View>
                  </>
                )}
              </View>
            </View>
          )}
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
  headerContainer: {
    paddingHorizontal: theme.spacing.space4,
    paddingTop: theme.spacing.space4,
    paddingBottom: theme.spacing.space2,
  },
  headerTitle: {
    fontSize: theme.typography.size2xl,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  headerSubtitle: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textMuted,
    marginTop: 2,
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: theme.colors.backgroundSubtle,
    marginHorizontal: theme.spacing.space4,
    marginTop: theme.spacing.space3,
    marginBottom: theme.spacing.space2,
    borderRadius: theme.radius.lg,
    padding: 4,
  },
  tabButton: {
    flex: 1,
    paddingVertical: theme.spacing.space2,
    alignItems: 'center',
    borderRadius: theme.radius.md,
  },
  activeTabButton: {
    backgroundColor: theme.colors.backgroundSurface,
    ...theme.shadow.subtle,
  },
  tabText: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightMedium,
    color: theme.colors.textMuted,
  },
  activeTabText: {
    color: theme.colors.textPrimary,
    fontWeight: theme.typography.weightSemiBold,
  },
  scrollContainer: {
    flex: 1,
  },
  contentContainer: {
    paddingHorizontal: theme.spacing.space4,
    paddingBottom: 40,
  },
  fab: {
    position: 'absolute',
    bottom: theme.spacing.space6,
    right: theme.spacing.space6,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: theme.colors.actionPrimary,
    justifyContent: 'center',
    alignItems: 'center',
    ...theme.shadow.strong,
    zIndex: 10,
  },
  actionSheetOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    justifyContent: 'flex-end',
  },
  actionSheetContent: {
    backgroundColor: theme.colors.backgroundSurface,
    borderTopLeftRadius: theme.radius.xl,
    borderTopRightRadius: theme.radius.xl,
    padding: theme.spacing.space6,
    paddingBottom: 40,
  },
  actionSheetTitle: {
    fontSize: theme.typography.sizeLg,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
    marginBottom: theme.spacing.space4,
    textAlign: 'center',
  },
  actionSheetOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: theme.spacing.space4,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderDefault,
    gap: theme.spacing.space3,
  },
  actionSheetOptionText: {
    fontSize: theme.typography.sizeMd,
    color: theme.colors.textPrimary,
    fontWeight: theme.typography.weightMedium,
  },
  cancelOption: {
    marginTop: theme.spacing.space3,
    borderBottomWidth: 0,
    justifyContent: 'center',
    backgroundColor: theme.colors.backgroundSubtle,
    borderRadius: theme.radius.lg,
  },
  cancelOptionText: {
    color: theme.colors.textSecondary,
    fontWeight: theme.typography.weightBold,
  },
  formOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  formCard: {
    backgroundColor: theme.colors.backgroundSurface,
    borderTopLeftRadius: theme.radius.xl,
    borderTopRightRadius: theme.radius.xl,
    padding: theme.spacing.space6,
    maxHeight: '90%',
  },
  formHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.space4,
  },
  formTitle: {
    fontSize: theme.typography.sizeLg,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  formGroup: {
    marginBottom: theme.spacing.space4,
  },
  formRow: {
    flexDirection: 'row',
    gap: theme.spacing.space3,
  },
  label: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.space2,
  },
  textInput: {
    height: 48,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    borderRadius: theme.radius.lg,
    paddingHorizontal: theme.spacing.space4,
    color: theme.colors.textPrimary,
    fontSize: theme.typography.sizeMd,
    backgroundColor: theme.colors.backgroundApp,
  },
  inputButton: {
    height: 48,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    borderRadius: theme.radius.lg,
    paddingHorizontal: theme.spacing.space4,
    backgroundColor: theme.colors.backgroundApp,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  inputButtonText: {
    fontSize: theme.typography.sizeMd,
    color: theme.colors.textPrimary,
  },
  inputDisabled: {
    backgroundColor: theme.colors.backgroundSubtle,
    borderColor: theme.colors.borderDefault,
    opacity: 0.8,
  },
  placeholderText: {
    color: theme.colors.textMuted,
  },
  submitButton: {
    height: 48,
    backgroundColor: theme.colors.actionPrimary,
    borderRadius: theme.radius.lg,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: theme.spacing.space4,
  },
  submitButtonText: {
    color: theme.colors.actionPrimaryForeground,
    fontWeight: theme.typography.weightBold,
    fontSize: theme.typography.sizeMd,
  },
  pickerOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.space6,
    zIndex: 30,
    elevation: 30,
  },
  customUnitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.space2,
    marginTop: theme.spacing.space3,
    paddingTop: theme.spacing.space3,
    borderTopWidth: 1,
    borderTopColor: theme.colors.borderDefault,
  },
  customUnitAddButton: {
    height: 48,
    paddingHorizontal: theme.spacing.space4,
    borderRadius: theme.radius.lg,
    backgroundColor: theme.colors.actionPrimary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  customUnitAddButtonText: {
    color: theme.colors.actionPrimaryForeground,
    fontWeight: theme.typography.weightBold,
    fontSize: theme.typography.sizeSm,
  },
  pickerCard: {
    width: '100%',
    maxHeight: '70%',
    backgroundColor: theme.colors.backgroundSurface,
    borderRadius: theme.radius.xl,
    padding: theme.spacing.space6,
    ...theme.shadow.strong,
  },
  pickerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.space4,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderDefault,
    paddingBottom: theme.spacing.space2,
  },
  pickerTitle: {
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  pickerItem: {
    paddingVertical: theme.spacing.space3,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderDefault,
  },
  pickerItemText: {
    fontSize: theme.typography.sizeMd,
    color: theme.colors.textPrimary,
  },
  pickerEmptyText: {
    textAlign: 'center',
    color: theme.colors.textMuted,
    paddingVertical: theme.spacing.space4,
  },
});
