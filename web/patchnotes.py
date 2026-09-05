"""The patch notes page, its two feeds, and the Discord announcer.

map/src/patchnotes.json is the single source: the frontend bundles it and the
feeds read it at request time, so neither can drift from the other.
"""
import json
import logging as log
import os
import re
from html import escape

import requests
from flask import Blueprint, make_response, redirect, render_template, request

import util
from models import AnnouncedPatchNotes, User
from util import (INDEX_TEMPLATE, VERSION, display_version, param_flag, param_val,
                  template_vals)
from web.responses import text_resp

bp = Blueprint("patchnotes", __name__)


@bp.route('/patchnotes') #  PatchNotes
def patchnotes():
    template_values = template_vals("PatchNotes", "Patch Notes", User.get())
    return render_template(INDEX_TEMPLATE, **template_values)

# the old per-line doc links are anchors on the one page now
PATCHNOTE_ALIASES = {"3.x": "3.0", "4.0.x": "4.0.0", "4.1.x": "4.1.0"}


@bp.route('/patchnotes/<version>')
def patchnotes_version(version):
    # "all" is not a release: it is the page with the minor entries unfolded
    if version == "all":
        return redirect("/patchnotes?all=1")
    return redirect("/patchnotes#%s" % PATCHNOTE_ALIASES.get(version, version))


# Atom ids are permanent identities rather than locations, so they must not move
# when the site is served from another host (bf.orirando.com, localhost, ...).
FEED_TAG_HOST = "orirando.com"

# map/src/patchnotes.json is what the frontend bundles, so the feeds can never
# drift from the page. Loaded lazily and cached: if the file ever fails to ship,
# only these two routes break instead of the whole app failing to import.
_patchnotes_cache = None


class PatchnotesMissing(Exception):
    pass


def patchnotes_doc():
    global _patchnotes_cache
    if _patchnotes_cache is None:
        src = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'map/src/patchnotes.json')
        try:
            with open(src, encoding='utf-8') as f:
                _patchnotes_cache = json.load(f)
        except FileNotFoundError:
            # says what to fix instead of a bare 500 six months from now
            raise PatchnotesMissing(
                "patchnotes.json is not in the image; check its COPY line in the Dockerfile")
    return _patchnotes_cache


# A note writes a link as [label](url), the same markdown discord speaks.
# PatchNotes.js renders the same syntax on the page.
LINK_RE = re.compile(r"\[([^\]\[]+)\]\(([^)\s]+)\)")


def link_href(href, base):
    """A feed is read off-site, so a site-rooted href needs the host on it.
    Anything that is not http(s) or site-rooted is not a link."""
    if href.startswith(("http://", "https://")):
        return href
    return base + href if href.startswith("/") else None


def markdown_links(text, base):
    """Links as discord's own markdown, hrefs made absolute."""
    def one(m):
        href = link_href(m.group(2), base)
        return "[%s](%s)" % (m.group(1), href) if href else m.group(1)
    return LINK_RE.sub(one, text)


def html_links(text, base):
    """Links as anchors. Runs on already-escaped text: an & inside an href is
    &amp; there too, which is what an HTML attribute wants."""
    def one(m):
        href = link_href(m.group(2), base)
        return '<a href="%s">%s</a>' % (href, m.group(1)) if href else m.group(1)
    return LINK_RE.sub(one, text)


def version_tuple(v):
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return ()


def latest_note_version():
    """The newest release in the notes: VER, plus a fourth number when the site
    shipped alone. Falls back to VERSION, so a missing file 503s only its own routes."""
    try:
        releases = patchnotes_doc()["releases"]
    except PatchnotesMissing:
        return VERSION
    return releases[0]["version"] if releases else VERSION


@bp.route('/patchnotes.json')
def patchnotes_json():
    """The notes as data. ?since=4.2.9 returns only releases newer than that,
    which is what a bot wants when it last announced 4.2.9. ?highlights=1 drops
    the minor changes, matching the page's default view."""
    try:
        doc = patchnotes_doc()
    except PatchnotesMissing as e:
        return text_resp(str(e), 503)
    releases = doc["releases"]

    since = param_val("since")
    if since:
        cutoff = version_tuple(since)
        if not cutoff:
            return text_resp("bad since= version: %s" % since, 400)
        releases = [r for r in releases if version_tuple(r["version"]) > cutoff]

    if param_flag("highlights"):
        releases = [dict(r, changes=[c for c in r["changes"] if c["importance"] == "major"])
                    for r in releases]

    # the newest note, not the dll version: it's what a caller passes back as since=
    body = json.dumps({"categories": doc["categories"], "current": latest_note_version(), "releases": releases})
    resp = make_response(body)
    resp.headers["Content-Type"] = "application/json"
    return resp


# "all" (the default when a release says nothing) reaches both channels, "dev"
# only the dev one, "none" neither.
ANNOUNCE_CHANNELS = {
    "main": lambda a: a == "all",
    "dev": lambda a: a in ("all", "dev"),
}


def announce_webhook(channel):
    return {"main": util.PATCHNOTES_WEBHOOK_MAIN, "dev": util.PATCHNOTES_WEBHOOK_DEV}[channel]


def site_only_note(version):
    """The aside a site-only release carries, or None for an ordinary one.
    Mirrored in PatchNotes.js, which renders the same line on the page."""
    parts = version.split(".")
    if len(parts) <= 3:
        return None
    return "(this is a site-only update. %s is still the latest dll)" % ".".join(parts[:3])


# A note's links outlive the request that posted them, so they may not carry the
# host that happened to trigger the announce.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1")


def announce_base():
    """Where a patch note should point people. CANONICAL_HOST is often unset,
    so the host the request arrived on is the fallback."""
    if util.CANONICAL_HOST:
        return "https://%s" % util.CANONICAL_HOST
    return request.host_url.rstrip("/")


def is_public(base):
    """A health check or a local probe arrives on a host nobody else can reach."""
    host = base.split("://", 1)[-1].split("/")[0].rsplit(":", 1)[0]
    return host not in LOCAL_HOSTS and not host.endswith(".local")

def announce_embed(release, base, everything=False):
    # the dev channel takes the whole list: it is the audience that wants the
    # minor entries, and a dev-only release is often all minor
    shown = [c for c in release["changes"] if everything or c["importance"] == "major"]
    lines = []
    note = site_only_note(release["version"])
    if note:
        lines.append("-# *%s*" % note)  # -# is discord's subtext
    if release.get("headline"):
        lines.append(markdown_links(release["headline"], base))
    for c in shown:
        lines.append("- %s" % markdown_links(c["text"], base))
        for s in c.get("sub", []):
            lines.append("  - %s" % markdown_links(s, base))
    if not shown and not release.get("headline"):
        lines.append("Small fixes only - see the full notes.")
    title = "%s%s" % (display_version(release["version"]),
                      " - %s" % release["title"] if release.get("title") else "")
    # discord truncates a description past 4096 rather than rejecting it, but
    # cutting it here keeps the "read the rest" link meaningful
    body = "\n".join(lines)
    if len(body) > 3900:
        body = body[:3900].rsplit("\n", 1)[0] + "\n- ..."
    return {"title": title, "url": "%s/patchnotes#%s" % (base, release["version"]), "description": body}


def announce_patchnotes(base, force=False, channels=None):
    """Post any releases newer than each channel's marker. Returns a per-channel
    summary. Inert unless a webhook is configured for that channel.

    channels limits which channels are considered; None means all of them, so
    catching one channel up cannot repost to a channel that has already seen it."""
    doc = patchnotes_doc()
    releases = doc["releases"]
    if not releases:
        return {}
    newest = releases[0]["version"]
    out = {}

    for channel, wants in ANNOUNCE_CHANNELS.items():
        if channels is not None and channel not in channels:
            continue
        hook = announce_webhook(channel)
        if not hook:
            # worth saying only when the caller named this channel; the boot
            # path runs on every deploy and would just be noise
            if channels is not None:
                out[channel] = "no webhook configured"
            continue
        was = AnnouncedPatchNotes.claim(channel, newest)
        if was is None:
            # marker already current (or just seeded); force resends the newest
            # only -- never the whole back catalogue
            if not force:
                out[channel] = "nothing new"
                continue
            pending = releases[:1]
        else:
            cutoff = version_tuple(was)
            pending = [r for r in releases if version_tuple(r["version"]) > cutoff]
        pending = [r for r in pending if wants(r.get("announce", "all"))]
        if not pending:
            out[channel] = "nothing for this channel"
            continue
        # oldest first so the channel reads chronologically, 10 embeds per message
        embeds = [announce_embed(r, base, everything=(channel == "dev"))
                  for r in reversed(pending)][-10:]
        try:
            resp = requests.post(hook, json={"embeds": embeds}, timeout=10)
            resp.raise_for_status()
            out[channel] = "posted %s" % ", ".join(r["version"] for r in reversed(pending))
            log.info("patchnotes: announced %s to %s", [r["version"] for r in pending], channel)
        except Exception as e:
            # the marker already moved, so this release will not retry by itself
            out[channel] = "FAILED: %s" % e
            log.error("patchnotes: %s announce POST failed for %s: %s",
                      channel, [r["version"] for r in pending], e)
    return out


_announce_checked = False


@bp.before_app_request
def announce_on_first_request():
    """Runs once per process. A deploy restarts the process, which is the only
    thing that can change VERSION, so this fires exactly once per release."""
    global _announce_checked
    if _announce_checked or not (util.PATCHNOTES_WEBHOOK_MAIN or util.PATCHNOTES_WEBHOOK_DEV):
        return
    # never make a game wait on Discord: the webhook POST is synchronous, so
    # let a browser request be the one that pays for it
    if request.path.startswith("/netcode/"):
        return
    # a health check's host would put localhost in front of a whole channel, and
    # the flag below makes that permanent for the process. Leave it for a request
    # that arrived somewhere people can actually reach.
    base = announce_base()
    if not is_public(base):
        return
    _announce_checked = True  # set first: a failure must not retry every request
    try:
        announce_patchnotes(base)
    except Exception:
        log.exception("patchnotes: announce check failed")


@bp.route('/patchnotes/announce')
def patchnotes_announce():
    """Manual resend, for when a POST failed and the marker already moved.
    ?force=1 reposts the newest release even if the marker is current.
    ?channel=main|dev|all picks which channels to post to (default all)."""
    if not User.is_admin():
        return text_resp("admins only", 401)
    if not (util.PATCHNOTES_WEBHOOK_MAIN or util.PATCHNOTES_WEBHOOK_DEV):
        return text_resp("no PATCHNOTES_WEBHOOK_MAIN or PATCHNOTES_WEBHOOK_DEV set", 503)
    channel = (param_val("channel") or "all").lower()
    if channel != "all" and channel not in ANNOUNCE_CHANNELS:
        return text_resp("channel must be all, %s" % ", ".join(ANNOUNCE_CHANNELS), 400)
    try:
        result = announce_patchnotes(announce_base(), force=param_flag("force"),
                                     channels=None if channel == "all" else {channel})
    except PatchnotesMissing as e:
        return text_resp(str(e), 503)
    return text_resp(json.dumps(result, indent=2))


@bp.route('/patchnotes.xml')
def patchnotes_feed():
    """Atom feed of the highlights, newest first -- for feed readers and the
    Discord bots that can consume one without anybody writing a poster."""
    try:
        doc = patchnotes_doc()
    except PatchnotesMissing as e:
        return text_resp(str(e), 503)
    base = announce_base()
    releases = doc["releases"][:25]

    def entry(r):
        major = [c for c in r["changes"] if c["importance"] == "major"]
        rich = lambda s: html_links(escape(s), base)
        items = "".join(
            "<li>%s%s</li>" % (
                rich(c["text"]),
                "<ul>%s</ul>" % "".join("<li>%s</li>" % rich(s) for s in c["sub"]) if c.get("sub") else "")
            for c in major)
        summary = "<p>%s</p>" % rich(r["headline"]) if r.get("headline") else ""
        content = "%s<ul>%s</ul>" % (summary, items) if items else (summary or "<p>Small fixes only.</p>")
        title = "%s%s" % (display_version(r["version"]),
                          " - %s" % r["title"] if r.get("title") else "")
        url = "%s/patchnotes#%s" % (base, r["version"])
        return (
            "<entry>"
            "<title>%s</title>"
            "<id>tag:%s,%s:patchnotes/%s</id>"  # stable identity, not a location
            "<link href=\"%s\"/>"
            "<updated>%sT00:00:00Z</updated>"
            "<content type=\"html\">%s</content>"
            "</entry>"
        ) % (escape(title), FEED_TAG_HOST, r["date"], r["version"], url, r["date"], escape(content))

    feed = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
        "<feed xmlns=\"http://www.w3.org/2005/Atom\">"
        "<title>Ori DE Randomizer patch notes</title>"
        "<id>%s/patchnotes.xml</id>"
        "<link href=\"%s/patchnotes\"/>"
        "<link rel=\"self\" href=\"%s/patchnotes.xml\"/>"
        "<updated>%sT00:00:00Z</updated>"
        "%s</feed>"
    ) % (base, base, base, releases[0]["date"] if releases else "1970-01-01",
         "".join(entry(r) for r in releases))

    resp = make_response(feed)
    resp.headers["Content-Type"] = "application/atom+xml; charset=utf-8"
    return resp
