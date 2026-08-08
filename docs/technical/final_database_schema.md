# MERCON Logistics - Final Practical Database Schema

This document contains the definitive, production-ready backend schema tailored exactly to our logistics business operations.

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// -----------------------------------------
// ENUMS (Strict State Machines)
// -----------------------------------------
enum Role {
  Admin
  Operator
  Driver
}

enum DriverStatus {
  Available
  OnTrip
  OffDuty
  Inactive
}

enum AssetStatus {
  Available
  OnTrip
  Maintenance
  Inactive
}

enum AssetType {
  Flatbed
  Reefer
  Box
  Tanker
}

enum TripStatus {
  Draft
  Dispatched
  AtPickup
  InTransit
  AtDelivery
  Completed
  Invoiced
  Cancelled
}

enum StopType {
  Pickup
  Dropoff
  Rest
  Refuel
}

enum InvoiceStatus {
  Draft
  Pending
  Paid
  Overdue
  Cancelled
}

enum DocType {
  DriverLicense
  VehicleRegistration
  Insurance
  POD
  CustomsClearance
  Waybill
  Contract
  Invoice
}

enum DocStatus {
  PendingReview
  Verified
  Rejected
  Expired
}

enum PaymentStatus {
  Pending
  Approved
  Paid
  Rejected
}

// -----------------------------------------
// 1. ORGANIZATION (Simplified)
// -----------------------------------------
model User {
  id            String  @id @default(uuid()) @db.Uuid
  username      String  @unique
  email         String? @unique
  phone         String? @unique
  password_hash String?
  name          String?
  role          Role    @default(Operator)

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
  isActive   Boolean   @default(true)
  version    Int       @default(1)

  verifiedDocs     Document[] @relation("VerifiedBy")
  approvedPayments Trip[]     @relation("PaymentApprovedBy")
  driver           Driver?
  notifications    Notification[]
}

model Customer {
  id            String @id @default(uuid()) @db.Uuid
  name          String
  contact_phone String
  credit_limit  Float  @default(0)

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
  isActive   Boolean   @default(true)
  version    Int       @default(1)

  trips     Trip[]
  invoices  Invoice[]
  rateCards RateCard[]
}

// -----------------------------------------
// 2. FLEET MANAGEMENT (Merged Vehicle/Trailer)
// -----------------------------------------
model Driver {
  id             String       @id @default(uuid()) @db.Uuid
  userId         String?      @unique @db.Uuid
  user           User?        @relation(fields: [userId], references: [id])
  ref_id         String?      @unique
  first_name     String
  last_name      String
  phone_primary  String?      @unique
  status         DriverStatus @default(Available)
  license_number String
  license_expiry DateTime     @db.Timestamptz
  ai_risk_score  Float        @default(0.0)

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
  isActive   Boolean   @default(true)
  version    Int       @default(1)

  trips Trip[]
}

model Vehicle {
  id               String      @id @default(uuid()) @db.Uuid
  ref_id           String?     @unique
  plate_number     String      @unique
  asset_type       AssetType
  status           AssetStatus @default(Available)
  capacity_kg      Int
  current_odometer Float       @default(0.0)
  gps_device_id    String?
  last_lat         Float?
  last_lng         Float?

  // Trailer Information Merged
  trailer_number      String?
  trailer_type        AssetType?
  trailer_capacity_kg Int?

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
  isActive   Boolean   @default(true)
  version    Int       @default(1)

  trips              Trip[]
  maintenanceRecords MaintenanceRecord[]
}

// -----------------------------------------
// 3. LOGISTICS ENGINE (Trips & Payments)
// -----------------------------------------
model Trip {
  id         String   @id @default(uuid()) @db.Uuid
  ref_id     String?  @unique
  customerId String   @db.Uuid
  customer   Customer @relation(fields: [customerId], references: [id])
  driverId   String?  @db.Uuid
  driver     Driver?  @relation(fields: [driverId], references: [id])
  vehicleId  String?  @db.Uuid
  vehicle    Vehicle? @relation(fields: [vehicleId], references: [id])

  status           TripStatus @default(Draft)
  cargo_type       String
  planned_distance Float?

  planned_start DateTime? @db.Timestamptz
  actual_start  DateTime? @db.Timestamptz
  planned_end   DateTime? @db.Timestamptz
  actual_end    DateTime? @db.Timestamptz

  // Extra Driver Payment Workflow
  extra_driver_payment Float?
  payment_reason       String?
  payment_approved_by  String?        @db.Uuid
  payment_approver     User?          @relation("PaymentApprovedBy", fields: [payment_approved_by], references: [id])
  payment_status       PaymentStatus?
  payment_date         DateTime?      @db.Timestamptz

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
  isActive   Boolean   @default(true)
  version    Int       @default(1)

  stops    TripStop[]
  invoices Invoice[]
}

model TripStop {
  id              String    @id @default(uuid()) @db.Uuid
  tripId          String    @db.Uuid
  trip            Trip      @relation(fields: [tripId], references: [id])
  stop_sequence   Int
  stop_type       StopType
  location_lat    Float
  location_lng    Float
  planned_arrival DateTime? @db.Timestamptz
  actual_arrival  DateTime? @db.Timestamptz

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
}

// -----------------------------------------
// 4. ENTERPRISE DMS (Document Management)
// -----------------------------------------
model Document {
  id          String    @id @default(uuid()) @db.Uuid
  entity_type String // "Driver", "Vehicle", "Trip", "MaintenanceRecord"
  entity_id   String    @db.Uuid
  doc_type    DocType
  status      DocStatus @default(PendingReview)

  file_url  String
  mime_type String?
  checksum  String?

  issue_date  DateTime? @db.Timestamptz
  expiry_date DateTime? @db.Timestamptz

  ocr_raw_text      String? @db.Text
  ai_extracted_json Json?   @db.JsonB
  is_confidential   Boolean @default(false)

  verified_by String? @db.Uuid
  verifier    User?   @relation("VerifiedBy", fields: [verified_by], references: [id])

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
  isActive   Boolean   @default(true)
  version    Int       @default(1)
}

// -----------------------------------------
// 5. MAINTENANCE (External Workflow)
// -----------------------------------------
model MaintenanceRecord {
  id        String  @id @default(uuid()) @db.Uuid
  vehicleId String  @db.Uuid
  vehicle   Vehicle @relation(fields: [vehicleId], references: [id])

  workshop_name    String
  workshop_contact String?
  maintenance_type String

  service_date     DateTime @db.Timestamptz
  odometer_reading Float
  cost             Float    @default(0.0)

  invoice_number   String?
  invoice_url      String?
  next_service_due DateTime? @db.Timestamptz
  remarks          String?   @db.Text

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
  isActive   Boolean   @default(true)
  version    Int       @default(1)
}

// -----------------------------------------
// 6. FINANCIALS (Simplified Tax-Free)
// -----------------------------------------
model Invoice {
  id         String        @id @default(uuid()) @db.Uuid
  ref_id     String?       @unique
  tripId     String        @db.Uuid
  trip       Trip          @relation(fields: [tripId], references: [id])
  customerId String        @db.Uuid
  customer   Customer      @relation(fields: [customerId], references: [id])
  status     InvoiceStatus @default(Draft)

  currency     String @default("SAR")
  subtotal     Float
  total_amount Float

  due_date DateTime @db.Timestamptz

  created_by String?   @db.Uuid
  updated_by String?   @db.Uuid
  deleted_by String?   @db.Uuid
  createdAt  DateTime  @default(now()) @db.Timestamptz
  updatedAt  DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt  DateTime? @db.Timestamptz
  isActive   Boolean   @default(true)
  version    Int       @default(1)
}

// -----------------------------------------
// 7. PRICING & QUOTATIONS (Rate Cards)
// -----------------------------------------
model RateCard {
  id               String    @id @default(uuid()) @db.Uuid
  name             String
  route_origin     String
  route_destination String
  base_price       Float
  currency         String    @default("SAR")
  
  customerId       String?   @db.Uuid // If null, it's a default/standard rate card
  customer         Customer? @relation(fields: [customerId], references: [id])
  
  is_active        Boolean   @default(true)
  
  created_by   String?   @db.Uuid
  updated_by   String?   @db.Uuid
  deleted_by   String?   @db.Uuid
  createdAt    DateTime  @default(now()) @db.Timestamptz
  updatedAt    DateTime  @default(now()) @updatedAt @db.Timestamptz
  deletedAt    DateTime? @db.Timestamptz
  version      Int       @default(1)
}

// -----------------------------------------
// 8. SYSTEM ALERTS (Notifications)
// -----------------------------------------
model Notification {
  id           String    @id @default(uuid()) @db.Uuid
  userId       String    @db.Uuid
  user         User      @relation(fields: [userId], references: [id])
  
  title        String
  message      String    @db.Text
  type         String    // "Emergency", "Trip", "Document", "System"
  is_read      Boolean   @default(false)
  entity_type  String?   // "Trip", "Driver", "Vehicle"
  entity_id    String?   @db.Uuid
  
  createdAt    DateTime  @default(now()) @db.Timestamptz
}
```
