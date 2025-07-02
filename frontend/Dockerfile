# Multi-stage build for React frontend

# Build stage
FROM node:18-alpine AS build

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Clean npm cache and install dependencies
RUN npm cache clean --force && \
    rm -rf package-lock.json node_modules && \
    npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy custom nginx config
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html index.htm;

    # Handle React Router
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Plot files proxy to backend (must come before static assets)
    location /plots/ {
        proxy_pass http://backend:8000/plots/;
        
        # Headers for static content
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Cache plot images
        proxy_cache_valid 200 1h;
        add_header Cache-Control "public, max-age=3600";
    }

    # WebSocket proxy to backend (must come before generic /api to ensure upgrade headers)
    location /ws/ {
        proxy_pass http://backend:8000/ws/;

        # WebSocket specific headers
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";

        # Preserve client details
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_redirect off;
        proxy_buffering off;
    }

    # API proxy to backend
    location /api/ {
        proxy_pass http://backend:8000/api/;
        
        # Enhanced proxy headers to preserve original request context
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Handle redirects properly
        proxy_redirect off;
        proxy_buffering off;
    }

    # Static assets caching (but not for plots)
    location ~* \\.(js|css|ico|svg)\\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Static image assets (but not plots)
    location ~* ^/static/.*\\.(png|jpg|jpeg|gif)\\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Copy built app from build stage
COPY --from=build /app/build /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"] 