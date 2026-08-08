# Build from the repo root: docker build -f backend/api-server/Dockerfile .
FROM node:18-alpine

RUN apk add --no-cache openssl

WORKDIR /app

# Workspace manifests first (for layer caching)
COPY package.json package-lock.json ./
COPY packages/shared-types/package.json ./packages/shared-types/
COPY backend/api-server/package.json ./backend/api-server/
COPY frontend/web-dashboard/package.json ./frontend/web-dashboard/
RUN npm install --ignore-scripts

# Shared types (built explicitly since --ignore-scripts skips prepare)
COPY packages/shared-types ./packages/shared-types
RUN npm run build -w @mercon/shared-types

# Prisma client
COPY backend/api-server/prisma ./backend/api-server/prisma
RUN cd backend/api-server && npx prisma generate

# API source + build
COPY backend/api-server ./backend/api-server
RUN npm run build -w @mercon/api-server

WORKDIR /app/backend/api-server

EXPOSE 3000

# Start command (Force schema sync, seed DB, then start server)
CMD ["sh", "-c", "npx prisma db push --accept-data-loss && npx ts-node prisma/seed.ts && node dist/index.js"]
