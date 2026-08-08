/**
 * "Active Vehicles" dashboard section — header, snapping horizontal carousel
 * of VehicleCards, and pagination dots. Owns its own data via
 * useActiveVehicles(); presentation-only components (VehicleCard, etc.)
 * never call the API themselves.
 */
import React, { useCallback, useRef, useState } from 'react';
import { FlatList, useWindowDimensions, View, type ViewToken } from 'react-native';
import { TruckIcon } from 'lucide-react-native';
import { EmptyState, ErrorState, SkeletonVehicleCard } from '@/shared/components';
import { SectionHeader } from './SectionHeader';
import { VehicleCard } from './VehicleCard';
import { CarouselPagination } from './CarouselPagination';
import { useActiveVehicles } from '../hooks';
import type { ActiveVehicleCard } from '../types';

const GAP = 14;
const MIN_CARD_WIDTH = 240;
const MAX_CARD_WIDTH = 300;

interface ActiveVehiclesSectionProps {
  onViewAll?: () => void;
  onVehiclePress?: (vehicle: ActiveVehicleCard) => void;
  className?: string;
}

export function ActiveVehiclesSection({ onViewAll, onVehiclePress, className }: ActiveVehiclesSectionProps) {
  const { width: windowWidth } = useWindowDimensions();
  const { data, isLoading, isError, refetch } = useActiveVehicles();
  const [activeIndex, setActiveIndex] = useState(0);

  const cardWidth = Math.max(MIN_CARD_WIDTH, Math.min(MAX_CARD_WIDTH, windowWidth / 1.35));

  const viewabilityConfig = useRef({ itemVisiblePercentThreshold: 60 }).current;
  const onViewableItemsChanged = useRef(({ viewableItems }: { viewableItems: ViewToken[] }) => {
    if (viewableItems.length > 0 && viewableItems[0].index !== null) {
      setActiveIndex(viewableItems[0].index);
    }
  }).current;

  const renderItem = useCallback(({ item }: { item: ActiveVehicleCard }) => (
    <VehicleCard
      width={cardWidth}
      driver={{ initials: item.driverInitials, name: item.driverName, online: item.driverOnline }}
      vehicle={{ truckId: item.truckId, model: item.assetType, capacityKg: item.capacityKg }}
      route={{ originLabel: item.originLabel, destinationLabel: item.destinationLabel }}
      status={item.cardStatus}
      lastLocation={item.lastLat !== null && item.lastLng !== null ? { lat: item.lastLat, lng: item.lastLng } : null}
      currentTrip={{ id: item.tripId, status: item.tripStatus }}
      onPress={onVehiclePress ? () => onVehiclePress(item) : undefined}
    />
  ), [cardWidth, onVehiclePress]);

  return (
    <View className={`gap-3 ${className ?? ''}`}>
      <SectionHeader title="Active Vehicles" actionLabel="View All" onActionPress={onViewAll} />

      {isLoading ? (
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={[0, 1]}
          keyExtractor={(i) => String(i)}
          contentContainerStyle={{ gap: GAP }}
          renderItem={() => <SkeletonVehicleCard />}
        />
      ) : isError ? (
        <ErrorState message="Couldn't load active vehicles." onRetry={() => refetch()} />
      ) : (data?.length ?? 0) === 0 ? (
        <EmptyState title="No vehicles on active trips" subtitle="Dispatched trucks will show up here." Icon={TruckIcon} />
      ) : (
        <View className="gap-2.5">
          <FlatList
            data={data}
            horizontal
            keyExtractor={(item) => item.tripId}
            showsHorizontalScrollIndicator={false}
            snapToInterval={cardWidth + GAP}
            decelerationRate="fast"
            contentContainerStyle={{ gap: GAP }}
            renderItem={renderItem}
            onViewableItemsChanged={onViewableItemsChanged}
            viewabilityConfig={viewabilityConfig}
          />
          <CarouselPagination count={data!.length} activeIndex={activeIndex} />
        </View>
      )}
    </View>
  );
}
