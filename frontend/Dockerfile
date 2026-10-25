FROM node:22-alpine
ARG APP_VERSION=dev
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ENV VITE_APP_VERSION=${APP_VERSION}

# A62: dev-сервер тоже не под root — образ node:alpine уже содержит пользователя
# node (uid 1000), нужно лишь отдать ему каталог с зависимостями и кэшем Vite.
RUN chown -R node:node /app
USER node

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
