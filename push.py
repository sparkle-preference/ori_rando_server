"""Hook from tick-cache busts to the websocket push layer.

Cache.clear_seen_checksum calls notify(gpid); ws.enable_push registers the handler.
Imports nothing, so anything can import it.
"""
import logging as log

_handler = None


def set_handler(handler):
    global _handler
    _handler = handler


def notify(gpid):
    if _handler is None:
        return
    try:
        _handler(gpid)
    except Exception:
        log.exception("push notify failed for %s", (gpid,))
