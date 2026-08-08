# MERCON User Flows

Complete flow documentation with Mermaid diagrams for all major user journeys.

---

## Authentication Flow (Driver)

```mermaid
flowchart TD
    A[App Launch] --> B{Saved Token?}
    B -->|Yes| C[Validate Token]
    C -->|Valid| D[HomeScreen Driver]
    C -->|Expired| E[LoginScreen]
    B -->|No| E
    E --> F[Enter Phone Number]
    F --> G{Valid Format?}
    G -->|No| H[Show error: Invalid number]
    H --> F
    G -->|Yes| I[Request OTP via API]
    I --> J[OTP Verification Screen]
    J --> K[Enter 6-digit OTP]
    K --> L{Correct OTP?}
    L -->|No| M[Clear boxes, show error]
    M --> K
    L -->|Yes| N[Save token to AsyncStorage]
    N --> D
    J --> O[Resend OTP after 30s]
    O --> I
```

---

## Authentication Flow (Operator)

```mermaid
flowchart TD
    A[App Launch] --> B{Saved Token?}
    B -->|Yes| C[Validate Token]
    C -->|Valid| D[HomeScreen Operator]
    C -->|Expired| E[LoginScreen]
    B -->|No| E
    E --> F[Enter Phone + OTP]
    F --> G[Operator Home Dashboard]
```

---

## Driver Trip Execution Flow

```mermaid
flowchart TD
    A[HomeScreen] --> B{Active Trip?}
    B -->|Yes| C[Active Trip Card shown]
    B -->|No| D[No trip state - awaiting assignment]
    C --> E[Tap Navigate]
    E --> F[LiveNavigation Screen]
    F --> G[Driver arrives at pickup]
    G --> H[Tap Verify Pickup]
    H --> I[Pickup Verification Screen]
    I --> J{GPS within 500m?}
    J -->|No| K[Error: Move closer to pickup]
    K --> I
    J -->|Yes| L[Capture loading photo optional]
    L --> M[Enter receiver code if required]
    M --> N[Confirm Pickup]
    N --> O[Trip status → In Transit]
    O --> P[Navigate to destination]
    P --> Q[Driver arrives at destination]
    Q --> R[Destination Reached Screen]
    R --> S[Upload POD photos min 1]
    S --> T[Enter receiver name]
    T --> U[Submit Delivery]
    U --> V[Trip Completed Screen]
    V --> W[Return to HomeScreen]
    W --> D
```

---

## Create Trip Flow (Operator)

```mermaid
flowchart TD
    A[OperatorBottomNav FAB press] --> B[CreateTripScreen]
    B --> C[Select Customer]
    C --> D[Enter Pickup Location]
    D --> E[Enter Destination]
    E --> F[Set Date and Time]
    F --> G[Describe Cargo optional]
    G --> H[Select Driver]
    H --> I{Driver Available?}
    I -->|Yes| J[Driver selected]
    I -->|No| K[Show on-trip/off-duty badge, still selectable]
    K --> J
    J --> L[Select Vehicle]
    L --> M{Vehicle Available?}
    M -->|Yes| N[Vehicle selected]
    M -->|No| O[Show on-trip/maintenance badge, selectable with warning]
    O --> N
    N --> P[Add Notes optional]
    P --> Q{All required fields filled?}
    Q -->|No| R[Submit button disabled]
    R --> Q
    Q -->|Yes| S[Submit enabled]
    S --> T[POST /trips]
    T --> U{API success?}
    U -->|Yes| V[Toast: Trip created]
    V --> W[Auto-navigate to TripDetailsScreen]
    U -->|No| X[Toast: Error creating trip]
    X --> B
```

---

## Navigation Flow — Driver App

```mermaid
flowchart LR
    SPLASH[SplashScreen] --> LOGIN[LoginScreen]
    LOGIN --> OTP[OTP Verification]
    OTP --> HOME[HomeScreen]
    HOME <--> TRIPS[TripsScreen]
    HOME <--> PROFILE[ProfileScreen]
    TRIPS --> TRIPDETAIL[TripDetails]
    HOME --> ACTIVETRIP[ActiveTripScreen]
    ACTIVETRIP --> LIVENAV[LiveNavigation]
    ACTIVETRIP --> PICKUPVERIFY[PickupVerification]
    PICKUPVERIFY --> ACTIVETRIP
    ACTIVETRIP --> DELIVERYVERIFY[DeliveryVerification]
    DELIVERYVERIFY --> TRIPCOMPLETE[TripCompleted]
    TRIPCOMPLETE --> HOME
    PROFILE --> DOCUMENTS[DocumentVault]
    PROFILE --> NOTIFICATIONS[Notifications]
    PROFILE --> SETTINGS[Settings]
    HOME --> EMERGENCY[Emergency Screen]
    HOME --> REPLACEMENT[ReplacementDriver]
    HOME --> ASSIGNEDVEHICLE[AssignedVehicle]
```

---

## Navigation Flow — Operator App

```mermaid
flowchart LR
    HOME[HomeScreen] <--> TRIPLIST[TripListScreen]
    HOME <--> DRIVERLIST[DriverListScreen]
    HOME --> FAB[FAB → CreateTrip]
    FAB --> CREATETRIP[CreateTripScreen]
    CREATETRIP --> TRIPDETAIL[TripDetailsScreen]
    TRIPLIST --> TRIPDETAIL
    DRIVERLIST --> DRIVERDETAIL[DriverDetails]
    DRIVERLIST --> ADDDRIVER[AddDriver]
    MORE[MoreTab] --> VEHICLELIST[VehicleListScreen]
    MORE --> INVOICELIST[InvoiceListScreen]
    MORE --> CUSTOMERS[CustomerList]
    MORE --> RATECARDS[RateCardList]
    VEHICLELIST --> VEHICLEDETAIL[VehicleDetails]
    VEHICLELIST --> VEHICLERENEWAL[VehicleRenewal]
    INVOICELIST --> INVOICEDETAIL[InvoiceDetails]
    INVOICELIST --> CREATEINVOICE[CreateInvoice]
```

---

## Document Upload Flow (Driver)

```mermaid
flowchart TD
    A[DocumentVaultScreen] --> B[Select document type]
    B --> C[Tap Upload]
    C --> D{Camera or Gallery?}
    D -->|Camera| E[Open Camera]
    D -->|Gallery| F[Open Image Picker]
    E --> G[Capture photo]
    F --> H[Select image]
    G --> I[Preview]
    H --> I
    I --> J{Image acceptable?}
    J -->|No| K[Retake / Re-select]
    K --> D
    J -->|Yes| L[Upload to server]
    L --> M{Upload success?}
    M -->|Yes| N[StatusBadge updates to Active]
    M -->|No| O[Error toast, retry option]
    O --> L
```

---

## Notification Flow

```mermaid
flowchart TD
    A[Push notification received] --> B{App state?}
    B -->|Foreground| C[In-app toast banner]
    B -->|Background| D[System notification]
    B -->|Killed| D
    D --> E[User taps notification]
    E --> F{Notification type?}
    F -->|Trip assigned| G[Navigate to ActiveTrip]
    F -->|Trip delayed| H[Navigate to TripDetails]
    F -->|Document expiring| I[Navigate to DocumentVault]
    F -->|Invoice due| J[Navigate to InvoiceDetails operator]
    F -->|System alert| K[Navigate to Notifications list]
    C --> L[Tap toast]
    L --> F
```

---

## Error Handling Flow

```mermaid
flowchart TD
    A[API call made] --> B{Response?}
    B -->|200 OK| C[Process response]
    B -->|400 Bad Request| D[Show validation error in form]
    B -->|401 Unauthorized| E[Clear token, navigate to Login]
    B -->|403 Forbidden| F[Show Permission denied toast]
    B -->|404 Not Found| G[Show Not found empty state]
    B -->|500 Server Error| H[Show Retry toast]
    B -->|Network error| I[Show Offline banner]
    H --> J{Retry attempts < 3?}
    J -->|Yes| K[Auto-retry after 2s delay]
    K --> A
    J -->|No| L[Show permanent error state]
    I --> M[Monitor connectivity]
    M --> N{Connection restored?}
    N -->|Yes| O[Auto-retry last request]
    N -->|No| M
```

---

## Offline Mode Flow

```mermaid
flowchart TD
    A[Network disconnected] --> B[Show offline banner at top]
    B --> C{Current screen?}
    C -->|List screens| D[Show cached data with stale indicator]
    C -->|Form screens| E[Disable submit, show offline warning]
    C -->|Active trip| F[Navigation still works offline GPS]
    D --> G[User pulls to refresh]
    G --> H{Connected?}
    H -->|Yes| I[Fetch fresh data, hide banner]
    H -->|No| J[Show offline toast]
```

---

## Settings and Profile Flow

```mermaid
flowchart TD
    PROFILE[ProfileScreen] --> INFO[Edit Personal Info]
    PROFILE --> DOCS[DocumentVault]
    PROFILE --> NOTIF[Notification Settings]
    PROFILE --> SECURITY[Security Settings]
    PROFILE --> HELP[Help and Support]
    PROFILE --> LOGOUT[Logout]
    LOGOUT --> CONFIRM{Confirm?}
    CONFIRM -->|Yes| CLEAR[Clear token]
    CLEAR --> LOGIN[LoginScreen]
    CONFIRM -->|No| PROFILE
    NOTIF --> PUSH[Toggle push notifications]
    NOTIF --> SMS[Toggle SMS]
    SECURITY --> BIOMETRIC[Toggle biometric login]
```

---

## Vehicle Renewal Flow (Operator)

```mermaid
flowchart TD
    A[VehicleRenewalScreen] --> B[View renewal list]
    B --> C[Tap renewal item]
    C --> D[VehicleRenewal detail view]
    D --> E[Upload renewed document photo]
    E --> F[Enter new expiry date]
    F --> G[Submit renewal]
    G --> H{API success?}
    H -->|Yes| I[StatusBadge updates to Renewed/Active]
    H -->|No| J[Error toast]
    J --> G
```

---

## Invoice Creation Flow (Operator)

```mermaid
flowchart TD
    A[InvoiceListScreen] --> B[Tap Create Invoice]
    B --> C[CreateInvoiceScreen]
    C --> D[Select Trip]
    D --> E[Customer auto-populated from trip]
    E --> F[Review line items]
    F --> G[Apply rate card if applicable]
    G --> H[Set payment terms]
    H --> I[Preview invoice]
    I --> J{Correct?}
    J -->|No| K[Edit fields]
    K --> I
    J -->|Yes| L[Generate invoice PDF]
    L --> M[Send to customer optional]
    M --> N[Invoice status → Pending]
    N --> O[Navigate to InvoiceDetails]
```
