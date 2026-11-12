"""Talk to one bitcoind via 'docker compose exec' (the network has no host route)."""
import json
import pathlib
import subprocess


class NodeRpc:
    PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
    BITCOIND_ARGS = ["bitcoind", "-datadir=/data", "-conf=/etc/bitcoin/bitcoin.conf"]
    TIMEOUT_S = 15

    def __init__(self, node: str):
        self.node = node

    def _run(self, args: list) -> subprocess.CompletedProcess:
        return subprocess.run(["docker", "compose", *args], cwd=self.PROJECT_DIR,
                              capture_output=True, text=True, timeout=self.TIMEOUT_S)

    def is_running(self) -> bool:
        out = self._run(["ps", "--status", "running", "--services"]).stdout.split()
        return self.node in out

    def call(self, *params):
        """Return parsed JSON, or the plain string the 2011 client prints."""
        res = self._run(["exec", "-T", self.node, *self.BITCOIND_ARGS, *map(str, params)])
        if res.returncode != 0:
            raise RuntimeError((res.stderr or res.stdout).strip())
        text = res.stdout.strip()
        try:
            return json.loads(text)
        except ValueError:
            return text

    def logs(self, tail: int) -> list:
        res = self._run(["logs", "--no-log-prefix", "--tail", str(tail), self.node])
        return res.stdout.splitlines()
