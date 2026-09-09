# PenPaw Web 前端（build → nginx）
FROM node:22-alpine AS build

RUN corepack enable

WORKDIR /repo
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile || pnpm install

COPY apps/web/ apps/web/
RUN pnpm --filter @penpaw/web build

FROM nginx:alpine
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html
EXPOSE 80
