# MERCON — The Real Plan to Handover

**Date:** July 11, 2026
**Who is building this:** One developer (Hysam), using AI to build everything.
**This document replaces the old plans. It is based on reading the actual code, not the docs.**

---

## Part 1: Where the project really stands today

### ✅ Backend API — DONE (about 90%)

This part is real and working. It is deployed at `mercon.tech` with Docker.

- 16 controllers with real database logic (trips, drivers, vehicles, customers, invoices, rate cards, documents, reports, notifications, users, auth)
- Login with JWT + role checks (Admin / Operator / Driver)
- Live GPS relay with Socket.io (receives `driver:location_update`, broadcasts to the dashboard)
- ICCES vehicle-tracker polling (3 background jobs: live fallback, odometer sync, alarm sync)
- File uploads (photos, documents)
- Database schema (Prisma + PostgreSQL) with seed script

**What is missing in the backend (for the driver app):**
- Only 3 mobile endpoints exist: driver login, get current trip, update trip status
- No mobile endpoints yet for: trip history, driver notifications, emergency alert, driver profile, linking uploaded photos to a trip step

### ✅ Web Dashboard (Operator) — DONE (about 95%)

This is genuinely finished and connected to the real API. 46 routes, all pages fetch real data.

- Dashboard, Trips (create/track/complete), Drivers, Vehicles, Customers, Invoices, Rate cards, Documents, Reports, Notifications, Settings
- Live trip tracking over WebSockets
- Role-based access (admin-only pages)

**Small things left:**
- ✅ The Settings user list is now real — it uses `UserManagementPage.tsx` wired to the `/users` API. The old fake `MOCK_USERS` page (`UserListPage.tsx`) was deleted (commit `3da2b27`).
- The tracking map is basic (no Google Maps / Mapbox yet)

### ❌ Mobile App — NOT BUILT (only the design exists)

**This is the honest truth: the mobile app is a picture, not an app.**

There are 24 screens (16 driver + 8 operator) that look finished, but:
- No screen talks to the API — there is no axios/fetch anywhere in the app
- Login button does nothing (`onPress={() => {}}`)
- All data on every screen is hardcoded (fake names, fake trips)
- No login token is saved anywhere (no AsyncStorage / SecureStore)
- No GPS package installed (no expo-location)
- No camera package installed (no expo-camera / image picker)
- No socket connection (no socket.io-client)
- Screens are not even connected to each other with real navigation

So the mobile work is not "polish" — it is **the main remaining build**.

---

## Part 2: The plan (in order)

The big goal: **one mobile app that serves BOTH drivers and operators.**

**How the login works:** there is ONE login screen. The user types their credentials, the backend checks them and sends back the person's role. The app then opens the right experience:
- **Driver** → driver screens (my trip, photos, navigation, GPS)
- **Operator** → operator screens (dashboard, trips, create trip, live tracking)

So "whatever they input decides where they land" — same screen, different app after login.

### Phase 1 — Shared skeleton + unified login (≈ 1 week) — MOSTLY DONE
Make the app "alive": packages installed, API client, login working for real.

1. ✅ Install packages (axios, socket.io-client, expo-secure-store, expo-location, expo-image-picker) — done
2. ✅ API client + token storage + auth context — done
3. ✅ Real driver login (phone + license) — done
4. **Still to do:** unified login — also accept operator credentials, read the role the backend returns, and route to driver screens or operator screens accordingly
5. **Backend work needed:** one mobile login that handles both driver and operator, and returns the role (today driver login and operator/web login are separate)

### Phase 2 — Driver trip workflow (≈ 1–1.5 weeks)
The heart of the driver side: a driver can actually do a trip.

1. Home screen: load the real current trip from `GET /api/mobile/trips/current`
2. Start trip / arrive / deliver: call `POST /api/mobile/trips/:id/status`
3. Cargo photos at pickup + delivery photos (POD): camera → upload to the existing upload endpoint
4. **Backend work needed:** new endpoints for trip history, emergency alert, driver notifications, and linking photos to trips

### Phase 3 — Operator app screens (≈ 1 week)
The operator side is easier — it is mostly reading data and one create form. All the endpoints already exist (the web dashboard uses them).

1. Operator dashboard: live trips, today's trips, alerts (read from the API)
2. Trip list + trip details + live tracking map (read + socket)
3. Create trip (the multi-step form) — reuse the same endpoints the web uses
4. No GPS sending and no camera here, so this is faster than the driver side

### Phase 4 — Live GPS (driver) (≈ 1 week)
1. When a trip is active, read GPS with expo-location every 10 seconds
2. Send `driver:location_update` over socket.io (backend already handles it — this connects the last wire)
3. Test it end to end: drive around, watch the truck move on the operator's screen
4. Handle the hard parts: app in background, phone locked, network drops

### Phase 5 — Remaining screens + real-phone testing (≈ 1 week)
1. Fill in the rest: driver trip history, notifications, emergency button, profile, documents, settings — swap fake data for real API calls
2. Test on real Android phones AND iPhones (both roles: log in as a driver, log in as an operator)
3. Fix crashes, slow screens, GPS battery drain
4. Build the release APK (Android) and iOS build with EAS — the GitHub Action already exists

### Phase 6 — Finish the web + handover (≈ 1 week)
1. ✅ Connect the user list in Settings to the real API (done — see Part 1)
2. Full end-to-end test: operator creates a trip (on web OR phone) → driver does it on the phone → invoice appears
3. Database backup set up and tested once
4. Rotate the JWT secret on the server (the old one was in git)
5. A short user guide (a few pages with screenshots) for operators and drivers
6. Hand it over

### Total: about 5–6 weeks of solo work

The deadline is ~1 month. Two apps in one month, solo, is **tight but doable** because the operator side is mostly read-only and reuses endpoints that already work. If time runs short, the safe cut is to ship the **driver app first** and let operators keep using the web dashboard for a few extra days — the operator mobile app can follow right after. Plan for 5–6 weeks, aim for 4.

---

## Part 3: What NOT to do (to protect your time)

- ❌ Don't add push notifications (FCM) in v1 — the app checks for its trip/data when opened; that is enough to start
- ❌ Don't write a big automated test suite now — one solo dev, changing code daily; test the main flow by hand instead
- ❌ Don't add OTP SMS login — the existing credential login is enough
- ❌ Don't chase the icon TODOs in the mobile screens until the app actually works
- ❌ Don't upgrade the map yet — the basic map is fine for v1

---

## Part 4: Decisions made (updated July 12, 2026)

| Question | Decision |
|---|---|
| Deadline | **~1 month** — tight; ship driver app first if needed |
| Phones | **Android + iPhone** (Expo builds both from one codebase) |
| Mobile app scope | **Both driver AND operator** in one app, unified login by role |
| Apple Developer account | **Already have it** ✅ (no waiting) |
| Map | **Keep the basic map** for v1, upgrade later |
| Install method | **Android:** share the APK file directly. **iPhone:** TestFlight |
| Who creates drivers | **Operators and Admins** (both, on the web dashboard) |
| ICCES credentials | **Not yet** — will add the env vars later; fallback stays untested until then |

**Still push past handover:** map upgrade, push notifications.

**Do this soon (calendar, not work days):**
- [x] ✅ Rotate `JWT_SECRET` — **done July 12, 2026.** Now a GitHub Actions secret
      injected at deploy; the leaked fallback is gone from `docker-compose.yml`
      (compose hard-fails if the secret is missing). Verified live: fresh logins work,
      and a token forged with the old git secret is rejected (403). All prior sessions
      were invalidated, so everyone must log in again.

## Part 5: The ~4-week schedule (both apps)

| Week | Goal | Done when… |
|---|---|---|
| **1** ✅ | Shared skeleton + driver login (done) → finish unified login + role routing | I can log in and land on the driver OR operator side based on my account |
| **2** | Driver trip workflow: current trip, status updates, cargo + POD photos (+ the missing backend endpoints) | A driver can do a full trip from the phone, photos show on the web |
| **3** | Operator app screens (dashboard, trips, create trip, live tracking) + start driver live GPS | An operator can run the day from the phone; a truck moves live on screen |
| **4** | Remaining driver screens, real-phone testing (both roles, Android + iPhone), EAS builds (APK + TestFlight), fix web user list, backup, mini guide | MERCON can use it without me in the room |

---

*Next step: finish Phase 1 — make the login unified (accept operator accounts too) and route by role.*
