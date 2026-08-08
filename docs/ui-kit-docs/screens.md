# MERCON Screen Documentation

Complete documentation for all screens across all three products.

---

## Driver App — 16 Screens

### 1. SplashScreen

**File:** `screens/driver/SplashScreen.tsx`
**Purpose:** Brand entry point while the app loads authentication state and fetches initial data.
**Business goal:** First impression, brand reinforcement, gate for unauthenticated users.

**Layout:**
- Full screen dark background (`Colors.darkCard` `#1C1C2E`)
- Centered MERCON logotype (SVG, white) with orange truck mark
- Tagline below logo: "Your journey, our commitment" — `Typography.bodyMedium`, `Colors.gray400`
- Progress indicator or animated ring below tagline
- Safe area insets respected

**Components used:** No custom components — raw View, Text, and logo SVG
**Navigation entry:** App cold start
**Navigation exit:** Auto-navigates to Login if unauthenticated, HomeScreen if token valid
**Loading:** This screen IS the loading state — the app checks auth in background
**Data required:** Auth token from AsyncStorage
**Animation:** Logo fade-in (300ms ease-out), tagline slide-up after logo settles (200ms delay, 300ms ease-out)

---

### 2. LoginScreen

**File:** `screens/driver/LoginScreen.tsx`
**Purpose:** Phone number entry for OTP authentication.
**Business goal:** Authenticate drivers using phone-based OTP, no password required.

**Layout:**
- Background: `Colors.gray100`
- Top: dark header area with back arrow, MERCON logo centered
- Card (white, `Radius['2xl']`) containing:
  - Heading: "Welcome back" — `headingXL`
  - Subtitle: "Enter your mobile number to continue" — `bodyMedium`, muted color
  - Country code picker (flag + +966)
  - Input: phone number, `keyboardType: 'phone-pad'`
  - Primary button: "Send OTP", `fullWidth`, `size: 'lg'`
- Bottom: "Don't have an account?" text link

**Components:** Input, Button
**States:** Default (empty phone), Valid (10-digit number entered), Loading (OTP request in flight), Error (invalid phone format)
**Validation:** Saudi phone number: 05XXXXXXXX (10 digits starting with 05)
**Error text:** "Please enter a valid Saudi mobile number"
**Navigation entry:** From SplashScreen (unauthenticated), from logout
**Navigation exit:** OTP Verification screen on success
**Accessibility:** Phone input must have `keyboardType: 'phone-pad'`, `accessibilityLabel: "Mobile number"`

---

### 3. OTP Verification Screen

**Purpose:** 6-digit OTP code entry with auto-advance.
**Business goal:** Complete phone-based authentication.

**Layout:**
- Background: `Colors.gray100`
- Back arrow header
- Heading: "Verify your number"
- Subtitle: "We sent a code to +966 5X XXX XXXX"
- 6 individual digit boxes (horizontally spaced)
  - Each box: 48×56px, `Radius.md`, `Colors.gray100` bg, `borderWidth: 2`, border transitions to `Colors.primary` when focused
  - Auto-advances focus to next box on digit entry
  - Backspace deletes current and moves to previous
- Resend link: "Didn't receive the code? Resend" — enabled after 30s countdown
- Countdown timer: "Resend in 0:28" — `Typography.caption`, muted
- Primary button: "Verify" — disabled until all 6 digits entered

**States:** Entering (partial), Complete (all 6 digits), Loading (verifying), Error (wrong OTP), Success (navigates away)
**Navigation exit:** HomeScreen (Driver) on success
**Error behavior:** Clears all boxes, shows error toast "Invalid code. Try again."

---

### 4. HomeScreen (Driver)

**File:** `screens/driver/HomeScreen.tsx`
**Purpose:** Driver's primary dashboard showing current status, active trip, and earnings.
**Business goal:** Give drivers immediate situational awareness of their current assignment.

**Layout:**
- Background: `Colors.gray100`
- StatusBar: light-content (dark background)
- Top section (dark `#1C1C2E` background, extends behind status bar):
  - Greeting: "Good morning, Ahmed" — `headingM`
  - Driver ID and status badge (Available/On Trip)
  - Today's earnings KPI: large display number
- Active trip card (if exists): DarkCard with route, progress bar (orange fill), ETA
- Quick action row: 3 buttons — Start Navigation, Upload POD, Report Issue
- Recent trips list (last 3): TripCard rows with status badges
- Bottom: DriverBottomNav (Home active)

**Components:** DarkCard, Card, StatusBadge, Button, DriverBottomNav
**Navigation entry:** Post-authentication, DriverBottomNav Home tab
**Navigation exit:** Trip row → TripDetails; Start Navigation → Navigation/Map; Upload POD → POD Upload; Profile tab → Profile
**Data required:** Driver profile (name, ID, status), active trip (if any), earnings today
**Loading:** Skeleton placeholders for KPI and active trip card
**Empty state (no active trip):** "No active trip assigned" card with illustration
**Accessibility:** Active trip card must have `accessibilityRole: 'button'` if tappable

---

### 5. Active Trip Screen

**Purpose:** Full-screen view of the currently assigned trip during execution.
**Business goal:** Central control panel for a driver during a trip — navigation, status updates, POD.

**Layout:**
- Dark header: Trip ID, route (origin → destination), status badge
- Progress bar: shows % of route completed (orange fill, gray track)
- Milestone cards: Pickup → In Transit → Delivered (step indicators)
- Current location: "You are here" with map thumbnail
- Cargo info card: description, weight, special instructions
- Action buttons:
  - "Navigate" (primary) — opens Navigation/Map
  - "Verify Pickup" / "Confirm Delivery" depending on trip phase
  - "Report Issue" (ghost, danger color)
- Bottom: DriverBottomNav (Trips active)

**Components:** DarkCard, Card, StatusBadge, Button, DriverBottomNav
**Navigation exit:** Navigate → LiveNavigation; Verify → PickupVerification; Confirm → DeliveryVerification
**States:** En-route-to-pickup, Picked-up (in transit), At-destination, Delivered

---

### 6. Trip Details (Driver)

**Purpose:** Full read-only summary of a completed or historical trip.
**Business goal:** Drivers can review past trips for disputes, records, and earnings.

**Layout:**
- Dark header card: Trip ID, status badge, route
- Distance, duration, earnings — 3-column stat row
- Timeline steps (vertical): Created → Assigned → Pickup → In Transit → Delivered
- Cargo details section
- Customer info section
- Earnings breakdown: base fare, bonus, deductions
- POD thumbnail (if uploaded)
- Bottom: DriverBottomNav

**Components:** Card, DarkCard, StatusBadge, Avatar, DriverBottomNav

---

### 7. Trips Screen (Driver)

**File:** `screens/driver/TripsScreen.tsx`
**Purpose:** Paginated list of all trips assigned to this driver.
**Business goal:** Historical trip record for driver reference and earnings verification.

**Layout:**
- White header, "My Trips" title
- SearchInput bar
- FilterChip row: All / Active / Completed / Cancelled
- Trip card list: ID, route, date, earnings, StatusBadge
- Pagination / infinite scroll
- Bottom: DriverBottomNav (Trips active)

**Components:** SearchInput, FilterChip, StatusBadge, DriverBottomNav
**Empty state:** "No trips found" with truck illustration
**Loading:** Skeleton cards (3 placeholder rows)

---

### 8. Live Navigation / Map Screen

**File:** `screens/driver/LiveNavigationScreen.tsx`
**Purpose:** Full-screen map with turn-by-turn navigation overlay.
**Business goal:** Guide driver from pickup to delivery point.

**Layout:**
- Full-screen map (MapView component)
- Floating bottom sheet with:
  - Next turn instruction: "Turn right in 500m"
  - Distance remaining and ETA
  - Current speed (km/h)
- Top floating controls: mute, back
- No standard navigation bar on this screen

**Components:** No standard design system components — native map + floating overlays
**Special behavior:** Screen stays awake (keepAwake), portrait lock recommended

---

### 9. Pickup Verification Screen

**File:** `screens/driver/PickupVerificationScreen.tsx`
**Purpose:** Driver confirms cargo pickup at origin location.
**Business goal:** Creates an auditable timestamp for trip commencement.

**Layout:**
- Header: "Verify Pickup"
- Location confirmation card: address, distance from location
- OTP / code entry (if shipper provides a pin)
- Camera capture button for loading photo
- Notes input (optional): any loading issues
- Primary button: "Confirm Pickup"

**Components:** Input, Button, Card
**Validation:** Location must be within 500m of pickup GPS coordinates
**Success:** Navigates to Active Trip screen, trip status changes to "In Transit"

---

### 10. Delivery Verification / POD Upload Screen

**File:** `screens/driver/DeliveryVerificationScreen.tsx`
**Purpose:** Driver confirms cargo delivery and uploads Proof of Delivery documents.
**Business goal:** Creates unambiguous delivery record for invoice and dispute resolution.

**Layout:**
- Header: "Confirm Delivery"
- Delivery address confirmation card
- Photo upload grid: 3 slots (cargo unloaded, door sealed, receiver present)
  - Each slot: 100×100px square, `Radius.md`, dashed border when empty, thumbnail when filled
- Signature pad section
- Receiver name input
- Notes input
- Primary button: "Submit Delivery" — disabled until at least 1 photo uploaded

**Components:** Input, Button, Card
**States:** Empty (no photos), Partial (some photos), Complete (min. 1 photo + receiver name)
**Navigation exit:** Trip Completed screen on success

---

### 11. Trip Completed Screen

**File:** `screens/driver/TripCompletedScreen.tsx`
**Purpose:** Success confirmation after delivery is submitted.
**Business goal:** Positive reinforcement for drivers, summary of earnings from this trip.

**Layout:**
- Full-screen centered layout
- Large green checkmark icon or animated success ring
- "Delivery Confirmed!" heading
- Trip summary: distance, duration, earnings
- "View Trip Details" secondary button
- "Return to Home" primary button

**Components:** Button
**Animation:** Scale-in success icon (300ms ease-out), stats fade up in sequence

---

### 12. Earnings Screen

**Purpose:** Driver earnings overview — daily, weekly, monthly.
**Business goal:** Drivers track their income and understand pay structure.

**Layout:**
- Header: "My Earnings"
- Period picker: Today / This Week / This Month (FilterChip row)
- Total earnings DarkCard (large number, period label)
- Breakdown bar chart (if feasible) or list
- Trip-by-trip earnings list: trip ID, route, amount, date
- Payout schedule info card

**Components:** DarkCard, FilterChip, Card, Mono (for amounts)

---

### 13. Profile Screen (Driver)

**File:** `screens/driver/ProfileScreen.tsx`
**Purpose:** Driver's personal information and account management.
**Business goal:** Drivers can view and update their contact info and documents.

**Layout:**
- Dark header with large Avatar (xl size, initials, online status dot)
- Driver name (headingL), ID (Mono), phone number
- Stat row: Total trips, Rating, Days active
- Section: Personal Information (name, phone, email, license number)
- Section: Document Vault shortcut
- Section: Account (settings, help, logout)
- Logout button (danger variant)
- Bottom: DriverBottomNav (Profile active)

**Components:** Avatar, Card, Button, Mono, DriverBottomNav

---

### 14. Notifications Screen

**File:** `screens/driver/NotificationsScreen.tsx`
**Purpose:** Chronological list of system and operational notifications.
**Business goal:** Drivers are informed of trip assignments, status changes, and system alerts.

**Layout:**
- Header: "Notifications"
- "Mark all as read" link (top right)
- Notification list: icon, title, body, timestamp, read/unread indicator
  - Unread: white card background, left border `Colors.primary`
  - Read: `Colors.gray50` background
- Empty state: bell icon + "No notifications yet"

**Components:** Card

---

### 15. Settings Screen

**File:** `screens/driver/SettingsScreen.tsx`
**Purpose:** App configuration and preferences.
**Business goal:** Drivers control their notification preferences, language, and security settings.

**Sections:**
- Notifications: push toggle, SMS toggle
- Appearance: language picker (Arabic/English), dark mode toggle
- Privacy: location sharing while on trip, data sharing
- Security: biometric login toggle, change PIN
- About: app version, terms, privacy policy

**Components:** Card, Button (for toggles)

---

### 16. Document Vault

**File:** `screens/driver/DocumentsScreen.tsx`
**Purpose:** Driver's personal documents — license, insurance, medical.
**Business goal:** Centralized document storage with expiry tracking.

**Layout:**
- Header: "Document Vault"
- Document cards with: document type, expiry date, StatusBadge (Active/Expiring/Expired)
- Upload button per document
- "Add Document" FAB (not the nav FAB — a screen-level FAB)

**Components:** Card, StatusBadge, Button

---

## Operator App — Core Documented Screens

### 1. Home Dashboard (Operator)

**File:** `screens/operator/HomeScreen.tsx`
**Purpose:** Operations command center — fleet status at a glance.
**Business goal:** Operator sees total fleet health, active trips, and alerts in one view.

**Layout:**
- StatusBar: light-content
- Dark header section (not a card — raw dark background):
  - Greeting + operator name
  - Date
  - Notification bell with badge count
- KPI stats row: 4 DarkCards (Total Trips, In Transit, Drivers Active, Revenue Today)
  - Each DarkCard: label (Caption/overline, gray), value (headingXL, white)
- Section: "Active Trips" — horizontal scroll or list of TripItem cards
  - TripItem: Trip ID, route, driver avatar + name, progress bar, ETA, StatusBadge
- Section: "Alerts" — amber/red badge cards for delayed trips or expiring documents
- Bottom: OperatorBottomNav (Home active)

**Components:** DarkCard, Card, StatusBadge, Avatar, OperatorBottomNav
**Data required:** Fleet stats, active trip list, active alerts
**Loading:** Skeleton KPI cards (4×), skeleton trip rows (3×)
**Empty state (no active trips):** "All trips completed — fleet standing by"

---

### 2. Trip List (Operator)

**File:** `screens/operator/TripListScreen.tsx`
**Purpose:** Searchable, filterable list of all trips.
**Business goal:** Operators find any trip quickly using search, filter, and status tabs.

**Layout:**
- White header, "Trips" title
- SearchInput
- FilterChip row: All / In Transit / Scheduled / Delayed / Completed / Cancelled
- KPI summary chips: counts per status
- Trip card list:
  - Trip ID (Mono), status badge, route, driver, cargo, date
  - Tap → TripDetails
- Bottom: OperatorBottomNav (Trips active)

**Components:** SearchInput, FilterChip, StatusBadge, Avatar, Mono, OperatorBottomNav
**Filtering:** Real-time filter as FilterChip state changes, search queries ID + route + driver name
**Loading:** 3 skeleton cards
**Empty state:** "No trips match your filter"

---

### 3. Trip Details (Operator)

**File:** `screens/operator/TripDetailsScreen.tsx`
**Purpose:** Full detail view of a single trip.
**Business goal:** Operator sees complete trip timeline, cargo info, driver, and can take actions.

**Layout:**
- Dark header card: Trip ID, route (origin → destination with dots), status badge, distance, ETA, progress
- Driver row: Avatar, name, ID, phone — with "Call" and "Message" actions
- Timeline: vertical step list (Created, Assigned, Pickup Verified, In Transit, Destination Reached, Delivery Confirmed)
  - Completed steps: green dot
  - Active step: orange dot, pulsing
  - Pending steps: gray dot
- Cargo section: description, weight, value, special instructions
- Vehicle section: vehicle ID, model
- Documents section: POD thumbnails if uploaded
- Action buttons: "Edit Trip", "Cancel Trip" (danger)
- Bottom navigation (back arrow or swipe)

**Components:** Card, DarkCard, StatusBadge, Avatar, Button

---

### 4. Create Trip Screen

**File:** `screens/operator/CreateTripScreen.tsx`
**Purpose:** Multi-section form to dispatch a new trip.
**Business goal:** Operator creates a trip by selecting customer, route, driver, vehicle, and cargo.

**Sections:**
1. Customer — tap to select from customer list
2. Pickup location — text input with location search
3. Destination — text input with location search
4. Date and Time — date picker + time picker
5. Cargo — description, weight, special instructions
6. Driver — select from available drivers list (filterable)
7. Vehicle — select from available vehicles list
8. Notes — optional multiline input
9. Submit — "Create Trip" primary button (disabled until required fields complete)

**Required fields:** Customer, pickup, destination, date, driver, vehicle
**Optional:** cargo weight, cargo description, notes, time

**Components:** Input, Button, Card, StatusBadge (for driver/vehicle availability in pickers)
**Navigation entry:** OperatorBottomNav FAB press
**Navigation exit:** Trip Details on success, or back on cancel
**Success feedback:** Toast "Trip TRP-XXXX created successfully" + auto-navigate to TripDetails

---

### 5. Driver List Screen

**File:** `screens/operator/DriverListScreen.tsx`
**Purpose:** Full list of drivers with search, filter, and quick actions.
**Business goal:** Operators see driver availability and contact drivers directly.

**Layout:**
- Header: "Drivers"
- SearchInput
- FilterChip row: All / Available / On Trip / Off Duty
- Driver cards:
  - Avatar (with online status dot), name, ID (Mono), trip count, rating
  - StatusBadge (Available/On Trip/Off Duty)
  - Footer actions: Call, Message, View Trips, Edit
- Bottom: OperatorBottomNav (Drivers active)

**Sample data (from source):**
- DRV-0112 Ahmed Al-Rashidi — 243 trips, 4.9 rating
- DRV-0147 Khalid Al-Zahrani — 312 trips, 4.9 rating
- DRV-0089 Faisal Al-Ghamdi — 178 trips, 4.7 rating
- DRV-0201 Omar Al-Shehri — 95 trips, 4.8 rating

**Components:** SearchInput, FilterChip, Avatar, StatusBadge, Mono, OperatorBottomNav

---

### 6. Vehicle List Screen

**File:** `screens/operator/VehicleListScreen.tsx`
**Purpose:** Fleet vehicle inventory with status and document health.
**Business goal:** Operators track vehicle availability and identify compliance risks.

**Layout:**
- Header: "Vehicles"
- SearchInput
- FilterChip row: All / Available / On Trip / In Service
- Vehicle cards:
  - Vehicle icon, vehicle ID (Mono), model, year, capacity, StatusBadge
  - Document health: "4/4 docs" (green) or "3/4 docs ⚠" (amber)
  - Footer: Documents, History, Edit
- Bottom: OperatorBottomNav (More tab active)

**Sample data (from source):**
- TRK-2041 Mercedes-Benz Actros 2022 — 25,000 kg GVW
- TRK-2038 Volvo FH 540 2021 — 24,000 kg
- TRK-2035 MAN TGX 480 2020 — 26,000 kg
- TRK-2030 Scania R 500 2019 — 23,000 kg

**Components:** SearchInput, FilterChip, StatusBadge, Mono, OperatorBottomNav

---

### 7. Vehicle Renewal Screen

**File:** `screens/operator/VehicleRenewalScreen.tsx`
**Purpose:** List of upcoming and overdue vehicle document renewals.
**Business goal:** Operators proactively manage compliance before documents expire.

**Layout:**
- Header: "Vehicle Renewals"
- Summary chips: Due Soon count, Critical count, Overdue count
- Renewal items list:
  - Vehicle ID (Mono), document type, expiry date, days remaining, cost, StatusBadge
  - Overdue: red badge, days shown as negative ("5 days overdue")
  - Critical (≤7 days): red/amber badge
  - Due Soon (≤30 days): amber badge
  - Renewed: green badge

**Sample data (from source):**
- TRK-2041 Annual Inspection — due 25 Jul, 19 days, SAR 350
- TRK-2038 Istimara (Registration) — due 28 Jul, 22 days, SAR 500
- TRK-2035 Insurance Certificate — overdue 5 days, SAR 2,200
- TRK-2030 Driving Permit — due 10 Jul, 4 days critical, SAR 120

**Components:** Card, StatusBadge, Mono, Button

---

### 8. Invoice List Screen

**File:** `screens/operator/InvoiceListScreen.tsx`
**Purpose:** Financial overview of all invoices.
**Business goal:** Operators track outstanding, paid, and overdue payments.

**Sample invoices (from source):**
- INV-2024-0445 Saudi Electronics Co. — SAR 4,200 — Pending
- INV-2024-0444 Al-Jazeera Trading — SAR 3,600 — Paid
- INV-2024-0443 Gulf Auto Parts — SAR 5,850 — Overdue
- INV-2024-0442 Aramco Supply Chain — SAR 12,400 — Paid

**Invoice status colors:**
- Paid → success (green)
- Pending → info (blue)
- Overdue → danger (red)

**Components:** SearchInput, FilterChip, StatusBadge, Mono, OperatorBottomNav

---

## Assigned Vehicle Screen (Driver)

**File:** `screens/driver/AssignedVehicleScreen.tsx`
**Purpose:** Driver sees details of the vehicle assigned to them.

**Vehicle documents (from source):**
- Istimara (Registration) — valid, exp 12 Mar 2025
- Insurance Certificate — valid, exp 30 Jun 2025
- Annual Inspection — expiring, exp 25 Jul 2024
- Load Permit — valid, exp 31 Dec 2024

**Vehicle specs (from source):**
- Make: Mercedes-Benz Actros
- Year: 2022
- Plate: أ ب ج 1234
- VIN: WDB9634031L1234567
- Engine: OM 471 — 510 HP
- Capacity: 25,000 kg GVW
- Fuel: Diesel
- Mileage: 187,420 km

**Layout:**
- Dark header with vehicle icon box
- Spec grid (2-column)
- Documents list with StatusBadge per document

**Components:** Card, DarkCard, StatusBadge

---

## Web Dashboard Screens (44 screens)

The web dashboard shares the same design tokens but uses a sidebar navigation layout at 1440px viewport width.

### Layout System

- **Sidebar:** Fixed left, width 240px, background `#1C1C2E`, logo at top, nav items below
- **Main area:** Right of sidebar, `Colors.gray100` background
- **Content area:** Max-width 1200px, centered with auto horizontal margins
- **Grid:** 12 columns, 24px gutters

### Sidebar Navigation Items

1. Overview (Dashboard icon)
2. Trips (Truck icon) — expandable: List, Create
3. Drivers (Users icon) — expandable: List, Add
4. Vehicles (Car icon) — expandable: List, Renewals
5. Customers (Building icon) — expandable: List
6. Invoices (FileText icon) — expandable: List, Create
7. Rate Cards (Tag icon)
8. Reports (BarChart icon) — expandable: Revenue, Performance, Driver, Vehicle
9. Settings (Settings icon) — expandable: General, Users, Billing, Integrations
10. Notifications (Bell icon)

### Dashboard / Overview

- KPI row: 4 stat cards (Total Trips, Active Drivers, Fleet Utilization %, Revenue MTD)
- Active trips map panel (full-width or half)
- Recent trips table
- Alert panel (document renewals, delayed trips)

### All other web screens

Follow the same component vocabulary (Button, Badge, Card, Input, Avatar, StatusBadge) but adapted for web with:
- Table components for list views (sortable columns, pagination)
- Sidebar filter panel for list views with many filter options
- Breadcrumb navigation above page title
- Bulk action toolbar for multi-select table rows
