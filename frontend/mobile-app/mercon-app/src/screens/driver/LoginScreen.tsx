/**
 * Shared MERCON login screen (drivers AND operators).
 * One form, no mode toggle: the user enters their credentials and `signIn`
 * (see lib/auth-context) figures out whether they belong to a driver
 * (phone + license) or an operator (username + password).
 * After sign-in, the auth guard in app/_layout.tsx + role routing in
 * app/index.tsx send the user to the correct home screen.
 */
import React, { useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, Image, ImageBackground,
  StyleSheet, SafeAreaView, StatusBar,
} from 'react-native';
import { User, Lock, Eye, EyeOff, ArrowRight, Headset } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { Button, Input } from '../../components';
import { useAuth } from '../../lib/auth-context';
import { api, getApiErrorMessage } from '../../lib/api';

// eslint-disable-next-line @typescript-eslint/no-var-requires
const logo = require('../../../assets/images/mercon-logo.png');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const heroBg = require('../../../assets/images/login-hero.png');

const LoginScreen = () => {
  const { signIn } = useAuth();

  const [identifier, setIdentifier] = useState('');
  const [secret, setSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleForgot = async () => {
    setError(null);
    setNotice(null);
    if (!identifier.trim()) {
      setError('Enter your username or mobile number first, then tap "Can\'t log in?" again.');
      return;
    }
    try {
      // Notifies all operators/admins that this user needs a reset.
      await api.post('/auth/request-reset', { identifier: identifier.trim() });
      setNotice('Your operator has been notified. They will help you log in.');
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  };

  const handleSignIn = async () => {
    if (!identifier.trim() || !secret.trim()) {
      setError('Please enter your credentials.');
      return;
    }
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await signIn(identifier, secret);
      // Success: the auth guard in app/_layout.tsx switches away from login.
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ImageBackground source={heroBg} style={styles.container} resizeMode="cover">
      <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.gray50} />

      <ScrollView style={styles.scrollFlex} contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Logo — centered, visual anchor */}
        <Image source={logo} style={styles.logo} resizeMode="contain" />

        {/* Card */}
        <View style={styles.card}>
          <View style={styles.form}>
            <Input
              label="Username"
              value={identifier}
              onChangeText={setIdentifier}
              placeholder="Enter your username"
              autoCapitalize="none"
              iconLeft={<User size={20} color={Colors.gray400} />}
            />
            <Input
              label="Password"
              value={secret}
              onChangeText={setSecret}
              placeholder="Enter your password"
              autoCapitalize="none"
              secureTextEntry={!showSecret}
              iconLeft={<Lock size={20} color={Colors.gray400} />}
              iconRight={
                <TouchableOpacity onPress={() => setShowSecret((v) => !v)} hitSlop={8} activeOpacity={0.7}>
                  {showSecret
                    ? <EyeOff size={20} color={Colors.gray400} />
                    : <Eye size={20} color={Colors.gray400} />}
                </TouchableOpacity>
              }
            />

            {error && <Text style={styles.errorText}>{error}</Text>}
            {notice && <Text style={styles.noticeText}>{notice}</Text>}

            <Button
              title={loading ? 'Signing In...' : 'Sign In'}
              onPress={handleSignIn}
              disabled={loading}
              size="lg"
              iconRight={!loading ? <ArrowRight size={20} color={Colors.white} /> : undefined}
            />
          </View>
        </View>

        {/* Notify my operator — outside the card */}
        <TouchableOpacity onPress={handleForgot} activeOpacity={0.7} style={styles.notifyBtn}>
          <Headset size={20} color={Colors.primary} />
          <Text style={styles.notifyText}>Can't log in? Notify my operator</Text>
        </TouchableOpacity>

        <Text style={styles.footer}>
          Having trouble? Contact{' '}
          <Text style={styles.footerLink}>support@mercon.sa</Text>
        </Text>
      </ScrollView>
      </SafeAreaView>
    </ImageBackground>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.gray50,
  },
  safe: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  scrollFlex: {
    flex: 1,
  },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.lg,
    justifyContent: 'center',   // center the login composition on the page
  },
  logo: {
    alignSelf: 'center',
    width: 200,
    height: 106,
  },
  card: {
    marginTop: Spacing['3xl'],   // 40 — breathing room under the logo
    marginHorizontal: Spacing.sm, // slightly narrower than full width
    backgroundColor: Colors.white,
    borderRadius: Radius['2xl'],
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.xl,
    ...Shadows.lg,
  },
  form: {
    gap: Spacing.sm + 2,       // ~10, tighter
  },
  errorText: {
    fontSize: Typography.sm,
    color: Colors.danger,
    marginTop: -Spacing.xs,
  },
  noticeText: {
    fontSize: Typography.sm,
    color: Colors.success,
    marginTop: -Spacing.xs,
  },
  // Secondary action — lighter than the solid Sign In button (no fill/border)
  notifyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    marginTop: Spacing.xl,     // 24
    paddingVertical: Spacing.sm,
  },
  notifyText: {
    fontSize: Typography.sm,
    color: Colors.primary,
    fontWeight: '600',
  },
  footer: {
    textAlign: 'center',
    fontSize: Typography.xs,
    color: Colors.gray500,
    marginTop: 28,
  },
  footerLink: {
    color: Colors.primary,
    fontWeight: '600',
  },
});

export default LoginScreen;
