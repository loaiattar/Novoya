# Development image: runs the Vite dev server. A production image comes with deployment.
FROM node:22-slim

# The node user has uid 1000, so files the dev server generates in the mounted
# source tree belong to a normal Linux user, not root.
ENV COREPACK_HOME=/opt/corepack
RUN corepack enable && mkdir -p /app /opt/corepack && chown node:node /app /opt/corepack
USER node
WORKDIR /app

COPY --chown=node:node package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY --chown=node:node . .

EXPOSE 5173
CMD ["pnpm", "dev"]
