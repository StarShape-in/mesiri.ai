import React, { useState, useRef } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, SafeAreaView,
  StatusBar, Image, Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { Button } from '../../components';
import { useCurrentTrip } from '../../lib/use-current-trip';
import { tripService } from '../../lib/trips';
import { ArrowLeft, Check, Camera, ClipboardCheck } from 'lucide-react-native';
import { choosePhoto, type CapturedPhoto } from '../../lib/camera';
import { getApiErrorMessage } from '../../lib/api';

const DeliveryVerificationScreen = () => {
  const router = useRouter();
  const { trip, loading } = useCurrentTrip();
  const [step, setStep] = useState(1);
  const [photos, setPhotos] = useState<CapturedPhoto[]>([]);
  const [submitting, setSubmitting] = useState(false);
  // Track which photo indices have already been uploaded successfully so a retry
  // doesn't re-upload them (prevents duplicate Document rows on a network hiccup).
  const uploadedIndices = useRef<Set<number>>(new Set());
  const inFlight = useRef(false);

  const addPhoto = async () => {
    try {
      const photo = await choosePhoto();
      if (photo) setPhotos((prev) => [...prev, photo].slice(0, 4));
    } catch (e) {
      Alert.alert('Camera', getApiErrorMessage(e));
    }
  };

  const canComplete =
    !!trip && trip.status === 'AtDelivery' && photos.length >= 1 && !submitting && !loading;

  const complete = async () => {
    if (!trip || !canComplete) return;
    // Prevent double-tap re-entrancy
    if (inFlight.current) return;
    inFlight.current = true;
    setSubmitting(true);
    try {
      // Only upload photos not yet successfully uploaded (retry-safe)
      for (let i = 0; i < photos.length; i++) {
        if (!uploadedIndices.current.has(i)) {
          await tripService.uploadPhoto(trip.id, 'pod', photos[i]);
          uploadedIndices.current.add(i);
        }
      }
      await tripService.updateStatus(trip.id, 'Completed');
      router.replace('/trip/completed');
    } catch (e) {
      Alert.alert('Could not complete', getApiErrorMessage(e));
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.backBtn} activeOpacity={0.8} onPress={() => router.back()}>
            <ArrowLeft size={22} color={Colors.gray900} strokeWidth={2.2} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Delivery Verification</Text>
          <View style={styles.placeholder} />
        </View>

        {/* Step Indicator */}
        <View style={styles.stepRow}>
          {[1, 2].map((s) => (
            <React.Fragment key={s}>
              <TouchableOpacity
                style={[styles.stepCircle, step >= s ? styles.stepActive : null]}
                activeOpacity={0.8}
                onPress={() => step > s && setStep(s)}
              >
                {step > s ? (
                  <Check size={16} color={Colors.white} strokeWidth={3} />
                ) : (
                  <Text style={[styles.stepNum, step >= s ? styles.stepNumActive : null]}>{s}</Text>
                )}
              </TouchableOpacity>
              {s < 2 && (
                <View style={[styles.stepLine, step > s ? styles.stepLineActive : null]} />
              )}
            </React.Fragment>
          ))}
        </View>
        <View style={styles.stepLabels}>
          <Text style={[styles.stepLabel, step === 1 ? styles.stepLabelActive : null]}>
            Delivery Photos
          </Text>
          <Text style={[styles.stepLabel, step === 2 ? styles.stepLabelActive : null]}>
            Review & Complete
          </Text>
        </View>

        {step === 1 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepTitle}>Proof of Delivery</Text>
            <Text style={styles.stepSub}>
              Take at least one photo of the delivered cargo (POD).
            </Text>
            <View style={styles.photoGrid}>
              {[0, 1, 2, 3].map((i) => (
                <TouchableOpacity
                  key={i}
                  style={[styles.photoSlot, photos[i] ? styles.photoFilled : null]}
                  activeOpacity={0.8}
                  onPress={photos[i] ? undefined : addPhoto}
                >
                  {photos[i] ? (
                    <Image source={{ uri: photos[i].uri }} style={styles.photoImg} />
                  ) : (
                    <View style={styles.photoEmpty}>
                      <Camera size={26} color={Colors.gray400} strokeWidth={1.8} />
                      <Text style={styles.photoEmptyText}>Photo {i + 1}</Text>
                    </View>
                  )}
                </TouchableOpacity>
              ))}
            </View>
            <TouchableOpacity style={styles.addPhotoBtn} activeOpacity={0.8} onPress={addPhoto}>
              <Text style={styles.addPhotoText}>+ Add Photo</Text>
            </TouchableOpacity>
            <View style={styles.notice}>
              <ClipboardCheck size={16} color={Colors.gray600} strokeWidth={2} />
              <Text style={styles.noticeText}>
                Ensure the delivered cargo is clearly visible in the photo.
              </Text>
            </View>
            <Button
              title="Continue to Review"
              onPress={() => setStep(2)}
              disabled={photos.length < 1}
            />
          </View>
        )}

        {step === 2 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepTitle}>Review &amp; Complete</Text>
            <Text style={styles.stepSub}>
              Confirm the delivery details, then complete the trip.
            </Text>

            <View style={styles.timestampRow}>
              <Text style={styles.timestampLabel}>Trip</Text>
              <Text style={styles.timestampValue}>#{trip?.ref_id ?? '—'}</Text>
            </View>
            <View style={styles.timestampRow}>
              <Text style={styles.timestampLabel}>Customer</Text>
              <Text style={styles.timestampValue}>{trip?.customer?.name ?? '—'}</Text>
            </View>
            <View style={styles.timestampRow}>
              <Text style={styles.timestampLabel}>Cargo</Text>
              <Text style={styles.timestampValue}>{trip?.cargo_type ?? '—'}</Text>
            </View>
            <View style={styles.timestampRow}>
              <Text style={styles.timestampLabel}>POD Photos</Text>
              <Text style={styles.timestampValue}>{photos.length}</Text>
            </View>
            <View style={styles.timestampRow}>
              <Text style={styles.timestampLabel}>Delivery Time</Text>
              <Text style={styles.timestampValue}>
                {new Date().toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
              </Text>
            </View>

            <Button
              title={submitting ? 'Completing…' : 'Complete Delivery'}
              onPress={complete}
              disabled={!canComplete}
            />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  scroll: {
    padding: Spacing.lg,
    paddingBottom: Spacing['3xl'],
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.xl,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: Colors.white,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadows.sm,
  },
  backIcon: {
    fontSize: 20,
    color: Colors.gray900,
  },
  headerTitle: {
    fontSize: Typography.lg,
    fontWeight: '700',
    color: Colors.gray900,
  },
  placeholder: {
    width: 40,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.xs,
    gap: 0,
  },
  stepCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.gray200,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepActive: {
    backgroundColor: Colors.primary,
  },
  stepNum: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray500,
  },
  stepNumActive: {
    color: Colors.white,
  },
  stepLine: {
    width: 60,
    height: 2,
    backgroundColor: Colors.gray200,
  },
  stepLineActive: {
    backgroundColor: Colors.primary,
  },
  stepLabels: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: Spacing.xl,
  },
  stepLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    fontWeight: '600',
  },
  stepLabelActive: {
    color: Colors.primary,
  },
  stepContent: {
    gap: Spacing.lg,
  },
  stepTitle: {
    fontSize: Typography.xl,
    fontWeight: '700',
    color: Colors.gray900,
  },
  stepSub: {
    fontSize: Typography.sm,
    color: Colors.gray500,
    lineHeight: 20,
  },
  photoGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  photoSlot: {
    width: '47%',
    aspectRatio: 1.3,
    borderRadius: Radius.lg,
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: Colors.gray300,
    borderStyle: 'dashed',
    backgroundColor: Colors.white,
  },
  photoFilled: {
    borderStyle: 'solid',
  },
  photoImg: {
    width: '100%',
    height: '100%',
  },
  photoEmpty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  photoEmoji: {
    fontSize: 24,
  },
  photoEmptyText: {
    fontSize: Typography.xs,
    color: Colors.gray400,
  },
  addPhotoBtn: {
    borderWidth: 2,
    borderColor: Colors.primary,
    borderStyle: 'dashed',
    borderRadius: Radius.lg,
    padding: Spacing.md,
    alignItems: 'center',
  },
  addPhotoText: {
    fontSize: Typography.sm,
    color: Colors.primary,
    fontWeight: '700',
  },
  notice: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: '#FFF7ED',
    borderRadius: Radius.lg,
    padding: Spacing.md,
  },
  noticeText: {
    flex: 1,
    fontSize: Typography.sm,
    color: Colors.gray700,
    lineHeight: 20,
  },
  signatureBox: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.gray200,
  },
  signatureArea: {
    height: 140,
    alignItems: 'center',
    justifyContent: 'center',
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray200,
  },
  signaturePlaceholder: {
    fontSize: Typography.sm,
    color: Colors.gray400,
    marginBottom: Spacing.xl,
  },
  signatureLine: {
    position: 'absolute',
    bottom: 30,
    left: 30,
    right: 30,
    height: 1,
    backgroundColor: Colors.gray300,
  },
  signatureLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    textAlign: 'center',
    padding: Spacing.sm,
  },
  timestampRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: Colors.white,
    borderRadius: Radius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.gray200,
  },
  timestampLabel: {
    fontSize: Typography.sm,
    color: Colors.gray500,
  },
  timestampValue: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
});

export default DeliveryVerificationScreen;
