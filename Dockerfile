FROM node:24-slim AS parcel

WORKDIR /app
COPY ./map ./

RUN npm ci && npm run build 


FROM python:3.12-slim

WORKDIR /app

COPY ./requirements.txt ./requirements.txt

RUN pip install --root-user-action ignore -r requirements.txt && rm requirements.txt

COPY --from=parcel /app/dist ./map/dist
COPY ./seedbuilder/areas.ori ./seedbuilder/areas.ori
COPY ./seedbuilder/*.py ./seedbuilder/

COPY *.py ./

# --threads sizes BOTH http concurrency and the websocket connection budget:
# every open socket pins one thread for its lifetime (see ws.py). Keep
# util.WS_CONN_LIMIT comfortably below this so http always has headroom.
CMD exec gunicorn --bind :$PORT --workers 1 --preload --threads 64 --timeout 0 main:app

