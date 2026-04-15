FROM node:20-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./

# --ignore-scripts avoids spawn sh EACCES on Proxmox Docker
RUN npm install --legacy-peer-deps --ignore-scripts && \
    npm rebuild esbuild 2>/dev/null || true

COPY . .

# Build with network isolation workaround for Proxmox Docker
ENV VITE_API_BASE=/api
RUN npx vite build 2>&1 || npx vite build --mode production

FROM nginx:1.25-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
