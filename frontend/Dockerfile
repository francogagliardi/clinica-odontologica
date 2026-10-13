# ---- build stage: compile the SPA ----
FROM node:20-alpine AS build
# Public API base baked at build time (not a secret; keeps .env out of the image, R-08)
ARG VITE_API_BASE_URL=http://127.0.0.1:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json ./
COPY src/ ./src/
RUN npm run build

# ---- production stage: non-root nginx serving dist/ (R-08) ----
FROM nginx:1.27-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
RUN touch /var/run/nginx.pid \
    && chown -R nginx:nginx /var/cache/nginx /var/run/nginx.pid \
       /var/log/nginx /usr/share/nginx/html /etc/nginx/conf.d
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/ > /dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
