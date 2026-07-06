import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity, Text, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { api } from '@mesiri/auth';
import { useTheme, useStyles } from '../../src/theme';
import { FormTextInput } from '../ui/FormTextInput';
import { FormSection } from '../ui/FormSection';
import { ArrowLeft } from 'lucide-react-native';

export function CreateProjectScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    location: '',
    client: '',
    description: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) newErrors.name = 'Project Name is required';
    if (!formData.location.trim()) newErrors.location = 'Location is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    
    setIsSubmitting(true);

    try {
      await api.post('/projects', {
        name: formData.name.trim(),
        code: formData.code.trim() || null,
        location: formData.location.trim() || null,
        client: formData.client.trim() || null,
        description: formData.description.trim() || null,
      });

      // On success, go back; the list refetches on focus.
      Alert.alert("Success", "Project created successfully");
      router.back();
    } catch (error: any) {
      Alert.alert(
        "Submission Failed",
        error?.response?.data?.detail || "There was an error creating the project. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <ArrowLeft size={24} color={theme.colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>New Project</Text>
        <View style={{ width: 24 }} />
      </View>

      <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
        
        <FormSection title="Project Details">
          <FormTextInput 
            label="Project Name *"
            placeholder="e.g. Skyline Towers Phase 2"
            value={formData.name}
            onChangeText={t => setFormData(p => ({ ...p, name: t }))}
            error={errors.name}
          />
          <FormTextInput 
            label="Project Code"
            placeholder="e.g. SKY-002"
            value={formData.code}
            onChangeText={t => setFormData(p => ({ ...p, code: t }))}
          />
          <FormTextInput 
            label="Location *"
            placeholder="e.g. North Zone, Sector 4"
            value={formData.location}
            onChangeText={t => setFormData(p => ({ ...p, location: t }))}
            error={errors.location}
          />
          <FormTextInput 
            label="Client"
            placeholder="e.g. Acme Corp"
            value={formData.client}
            onChangeText={t => setFormData(p => ({ ...p, client: t }))}
          />
          <FormTextInput 
            label="Description"
            placeholder="Brief overview of the project..."
            multiline
            numberOfLines={3}
            value={formData.description}
            onChangeText={t => setFormData(p => ({ ...p, description: t }))}
            style={{ height: 80, textAlignVertical: 'top' }}
          />
        </FormSection>

      </ScrollView>

      {/* Fixed Footer Actions */}
      <View style={styles.footer}>
        <TouchableOpacity 
          style={[styles.submitButton, isSubmitting && styles.submitButtonDisabled]}
          onPress={handleSubmit}
          disabled={isSubmitting}
        >
          <Text style={styles.submitText}>
            {isSubmitting ? 'Creating...' : 'Create Project'}
          </Text>
        </TouchableOpacity>
      </View>
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
    maxWidth: 600,
    marginHorizontal: 'auto',
    width: '100%',
    paddingBottom: 40,
  },
  footer: {
    padding: 16,
    backgroundColor: theme.colors.backgroundSurface,
    borderTopWidth: 1,
    borderTopColor: theme.colors.borderSubtle,
  },
  submitButton: {
    backgroundColor: theme.colors.actionPrimary,
    paddingVertical: 14,
    borderRadius: theme.radius.md,
    alignItems: 'center',
  },
  submitButtonDisabled: {
    opacity: 0.6,
  },
  submitText: {
    fontSize: 15,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.actionPrimaryForeground,
  }
});
