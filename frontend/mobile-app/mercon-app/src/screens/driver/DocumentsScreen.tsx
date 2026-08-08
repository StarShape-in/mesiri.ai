import React from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, SafeAreaView, StatusBar,
  FlatList, ActivityIndicator, Linking, RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { ArrowLeft, TriangleAlert } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { StatusBadge } from '../../components';
import { API_URL } from '../../lib/api';
import { useDocuments, docTypeLabel, docIcon, docStatus, type DriverDocument } from '../../lib/documents';

const FILE_BASE = API_URL.replace(/\/api\/?$/, '');

function formatDate(iso?: string | null): string {
  if (!iso) return 'No expiry';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

function openFile(fileUrl: string) {
  const url = fileUrl.startsWith('http') ? fileUrl : `${FILE_BASE}${fileUrl}`;
  Linking.openURL(url).catch(() => {});
}

const DocumentCard = ({ doc }: { doc: DriverDocument }) => {
  const st = docStatus(doc);
  return (
    <View style={[styles.card, st.kind === 'expired' ? styles.cardExpired : null]}>
      <View style={styles.cardHeader}>
        <View style={styles.iconBox}>
          {(() => { const Icon = docIcon(doc.doc_type); return <Icon size={22} color={Colors.primary} strokeWidth={2} />; })()}
        </View>
        <View style={styles.cardInfo}>
          <Text style={styles.docTitle}>{docTypeLabel(doc.doc_type)}</Text>
          {doc.issue_date ? <Text style={styles.docNumber}>Issued {formatDate(doc.issue_date)}</Text> : null}
        </View>
        <StatusBadge status={st.label} />
      </View>

      <View style={styles.expiryRow}>
        <Text style={styles.expiryLabel}>Expires</Text>
        <Text
          style={[
            styles.expiryValue,
            st.kind === 'expired' ? styles.expiredText : st.kind === 'expiring' ? styles.expiringText : null,
          ]}
        >
          {formatDate(doc.expiry_date)}
        </Text>
      </View>

      <View style={styles.actionRow}>
        <TouchableOpacity style={styles.viewBtn} activeOpacity={0.8} onPress={() => openFile(doc.file_url)}>
          <Text style={styles.viewBtnText}>View</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const DocumentsScreen = () => {
  const router = useRouter();
  const { documents, loading, error, refetch } = useDocuments();

  const expiredCount = documents.filter((d) => docStatus(d).kind === 'expired').length;
  const expiringCount = documents.filter((d) => docStatus(d).kind === 'expiring').length;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} activeOpacity={0.8} onPress={() => router.back()}>
          <ArrowLeft size={22} color={Colors.gray900} strokeWidth={2.2} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>My Documents</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Alert Banner */}
      {(expiredCount > 0 || expiringCount > 0) && (
        <View style={styles.alertBanner}>
          <TriangleAlert size={18} color="#D97706" strokeWidth={2} />
          <Text style={styles.alertText}>
            {expiredCount > 0 && `${expiredCount} document(s) expired. `}
            {expiringCount > 0 && `${expiringCount} document(s) expiring soon.`}
          </Text>
        </View>
      )}

      <FlatList
        data={documents}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading && documents.length > 0} onRefresh={refetch} />}
        renderItem={({ item }) => <DocumentCard doc={item} />}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
          ) : (
            <Text style={styles.emptyText}>{error ?? 'No documents on file.'}</Text>
          )
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  header: {
    backgroundColor: Colors.white,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: Colors.gray100,
    alignItems: 'center',
    justifyContent: 'center',
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
  alertBanner: {
    backgroundColor: '#FFF7ED',
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: '#FED7AA',
  },
  alertIcon: {
    fontSize: 18,
  },
  alertText: {
    fontSize: Typography.sm,
    color: '#92400E',
    fontWeight: '600',
    flex: 1,
  },
  list: {
    padding: Spacing.lg,
    gap: Spacing.md,
    flexGrow: 1,
  },
  emptyText: {
    textAlign: 'center',
    color: Colors.gray500,
    fontSize: Typography.sm,
    marginTop: Spacing['3xl'],
  },
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    ...Shadows.sm,
    gap: Spacing.md,
  },
  cardExpired: {
    borderLeftWidth: 3,
    borderLeftColor: Colors.error,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  iconBox: {
    width: 48,
    height: 48,
    borderRadius: Radius.lg,
    backgroundColor: Colors.gray100,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  docIcon: {
    fontSize: 24,
  },
  cardInfo: {
    flex: 1,
  },
  docTitle: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  docNumber: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    marginTop: 2,
  },
  expiryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: Colors.gray50,
    borderRadius: Radius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  expiryLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  expiryValue: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  expiredText: {
    color: Colors.error,
  },
  expiringText: {
    color: '#D97706',
  },
  actionRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  viewBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: Colors.gray300,
    borderRadius: Radius.lg,
    paddingVertical: Spacing.sm,
    alignItems: 'center',
  },
  viewBtnText: {
    fontSize: Typography.sm,
    color: Colors.gray700,
    fontWeight: '600',
  },
});

export default DocumentsScreen;
