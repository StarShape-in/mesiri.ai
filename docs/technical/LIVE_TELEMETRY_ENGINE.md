# Live GPS Telemetry Engine (WebSockets)

MERCON relies on a high-performance, low-latency live tracking system to monitor the fleet in real time. This is achieved using **Socket.io**.

## Architecture Flow

1. **Driver App Initialization**
   Upon logging in and starting an active trip, the React Native mobile app establishes a persistent WebSocket connection to `mercon.tech` (Port 3050).

2. **Emitting GPS Coordinates**
   The Mobile App hooks into the device's native GPS API and emits a payload every 10 seconds.
   
   **Event:** `driver:location_update`
   **Payload:**
   ```javascript
   {
     tripId: "uuid",
     driverId: "uuid",
     lat: 24.7136,
     lng: 46.6753,
     speed: 85 // in km/h
   }
   ```

3. **Backend Broadcasting**
   The Node.js server intercepts the `driver:location_update` event and immediately broadcasts it on a room/channel specific to that Trip ID.
   
   **Broadcast Event:** `trip:location_update:{tripId}`

4. **Dashboard Consumption**
   The Operator navigates to `http://mercon.tech/trips/:id/track`.
   The React application uses `socket.io-client` to listen to `trip:location_update:{tripId}` and updates the React local state (`lat`, `lng`, `speed`) instantly, causing the map UI to re-render smoothly.

## Security Considerations
- In production, the WebSocket handshake must pass the JWT token for authentication.
- Rate limiting should be applied to the `driver:location_update` event to prevent abuse or accidental DDOS from malfunctioning mobile clients.
