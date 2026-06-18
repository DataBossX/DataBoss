# Stage 1: Build React App
FROM node:20 AS frontend-build
ARG FRONTEND_ENV
ENV FRONTEND_ENV=${FRONTEND_ENV}
WORKDIR /app
COPY frontend/ /app/
# Build-time frontend env is injected via the FRONTEND_ENV build arg
# (comma-separated KEY=VALUE pairs). Do NOT print it — that would leak
# values into the build logs.
RUN rm -f /app/.env && \
    printf '%s\n' "${FRONTEND_ENV}" | tr ',' '\n' > /app/.env
RUN yarn install --frozen-lockfile && yarn build

# Stage 2: Install Python Backend
FROM python:3.11-slim as backend
WORKDIR /app
COPY backend/ /app/
# Never bake a committed .env into the image; runtime env is injected at deploy.
RUN rm -f /app/.env
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Final Image
FROM nginx:stable-alpine
# Copy built frontend
COPY --from=frontend-build /app/build /usr/share/nginx/html
# Copy backend
COPY --from=backend /app /backend
# Copy nginx config
COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install Python and dependencies
RUN apk add --no-cache python3 py3-pip \
    && pip3 install --break-system-packages -r /backend/requirements.txt

# Add env variables if needed
ENV PYTHONUNBUFFERED=1

# Start both services: Uvicorn and Nginx
CMD ["/entrypoint.sh"]
