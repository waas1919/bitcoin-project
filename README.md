# Private 2011 Bitcoin (v0.3.24) in Docker

The real Bitcoin v0.3.24 (July 2011), built with 2011 tools, running as your own private chain.
There are two nodes: **satoshi** (mines) and **hal** (receives coins).

## Files

| File | Purpose |
|---|---|
| `docker/Dockerfile` | Downloads v0.3.24 (sha256 checked), applies the patch, builds `bitcoind` on Debian 6 squeeze (g++ 4.4, Boost 1.42, OpenSSL 0.9.8, BDB 4.8) |
| `patches/0001-private-chain.patch` | Our own genesis block, magic bytes, ports; removes mainnet checkpoints; adds `dumpprivkey` |
| `tools/mine_genesis.py` | Builds the genesis block the same way `main.cpp` does and finds its nonce |
| `tools/make_patch.py` | Regenerates the patch from a clean v0.3.24 tree (every edit is checked) |
| `dashboard/` | HTML dashboard: `server.py`, `node_rpc.py`, `node_log.py`, `node_state.py`, `key_view.py`, `bip39.py`, `static/` |
| `docker-compose.yml` | 2 nodes on `10.83.11.0/24`, `internal: true` (no internet) |
| `conf/satoshi.conf`, `conf/hal.conf` | Node settings |
| `scripts/start.sh`, `scripts/stop.sh` | Start nodes + dashboard / stop everything (chain kept) |
| `scripts/cli.sh` | Runs an RPC command on a node |

## What the patch changes

| Item | Mainnet 2011 | Private chain |
|---|---|---|
| `pchMessageStart` | `f9 be b4 d9` | `fa ce b0 0c` |
| P2P / RPC port | 8333 / 8332 | 9333 / 9332 |
| `pszTimestamp` | "The Times 03/Jan/2009 Chancellor…" | "Laptop 12/Nov/2026 A private chain on 2011 rules, mined from block zero" |
| genesis `nTime` | 1231006505 | 1794498745 |
| genesis `nBits` | `0x1d00ffff` | `0x1d7fffff` |
| genesis `nNonce` | 2083236893 | 13291089 |
| genesis hash | `000000000019d6…` | `0000000f5d8fa763600966bc346f4e177728760aa114bec6f8c7b486d68368c9` |
| merkle root | `4a5e1e4b…` | `c65a1d92e2ae660edba5990c7a24e6d6cb2593984875d104471fd75ebbf6152a` |
| `nTotalBlocksEstimate` | 134444 | 0 (otherwise the miner waits for block 134324, which never comes) |
| Checkpoints (11111 …) | 8 mainnet hashes | removed |
| `bnProofOfWorkLimit` | `~0 >> 32` | `~0 >> 25` (128× easier) |
| `nTargetSpacing` | 10 min | 10 s |
| `nTargetTimespan` | 2 weeks (2016 blocks) | 600 s (60 blocks) |
| `COINBASE_MATURITY` | 100 | 6 |
| wallet maturity margin | `+20` (bare number) | `COINBASE_MATURITY_WALLET_MARGIN = 0` |
| `dumpprivkey <address>` RPC | did not exist (added in 2012) | backported: returns WIF (uncompressed, `0x80` + 32-byte secret) |

All consensus values are named constants in the `Consensus` class in `tools/make_patch.py`.
Unchanged from 2011: 50 BTC reward, halving every 210000 blocks, max 4× change per retarget,
addresses starting with `1`.

## Proof-of-work flow
```
nBits    = 0x1d7fffff  → exponent 0x1d = 29, mantissa 0x7fffff
target   = 0x7fffff * 256^(29-3)
         = 0x0000007fffff0000000000000000000000000000000000000000000000000000
hash must be <= target  → about 25 leading zero bits
work     ≈ 2^25 ≈ 3.4e7 hashes per block
time     ≈ 3.4e7 / 3.3e6 (2 cores) ≈ 10 s per block
getdifficulty = 0x00ffff·256^26 / target ≈ 0.0078  (= 1/128 of Bitcoin's difficulty 1)
```

## Maturity flow
```
block 1 mined at height 1; confirmations = height − 1 + 1
height 1..5 → immature      height 6 → 6 conf → 50 BTC spendable (≈ 60 s after block 1)
```
Measured: height 10 → satoshi balance 5 × 50 − 10 sent = 240 BTC, immature 250 BTC (blocks 6..10).

## Run

Needs Docker, and your user in the `docker` group (`sudo usermod -aG docker $USER`, then log in again).

```bash
./scripts/start.sh
```
- The first run builds the image (several minutes).
- It starts both nodes, turns on mining with `setgenerate true 2` (2 cores), then starts the dashboard.
- Open http://127.0.0.1:8011

```bash
./scripts/stop.sh
```
- This stops the dashboard and both nodes. bitcoind gets SIGTERM and shuts down cleanly.
- The chain and wallets stay in the Docker volumes, so `start.sh` resumes at the same block.
- There is no restart policy, so nothing runs until you call `start.sh`.
- To wipe everything and start again from genesis: `docker compose down -v`.

Mining only starts once satoshi has a peer (`vNodes.empty()` check in `BitcoinMiner`),
so it begins after hal connects.

### Dashboard
For each node, every 3 s:
- the block it is trying to find, hash rate, and expected time per block
- balance, plus coins still waiting for their 6 confirmations, and how long until they mature
- receiving address, private key (WIF + hex), and the key written as 24 words
- the latest block hashes (from the log: v0.3.24 has no `getblock` RPC)
- recent transactions

Each mined block pays to a **new** keypool key, not the receiving address (the same as 2011).

The 24 words are just the 32-byte private key written in BIP39 words.
2011 wallets had no seed words, so a modern wallet cannot restore from them.

### RPC by hand
```bash
./scripts/cli.sh satoshi getinfo
```
```bash
./scripts/cli.sh hal getaccountaddress ""
```
After 6 blocks (≈ 1 min) the first coinbase is spendable. Do the
"first transaction", the same as Satoshi → Hal in block 170:
```bash
./scripts/cli.sh satoshi sendtoaddress <hal_address> 10
```
Hal sees it at once with 0 confirmations (`listtransactions`). It counts in `getbalance` after the next block.

## Re-mining the genesis (optional)
```bash
python3 tools/mine_genesis.py --selftest
```
```bash
python3 tools/mine_genesis.py "<headline, max 75 chars>" <unix time>
```
Default `nBits` is `0x1d7fffff` (the 25-bit limit). Then put the new values in the `Genesis` class in `tools/make_patch.py` and run:
```bash
python3 tools/make_patch.py <clean bitcoin-0.3.24 dir> patches/0001-private-chain.patch
```

## Notes from the first build (12 Nov 2026)
- Debian squeeze toolchain built v0.3.24 + patch with no errors; image build takes a few minutes.
- First chain used Bitcoin's 32-bit limit: ~22 min per block, 120-block wait. Replaced with the toy rules above
  (new genesis `0000000f5d8f…`, mined in 7 s).
- Genesis asserts passed on both chains.
- satoshi → hal 10 BTC: 0 conf right away, in hal's balance after the next block.
- Not watched yet: the first retarget at block 60. The hash-rate number is noisy because blocks are so short.
- `dumpprivkey` checked: WIF → secp256k1 public key → address gives back the node's address.
- Stop/start: shutdown logs `DBFlush(true)` / `Bitcoin exiting`; the next boot logs
  `LoadBlockIndex(): hashBestChain=…` (loaded from disk, not a new genesis).
- `tty: true` in compose: without it bitcoind's stdout is block-buffered and the log lags by kilobytes.
