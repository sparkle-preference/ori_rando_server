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

# ap_bridge reads oride_apworld data at import and /generator/apworld zips the
# whole package, so both ship or the app dies at boot; difftest/ is dev-only
COPY ./archipelago/*.py ./archipelago/
COPY ./archipelago/oride_apworld/ ./archipelago/oride_apworld/

# the runtime copy the patch-note feeds read; missing, only those two routes break
COPY ./map/src/patchnotes.json ./map/src/patchnotes.json

# main imports web.responses at module scope, so a missing COPY here kills the
# container rather than one route.
COPY ./web/*.py ./web/

COPY *.py ./

# --threads is both http concurrency and the socket budget (a socket pins a thread);
# keep util.WS_CONN_LIMIT well below it
CMD exec gunicorn --bind :$PORT --workers 1 --preload --threads 64 --timeout 0 main:app

