# Build from the repo root: docker build -f frontend/web-dashboard/Dockerfile .
# Build stage
FROM node:22-alpine as build
WORKDIR /app
# Workspace manifests first (for layer caching).
# NOTE: the lockfile is intentionally NOT copied. It is generated on macOS
# (darwin-arm64), and npm's optional-dependencies bug (npm/cli#4828) then
# skips the Linux rolldown native binding Vite 8 needs, breaking the build
# with "Cannot find module '@rolldown/binding-linux-x64-musl'". Installing
# without the lockfile lets npm resolve the correct binding for this platform.
COPY package.json ./
COPY packages/shared-types/package.json ./packages/shared-types/
COPY backend/api-server/package.json ./backend/api-server/
COPY frontend/web-dashboard/package.json ./frontend/web-dashboard/
RUN npm install --legacy-peer-deps --ignore-scripts
# Shared types (built explicitly since --ignore-scripts skips prepare)
COPY packages/shared-types ./packages/shared-types
RUN npm run build -w @mercon/shared-types
# Copy source code and build the Vite app
COPY frontend/web-dashboard ./frontend/web-dashboard
RUN npm run build -w @mercon/web-dashboard

# Production stage
FROM nginx:alpine
# Copy the custom nginx configuration
COPY frontend/web-dashboard/nginx.conf /etc/nginx/conf.d/default.conf
# Copy the built assets from the build stage
COPY --from=build /app/frontend/web-dashboard/dist /usr/share/nginx/html
# Expose port 80
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
