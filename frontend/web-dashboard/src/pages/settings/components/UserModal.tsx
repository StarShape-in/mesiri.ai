import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import Btn from '@/components/ui/Btn';
import FormInput from '@/components/ui/FormInput';
import { UserDTO } from '@/services/userService';

interface UserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<UserDTO> & { password?: string }) => void;
  initialData?: UserDTO | null;
  isLoading: boolean;
}

export default function UserModal({ isOpen, onClose, onSave, initialData, isLoading }: UserModalProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('Operator');
  const [status, setStatus] = useState<'Active'|'Inactive'>('Active');
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (isOpen) {
      if (initialData) {
        setName(initialData.name || '');
        setEmail(initialData.email || '');
        setRole(initialData.role || 'Operator');
        setStatus(initialData.status || 'Active');
        setPassword('');
      } else {
        setName('');
        setEmail('');
        setRole('Operator');
        setStatus('Active');
        setPassword('');
      }
    }
  }, [isOpen, initialData]);

  const handleSubmit = () => {
    const data: any = { name, email, role, status };
    if (password) data.password = password;
    onSave(data);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{initialData ? 'Edit User' : 'Invite New User'}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <FormInput label="Full Name" name="name" value={name} onChange={(e) => setName(e.target.value)} />
          <FormInput label="Email" name="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-bold text-[#111]">Role</label>
            <select 
              value={role} 
              onChange={(e) => setRole(e.target.value)}
              className="w-full bg-[#F9F9FB] border border-black/[0.05] rounded-xl px-4 py-2.5 text-sm outline-none focus:bg-white focus:border-[#E8450F] transition-all"
            >
              <option value="Admin">Admin</option>
              <option value="Operator">Operator</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-bold text-[#111]">Status</label>
            <select 
              value={status} 
              onChange={(e) => setStatus(e.target.value as 'Active'|'Inactive')}
              className="w-full bg-[#F9F9FB] border border-black/[0.05] rounded-xl px-4 py-2.5 text-sm outline-none focus:bg-white focus:border-[#E8450F] transition-all"
            >
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>

          <FormInput 
            label={initialData ? "New Password (Leave blank to keep current)" : "Password"} 
            name="password" 
            type="password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
          />
        </div>
        <DialogFooter>
          <Btn variant="outline" label="Cancel" onClick={onClose} disabled={isLoading} />
          <Btn label="Save User" onClick={handleSubmit} disabled={isLoading || !name || !email || (!initialData && !password)} />
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
