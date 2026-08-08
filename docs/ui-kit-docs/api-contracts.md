# MERCON API Contracts

Data models, request/response shapes, validation rules, and status enumerations for all MERCON entities.

---

## Base Configuration

```typescript
BASE_URL = process.env.MERCON_API_BASE_URL  // e.g. https://api.mercon.sa/v1
Authorization: Bearer {JWT_TOKEN}
Content-Type: application/json
Accept-Language: ar  // or 'en'
```

All successful responses follow:
```json
{
  "success": true,
  "data": { ... },
  "meta": { "page": 1, "per_page": 20, "total": 145 }
}
```

All error responses:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Phone number is invalid",
    "fields": { "phone": "Must be a valid Saudi mobile number" }
  }
}
```

---

## Authentication

### POST /auth/request-otp

**Request:**
```json
{ "phone": "+966501234567" }
```

**Validation:**
- `phone`: required, Saudi format `+9665XXXXXXXX` or `05XXXXXXXX`, 10 digits after 0

**Response (200):**
```json
{
  "success": true,
  "data": {
    "phone": "+966501234567",
    "expires_in": 300,
    "resend_after": 30
  }
}
```

### POST /auth/verify-otp

**Request:**
```json
{
  "phone": "+966501234567",
  "otp": "483920"
}
```

**Validation:**
- `otp`: required, exactly 6 digits

**Response (200):**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": "2024-07-07T06:00:00Z",
    "user": {
      "id": "USR-001",
      "name": "Ahmed Al-Rashidi",
      "phone": "+966501234567",
      "role": "driver",
      "driver_id": "DRV-0112"
    }
  }
}
```

**Error codes:** `INVALID_OTP`, `OTP_EXPIRED`, `TOO_MANY_ATTEMPTS`

---

## Trips

### Trip Object

```typescript
interface Trip {
  id: string;                    // "TRP-2024-0891"
  status: TripStatus;            // See status enum below
  customer: {
    id: string;                  // "CUS-001"
    name: string;                // "Saudi Electronics Co."
  };
  origin: {
    address: string;             // "Riyadh Industrial Zone"
    city: string;                // "Riyadh"
    coordinates: { lat: number; lng: number };
  };
  destination: {
    address: string;             // "Jeddah Port, Gate 7"
    city: string;                // "Jeddah"
    coordinates: { lat: number; lng: number };
  };
  driver: {
    id: string;                  // "DRV-0112"
    name: string;                // "Ahmed Al-Rashidi"
    phone: string;               // "+966501234567"
  } | null;
  vehicle: {
    id: string;                  // "TRK-2041"
    model: string;               // "Mercedes-Benz Actros"
    plate: string;               // "أ ب ج 1234"
  } | null;
  cargo: {
    description: string;         // "Electronics"
    weight_kg: number;           // 2400
    value_sar: number | null;
    special_instructions: string | null;
  };
  scheduled_at: string;          // ISO 8601: "2024-07-06T06:00:00Z"
  started_at: string | null;
  completed_at: string | null;
  distance_km: number;           // 950
  eta: string | null;            // ISO 8601
  progress_percent: number;      // 0-100
  invoice_id: string | null;     // "INV-2024-0445"
  notes: string | null;
  created_at: string;
  updated_at: string;
}
```

**TripStatus enum:**
```typescript
type TripStatus = 'Pending' | 'Scheduled' | 'In Transit' | 'Delayed' | 'Completed' | 'Cancelled';
```

**Status → Badge color mapping (via getStatusColors):**
- `Pending` → gray (`#6E6E80` / `#F5F5F7`)
- `Scheduled` → gray (same as Pending)
- `In Transit` → blue (`#2563EB` / `#EFF6FF`)
- `Delayed` → amber (`#D97706` / `#FFFBEB`)
- `Completed` → green (`#16A34A` / `#F0FDF4`)
- `Cancelled` → red (`#DC2626` / `#FEF2F2`)

### GET /trips

**Query params:**
```
?status=In Transit          // Filter by status
&driver_id=DRV-0112         // Filter by driver
&customer_id=CUS-001        // Filter by customer
&date_from=2024-07-01       // Date range start (YYYY-MM-DD)
&date_to=2024-07-07         // Date range end
&search=Riyadh              // Search in ID, route city, driver name
&page=1
&per_page=20
&sort=created_at            // Field to sort by
&order=desc                 // 'asc' | 'desc'
```

**Response (200):**
```json
{
  "success": true,
  "data": [ { ...Trip }, { ...Trip } ],
  "meta": { "page": 1, "per_page": 20, "total": 145 }
}
```

### GET /trips/:id

**Response (200):**
```json
{
  "success": true,
  "data": {
    ...Trip,
    "timeline": [
      { "step": "Trip Created", "at": "2024-07-05T22:10:00Z", "done": true, "active": false },
      { "step": "Driver Assigned", "at": "2024-07-05T22:45:00Z", "done": true, "active": false },
      { "step": "Pickup Verified", "at": "2024-07-06T06:15:00Z", "done": true, "active": false },
      { "step": "In Transit", "at": "2024-07-06T06:30:00Z", "done": true, "active": true },
      { "step": "Destination Reached", "at": null, "done": false, "active": false },
      { "step": "Delivery Confirmed", "at": null, "done": false, "active": false }
    ],
    "pod_photos": [
      { "url": "https://cdn.mercon.sa/pod/abc123.jpg", "uploaded_at": "..." }
    ]
  }
}
```

### POST /trips

**Request:**
```json
{
  "customer_id": "CUS-001",
  "origin_address": "Riyadh Industrial Zone",
  "origin_coordinates": { "lat": 24.7136, "lng": 46.6753 },
  "destination_address": "Jeddah Port, Gate 7",
  "destination_coordinates": { "lat": 21.4858, "lng": 39.1925 },
  "scheduled_at": "2024-07-06T06:00:00Z",
  "driver_id": "DRV-0112",
  "vehicle_id": "TRK-2041",
  "cargo_description": "Electronics",
  "cargo_weight_kg": 2400,
  "cargo_value_sar": null,
  "special_instructions": null,
  "notes": null
}
```

**Required fields:** `customer_id`, `origin_address`, `origin_coordinates`, `destination_address`, `destination_coordinates`, `scheduled_at`, `driver_id`, `vehicle_id`

**Response (201):**
```json
{ "success": true, "data": { ...Trip } }
```

### PATCH /trips/:id

Partial update. Send only the fields to change.

```json
{ "status": "Cancelled", "notes": "Customer request" }
```

### POST /trips/:id/verify-pickup

```json
{
  "coordinates": { "lat": 24.7140, "lng": 46.6750 },
  "photo_url": "https://cdn.mercon.sa/pickup/xyz789.jpg"
}
```

**Validation:** Coordinates must be within 500m of trip origin.

### POST /trips/:id/confirm-delivery

```json
{
  "coordinates": { "lat": 21.4860, "lng": 39.1927 },
  "pod_photos": ["https://cdn.mercon.sa/pod/abc123.jpg"],
  "receiver_name": "Mohammed Al-Otaibi",
  "signature_url": "https://cdn.mercon.sa/signatures/sig456.png",
  "notes": null
}
```

**Validation:** `pod_photos` must have at least 1 item. `receiver_name` required.

---

## Drivers

### Driver Object

```typescript
interface Driver {
  id: string;                    // "DRV-0112"
  name: string;                  // "Ahmed Al-Rashidi"
  phone: string;                 // "+966501234567"
  status: DriverStatus;
  avatar_initials: string;       // "AA" (first letters of name)
  avatar_color: string;          // One of the Colors palette values
  trips_count: number;           // 243
  rating: number;                // 4.9
  license_number: string;        // "SA-123456"
  license_expiry: string;        // "2025-12-31"
  national_id: string | null;
  email: string | null;
  assigned_vehicle_id: string | null;
  joined_at: string;
  documents: DriverDocument[];
}

type DriverStatus = 'Available' | 'On Trip' | 'Off Duty' | 'Inactive';

interface DriverDocument {
  type: 'License' | 'National ID' | 'Medical Certificate' | 'Driving Permit';
  status: DocStatus;            // 'Active' | 'Expiring' | 'Expired' | 'Pending Upload'
  expiry: string | null;
  document_url: string | null;
}
```

### GET /drivers

**Query params:** `?status=Available&search=Ahmed&page=1&per_page=20&sort=name&order=asc`

**Example response data:**
```json
[
  {
    "id": "DRV-0112",
    "name": "Ahmed Al-Rashidi",
    "phone": "+966501234567",
    "status": "On Trip",
    "trips_count": 243,
    "rating": 4.9,
    "avatar_initials": "AA"
  },
  {
    "id": "DRV-0147",
    "name": "Khalid Al-Zahrani",
    "phone": "+966552345678",
    "status": "Available",
    "trips_count": 312,
    "rating": 4.9,
    "avatar_initials": "KA"
  }
]
```

### GET /drivers/:id

Returns full Driver object including documents array.

### POST /drivers

Create a new driver.

**Required:** `name`, `phone`, `license_number`, `license_expiry`

### PATCH /drivers/:id

Partial update.

---

## Vehicles

### Vehicle Object

```typescript
interface Vehicle {
  id: string;                    // "TRK-2041"
  make: string;                  // "Mercedes-Benz"
  model: string;                 // "Actros"
  year: number;                  // 2022
  plate: string;                 // "أ ب ج 1234"
  vin: string;                   // "WDB9634031L1234567"
  capacity_kg: number;           // 25000
  fuel_type: 'Diesel' | 'Petrol' | 'Electric' | 'Hybrid';
  mileage_km: number;            // 187420
  status: VehicleStatus;
  assigned_driver_id: string | null;
  documents: VehicleDocument[];
  created_at: string;
}

type VehicleStatus = 'Available' | 'On Trip' | 'Maintenance' | 'Inactive';

interface VehicleDocument {
  id: string;
  type: 'Istimara' | 'Insurance' | 'Annual Inspection' | 'Load Permit' | 'Driving Permit';
  status: DocStatus;
  expiry: string;               // "2025-03-12"
  days_until_expiry: number;    // -5 = expired 5 days ago
  document_url: string | null;
  renewal_cost_sar: number | null;
}
```

**VehicleStatus → StatusBadge color:**
- `Available` → green (via getStatusColors)
- `On Trip` → blue
- `Maintenance` → amber
- `Inactive` → gray

### GET /vehicles

**Query params:** `?status=Available&search=TRK&page=1&per_page=20`

**Example response data:**
```json
[
  { "id": "TRK-2041", "make": "Mercedes-Benz", "model": "Actros", "year": 2022, "capacity_kg": 25000, "status": "On Trip", "documents": 4 },
  { "id": "TRK-2038", "make": "Volvo", "model": "FH 540", "year": 2021, "capacity_kg": 24000, "status": "Available", "documents": 4 }
]
```

### GET /vehicles/renewals

Returns all vehicle documents that are expired, critical (≤7 days), or due soon (≤30 days).

**Query params:** `?status=due&vehicle_id=TRK-2041`

**Example response:**
```json
[
  {
    "vehicle_id": "TRK-2041",
    "doc_type": "Annual Inspection",
    "expiry": "2024-07-25",
    "days_until_expiry": 19,
    "status": "Due Soon",
    "renewal_cost_sar": 350
  },
  {
    "vehicle_id": "TRK-2035",
    "doc_type": "Insurance Certificate",
    "expiry": "2024-07-01",
    "days_until_expiry": -5,
    "status": "Overdue",
    "renewal_cost_sar": 2200
  }
]
```

---

## Customers

### Customer Object

```typescript
interface Customer {
  id: string;                    // "CUS-001"
  name: string;                  // "Saudi Electronics Co."
  contact_name: string;          // "Mohammed Al-Otaibi"
  contact_phone: string;
  contact_email: string | null;
  address: string;
  city: string;
  trips_count: number;
  total_invoiced_sar: number;
  status: 'Active' | 'Inactive';
  created_at: string;
}
```

### GET /customers

**Query params:** `?status=Active&search=Saudi&page=1&per_page=20`

---

## Invoices

### Invoice Object

```typescript
interface Invoice {
  id: string;                    // "INV-2024-0445"
  trip_id: string;               // "TRP-2024-0891"
  customer_id: string;
  customer_name: string;         // "Saudi Electronics Co."
  status: InvoiceStatus;
  amount_sar: number;            // 4200
  tax_sar: number;               // 630 (15% VAT)
  total_sar: number;             // 4830
  issued_at: string;             // "2024-07-06"
  due_at: string;                // "2024-07-13"
  paid_at: string | null;
  payment_terms: string;         // "Net 7"
  line_items: InvoiceLineItem[];
  pdf_url: string | null;
  notes: string | null;
}

type InvoiceStatus = 'Draft' | 'Pending' | 'Paid' | 'Overdue' | 'Cancelled';

interface InvoiceLineItem {
  description: string;           // "Transportation: Riyadh → Jeddah"
  quantity: number;              // 1
  unit_price_sar: number;        // 3500
  total_sar: number;             // 3500
}
```

**InvoiceStatus → badge color:**
- `Draft` → gray
- `Pending` → blue (info)
- `Paid` → green (success)
- `Overdue` → red (danger)
- `Cancelled` → gray

### GET /invoices

**Query params:** `?status=Pending&customer_id=CUS-001&date_from=2024-07-01&page=1&per_page=20`

### POST /invoices

**Request:**
```json
{
  "trip_id": "TRP-2024-0891",
  "payment_terms": "Net 7",
  "notes": null
}
```

### POST /invoices/:id/send

Sends invoice PDF to customer email. Returns updated invoice with `pdf_url`.

---

## Rate Cards

### RateCard Object

```typescript
interface RateCard {
  id: string;                    // "RC-001"
  name: string;                  // "Standard Long Haul"
  customer_id: string | null;    // null = default rate card
  base_rate_sar: number;         // 2.5 (per km)
  min_charge_sar: number;        // 500
  fuel_surcharge_percent: number; // 15
  waiting_rate_per_hour: number; // 100
  cargo_type: string | null;     // "General" | "Pharma" | null (all)
  is_active: boolean;
  created_at: string;
}
```

---

## Notifications

### Notification Object

```typescript
interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  data: {
    trip_id?: string;
    driver_id?: string;
    vehicle_id?: string;
    invoice_id?: string;
  };
  is_read: boolean;
  created_at: string;
}

type NotificationType =
  | 'trip_assigned'
  | 'trip_started'
  | 'trip_delayed'
  | 'trip_completed'
  | 'trip_cancelled'
  | 'document_expiring'
  | 'document_expired'
  | 'invoice_paid'
  | 'invoice_overdue'
  | 'system_alert';
```

### GET /notifications

**Query params:** `?is_read=false&page=1&per_page=50`

### POST /notifications/mark-all-read

No request body. Marks all notifications as read.

### PATCH /notifications/:id/read

Marks a single notification as read.

---

## User / Profile

### User Object (Driver variant)

```typescript
interface DriverUser {
  id: string;
  driver_id: string;            // "DRV-0112"
  name: string;
  phone: string;
  email: string | null;
  avatar_initials: string;
  rating: number;
  trips_count: number;
  days_active: number;
  status: DriverStatus;
  documents: DriverDocument[];
  notification_preferences: {
    push: boolean;
    sms: boolean;
  };
  biometric_enabled: boolean;
  language: 'ar' | 'en';
  created_at: string;
}
```

### User Object (Operator variant)

```typescript
interface OperatorUser {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  role: 'admin' | 'dispatcher' | 'viewer';
  company_name: string;         // "MERCON Logistics"
  notification_preferences: {
    push: boolean;
    sms: boolean;
    email: boolean;
  };
  language: 'ar' | 'en';
  created_at: string;
}
```

### GET /profile

Returns the current authenticated user's profile.

### PATCH /profile

Partial update of profile fields.

**Example:**
```json
{ "name": "Ahmed Al-Rashidi", "email": "ahmed@example.com" }
```

---

## Loading Placeholder Shapes

When displaying lists before data loads, render skeleton placeholders matching these shapes:

| Screen | Skeleton elements |
|--------|-----------------|
| TripList | 3 cards: 100% wide, 100px tall each |
| DriverList | 3 cards: 100% wide, 120px tall each |
| VehicleList | 3 cards: 100% wide, 100px tall each |
| InvoiceList | 3 rows: 100% wide, 72px tall each |
| HomeDashboard KPIs | 4 blocks: 25% wide, 80px tall each |
| Trip details timeline | 6 rows: 80% wide, 32px tall each |
| Driver detail stats | 3 blocks: 33% wide, 60px tall each |

All skeletons use `Colors.gray200` background with shimmer gradient.

---

## Pagination

All list endpoints support pagination via:

```
?page=1&per_page=20
```

Default `per_page`: 20. Maximum `per_page`: 100.

Response `meta`:
```json
{
  "page": 1,
  "per_page": 20,
  "total": 145,
  "total_pages": 8,
  "has_next": true,
  "has_prev": false
}
```

Client-side: use `onEndReached` on FlatList with a threshold of 0.5 to trigger fetching page `n+1` when the user scrolls 50% of the way through the current list.
