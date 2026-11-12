#!/usr/bin/env python3
"""Regenerate patches/0001-private-chain.patch from a clean v0.3.24 tree.

Usage:
  python3 tools/make_patch.py <clean bitcoin-0.3.24 dir> <out.patch>

Every edit checks that the original text is found exactly once,
so the patch fails loudly if the source is not v0.3.24.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile


class Genesis:
    """Values from tools/mine_genesis.py (see README)."""
    HEADLINE = "Laptop 12/Nov/2026 A private chain on 2011 rules, mined from block zero"
    TIME = 1794498745
    NONCE = 13291089
    BITS = "0x1d7fffff"     # = Consensus.POW_LIMIT_BITS (compact form)
    HASH = "0000000f5d8fa763600966bc346f4e177728760aa114bec6f8c7b486d68368c9"
    MERKLE = "c65a1d92e2ae660edba5990c7a24e6d6cb2593984875d104471fd75ebbf6152a"


class Consensus:
    """Fast toy chain: ~10 s blocks, coins spendable after ~60 s."""
    POW_LIMIT_BITS = 25             # leading zero bits at easiest (Bitcoin: 32)
    COINBASE_MATURITY = 6           # blocks (Bitcoin: 100)
    WALLET_MATURITY_MARGIN = 0      # extra blocks the wallet waits (Bitcoin: 20)
    TARGET_SPACING_S = 10           # seconds per block (Bitcoin: 600)
    RETARGET_BLOCKS = 60            # blocks per retarget (Bitcoin: 2016)


class Net:
    MAGIC = "{ 0xfa, 0xce, 0xb0, 0x0c }"
    P2P_PORT = 9333
    RPC_PORT = 9332


GET_SECRET = """
    // Private chain: raw 32-byte secret, used by the dumpprivkey RPC
    std::vector<unsigned char> GetSecret() const
    {
        static const int SECRET_SIZE = 32;
        const BIGNUM* bn = EC_KEY_get0_private_key(pkey);
        if (bn == NULL || BN_num_bytes(bn) > SECRET_SIZE)
            throw key_error("CKey::GetSecret() : bad private key");
        std::vector<unsigned char> vchSecret(SECRET_SIZE, 0);
        BN_bn2bin(bn, &vchSecret[SECRET_SIZE - BN_num_bytes(bn)]);
        return vchSecret;
    }

    std::vector<unsigned char> GetPubKey() const"""

DUMPPRIVKEY = """Value dumpprivkey(const Array& params, bool fHelp)
{
    // Private chain: backport of the 2012 RPC (same name, WIF output)
    static const unsigned char WIF_VERSION = 128;
    if (fHelp || params.size() != 1)
        throw runtime_error(
            "dumpprivkey <bitcoinaddress>\\n"
            "Reveals the private key (WIF) for <bitcoinaddress>.");

    string strAddress = params[0].get_str();
    uint160 hash160;
    if (!AddressToHash160(strAddress, hash160))
        throw JSONRPCError(-5, "Invalid bitcoin address");

    vector<unsigned char> vchPubKey;
    CRITICAL_BLOCK(cs_mapPubKeys)
    {
        if (!mapPubKeys.count(hash160))
            throw JSONRPCError(-4, "Address is not in this wallet");
        vchPubKey = mapPubKeys[hash160];
    }

    CPrivKey vchPrivKey;
    CRITICAL_BLOCK(pwalletMain->cs_mapKeys)
        if (!pwalletMain->GetPrivKey(vchPubKey, vchPrivKey))
            throw JSONRPCError(-4, "Private key not found");

    CKey key;
    if (!key.SetPrivKey(vchPrivKey))
        throw JSONRPCError(-4, "Bad private key");

    vector<unsigned char> vchWif(1, WIF_VERSION);
    vector<unsigned char> vchSecret = key.GetSecret();
    vchWif.insert(vchWif.end(), vchSecret.begin(), vchSecret.end());
    return EncodeBase58Check(vchWif);
}


Value getwork(const Array& params, bool fHelp)"""


class SourceTree:
    def __init__(self, src: pathlib.Path):
        self.src = src

    def edit(self, name: str, old: str, new: str, count: int = 1) -> None:
        path = self.src / name
        text = path.read_text(encoding="latin-1")
        found = text.count(old)
        if found != count:
            raise SystemExit(f"{name}: expected {count}x, found {found}x: {old[:70]!r}")
        path.write_text(text.replace(old, new), encoding="latin-1")

    def cut(self, name: str, first_line: str, last_line: str, new: str) -> None:
        path = self.src / name
        text = path.read_text(encoding="latin-1")
        start = text.index(first_line)
        end = text.index(last_line, start) + len(last_line)
        path.write_text(text[:start] + new + text[end:], encoding="latin-1")


def apply_private_chain(t: SourceTree) -> None:
    g = Genesis
    # main.cpp: genesis, initial-download estimate, checkpoints, magic
    t.edit("main.cpp",
           'uint256 hashGenesisBlock("0x000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f");',
           f'uint256 hashGenesisBlock("0x{g.HASH}");')
    t.edit("main.cpp",
           "const int nTotalBlocksEstimate = 134444; // Conservative estimate of total nr of blocks on main chain",
           "const int nTotalBlocksEstimate = 0; // Private chain: no known blocks, so mining can start at once")
    t.cut("main.cpp",
          "    // Check that the block chain matches the known block chain up to a checkpoint",
          'return error("AcceptBlock() : rejected by checkpoint lockin at %d", nHeight);\n',
          "    // Private chain: mainnet checkpoints removed\n")
    t.edit("main.cpp",
           'const char* pszTimestamp = "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks";',
           f'const char* pszTimestamp = "{g.HEADLINE}";')
    t.edit("main.cpp", "block.nTime    = 1231006505;", f"block.nTime    = {g.TIME};")
    t.edit("main.cpp", "block.nNonce   = 2083236893;", f"block.nNonce   = {g.NONCE};")
    t.edit("main.cpp",
           'assert(block.hashMerkleRoot == uint256("0x4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"));',
           f'assert(block.hashMerkleRoot == uint256("0x{g.MERKLE}"));')
    t.edit("main.cpp",
           "char pchMessageStart[4] = { 0xf9, 0xbe, 0xb4, 0xd9 };",
           f"char pchMessageStart[4] = {Net.MAGIC}; // private chain magic")

    # consensus: easier PoW, short maturity, fast retarget
    c = Consensus
    t.edit("main.cpp", "CBigNum bnProofOfWorkLimit(~uint256(0) >> 32);",
           f"CBigNum bnProofOfWorkLimit(~uint256(0) >> {c.POW_LIMIT_BITS}); // private chain: ~10 s blocks")
    t.edit("main.cpp", "block.nBits    = 0x1d00ffff;", f"block.nBits    = {g.BITS};")
    t.edit("main.h", "static const int COINBASE_MATURITY = 100;",
           f"static const int COINBASE_MATURITY = {c.COINBASE_MATURITY}; // private chain (Bitcoin: 100)\n"
           f"static const int COINBASE_MATURITY_WALLET_MARGIN = {c.WALLET_MATURITY_MARGIN}; // Bitcoin: 20")
    t.edit("main.cpp", "(COINBASE_MATURITY+20)", "(COINBASE_MATURITY+COINBASE_MATURITY_WALLET_MARGIN)")
    t.edit("main.cpp", "const int64 nTargetTimespan = 14 * 24 * 60 * 60; // two weeks",
           f"const int64 nTargetTimespan = {c.RETARGET_BLOCKS} * {c.TARGET_SPACING_S}; // private chain: {c.RETARGET_BLOCKS} blocks")
    t.edit("main.cpp", "const int64 nTargetSpacing = 10 * 60;",
           f"const int64 nTargetSpacing = {c.TARGET_SPACING_S}; // private chain (Bitcoin: 10 min)")

    # ports
    t.edit("net.h", "return fTestNet ? 18333 : 8333;", f"return fTestNet ? 18333 : {Net.P2P_PORT};")
    t.edit("rpc.cpp", 'GetArg("-rpcport", 8332)', f'GetArg("-rpcport", {Net.RPC_PORT})')
    t.edit("rpc.cpp", 'GetArg("-rpcport", "8332")', f'GetArg("-rpcport", "{Net.RPC_PORT}")', count=2)
    t.edit("init.cpp", "(default: 8332)", f"(default: {Net.RPC_PORT})")

    # dumpprivkey RPC
    t.edit("key.h", "\n    std::vector<unsigned char> GetPubKey() const", GET_SECRET)
    t.edit("rpc.cpp", "Value getwork(const Array& params, bool fHelp)", DUMPPRIVKEY)
    t.edit("rpc.cpp",
           '    make_pair("getwork",               &getwork),',
           '    make_pair("getwork",               &getwork),\n'
           '    make_pair("dumpprivkey",           &dumpprivkey),')


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    clean = pathlib.Path(sys.argv[1]).resolve()
    out = pathlib.Path(sys.argv[2]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        shutil.copytree(clean / "src", work / "a" / "src")
        shutil.copytree(clean / "src", work / "b" / "src")
        apply_private_chain(SourceTree(work / "b" / "src"))
        diff = subprocess.run(["diff", "-ru", "a", "b"], cwd=work,
                              capture_output=True, text=True, encoding="latin-1")
        if diff.returncode != 1:
            raise SystemExit(f"diff failed: {diff.stderr}")
        out.write_text(diff.stdout, encoding="latin-1")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
