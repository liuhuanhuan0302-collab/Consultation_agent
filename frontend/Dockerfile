FROM node:20-alpine AS diagnosis-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ARG VITE_APP_BASE_PATH=/diagnosis/
ENV VITE_APP_BASE_PATH=$VITE_APP_BASE_PATH
RUN npm run build

FROM node:20-alpine AS official-website-builder
WORKDIR /app
COPY official-website/package*.json ./
RUN npm ci
COPY official-website/ .
ARG VITE_DIAGNOSIS_URL=/diagnosis/?source=OFFICIAL_WEBSITE
ENV VITE_DIAGNOSIS_URL=$VITE_DIAGNOSIS_URL
RUN npm run build

FROM caddy:2-alpine
COPY --from=diagnosis-builder /app/dist /srv/diagnosis
COPY --from=official-website-builder /app/dist /srv/official
COPY frontend/Caddyfile /etc/caddy/Caddyfile
EXPOSE 80 443
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
