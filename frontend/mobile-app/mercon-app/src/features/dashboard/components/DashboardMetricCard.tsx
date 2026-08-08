import React from 'react';
import { Image, Text, TouchableOpacity, View, type ImageSourcePropType } from 'react-native';
import { ArrowRight } from 'lucide-react-native';

interface DashboardMetricCardProps {
  title: string;
  value: string | number;
  /** Optional — cards with no illustration use the full card width for their text. */
  image?: ImageSourcePropType;
  onPress?: () => void;
  /** Card height in px — the illustration is sized as a fraction of this, so pass it if you override the default. */
  cardHeight?: number;
  className?: string;
}

const CARD_PADDING = 18;
const ILLUSTRATION_HEIGHT_RATIO = 0.95;

/**
 * Premium, Swiss-minimal KPI card: title + big value + "View all" on the
 * left, an optional illustration anchored bottom-right. Used for dashboard
 * metrics like Active Trips, Delayed Deliveries, Active Drivers, etc.
 */
export function DashboardMetricCard({
  title, value, image, onPress, cardHeight = 140, className,
}: DashboardMetricCardProps) {
  // RN Web only resolves a percentage height on a child if its parent has an
  // *explicit* height — a flex-stretched parent height doesn't count. So the
  // illustration's height is computed here and passed as a literal number
  // instead of a `%` className, which silently collapses to 0 on web.
  const illustrationHeight = (cardHeight - CARD_PADDING * 2) * ILLUSTRATION_HEIGHT_RATIO;

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.85}
      disabled={!onPress}
      style={{
        height: cardHeight,
        padding: CARD_PADDING,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.06,
        shadowRadius: 20,
        elevation: 3,
      }}
      className={`flex-1 flex-row overflow-hidden rounded-3xl border border-[#F3F3F3] bg-white ${className ?? ''}`}
    >
      {/* Left — title, value, view all */}
      <View className={`justify-start gap-2 ${image ? 'w-[52%] pr-1.5' : 'w-full'}`}>
        <Text numberOfLines={2} className="text-[15px] font-semibold leading-[19px] text-gray-900">
          {title}
        </Text>

        <Text numberOfLines={1} className="text-[34px] font-bold leading-[38px] text-[#F24822]">
          {value}
        </Text>

        <View className="flex-row items-center gap-1">
          <Text numberOfLines={1} className="text-[13px] font-semibold text-[#F24822]">
            View all
          </Text>
          <ArrowRight size={13} color="#F24822" strokeWidth={2.5} />
        </View>
      </View>

      {/* Right — illustration, anchored bottom-right, never stretched */}
      {image && (
        <View className="w-[48%] items-end justify-end">
          <Image source={image} resizeMode="contain" style={{ height: illustrationHeight, width: '100%' }} />
        </View>
      )}
    </TouchableOpacity>
  );
}
