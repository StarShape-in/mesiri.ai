import React from 'react';
import { View, StyleSheet, Text, TouchableOpacity, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { Boxes, FileText, WalletCards, Images, ChevronRight, HardHat } from 'lucide-react-native';
import { useScope } from '../../state/ScopeProvider';
import { useStyles, useTheme } from '../../src/theme';

export function FieldDashboardScreen() {
  const router = useRouter();
  const { scope } = useScope();
  const styles = useStyles(createStyles);
  const { theme } = useTheme();

  const scopeText =
    scope.mode === 'portfolio'
      ? 'All Projects Portfolio'
      : scope.mode === 'project'
      ? scope.projectName
      : `${scope.projectName} • ${scope.siteName}`;

  const dashboardItems = [
    {
      id: 'materials',
      title: 'Materials Log',
      description: 'Track material inflows, outflows, and current inventory',
      icon: Boxes,
      color: '#3B82F6', // Blue
      route: '/field/materials' as const,
    },
    {
      id: 'dprs',
      title: 'Daily Progress Reports',
      description: 'Submit and view daily site updates and logs',
      icon: FileText,
      color: '#10B981', // Green
      route: '/dprs' as const,
    },
    {
      id: 'expenses',
      title: 'Expenses & Petty Cash',
      description: 'Log vendor invoices and petty cash disbursements',
      icon: WalletCards,
      color: '#F59E0B', // Amber
      route: '/expenses' as const,
    },
    {
      id: 'gallery',
      title: 'Site Gallery',
      description: 'View and upload progress photos from the field',
      icon: Images,
      color: '#EC4899', // Pink
      route: '/gallery' as const,
    },
  ];

  return (
    <View style={styles.container}>
      {/* Scope Header */}
      <View style={styles.headerContainer}>
        <View style={styles.titleRow}>
          <HardHat size={24} color={theme.colors.textPrimary} style={{ marginRight: 8 }} />
          <Text style={styles.headerTitle}>Field Operations</Text>
        </View>
        <Text style={styles.headerSubtitle}>{scopeText}</Text>
      </View>

      <ScrollView 
        style={styles.scrollContainer}
        contentContainerStyle={styles.contentContainer}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.sectionTitle}>Field Tools</Text>
        
        {dashboardItems.map((item) => {
          const IconComponent = item.icon;
          return (
            <TouchableOpacity
              key={item.id}
              style={styles.card}
              onPress={() => router.push(item.route as any)}
              activeOpacity={0.7}
            >
              <View style={[styles.iconWrapper, { backgroundColor: `${item.color}15` }]}>
                <IconComponent size={22} color={item.color} />
              </View>
              <View style={styles.cardContent}>
                <Text style={styles.cardTitle}>{item.title}</Text>
                <Text style={styles.cardDescription}>{item.description}</Text>
              </View>
              <ChevronRight size={18} color={theme.colors.textMuted} />
            </TouchableOpacity>
          );
        })}
      </ScrollView>
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
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
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
  scrollContainer: {
    flex: 1,
  },
  contentContainer: {
    paddingHorizontal: theme.spacing.space4,
    paddingTop: theme.spacing.space4,
    paddingBottom: 40,
  },
  sectionTitle: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: theme.spacing.space3,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.backgroundSurface,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.space4,
    marginBottom: theme.spacing.space3,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    ...theme.shadow.subtle,
  },
  iconWrapper: {
    width: 44,
    height: 44,
    borderRadius: theme.radius.md,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: theme.spacing.space4,
  },
  cardContent: {
    flex: 1,
    paddingRight: theme.spacing.space2,
  },
  cardTitle: {
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
    marginBottom: 2,
  },
  cardDescription: {
    fontSize: 13,
    color: theme.colors.textSecondary,
    lineHeight: 18,
  },
});
