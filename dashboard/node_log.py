"""Read block events from the bitcoind console log.

v0.3.24 has no getblock RPC, so block hashes come from these log lines:
  proof-of-work found
    hash: 0000000086ea...           (full hash, only on the node that mined it)
  SetBestChain: new best=0000000086ea3381e6f4  height=1  work=8590065666
  LoadBlockIndex(): hashBestChain=0000000086ea3381e6f4  height=0   (at start-up)
"""
import re


class NodeLog:
    TAIL_LINES = 5000
    MAX_BLOCKS = 10
    # new tip while running, or the tip loaded from disk at start-up
    RE_BEST = re.compile(r"(?:SetBestChain: new best|LoadBlockIndex\(\): hashBestChain)=([0-9a-f]+)\s+height=(\d+)")
    RE_FOUND = re.compile(r"^\s*hash: ([0-9a-f]{64})")

    def __init__(self, rpc):
        self.rpc = rpc

    def recent_blocks(self) -> list:
        """Newest first: [{height, hash, mined_here}]."""
        found = []                      # full hashes this node mined
        blocks = {}
        for line in self.rpc.logs(self.TAIL_LINES):
            m = self.RE_FOUND.match(line)
            if m:
                found.append(m.group(1))
                continue
            m = self.RE_BEST.search(line)
            if m:
                short, height = m.group(1), int(m.group(2))
                full = next((h for h in found if h.startswith(short)), None)
                blocks[height] = {"height": height, "hash": full or short + "…",
                                  "mined_here": full is not None}
        newest = sorted(blocks.values(), key=lambda b: b["height"], reverse=True)
        return newest[:self.MAX_BLOCKS]
