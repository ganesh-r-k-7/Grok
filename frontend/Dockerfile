FROM node:20-alpine

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

# Use existing node user (UID 1000) and create app group
RUN addgroup -g 1001 -S nodejs

COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .

# Change ownership to node user (UID 1000)
RUN chown -R node:nodejs /app

USER node

EXPOSE 3000

CMD ["npm", "run", "dev"]