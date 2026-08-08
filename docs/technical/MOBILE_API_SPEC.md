# MERCON Mobile API Specification

This document details the RESTful endpoints exposed specifically for the upcoming Driver Mobile Application.

## Authentication

### `POST /api/mobile/auth/login`
Authenticates a driver and returns a JWT token.

**Request Body:**
```json
{
  "phone_primary": "+966500000000",
  "license_number": "SA-12345678"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "token": "eyJhb...",
    "driver": {
      "id": "uuid",
      "name": "Mohammed Ali",
      "ref_id": "DRV-1002",
      "status": "Available"
    }
  }
}
```

---

## Trip Workflow

### `GET /api/mobile/trips/current`
Fetches the driver's currently assigned active trip (status `Dispatched`, `AtPickup`, `InTransit`, `AtDelivery`).

**Headers:**
`Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "ref_id": "TRP-2023-001",
    "status": "InTransit",
    "cargo_type": "Electronics",
    "customer": { ... },
    "vehicle": { ... },
    "stops": [
      { "stop_type": "Pickup", "location_lat": 24.71, "location_lng": 46.67 },
      { "stop_type": "Dropoff", "location_lat": 26.39, "location_lng": 49.97 }
    ]
  }
}
```

### `POST /api/mobile/trips/:id/status`
Updates the status of the current trip.

**Headers:**
`Authorization: Bearer <token>`

**Request Body:**
```json
{
  "status": "Completed"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "Completed"
  }
}
```
*Note: If marked as `Completed`, the backend automatically frees up the assigned Driver and Vehicle back to `Available` status.*
