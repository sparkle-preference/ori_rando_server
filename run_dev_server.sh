if [ ! -f "map/dist/index.html" -o "${FORCE_BUILD_REACT_APP}" -eq "1"]; then
    cd map
    npm run build
    cd ../
fi


if [ -z "${GCLOUD_CLI_ROOT}" ]; then
    GCLOUD_CLI_ROOT="$(gcloud info --format="value(installation.sdk_root)")"
fi

if [ -z "${CLOUDSDK_PYTHON}" ]; then
    which pyenv > /dev/null 2>&1
    if [ $? -eq 0 ]; then 
        CLOUDSDK_PYTHON="$(PYENV_VERSION=3.12 pyenv which python)"
    else
        #pyenv not found.
        CLOUDSDK_PYTHON="$(which python3)"
    fi
fi

${CLOUDSDK_PYTHON} "$GCLOUD_CLI_ROOT/bin/dev_appserver.py" app.yaml --port "${APP_PORT:-"8080"}" --host "${APP_HOST:-"127.0.0.1"}" --enable_host_checking=false
