#!/usr/bin/env python3
"""Mine a genesis block exactly like Bitcoin v0.3.24 builds it in main.cpp.

Usage:
  python3 tools/mine_genesis.py --selftest          # check against the 2009 block
  python3 tools/mine_genesis.py "headline" <nTime>  # mine a new genesis
"""
import hashlib
import multiprocessing
import struct
import sys
import time


def dsha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def to_display_hex(h: bytes) -> str:
    """Bitcoin prints hashes byte-reversed (little-endian number)."""
    return h[::-1].hex()


class Script:
    """Tiny subset of CScript: data pushes only."""
    OP_PUSHDATA1 = 0x4C
    OP_CHECKSIG = 0xAC
    MAX_DIRECT_PUSH = 0x4B  # 75: longer pushes need OP_PUSHDATA1

    @classmethod
    def push(cls, data: bytes) -> bytes:
        if len(data) <= cls.MAX_DIRECT_PUSH:
            return bytes([len(data)]) + data
        return bytes([cls.OP_PUSHDATA1, len(data)]) + data


class GenesisTx:
    """The genesis coinbase transaction (same layout as main.cpp)."""
    TX_VERSION = 1
    LOCK_TIME = 0
    COIN = 100_000_000
    REWARD = 50 * COIN
    NULL_PREVOUT = b"\x00" * 32 + b"\xff\xff\xff\xff"
    SEQUENCE_FINAL = b"\xff\xff\xff\xff"
    SCRIPTSIG_BITS = 486604799          # 0x1d00ffff, pushed as 4 bytes
    SCRIPTSIG_EXTRA = b"\x04"           # CBigNum(4)
    # Satoshi's genesis public key. The genesis output can never be spent.
    PUBKEY = bytes.fromhex(
        "04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61de"
        "b649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f")

    def __init__(self, headline: str):
        self.headline = headline.encode()

    def script_sig(self) -> bytes:
        return (Script.push(struct.pack("<I", self.SCRIPTSIG_BITS))
                + Script.push(self.SCRIPTSIG_EXTRA)
                + Script.push(self.headline))

    def script_pubkey(self) -> bytes:
        return Script.push(self.PUBKEY) + bytes([Script.OP_CHECKSIG])

    def serialize(self) -> bytes:
        sig = self.script_sig()
        pk = self.script_pubkey()
        return (struct.pack("<i", self.TX_VERSION)
                + b"\x01" + self.NULL_PREVOUT
                + bytes([len(sig)]) + sig + self.SEQUENCE_FINAL
                + b"\x01" + struct.pack("<q", self.REWARD)
                + bytes([len(pk)]) + pk
                + struct.pack("<I", self.LOCK_TIME))

    def txid(self) -> bytes:
        return dsha256(self.serialize())


class GenesisHeader:
    """80-byte header: version | prev | merkle | time | bits | nonce."""
    BLOCK_VERSION = 1
    MAINNET_BITS = 0x1D00FFFF           # 2009 genesis: limit ~0 >> 32 (2^32 hashes)
    PRIVATE_BITS = 0x1D7FFFFF           # our chain: limit ~0 >> 25 (2^25 hashes, ~10 s)
    PREFIX_LEN = 76                     # header without the nonce
    NONCE_MAX = 0xFFFFFFFF

    def __init__(self, merkle_root: bytes, n_time: int, bits: int = PRIVATE_BITS):
        self.bits = bits
        self.prefix = (struct.pack("<i", self.BLOCK_VERSION) + b"\x00" * 32
                       + merkle_root + struct.pack("<II", n_time, bits))

    def target(self) -> int:
        exponent = self.bits >> 24
        mantissa = self.bits & 0xFFFFFF
        return mantissa << (8 * (exponent - 3))

    def hash_with(self, nonce: int) -> bytes:
        return dsha256(self.prefix + struct.pack("<I", nonce))


class GenesisMiner:
    """Splits the nonce range over all CPU cores."""
    CHUNK = 1 << 20                     # nonces per work item
    REPORT_EVERY_S = 10

    def __init__(self, header: GenesisHeader):
        self.header = header

    def mine(self):
        chunks = range(0, GenesisHeader.NONCE_MAX + 1, self.CHUNK)
        start = time.time()
        last_report = start
        done = 0
        with multiprocessing.Pool() as pool:
            args = ((self.header.prefix, self.header.target(), c) for c in chunks)
            for result in pool.imap(_search_chunk, args):
                done += self.CHUNK
                if result is not None:
                    pool.terminate()
                    return result
                now = time.time()
                if now - last_report > self.REPORT_EVERY_S:
                    rate = done / (now - start)
                    print(f"  {done:>13,} nonces  {rate / 1e6:5.2f} MH/s", flush=True)
                    last_report = now
        return None


def _search_chunk(args):
    """Worker: uses the SHA-256 midstate of the first 64 bytes."""
    prefix, target, first = args
    mid = hashlib.sha256(prefix[:64])
    tail = prefix[64:]
    pack = struct.Struct("<I").pack
    for nonce in range(first, min(first + GenesisMiner.CHUNK, GenesisHeader.NONCE_MAX + 1)):
        h1 = mid.copy()
        h1.update(tail + pack(nonce))
        h = hashlib.sha256(h1.digest()).digest()
        if int.from_bytes(h, "little") <= target:
            return nonce, h
    return None


def selftest() -> None:
    headline = "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks"
    tx = GenesisTx(headline)
    header = GenesisHeader(tx.txid(), 1231006505, GenesisHeader.MAINNET_BITS)
    merkle = to_display_hex(tx.txid())
    block = to_display_hex(header.hash_with(2083236893))
    assert merkle == "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b", merkle
    assert block == "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f", block
    print("selftest OK: 2009 genesis reproduced")
    print("  merkle", merkle)
    print("  hash  ", block)


def main() -> None:
    if sys.argv[1:] == ["--selftest"]:
        selftest()
        return
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    headline, n_time = sys.argv[1], int(sys.argv[2])
    tx = GenesisTx(headline)
    header = GenesisHeader(tx.txid(), n_time)
    print(f"headline : {headline}")
    print(f"nTime    : {n_time}")
    print(f"merkle   : {to_display_hex(tx.txid())}")
    print(f"nBits    : {header.bits:#010x}")
    print(f"target   : {header.target():064x}")
    found = GenesisMiner(header).mine()
    if found is None:
        print("no nonce found: change nTime and run again")
        sys.exit(1)
    nonce, h = found
    print(f"nNonce   : {nonce}")
    print(f"hash     : {to_display_hex(h)}")


if __name__ == "__main__":
    main()
