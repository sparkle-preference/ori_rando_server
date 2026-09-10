"""A real Archipelago room, hosted from the official container.

Everything the bridge is tested against elsewhere is a FakeSocket whose frames are our own
transcription of MultiServer.py. This is the other half: an actual 0.6.7 server, generated
from the apworld and the yamls **our site serves** rather than from anything the test
writes, so the artifacts a tester downloads are the artifacts under test.

No custom image and no local Archipelago install: the official one carries the whole source
tree, so overriding its WebHost entrypoint is the entire trick.
"""
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request

IMAGE = os.environ.get("AP_IMAGE", "ghcr.io/archipelagomw/archipelago:0.6.7")
ROOM_PORT = 38281


def docker_ok():
    """Docker answering AND the image present -- pulling 353 MB is not a test's job."""
    try:
        if subprocess.run(["docker", "version"], capture_output=True).returncode:
            return False
        got = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True)
        return got.returncode == 0
    except OSError:
        return False


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _fetch(url, timeout=120):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


class ApRoom(object):
    """Generate a multiworld from a rolled AP seed, then host it. `with` it."""

    def __init__(self, stack, param_id, name=None, port=None):
        self.base_url = stack.base_url
        self.param_id = param_id
        self.port = port or free_port()
        self.host = "127.0.0.1"
        self.name = name or "ap_room_%d" % self.port
        self.dir = tempfile.mkdtemp(prefix="aproom_")
        self.zip_name = None

    # -- container plumbing ---------------------------------------------------
    def _run(self, args, **kw):
        return subprocess.run(["docker"] + args, capture_output=True, text=True, **kw)

    def _mount(self, sub, dest):
        return ["-v", "%s:%s" % (os.path.join(self.dir, sub), dest)]

    def __enter__(self):
        players = os.path.join(self.dir, "Players")
        output = os.path.join(self.dir, "output")
        worlds = os.path.join(self.dir, "worlds")
        for d in (players, output, worlds):
            os.makedirs(d)

        # the artifacts a tester would download, from our own routes
        yamls = _fetch("%s/generator/apyamls/%s" % (self.base_url, self.param_id))
        with open(os.path.join(players, "ori.yaml"), "wb") as f:
            f.write(yamls)
        # the filename IS the module name Archipelago imports, so it must be oride.apworld
        with open(os.path.join(worlds, "oride.apworld"), "wb") as f:
            f.write(_fetch("%s/generator/apworld" % self.base_url))

        gen = self._run(["run", "--rm"]
                        + self._mount("worlds/oride.apworld", "/app/worlds/oride.apworld")
                        + self._mount("Players", "/app/Players")
                        + self._mount("output", "/app/output")
                        + ["--entrypoint", "python", IMAGE, "Generate.py"])
        if gen.returncode:
            raise RuntimeError("AP generation failed:\n%s\n%s"
                               % (gen.stdout[-2000:], gen.stderr[-2000:]))
        zips = [f for f in os.listdir(output) if f.startswith("AP_") and f.endswith(".zip")]
        if not zips:
            raise RuntimeError("generation made no multidata:\n%s" % gen.stdout[-2000:])
        self.zip_name = zips[0]

        up = self._run(["run", "-d", "--name", self.name, "-p", "%d:%d" % (self.port, ROOM_PORT)]
                       + self._mount("output", "/app/output")
                       + ["--entrypoint", "python", IMAGE, "MultiServer.py",
                          # the default bind is unreachable through a published port
                          "--host", "0.0.0.0", "--port", str(ROOM_PORT),
                          "--disable_save", "/app/output/%s" % self.zip_name])
        if up.returncode:
            raise RuntimeError("could not host the room: %s" % up.stderr[-2000:])
        self._await_port()
        return self

    def __exit__(self, *exc):
        self._run(["rm", "-f", self.name])
        shutil.rmtree(self.dir, ignore_errors=True)

    def _await_port(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                socket.create_connection((self.host, self.port), timeout=2).close()
                return
            except OSError:
                time.sleep(0.5)
        raise RuntimeError("the room never listened on %s:\n%s" % (self.port, self.logs()))

    # -- what a scenario asks it ---------------------------------------------
    def logs(self):
        return self._run(["logs", self.name]).stdout + self._run(["logs", self.name]).stderr

    def wait_for(self, needle, timeout=30):
        """The room narrates joins, checks and goals to its log; that is the only view of
        it that does not require speaking the protocol a second time."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if needle in self.logs():
                return True
            time.sleep(0.5)
        return False

    def joined_slots(self):
        return sorted({line.split(" (Team")[0].split("Notice (all): ")[1]
                       for line in self.logs().splitlines()
                       if "Notice (all): " in line and " has joined." in line})
