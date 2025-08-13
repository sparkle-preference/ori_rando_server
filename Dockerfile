FROM node:24-slim AS parcel

WORKDIR /app
COPY ./map ./

RUN npm ci && npm run build 


FROM python:3.12-slim

WORKDIR /app

ENV OIDC_CLIENT_SECRETS="./app_secrets/client_secret.json"

COPY ./requirements.txt ./requirements.txt

RUN pip install -r requirements.txt && rm requirements.txt

COPY --from=parcel /app/dist ./map/dist
COPY ./seedbuilder/areas.ori ./seedbuilder/areas.ori
COPY ./seedbuilder/*.py ./seedbuilder

COPY *.py ./

CMD exec gunicorn --bind :$PORT --workers 1 --preload --threads 8 --timeout 0 main:app

