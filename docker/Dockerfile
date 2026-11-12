# Bitcoin v0.3.24 (July 2011) on Debian 6 "squeeze" (Feb 2011).
# Same era toolchain: g++ 4.4, Boost 1.42, OpenSSL 0.9.8, BerkeleyDB 4.8.

ARG BITCOIN_VERSION=0.3.24
ARG BITCOIN_SHA256=b56802d7fee25951a0e8b6a3d30090307e6c4aab99a7db26b4bdc48657f66292

# ---- Stage 1: fetch + patch (modern image, because squeeze cannot do modern TLS)
FROM debian:bookworm-slim AS fetch
ARG BITCOIN_VERSION
ARG BITCOIN_SHA256
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl patch \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl -fsSL -o bitcoin.tar.gz \
      https://github.com/bitcoin/bitcoin/archive/refs/tags/v${BITCOIN_VERSION}.tar.gz \
 && echo "${BITCOIN_SHA256}  bitcoin.tar.gz" | sha256sum -c - \
 && tar xzf bitcoin.tar.gz \
 && mv bitcoin-${BITCOIN_VERSION} bitcoin
COPY patches/ /patches/
RUN cd bitcoin && for p in /patches/*.patch; do patch -p1 < "$p"; done

# ---- Stage 2: build with the 2011 toolchain
FROM debian/eol:squeeze AS build
ARG APT_OPTS="-o Acquire::Check-Valid-Until=false -y --force-yes --no-install-recommends"
RUN apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install ${APT_OPTS} \
      g++ make \
      libboost-system-dev libboost-filesystem-dev \
      libboost-program-options-dev libboost-thread-dev \
      libdb4.8++-dev libssl-dev libglib2.0-dev zlib1g-dev
COPY --from=fetch /src/bitcoin /bitcoin
WORKDIR /bitcoin/src
# USE_UPNP= (empty) turns UPnP off, so no miniupnpc is needed.
RUN make -f makefile.unix bitcoind USE_UPNP= -j"$(nproc)" \
 && strip bitcoind

# ---- Stage 3: small runtime image, same distro
FROM debian/eol:squeeze
RUN apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -o Acquire::Check-Valid-Until=false -y --force-yes --no-install-recommends \
      libglib2.0-0 zlib1g \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /bitcoin/src/bitcoind /usr/local/bin/bitcoind
RUN useradd -m bitcoin && mkdir /data && chown bitcoin:bitcoin /data
USER bitcoin
VOLUME /data
EXPOSE 9333
ENTRYPOINT ["bitcoind", "-datadir=/data", "-conf=/etc/bitcoin/bitcoin.conf"]
CMD ["-printtoconsole"]
