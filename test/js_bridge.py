"""Calls map/src JS from Python through one long-lived node (needs node on PATH and map/node_modules)."""
import atexit
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
_proc = None


class JsError(Exception):
    pass


def _xhr_bodies():
    """What map/src fetches synchronously at import, served by the real routes."""
    from flask import Flask
    from web import meta
    with Flask(__name__).app_context():
        return {"/pickupandlocinfo": meta.picks_by_type().get_data(as_text=True)}


def _send(msg):
    _proc.stdin.write(json.dumps(msg) + "\n")
    _proc.stdin.flush()
    line = _proc.stdout.readline()
    if not line:
        raise JsError("the node bridge exited")
    out = json.loads(line)
    if "err" in out:
        raise JsError(out["err"])
    return out["ok"]


def _stop(proc):
    proc.kill()
    proc.communicate()


def call(mod, fn, *args):
    """mod.fn(*args), JSON in and out; a binding that isn't a function comes back as its value."""
    global _proc
    if _proc is None or _proc.poll() is not None:
        _proc = subprocess.Popen(["node", "--no-warnings", "--import", "./jsx_loader.mjs", "js_bridge.mjs"], cwd=HERE,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        atexit.register(_stop, _proc)
        _send({"xhr": _xhr_bodies()})
    return _send({"mod": mod, "fn": fn, "args": list(args)})
