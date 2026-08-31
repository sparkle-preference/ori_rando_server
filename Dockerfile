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

# archipelago: netcode imports ap_bridge unconditionally, and ap_bridge +
# convert read oride_apworld/oride/data/*.json AT IMPORT TIME — so both the
# modules and that data dir must ship or the app dies before serving (a
# missing COPY here failed 4.2.6's health check). The whole oride package
# ships too: /generator/apworld zips it live, docs and manifest included.
# difftest/ is dev-only.
COPY ./archipelago/*.py ./archipelago/
COPY ./archipelago/oride_apworld/ ./archipelago/oride_apworld/

# the patch notes feeds (/patchnotes.json, /patchnotes.xml) read this file at
# request time. Parcel already bundles a copy into the page from the build
# stage above; this is the runtime copy. main.py loads it lazily, so a missing
# COPY here breaks only those two routes rather than killing the container.
COPY ./map/src/patchnotes.json ./map/src/patchnotes.json

# main imports web.responses at module scope, so a missing COPY here kills the
# container rather than one route.
COPY ./web/*.py ./web/

COPY *.py ./

# --threads sizes BOTH http concurrency and the websocket connection budget:
# every open socket pins one thread for its lifetime (see ws.py). Keep
# util.WS_CONN_LIMIT comfortably below this so http always has headroom.
CMD exec gunicorn --bind :$PORT --workers 1 --preload --threads 64 --timeout 0 main:app

