/**
 * Driver emergency alert — POST /mobile/emergency (multipart: incident photos
 * + fields). Notifies all operators/admins and attaches any incident photos
 * as Documents on the driver's active trip.
 */
import { api } from './api';

export interface EmergencyPhoto {
  uri: string;
  mimeType?: string | null;
  fileName?: string | null;
}

export interface EmergencyPayload {
  incident_type: string;
  notes?: string;
  lat?: number;
  lng?: number;
  photos?: EmergencyPhoto[];
}

export const emergencyService = {
  async raise(payload: EmergencyPayload): Promise<{ notified: number }> {
    const form = new FormData();
    form.append('incident_type', payload.incident_type);
    if (payload.notes) form.append('notes', payload.notes);
    if (payload.lat !== undefined) form.append('lat', String(payload.lat));
    if (payload.lng !== undefined) form.append('lng', String(payload.lng));
    (payload.photos ?? []).forEach((photo, i) => {
      form.append('photos', {
        uri: photo.uri,
        name: photo.fileName ?? `incident-${i}.jpg`,
        type: photo.mimeType ?? 'image/jpeg',
        // React Native's FormData file shape isn't in the DOM lib types.
      } as unknown as Blob);
    });

    // Don't set Content-Type manually — axios/RN needs to generate it itself
    // so it includes the multipart boundary.
    const { data } = await api.post('/mobile/emergency', form);
    return (data.data ?? { notified: 0 }) as { notified: number };
  },
};
