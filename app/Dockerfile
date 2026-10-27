# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@10.12.4 --activate
COPY package.json pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN SKIP_ENV_VALIDATION=1 pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080
RUN corepack enable && corepack prepare pnpm@10.12.4 --activate
# Migration and seed tools are included so this review image initializes itself.
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/src ./src
COPY --from=build /app/scripts ./scripts
COPY --from=build /app/patients ./patients
COPY --from=build /app/templates ./templates
COPY --from=build /app/drizzle-postgres ./drizzle-postgres
COPY --from=build /app/package.json /app/pnpm-lock.yaml /app/.npmrc /app/next.config.js /app/tsconfig.json /app/drizzle.config.ts ./
EXPOSE 8080
CMD ["pnpm", "start"]
