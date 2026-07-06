import React from 'react';
import { View, StyleSheet, ScrollView, Text, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { useTheme, useStyles } from '../../src/theme';
import { ThemeOptionCard } from '../ui/ThemeOptionCard';
import { AppearanceSelector } from '../ui/AppearanceSelector';
import { ArrowLeft } from 'lucide-react-native';

export function ThemeSettingsScreen() {
  const router = useRouter();
  const { theme, themeId, appearance, availableThemes, setThemeId, setAppearance } = useTheme();
  const styles = useStyles(createStyles);

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <ArrowLeft size={24} color={theme.colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Theme & Appearance</Text>
        <View style={{ width: 24 }} />
      </View>

      <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
        
        {/* Theme Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Theme</Text>
          <Text style={styles.sectionDescription}>
            Choose the visual identity used across Mesiri Daily.
          </Text>
          
          <View style={styles.themeList}>
            {availableThemes.map(themeDef => (
              <ThemeOptionCard 
                key={themeDef.id}
                themeDef={themeDef}
                isSelected={themeId === themeDef.id}
                onSelect={setThemeId}
              />
            ))}
          </View>
        </View>
        
        {/* Appearance Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Appearance</Text>
          <Text style={styles.sectionDescription}>
            Choose how Mesiri Daily adapts to light and dark environments.
          </Text>
          
          <AppearanceSelector 
            currentMode={appearance}
            onSelect={setAppearance}
          />
        </View>

      </ScrollView>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.backgroundApp,
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
  backButton: {
    padding: 8,
    marginLeft: -8,
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
    paddingTop: 24,
    maxWidth: 600,
    marginHorizontal: 'auto',
    width: '100%',
    paddingBottom: 40,
  },
  section: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionDescription: {
    fontSize: 14,
    color: theme.colors.textMuted,
    marginBottom: 16,
  },
  themeList: {
    gap: 12,
  },
});
