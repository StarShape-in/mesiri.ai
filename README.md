# MERCON Logistics Platform

The MERCON Logistics Platform is a comprehensive, enterprise-grade fleet and trip management ecosystem built for seamless operations, dispatching, and real-time live telemetry tracking.

## 🚀 System Architecture

The ecosystem consists of two primary applications communicating over a unified Postgres Database.

### 1. The Operator Web Dashboard (`frontend/web-dashboard`)
Built with **React, Vite, TypeScript, TailwindCSS, and Recharts**.
- **Dashboard Analytics**: Real-time KPI cards and dynamic charts summarizing revenue, active fleet, and trip status distributions.
- **Trip Management**: End-to-end trip lifecycle control. Create trips, assign vehicles/drivers, track statuses, and view trip details.
- **Fleet & Driver Hub**: Complete CRM for managing Driver profiles (including AI risk scores and documents) and Vehicles (maintenance logs and availability).
- **Live GPS Tracking**: Uses `socket.io-client` to connect to the backend's live telemetry stream, updating driver coordinates on the map in real-time.

### 2. The API Server & WebSockets (`backend/api-server`)
Built with **Node.js, Express, TypeScript, Prisma (PostgreSQL), and Socket.io**.
- **Authentication**: JWT-based login systems for Operators (Web) and Drivers (Mobile app).
- **RESTful Endpoints**: Full CRUD endpoints powering the frontend's Trip, Driver, Vehicle, Customer, and Reporting services.
- **Socket.io Telemetry Engine**: A low-latency WebSocket server that listens for `driver:location_update` events from the mobile apps and broadcasts them directly to tracking dashboards via `trip:location_update`.

---

## 🛠️ Technology Stack

- **Frontend:** React 18, Vite, TypeScript, TailwindCSS, React Query, React Router, Lucide Icons, Recharts, Socket.io-client.
- **Backend:** Node.js, Express, TypeScript, Prisma ORM, Socket.io.
- **Database:** PostgreSQL.
- **Deployment & CI/CD:** GitHub Actions, Docker, Docker Compose, Nginx Reverse Proxy, Let's Encrypt (Certbot) SSL.

---

## 📦 Deployment Pipeline

The project uses a highly optimized GitHub Actions CI/CD pipeline (`.github/workflows/ci-cd.yml`) that deploys directly to a live VPS at `mercon.tech`.

1. **Trigger:** Code pushed to `main` branch.
2. **Transfer:** Source code is synced to the VPS using `rsync` over SSH.
3. **Build:** Docker Compose rebuilds the containers (`mercon-api` and `mercon-frontend`).
4. **Proxy:** An external Nginx instance safely routes traffic to the containers, ensuring SSL certificates generated via Certbot are preserved and not overwritten.

---

## 📡 Live Telemetry Engine (WebSockets)

One of the most advanced features is the real-time tracking engine:
1. **Driver's App** emits a `driver:location_update` over WebSockets containing `lat`, `lng`, and `speed`.
2. **Node.js Server** intercepts the payload and emits it on a dedicated trip channel `trip:location_update:{tripId}`.
3. **Operator Dashboard** subscribes to this channel on the `TripTrackingPage` and dynamically updates the UI coordinates and speed every 10 seconds without refreshing.

---

## 🏗️ Future Roadmap (Phase 4+)

- **Map Integration**: Integrate Mapbox or Google Maps API to visually plot the truck's coordinates on a real interactive map.
- **Driver Mobile App**: Build the React Native mobile application for the drivers to capture Proof of Delivery (POD) photos and trigger the live GPS engine.
- **Automated Invoicing**: Generate automated PDF invoices upon Trip Completion.

## 📁 Repository Structure (npm workspaces)

```
mercon/
├── package.json               # Root — npm workspaces + shared scripts
├── docker-compose.yml         # Workspace-aware container builds
├── backend/api-server/        # @mercon/api-server    — Express + Prisma API
├── frontend/
│   ├── web-dashboard/         # @mercon/web-dashboard — React + Vite dashboard
│   └── mobile-app/mercon-app/ # @mercon/mobile-app    — Expo app (standalone install)
├── packages/shared-types/     # @mercon/shared-types  — DTOs shared API ↔ dashboard
├── deploy/                    # Nginx / VPS configs
└── docs/                      # Business & technical documentation
```

The API server, web dashboard, and shared-types are **npm workspaces** — one `npm install` at the root installs and links everything. The **mobile app is intentionally standalone** (Expo/Metro does not play well with hoisted node_modules); install it separately.

## 🏃‍♂️ Getting Started Locally

1. **Install everything** (from the repo root)
   ```bash
   npm install
   ```

2. **Configure env** — copy `backend/api-server/.env.example` → `.env` and set `DATABASE_URL` / `JWT_SECRET` (the server fails fast if these are missing). For the dashboard, copy `frontend/web-dashboard/.env.example` → `.env`.

3. **Run the apps**
   ```bash
   npm run dev:api    # Express API  (backend/api-server)
   npm run dev:web    # Web dashboard (frontend/web-dashboard)
   npm run mobile     # Expo dev server (installs standalone)
   ```

4. **Build for production**
   ```bash
   npm run build      # shared-types → api-server → web-dashboard
   ```
