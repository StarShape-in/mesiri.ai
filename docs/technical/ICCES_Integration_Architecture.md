# MERCON ICCES Integration Architecture

**Date:** July 2026  
**Status:** Completed  
**Component:** Backend Polling Engine & Frontend Dashboard  

## Overview
The MERCON Logistics platform requires secondary vehicle GPS tracking to complement the primary Driver Mobile GPS. This is provided by the ICCES hardware GPS devices installed on the fleet vehicles. 

Because the ICCES API uses a pull-based REST architecture (it does not push webhooks), we have architected a custom Node.js Background Worker (Cron) system to poll the API and synchronize the data seamlessly into our real-time WebSocket engine and PostgreSQL database.

## System Architecture

### 1. Database Layer (PostgreSQL)
A new field `icces_device_id` was added to the `Vehicle` model. This allows operators to manually pair a physical ICCES hardware tracker to a specific truck in the fleet via the Operator Web Dashboard.

```prisma
model Vehicle {
  // ... existing fields ...
  
  // Third-Party Tracking
  icces_device_id String? @unique
}
```

### 2. Frontend Layer (React Web Dashboard)
The Operator Dashboard was updated to allow seamless entry and modification of the ICCES Tracker ID.
- **Add Vehicle Page**: Operators input the `icces_device_id` during onboarding.
- **Edit Vehicle Page**: Operators can update or swap the tracker ID if a hardware replacement occurs.

### 3. Backend Polling Engine (Node.js & node-cron)
The core of the integration lives in `backend/api-server/src/services/cronJobs.ts`. We built three specialized background workers to poll the `https://fleet.icces.com:8443` API.

#### Worker 1: Live Telemetry Fallback (Runs every 30 seconds)
- **Endpoint:** `POST /iccWebService1.2` (EVENT_DETAILS)
- **Behavior:** The worker queries our database for all trips currently in `InTransit` status. For any trip whose vehicle has an assigned `icces_device_id`, the worker polls the ICCES API for the latest GPS coordinates (Latitude, Longitude, Heading, Speed).
- **Socket Injection:** The worker then immediately broadcasts this coordinate payload to our WebSocket server via the `trip:location_update:{trip_id}` channel.
- **Result:** If the driver loses cell service or their phone dies, the Web Dashboard map will automatically fallback to the ICCES hardware tracker, and the truck will continue moving seamlessly on the operator's screen without a page refresh.

#### Worker 2: Daily Odometer Sync (Runs daily at 2:00 AM)
- **Endpoint:** `GET /iccWebService1.2`
- **Behavior:** Fetches the bulk list of all registered vehicles on the ICCES account.
- **Database Sync:** Matches the ICCES `deviceID` to our `icces_device_id` in PostgreSQL and updates the `current_odometer` reading for accurate maintenance forecasting and billing.

#### Worker 3: Active Alarms Sync (Runs every 1 minute)
- **Endpoint:** `GET /iccWebService1.2` (Alerts)
- **Behavior:** Polls for critical hardware alerts such as `OVER_SPEEDING`, `ACCIDENT`, or `DEVICE_NOT_WORKING`.
- **Database Sync:** Generates a persistent alert in our `Notification` table, pushing a real-time toast notification to the operator's dashboard.

## Authentication
The ICCES API requires Basic Authentication. The backend constructs a Base64 encoded token in the format `<user>:<password>:<account>`.

For security, these credentials are not hardcoded. They are loaded securely from the server's environment variables:
- `ICCES_USER`
- `ICCES_PASS`
- `ICCES_ACCT`

## Conclusion
This integration guarantees that MERCON Logistics maintains uninterrupted, real-time visibility over its fleet, regardless of driver compliance or mobile network stability.
