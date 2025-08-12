if [ ! -e /tmp/started ]; then
    touch /tmp/started
    rm node_modules/.package_lock.json
    npm i
fi

npm run watch
