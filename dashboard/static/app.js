// Polls /api/state and draws one card per node.
const POLL_MS = 3000;
const SECONDS_PER_MINUTE = 60;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const btc = (v) => `${Number(v).toFixed(2)} BTC`;
const row = (k, v) => `<tr><td class="k">${k}</td><td>${v}</td></tr>`;

function duration(seconds) {
  if (seconds == null) return "–";
  if (seconds < SECONDS_PER_MINUTE) return `≈ ${Math.round(seconds)} s`;
  return `≈ ${Math.round(seconds / SECONDS_PER_MINUTE)} min`;
}

function immatureText(n) {
  const wait = n.spendable_in_s == null ? "" : ` · next spendable in ${duration(n.spendable_in_s)}`;
  return `${btc(n.immature)} <span class="note">(needs ${n.maturity_blocks} confirmations${wait})</span>`;
}

function miningText(n) {
  if (!n.generate) return `not mining (has ${n.blocks} blocks)`;
  return `<span class="big">trying to find block ${n.mining_block}</span>`;
}

function blocksTable(blocks) {
  if (!blocks.length) return `<div class="note">no blocks in the log yet</div>`;
  return "<table>" + blocks.map((b) =>
    row(`#${b.height}${b.mined_here ? ' <span class="mine">mined</span>' : ""}`,
        `<span class="hash">${esc(b.hash)}</span>`)).join("") + "</table>";
}

function txTable(txs) {
  if (!txs.length) return `<div class="note">no transactions yet</div>`;
  return "<table>" + txs.map((t) =>
    row(esc(t.category), `${btc(t.amount)} · ${t.confirmations} conf${t.address ? " · " + esc(t.address) : ""}`)).join("") + "</table>";
}

function keyBlock(key) {
  const words = key.words.map((w, i) => `<span data-n="${i + 1}">${esc(w)}</span>`).join("");
  return "<table>" +
    row("address", esc(key.address)) +
    row("private (WIF)", `<span class="hash">${esc(key.wif)}</span>`) +
    row("private (hex)", `<span class="hash">${esc(key.hex)}</span>`) +
    "</table>" + `<div class="words">${words}</div>`;
}

function card(n) {
  const head = `<h2>${esc(n.node)} <span class="pill ${n.running ? "on" : "off"}">${n.running ? "running" : "stopped"}</span></h2>`;
  if (!n.running || n.error) {
    return `<div class="card">${head}<div class="note">${esc(n.error || "container not running · ./scripts/start.sh")}</div></div>`;
  }
  return `<div class="card">${head}
    <div>${miningText(n)}</div>
    <table>
      ${row("chain height", n.blocks)}
      ${row("difficulty", n.difficulty)}
      ${row("hash rate", n.generate ? `${n.khash_per_s.toLocaleString()} khash/s on ${n.cores} cores` : "–")}
      ${row("expected / block", duration(n.expected_block_s))}
      ${row("peers", n.peers)}
      ${row("balance", `<b>${btc(n.balance)}</b>`)}
      ${row("immature", immatureText(n))}
    </table>
    <h3>Receiving key</h3>${keyBlock(n.key)}
    <h3>Recent blocks</h3>${blocksTable(n.recent_blocks)}
    <h3>Recent transactions</h3>${txTable(n.transactions)}
  </div>`;
}

async function refresh() {
  try {
    const state = await (await fetch("/api/state")).json();
    document.getElementById("updated").textContent = state.updated || "starting…";
    document.getElementById("nodes").innerHTML = state.nodes.map(card).join("");
  } catch (e) {
    document.getElementById("updated").textContent = "dashboard server not reachable";
  }
}

refresh();
setInterval(refresh, POLL_MS);
