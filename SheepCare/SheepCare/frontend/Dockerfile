# Build stage
FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx config for SPA + API proxy + Farm Calendar proxy
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # API proxy (must be before SPA fallback)
    location /api/ {
        client_max_body_size 50M;
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Farm Calendar proxy - static files
    location /static/ {
        proxy_pass http://farmcalendar:8002;
        proxy_set_header Host $host;
    }

    # Farm Calendar proxy - API
    location /api/v1/ {
        proxy_pass http://farmcalendar:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Farm Calendar proxy - login, admin, and all other paths
    location = /calendar {
        return 301 /calendar/;
    }

    location /login/ {
        proxy_pass http://farmcalendar:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_hide_header X-Frame-Options;
        proxy_redirect off;
    }

    location /admin/ {
        proxy_pass http://farmcalendar:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_hide_header X-Frame-Options;
        proxy_redirect off;
    }

    # Farm Calendar proxy - main calendar page
    location /calendar/ {
        proxy_pass http://farmcalendar:8002/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_hide_header X-Frame-Options;
        proxy_redirect http://farmcalendar:8002/ /calendar/;
        proxy_redirect http://farmcalendar:8002 /calendar/;
        proxy_cookie_path / /;
    }

    # Farm Calendar proxy - any other Farm Calendar paths
    location /favicon.ico {
        proxy_pass http://farmcalendar:8002;
    }

    # SPA fallback (last)
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
