"""The scenario stack: the datastore_test emulator plus a flask this module owns."""
import os
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(REPO, ".venv312", "Scripts", "python.exe")
EMULATOR = os.environ.get("DATASTORE_TEST_EMULATOR_HOST", "localhost:8001")
PORT = int(os.environ.get("MOCKCLIENT_PORT", "8095"))


def _emulator_up():
    try:
        with urllib.request.urlopen("http://%s/" % EMULATOR, timeout=2):
            return True
    except OSError:
        return False


class LocalStack(object):
    """Starts flask against the test emulator; reset() wipes the datastore."""

    def __init__(self, port=PORT, log_path=None, env=None):
        self.port = port
        self.base_url = "http://127.0.0.1:%d" % port
        self.ws_base = "ws://127.0.0.1:%d" % port
        self.log_path = log_path or os.path.join(REPO, "mockclient",
                                                 "flask_scenario_%d.log" % port)
        self.env_extra = env or {}
        self.proc = None
        self._log = None

    def __enter__(self):
        if not _emulator_up():
            subprocess.run(["docker", "compose", "up", "-d", "datastore_test"],
                           cwd=REPO, capture_output=True)
            deadline = time.time() + 60
            while not _emulator_up():
                if time.time() > deadline:
                    raise RuntimeError("datastore_test emulator never answered on %s "
                                       "(is Docker Desktop running?)" % EMULATOR)
                time.sleep(1)
        env = dict(os.environ)
        env.update({
            "DATASTORE_EMULATOR_HOST": EMULATOR,
            "DATASTORE_PROJECT_ID": "orirandov3",
            "GOOGLE_CLOUD_PROJECT": "orirandov3",
            "OIDC_ENABLED": "False",
            "ARCHIPELAGO": "1",
            "APP_SECRET_KEY": "scenario-secret",
            "K_REVISION": "dev",
        })
        env.pop("MEMCACHED_HOST", None)
        env.update(self.env_extra)
        self._log = open(self.log_path, "w")
        self.proc = subprocess.Popen(
            [PYTHON, "-u", "-m", "flask", "--app", "main", "run", "--port", str(self.port)],
            cwd=REPO, env=env, stdout=self._log, stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + 90
        while True:
            try:
                with urllib.request.urlopen(self.base_url + "/quickstart", timeout=3):
                    break
            except OSError:
                if self.proc.poll() is not None:
                    raise RuntimeError("flask exited on boot; see " + self.log_path)
                if time.time() > deadline:
                    raise RuntimeError("flask never answered; see " + self.log_path)
                time.sleep(1)
        return self

    def reset(self):
        req = urllib.request.Request("http://%s/reset" % EMULATOR, method="POST")
        with urllib.request.urlopen(req, timeout=10):
            pass

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self._log:
            self._log.close()


if __name__ == "__main__":
    with LocalStack() as stack:
        print("stack up at", stack.base_url, "- ctrl+c to stop")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
