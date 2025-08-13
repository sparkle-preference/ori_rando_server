if [ ! -e /tmp/started ]; then
    touch /tmp/started
    rm node_modules/.package_lock.json
    npm i
fi
if [ "${NO_WATCH_REACT_APP:-"0"}" == "1" ]; then
    npm run build
else
    npm run watch
fi
