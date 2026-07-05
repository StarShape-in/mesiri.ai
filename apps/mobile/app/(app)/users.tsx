import { View, Text, StyleSheet, FlatList, TouchableOpacity, TextInput, Modal, ActivityIndicator, Alert } from 'react-native';
import { useState, useEffect } from 'react';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@mesiri/auth'; // Reuse axios client
import { useTheme, useStyles } from '../../src/theme';

type User = {
  id: string;
  full_name: string;
  email: string;
  role: string;
  whatsapp_number?: string | null;
};

const ROLES = ["ADMIN", "PROJECT_MANAGER", "SITE_ENGINEER", "FINANCE"];

export default function UsersScreen() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  // Form state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('SITE_ENGINEER');
  const [whatsapp, setWhatsapp] = useState('');
  const [creating, setCreating] = useState(false);

  const isEditing = editingUser !== null;

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await api.get('/users');
      setUsers(res.data);
    } catch (e: any) {
      if (e.response?.status === 403) {
        Alert.alert("Access Denied", "Only administrators can view the team.");
      } else {
        Alert.alert("Error", "Failed to fetch users");
      }
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setName('');
    setEmail('');
    setPassword('');
    setRole('SITE_ENGINEER');
    setWhatsapp('');
  };

  const openCreate = () => {
    setEditingUser(null);
    resetForm();
    setIsModalOpen(true);
  };

  const openEdit = (user: User) => {
    setEditingUser(user);
    setName(user.full_name);
    setEmail(user.email);
    setPassword('');
    setRole(user.role);
    setWhatsapp(user.whatsapp_number ?? '');
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingUser(null);
    resetForm();
  };

  const handleSubmit = async () => {
    if (isEditing) {
      if (!name) {
        Alert.alert("Error", "Name is required");
        return;
      }
    } else if (!name || !email || !password) {
      Alert.alert("Error", "Please fill name, email and password");
      return;
    }

    setCreating(true);
    try {
      if (isEditing && editingUser) {
        const payload: Record<string, string> = {
          full_name: name,
          role,
          whatsapp_number: whatsapp.trim(),
        };
        if (password) payload.password = password;
        await api.patch(`/users/${editingUser.id}`, payload);
      } else {
        await api.post('/users', {
          full_name: name,
          email,
          password,
          role,
          whatsapp_number: whatsapp.trim() || null,
        });
      }
      closeModal();
      fetchUsers();
    } catch (e: any) {
      Alert.alert(
        "Error",
        e.response?.data?.detail || `Failed to ${isEditing ? 'update' : 'create'} user`
      );
    } finally {
      setCreating(false);
    }
  };

  const renderItem = ({ item }: { item: User }) => (
    <TouchableOpacity style={styles.userCard} onPress={() => openEdit(item)} activeOpacity={0.7}>
      <View style={styles.userInfo}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{item.full_name.charAt(0)}</Text>
        </View>
        <View style={styles.userInfoText}>
          <Text style={styles.userName}>{item.full_name}</Text>
          <Text style={styles.userEmail}>{item.email}</Text>
          <Text style={styles.userWhatsapp}>
            <Ionicons name="logo-whatsapp" size={12} color={theme.colors.textMuted} />
            {' '}{item.whatsapp_number || 'No WhatsApp number'}
          </Text>
        </View>
      </View>
      <View style={styles.roleBadge}>
        <Text style={styles.roleText}>{item.role.replace('_', ' ')}</Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Team Members</Text>
        <TouchableOpacity style={styles.addButton} onPress={openCreate}>
          <Ionicons name="add" size={20} color={theme.colors.actionPrimaryForeground} />
          <Text style={styles.addButtonText}>Add User</Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={theme.colors.actionPrimary} />
        </View>
      ) : (
        <FlatList
          data={users}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          contentContainerStyle={{ paddingBottom: 24 }}
          ListEmptyComponent={<Text style={styles.emptyText}>No users found.</Text>}
        />
      )}

      {/* CREATE USER MODAL */}
      <Modal visible={isModalOpen} animationType="slide" transparent={true}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{isEditing ? 'Edit Team Member' : 'Add Team Member'}</Text>
              <TouchableOpacity onPress={closeModal}>
                <Ionicons name="close" size={24} color={theme.colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>Full Name</Text>
              <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Jane Doe" />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>Email Address</Text>
              <TextInput
                style={[styles.input, isEditing && styles.inputDisabled]}
                value={email}
                onChangeText={setEmail}
                placeholder="jane@example.com"
                autoCapitalize="none"
                keyboardType="email-address"
                editable={!isEditing}
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>WhatsApp Number</Text>
              <TextInput
                style={styles.input}
                value={whatsapp}
                onChangeText={setWhatsapp}
                placeholder="+91 98765 43210"
                autoCapitalize="none"
                keyboardType="phone-pad"
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>{isEditing ? 'New Password' : 'Password'}</Text>
              <TextInput style={styles.input} value={password} onChangeText={setPassword} placeholder={isEditing ? 'Leave blank to keep current' : 'Temporary Password'} secureTextEntry />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>Role</Text>
              <View style={styles.roleSelector}>
                {ROLES.map((r) => (
                  <TouchableOpacity
                    key={r}
                    style={[styles.roleOption, role === r && styles.roleOptionActive]}
                    onPress={() => setRole(r)}
                  >
                    <Text style={[styles.roleOptionText, role === r && styles.roleOptionTextActive]}>
                      {r.replace('_', ' ')}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <TouchableOpacity style={styles.submitButton} onPress={handleSubmit} disabled={creating}>
              {creating ? <ActivityIndicator color={theme.colors.actionPrimaryForeground} /> : <Text style={styles.submitButtonText}>{isEditing ? 'Save Changes' : 'Create User'}</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.backgroundApp, paddingHorizontal: theme.spacing.space4 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: theme.spacing.space6 },
  title: { fontSize: theme.typography.size2xl, fontWeight: theme.typography.weightBold, color: theme.colors.textPrimary },
  addButton: { flexDirection: 'row', alignItems: 'center', backgroundColor: theme.colors.actionPrimary, paddingHorizontal: theme.spacing.space4, paddingVertical: theme.spacing.space2, borderRadius: theme.radius.md, gap: theme.spacing.space1 },
  addButtonText: { color: theme.colors.actionPrimaryForeground, fontWeight: theme.typography.weightSemiBold, fontSize: theme.typography.sizeSm },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyText: { textAlign: 'center', color: theme.colors.textSecondary, marginTop: 40 },
  userCard: { backgroundColor: theme.colors.backgroundSurface, borderRadius: theme.radius.lg, padding: theme.spacing.space4, marginBottom: theme.spacing.space3, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderWidth: 1, borderColor: theme.colors.borderDefault },
  userInfo: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.space3 },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: theme.colors.backgroundInverse, justifyContent: 'center', alignItems: 'center' },
  avatarText: { color: theme.colors.textInverse, fontWeight: theme.typography.weightSemiBold, fontSize: theme.typography.sizeMd },
  userInfoText: { flexShrink: 1 },
  userName: { fontSize: theme.typography.sizeMd, fontWeight: theme.typography.weightSemiBold, color: theme.colors.textPrimary, marginBottom: 2 },
  userEmail: { fontSize: 13, color: theme.colors.textSecondary },
  userWhatsapp: { fontSize: 12, color: theme.colors.textMuted, marginTop: 2 },
  roleBadge: { backgroundColor: theme.colors.backgroundSubtle, paddingHorizontal: 10, paddingVertical: 4, borderRadius: theme.radius.lg },
  roleText: { fontSize: 11, fontWeight: theme.typography.weightSemiBold, color: theme.colors.textMuted, textTransform: 'capitalize' },
  
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: theme.colors.backgroundSurface, borderTopLeftRadius: theme.radius.xl, borderTopRightRadius: theme.radius.xl, padding: theme.spacing.space6, paddingBottom: 40 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.space6 },
  modalTitle: { fontSize: theme.typography.sizeXl, fontWeight: theme.typography.weightSemiBold, color: theme.colors.textPrimary },
  formGroup: { marginBottom: theme.spacing.space4 },
  label: { fontSize: theme.typography.sizeSm, fontWeight: theme.typography.weightMedium, color: theme.colors.textMuted, marginBottom: theme.spacing.space2 },
  input: { backgroundColor: theme.colors.backgroundSubtle, borderRadius: theme.radius.md, padding: theme.spacing.space3, fontSize: 15, color: theme.colors.textPrimary, borderWidth: 1, borderColor: theme.colors.borderDefault },
  inputDisabled: { opacity: 0.6, color: theme.colors.textMuted },
  roleSelector: { flexDirection: 'row', flexWrap: 'wrap', gap: theme.spacing.space2 },
  roleOption: { paddingHorizontal: theme.spacing.space3, paddingVertical: theme.spacing.space2, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.colors.borderDefault, backgroundColor: theme.colors.backgroundSurface },
  roleOptionActive: { borderColor: theme.colors.actionPrimary, backgroundColor: theme.colors.actionSecondary },
  roleOptionText: { fontSize: theme.typography.sizeXs, fontWeight: theme.typography.weightMedium, color: theme.colors.textSecondary },
  roleOptionTextActive: { color: theme.colors.textPrimary, fontWeight: theme.typography.weightSemiBold },
  submitButton: { backgroundColor: theme.colors.actionPrimary, borderRadius: theme.radius.md, padding: theme.spacing.space4, alignItems: 'center', marginTop: theme.spacing.space4 },
  submitButtonText: { color: theme.colors.actionPrimaryForeground, fontWeight: theme.typography.weightSemiBold, fontSize: theme.typography.sizeMd }
});
