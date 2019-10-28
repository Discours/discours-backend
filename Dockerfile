FROM node:12.9-alpine as prod
RUN addgroup -S discoursUser \
    && adduser -S -g discoursUser discoursUser \
    && mkdir /app \
    && chown -R discoursUser:discoursUser /app
USER discoursUser
WORKDIR /app
COPY package.json package-lock.json /app/
RUN npm install
COPY src/ /app/src
COPY tsconfig.json /app/tsconfig.json

EXPOSE 4000
CMD npm start