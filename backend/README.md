# 🏢 Backend (The Core Engine)

## What is this folder?
Welcome to the `backend`! Think of this entire folder as the main engine of a car. While the mobile app or the WhatsApp bot is the steering wheel and dashboard that the user interacts with, this folder is where the actual heavy lifting happens. It contains the central logic for the entire Mesiri platform. 

It handles security (who is allowed to do what), stores all the important data (users, projects, materials), and makes sure all the different parts of the platform run smoothly.

## What's inside right now?
Here are the main pieces you'll see in this root folder:

*   **`src/` (Source Code):** This is the actual engine block. It contains all the Python code that makes the backend work (the business logic, the database connections, the API routes). 
*   **`migrations/` (Database History):** Think of this as the architectural blueprints for your database. Every time you want to add a new table (like a new "Invoices" table), you write a migration file here. It keeps a history of how your database structure changes over time.
*   **`apps/`:** Scripts or mini-applications that help manage this backend environment.
*   **`tests/`:** The quality assurance department. It contains code that automatically checks if the engine (`src/`) is working correctly without having to test it manually.

## 🛠️ Workflow Example: User Views Their Assigned Projects

This detailed workflow traces the exact path through the codebase when a user opens the mobile app and views their assigned projects.

### 📱 Client Side (Mobile App)

1. **Mobile Screen Renders** (`apps/mobile/components/screens/ProjectsManagementScreen.tsx`)
   - User opens the Projects screen
   - Component calls the `useProjects()` hook to fetch data

2. **Projects Hook Executes** (`apps/mobile/hooks/useProjects.ts`)
   - `useProjects()` hook triggers on mount via `useEffect`
   - Calls `api.get('/projects')` to fetch projects from the backend

3. **API Client Intercepts Request** (`packages/auth/src/client.ts`)
   - Axios interceptor retrieves the JWT token from Expo SecureStore (`mesiri_access_token` key)
   - Adds `Authorization: Bearer <token>` header to the request
   - Logs the request: `[API REQUEST] GET http://localhost:8000/projects`
   - Sends HTTP GET request to `${baseURL}/projects`

### 🌐 Network Layer
- Request travels over HTTP/HTTPS to the backend server (default: `http://localhost:8000`)

### 🏗️ Backend Entry Point

4. **FastAPI Application Receives Request** (`backend/src/mesiri/http/app.py`)
   - Request arrives at the FastAPI application
   - **CORS Middleware**: Handles cross-origin request headers
   - **Correlation Middleware**: Extracts or generates `X-Correlation-ID` for request tracing
   - FastAPI routes the request to the appropriate router based on URL prefix `/projects`

5. **Projects Router Handles Request** (`backend/src/mesiri/domains/projects/router.py`)
   - FastAPI matches the route: `GET /projects` → `list_projects()` function
   - Two dependencies are injected before the handler runs:
     - `get_current_user` (authentication)
     - `get_db_conn` (database connection)

### 🔐 Authentication Layer

6. **Authentication Dependency** (`backend/src/mesiri/domains/shared/auth.py`)
   - `get_current_user()` function extracts the `Authorization` header
   - Validates it starts with `Bearer `
   - Extracts the JWT token (removes "Bearer " prefix)

7. **JWT Token Verification** (`backend/src/mesiri/domains/identity/auth_service.py`)
   - Uses `jwt.decode()` with `SECRET_KEY` and `ALGORITHM` (HS256)
   - Decodes token payload containing:
     - `sub`: user ID
     - `org`: organization ID
     - `role`: user role (ADMIN, PM, FOREMAN, etc.)
     - `exp`: token expiration timestamp
   - If invalid or expired: raises `HTTPException(401, "Invalid token")`
   - If valid: returns decoded payload as a dictionary

### 💾 Database Connection Layer

8. **Database Connection Dependency** (`backend/src/mesiri/infrastructure/postgres/dependency.py`)
   - `get_db_conn()` retrieves the PostgreSQL adapter from application state
   - Accesses `request.app.state.lifecycle.container.postgres`
   - Opens a new transaction context (`async with postgres.transaction()`)

9. **PostgreSQL Connection Pool** (`backend/src/mesiri/infrastructure/postgres/database.py`)
   - `transaction()` method yields an `AsyncConnection` from the SQLAlchemy engine
   - Connection is managed by the pool (configured at startup with `pool_size`, `pool_pre_ping`)
   - Transaction automatically commits on success or rolls back on error

### 📊 Business Logic Layer

10. **List Projects Handler** (`backend/src/mesiri/domains/projects/router.py` - line 134)
    - Extracts `org_id` from the authenticated user payload: `user.get("org")`
    - Validates `org_id` exists (raises 400 if missing)
    - Builds SQL query using SQLAlchemy Core:
      ```python
      sa.select(_projects).where(_projects.c.organization_id == org_id)
      ```
    - Executes query against the `projects` table via the database connection
    - Fetches all matching rows from the result set

11. **Response Transformation**
    - Iterates through database rows
    - Transforms each row into a `ProjectResponse` Pydantic model:
      - Maps database columns to response fields
      - Sets default values (`status="on_track"`, `progress=0`, `open_issues=0`)
    - Returns list of `ProjectResponse` objects

### 🔄 Response Journey Back

12. **FastAPI Serialization**
    - FastAPI serializes `ProjectResponse` objects to JSON using Pydantic
    - Sets response headers (including `X-Correlation-ID`)
    - Returns HTTP 200 with JSON body

13. **Network Transport**
    - Response travels back over HTTP/HTTPS to the mobile client

14. **Mobile API Client Receives Response** (`packages/auth/src/client.ts`)
    - Axios receives the HTTP response
    - Response interceptor logs success or error
    - Returns response data to the calling hook

15. **Projects Hook Updates State** (`apps/mobile/hooks/useProjects.ts`)
    - `setProjects(res.data)` updates React state with fetched projects
    - `setIsLoading(false)` marks loading as complete
    - Component re-renders with the project data

16. **UI Renders Projects** (`apps/mobile/components/screens/ProjectsManagementScreen.tsx`)
    - React Native components display the list of projects
    - User sees their organization's projects on screen

### 🚀 Bootstrap & Initialization

The entire backend infrastructure is initialized at startup:

**Application Lifecycle** (`backend/src/mesiri/bootstrap/lifecycle.py`)
- `AppLifecycle.startup()` orchestrates dependency initialization:
  1. Validates configuration settings
  2. Configures structured logging
  3. Connects to PostgreSQL (creates engine and connection pool)
  4. Connects to Redis
  5. Verifies object storage reachability
- If any step fails, previously opened resources are closed (rollback)

**Dependency Container** (`backend/src/mesiri/bootstrap/container.py`)
- `build_container()` assembles all infrastructure adapters:
  - PostgreSQL client (`PostgresDatabase` or `FakePostgres` for testing)
  - Redis client (`RedisClient` or `FakeRedis` for testing)
  - Object storage client (R2, S3, or fake)
- Container is attached to `app.state.lifecycle` for request-scoped access

### 📝 Summary of Files in Order

| Step | File Path | Purpose |
|------|-----------|---------|
| 1 | `apps/mobile/components/screens/ProjectsManagementScreen.tsx` | UI component |
| 2 | `apps/mobile/hooks/useProjects.ts` | React hook for data fetching |
| 3 | `packages/auth/src/client.ts` | API client with auth interceptors |
| 4 | `backend/src/mesiri/http/app.py` | FastAPI app factory & middleware |
| 5 | `backend/src/mesiri/domains/projects/router.py` | Projects API endpoints |
| 6 | `backend/src/mesiri/domains/shared/auth.py` | Auth dependencies |
| 7 | `backend/src/mesiri/domains/identity/auth_service.py` | JWT utilities |
| 8 | `backend/src/mesiri/infrastructure/postgres/dependency.py` | Database dependency injection |
| 9 | `backend/src/mesiri/infrastructure/postgres/database.py` | PostgreSQL connection management |
| 10 | `backend/src/mesiri/bootstrap/lifecycle.py` | Startup/shutdown orchestration |
| 11 | `backend/src/mesiri/bootstrap/container.py` | Dependency container assembly |

## What should go here in the future?
*   **Configuration Files:** If you need to add a new global setting (like a new `.env` file template, or a docker-compose configuration file to run the server), it usually goes in this root folder.
*   **DO NOT** put direct business logic (like a new file called `calculate_taxes.py`) directly in this root folder. All the actual working code belongs deep inside the `src/mesiri/` folder, which we will explore next!
