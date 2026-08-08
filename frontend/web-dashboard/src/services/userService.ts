import { api } from '@/lib/api';
import type { User } from '@mercon/shared-types';

/** @deprecated alias kept for existing imports — use `User` from @mercon/shared-types */
export type UserDTO = User;

export const userService = {
  getUsers: async (): Promise<UserDTO[]> => {
    const { data } = await api.get('/users');
    return data.data;
  },
  
  createUser: async (userData: Partial<UserDTO> & { password?: string }): Promise<UserDTO> => {
    const { data } = await api.post('/users', userData);
    return data.data;
  },
  
  updateUser: async (id: string, userData: Partial<UserDTO> & { password?: string }): Promise<UserDTO> => {
    const { data } = await api.put(`/users/${id}`, userData);
    return data.data;
  },
  
  deleteUser: async (id: string): Promise<void> => {
    await api.delete(`/users/${id}`);
  }
};
