import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { login } from '@mesiri/auth';
import { useAuth } from './_layout';
import { useTheme, useStyles } from '../src/theme';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { signIn } = useAuth();
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const handleLogin = async () => {
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      await login(email, password);
      signIn();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.content}>
        <View style={styles.headerContainer}>
          <Text style={styles.title}>Mesiri AI</Text>
          <Text style={styles.subtitle}>Welcome back. Sign in to your workspace.</Text>
        </View>

        <View style={styles.form}>
          {error ? (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}
          
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Email Address</Text>
            <TextInput
              style={styles.input}
              placeholder="you@construction.com"
              placeholderTextColor={theme.colors.textMuted}
              autoCapitalize="none"
              keyboardType="email-address"
              value={email}
              onChangeText={setEmail}
            />
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              placeholder="••••••••"
              placeholderTextColor={theme.colors.textMuted}
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />
          </View>

          <TouchableOpacity 
            style={[styles.button, loading && styles.buttonDisabled]} 
            onPress={handleLogin}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color={theme.colors.actionPrimaryForeground} />
            ) : (
              <Text style={styles.buttonText}>Sign In</Text>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.backgroundApp, // surface-app
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: theme.spacing.space6, // 24
  },
  headerContainer: {
    marginBottom: theme.spacing.space10, // 40
  },
  title: {
    fontSize: 32,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary, // neutral-900
    marginBottom: theme.spacing.space2,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: theme.typography.sizeMd,
    color: theme.colors.textSecondary, // neutral-500
    lineHeight: 24,
  },
  form: {
    gap: theme.spacing.space5, // 20
  },
  inputContainer: {
    gap: theme.spacing.space2,
  },
  label: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightMedium,
    color: theme.colors.textPrimary, // neutral-800
  },
  input: {
    backgroundColor: theme.colors.backgroundSurface, // surface-primary
    borderWidth: 1,
    borderColor: theme.colors.borderDefault, // border-strong
    borderRadius: theme.radius.lg, // input default radius
    padding: theme.spacing.space4,
    height: 52, // Better touch target for mobile (44px min, 52px comfortable)
    fontSize: theme.typography.sizeMd,
    color: theme.colors.textPrimary, // neutral-800
  },
  button: {
    backgroundColor: theme.colors.actionPrimary, // primary
    borderRadius: theme.radius.lg,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: theme.spacing.space3,
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  buttonText: {
    color: theme.colors.actionPrimaryForeground, // dark-deep
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightSemiBold,
  },
  errorContainer: {
    backgroundColor: theme.colors.statusDangerBackground, // error-soft
    padding: theme.spacing.space3,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.statusDangerBorder, // error
  },
  errorText: {
    color: theme.colors.statusDangerForeground,
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightMedium,
  }
});
