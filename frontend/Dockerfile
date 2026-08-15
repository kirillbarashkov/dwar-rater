FROM node:22-alpine
ARG APP_VERSION=dev
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ENV VITE_APP_VERSION=${APP_VERSION}

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
