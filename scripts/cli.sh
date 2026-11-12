#!/bin/sh
# Run an RPC command on one node.
#   ./scripts/cli.sh satoshi getinfo
#   ./scripts/cli.sh hal getnewaddress
set -eu
if [ $# -lt 2 ]; then
    echo "usage: $0 <satoshi|hal> <command> [args...]" >&2
    exit 1
fi
NODE=$1
shift
exec docker compose exec "$NODE" \
    bitcoind -datadir=/data -conf=/etc/bitcoin/bitcoin.conf "$@"
