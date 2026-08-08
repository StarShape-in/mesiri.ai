import React, { useState } from 'react';
import { Modal, Pressable, Text, TouchableOpacity, View } from 'react-native';
import { Ban, CircleCheck, EllipsisVertical, SquarePen, Trash2 } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';
import type { CustomerListItem, CustomerPermissions } from '../types';

interface MenuAction {
  key: string;
  label: string;
  Icon: LucideIcon;
  onPress: () => void;
  destructive?: boolean;
}

interface CustomerOverflowMenuProps {
  customer: CustomerListItem;
  permissions: CustomerPermissions;
  onEdit: () => void;
  onToggleActive: () => void;
  onDelete: () => void;
}

/**
 * Three-dot menu on the customer card.
 *
 * Only actions the signed-in role is allowed to perform are listed, and the
 * trigger hides entirely when none are. "Renew Contract", "View Billing" and
 * "View Documents" from the design are absent: there is no contract entity,
 * and no customer-scoped billing or document screen exists in the app yet —
 * listing them would be dead UI.
 */
export function CustomerOverflowMenu({
  customer,
  permissions,
  onEdit,
  onToggleActive,
  onDelete,
}: CustomerOverflowMenuProps) {
  const [open, setOpen] = useState(false);

  const actions: MenuAction[] = [];
  if (permissions.canEdit) {
    actions.push({ key: 'edit', label: 'Edit Customer', Icon: SquarePen, onPress: onEdit });
  }
  if (permissions.canSuspend) {
    actions.push({
      key: 'suspend',
      label: customer.isActive ? 'Suspend' : 'Reactivate',
      Icon: customer.isActive ? Ban : CircleCheck,
      onPress: onToggleActive,
    });
  }
  if (permissions.canDelete) {
    actions.push({ key: 'delete', label: 'Delete', Icon: Trash2, onPress: onDelete, destructive: true });
  }

  if (actions.length === 0) return null;

  const run = (action: MenuAction) => {
    setOpen(false);
    // Let the sheet finish dismissing before an Alert takes over the screen.
    requestAnimationFrame(action.onPress);
  };

  return (
    <>
      <TouchableOpacity
        onPress={() => setOpen(true)}
        hitSlop={10}
        activeOpacity={0.7}
        accessibilityRole="button"
        accessibilityLabel={`Actions for ${customer.name}`}
        className="h-8 w-8 items-center justify-center rounded-full"
      >
        <EllipsisVertical size={17} color={Colors.gray400} strokeWidth={2} />
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable className="flex-1 items-center justify-center bg-black/30 px-8" onPress={() => setOpen(false)}>
          <View className="w-full max-w-xs rounded-2xl bg-white p-2">
            <Text numberOfLines={1} className="px-3 pb-1 pt-2 text-[11px] font-semibold text-gray-400">
              {customer.name}
            </Text>
            {actions.map((action) => (
              <TouchableOpacity
                key={action.key}
                onPress={() => run(action)}
                activeOpacity={0.7}
                className="flex-row items-center rounded-xl px-3 py-3"
              >
                <action.Icon
                  size={16}
                  color={action.destructive ? Colors.danger : Colors.gray700}
                  strokeWidth={2}
                />
                <Text
                  className="ml-2.5 text-sm font-medium"
                  style={{ color: action.destructive ? Colors.danger : Colors.gray900 }}
                >
                  {action.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </Pressable>
      </Modal>
    </>
  );
}
