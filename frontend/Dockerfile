FROM nginx:1.25-alpine

# Frontend is built on the host (npm install && npx vite build)
# The dist/ directory is mounted or copied at deploy time
COPY dist/ /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
