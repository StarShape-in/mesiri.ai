/**
 * Shared socket.io connection to the MERCON server.
 * The socket server lives at the API origin (not under /api), same as the web
 * dashboard connects. Backend contract (see api-server/src/index.ts):
 *   emit  'driver:location_update'  { tripId, driverId, lat, lng, speed }
 *   → server relays 'trip:location_update:<tripId>' to that trip's room.
 * The server requires a valid JWT in the connection handshake — connecting
 * without one is rejected.
 */
import { io, type Socket } from 'socket.io-client';
import { safeSecureStore as SecureStore } from './secure-store';
import { API_URL, TOKEN_KEY } from './api';

const SOCKET_URL = API_URL.replace(/\/api\/?$/, '');

let socket: Socket | null = null;

export async function getSocket(): Promise<Socket> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  if (!socket) {
    socket = io(SOCKET_URL, { transports: ['websocket'], auth: { token } });
  } else {
    // Token may have changed (re-login) since the socket was created.
    socket.auth = { token };
  }
  return socket;
}
