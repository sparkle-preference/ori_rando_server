"""Decoupling hub between game-state code and the websocket push layer.

models/cache call notify(gpid) at the moments a player's next tick output
is known to have changed (in practice: every tick-cache checksum bust).
If the websocket layer has push enabled it registers a handler that sends
that player a fresh tick frame immediately; with no handler registered
this is a no-op. This module imports nothing so anything can import it.
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
