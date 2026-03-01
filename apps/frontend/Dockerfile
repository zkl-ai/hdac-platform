FROM node:20-slim AS builder

WORKDIR /app
# Enable pnpm
RUN corepack enable && corepack prepare pnpm@10.22.0 --activate

COPY . .

# Install dependencies
RUN pnpm install

# Build the application
# We use the filter to build only the web-antd app
RUN pnpm run build:antd

# Production stage
FROM nginx:alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the build artifacts from the builder stage
# Verify the output directory, usually apps/web-antd/dist
COPY --from=builder /app/apps/web-antd/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
