if [ "${NO_BUILD_REACT_APP}" != "1" ]; then
    cd map
    if [ "${NO_WATCH_REACT_APP}" == "1" ]; then
        npm run build
    else
        # Parcel is almost always faster than appengine
        npm run watch &
    fi
    cd ../
fi

if [ -z "${GCLOUD_CLI_ROOT}" ]; then
    GCLOUD_CLI_ROOT="$(gcloud info --format="value(installation.sdk_root)")"
fi

if [ -z "${GOOGLE_CLOUD_PROJECT}" ]; then
    GOOGLE_CLOUD_PROJECT="$(gcloud config get project)"
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
