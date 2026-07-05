import { View, Text, StyleSheet, FlatList, TouchableOpacity, TextInput, Modal, ActivityIndicator, Alert } from 'react-native';
import { useState, useEffect } from 'react';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../../packages/auth/src/client'; // Reuse axios client

type User = {
  id: string;
  full_name: string;
  email: string;
  role: string;
};

const ROLES = ["ADMIN", "PROJECT_MANAGER", "SITE_ENGINEER", "FINANCE"];

export default function UsersScreen() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  // Form state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('SITE_ENGINEER');
  const [creating, setCreating] = useState(false);

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

  const handleCreateUser = async () => {
    if (!name || !email || !password) {
      Alert.alert("Error", "Please fill all fields");
      return;
    }

    setCreating(true);
    try {
      await api.post('/users', {
        full_name: name,
        email,
        password,
        role
      });
      setIsModalOpen(false);
      setName('');
      setEmail('');
      setPassword('');
      setRole('SITE_ENGINEER');
      fetchUsers();
    } catch (e: any) {
      Alert.alert("Error", e.response?.data?.detail || "Failed to create user");
    } finally {
      setCreating(false);
    }
  };

  const renderItem = ({ item }: { item: User }) => (
    <View style={styles.userCard}>
      <View style={styles.userInfo}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{item.full_name.charAt(0)}</Text>
        </View>
        <View>
          <Text style={styles.userName}>{item.full_name}</Text>
          <Text style={styles.userEmail}>{item.email}</Text>
        </View>
      </View>
      <View style={styles.roleBadge}>
        <Text style={styles.roleText}>{item.role.replace('_', ' ')}</Text>
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Team Members</Text>
        <TouchableOpacity style={styles.addButton} onPress={() => setIsModalOpen(true)}>
          <Ionicons name="add" size={20} color="#0E1116" />
          <Text style={styles.addButtonText}>Add User</Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#7ED957" />
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
              <Text style={styles.modalTitle}>Add Team Member</Text>
              <TouchableOpacity onPress={() => setIsModalOpen(false)}>
                <Ionicons name="close" size={24} color="#687280" />
              </TouchableOpacity>
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>Full Name</Text>
              <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Jane Doe" />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>Email Address</Text>
              <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="jane@example.com" autoCapitalize="none" keyboardType="email-address" />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>Password</Text>
              <TextInput style={styles.input} value={password} onChangeText={setPassword} placeholder="Temporary Password" secureTextEntry />
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

            <TouchableOpacity style={styles.submitButton} onPress={handleCreateUser} disabled={creating}>
              {creating ? <ActivityIndicator color="#0E1116" /> : <Text style={styles.submitButtonText}>Create User</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FAFAFB', paddingHorizontal: 16 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 24 },
  title: { fontSize: 24, fontWeight: '700', color: '#0E1116' },
  addButton: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#7ED957', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 8, gap: 4 },
  addButtonText: { color: '#0E1116', fontWeight: '600', fontSize: 14 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyText: { textAlign: 'center', color: '#687280', marginTop: 40 },
  userCard: { backgroundColor: '#FFFFFF', borderRadius: 12, padding: 16, marginBottom: 12, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderWidth: 1, borderColor: '#E5E7EB' },
  userInfo: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#1F222B', justifyContent: 'center', alignItems: 'center' },
  avatarText: { color: '#FFFFFF', fontWeight: '600', fontSize: 16 },
  userName: { fontSize: 16, fontWeight: '600', color: '#0E1116', marginBottom: 2 },
  userEmail: { fontSize: 13, color: '#687280' },
  roleBadge: { backgroundColor: '#F3F4F6', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  roleText: { fontSize: 11, fontWeight: '600', color: '#485563', textTransform: 'capitalize' },
  
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, paddingBottom: 40 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 },
  modalTitle: { fontSize: 20, fontWeight: '600', color: '#0E1116' },
  formGroup: { marginBottom: 16 },
  label: { fontSize: 14, fontWeight: '500', color: '#485563', marginBottom: 8 },
  input: { backgroundColor: '#F3F4F6', borderRadius: 8, padding: 12, fontSize: 15, color: '#0E1116', borderWidth: 1, borderColor: '#E5E7EB' },
  roleSelector: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  roleOption: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF' },
  roleOptionActive: { borderColor: '#7ED957', backgroundColor: '#EFFBE8' },
  roleOptionText: { fontSize: 12, fontWeight: '500', color: '#687280' },
  roleOptionTextActive: { color: '#5EB83A', fontWeight: '600' },
  submitButton: { backgroundColor: '#7ED957', borderRadius: 8, padding: 16, alignItems: 'center', marginTop: 16 },
  submitButtonText: { color: '#0E1116', fontWeight: '600', fontSize: 16 }
});
