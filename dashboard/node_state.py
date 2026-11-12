"""Collect everything the page shows for one node."""
from key_view import KeyView
from node_log import NodeLog
from node_rpc import NodeRpc


class NodeState:
    HASHES_PER_DIFFICULTY_1 = 2 ** 32       # average tries per block at difficulty 1
    MATURITY_BLOCKS = 6                     # = Consensus.COINBASE_MATURITY + WALLET_MATURITY_MARGIN in tools/make_patch.py
    RECENT_TX = 20
    DEFAULT_ACCOUNT = ""

    def __init__(self, node: str):
        self.rpc = NodeRpc(node)
        self.log = NodeLog(self.rpc)
        self._key = None                    # receiving key never changes: cache it

    def _key_info(self) -> dict:
        if self._key is None:
            address = self.rpc.call("getaccountaddress", self.DEFAULT_ACCOUNT)
            wif = self.rpc.call("dumpprivkey", address)
            self._key = KeyView(address, wif).as_dict()
        return self._key

    def _expected_seconds(self, info: dict):
        rate = info.get("hashespersec", 0)
        if not info.get("generate") or rate <= 0:
            return None
        return self.HASHES_PER_DIFFICULTY_1 * info["difficulty"] / rate

    def snapshot(self) -> dict:
        state = {"node": self.rpc.node, "running": self.rpc.is_running()}
        if not state["running"]:
            return state
        try:
            info = self.rpc.call("getinfo")
            txs = self.rpc.call("listtransactions", "*", self.RECENT_TX)
        except RuntimeError as err:         # node still starting up
            state["error"] = str(err)
            return state
        immature_txs = [t for t in txs if t.get("category") == "immature"]
        immature = sum(t["amount"] for t in immature_txs)
        expected = self._expected_seconds(info)
        spendable_in_s = None
        if immature_txs and expected:
            blocks_left = self.MATURITY_BLOCKS - max(t["confirmations"] for t in immature_txs)
            spendable_in_s = max(0, blocks_left) * expected
        state.update({
            "blocks": info["blocks"],
            "mining_block": info["blocks"] + 1,
            "difficulty": info["difficulty"],
            "generate": info["generate"],
            "cores": info.get("genproclimit"),
            "khash_per_s": round(info.get("hashespersec", 0) / 1000),
            "expected_block_s": expected,
            "peers": info["connections"],
            "balance": info["balance"],
            "immature": immature,
            "maturity_blocks": self.MATURITY_BLOCKS,
            "spendable_in_s": spendable_in_s,
            "key": self._key_info(),
            "transactions": list(reversed(txs)),
            "recent_blocks": self.log.recent_blocks(),
        })
        return state
