if [ ! -e /tmp/pipcache ] || cmp -s "requirements.txt" "/tml/pipcache"; then
    cp requirements.txt /tmp/pipcache
    pip install -r requirements.txt
fi

python -m flask --debug --app main run --host="0.0.0.0"
