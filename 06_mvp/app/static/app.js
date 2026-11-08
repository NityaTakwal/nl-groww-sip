const $ = (id) => document.getElementById(id);
const rupee = (n) => "₹" + Number(n).toLocaleString("en-IN");
const ord = (n) => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th"));
const CHIPS = ["Salary comes late this month", "Client hasn't paid yet", "Portfolio is showing red", "Need cash for an emergency", "Does skipping cancel my SIP?"];
const QC_LABELS = {
  no_fund_or_stock_names: "No fund or stock suggestions",
  no_fear_fomo_urgency: "No fear, FOMO or pressure",
  no_return_promises: "No return promises",
  not_framed_as_advice: "Not framed as advice",
  understood_situation_confidently: "Understood your situation confidently",
};
let scenarios = {}, current = "due_soon", last = null;

function show(view) { ["home", "ask", "result"].forEach((v) => $(v).classList.toggle("hidden", v !== view)); $("screen").scrollTop = 0; }
document.querySelectorAll("[data-go]").forEach((el) => el.onclick = () => show(el.dataset.go));

function renderHome() {
  const s = scenarios[current];
  $("sipAmount").textContent = rupee(s.amount);
  $("sipDate").textContent = `${ord(s.sip_day)} of every month`;
  $("sipMonths").textContent = s.months_active;
  $("sipInvested").textContent = rupee(s.invested);
  $("sipValue").textContent = `${rupee(s.current_value)} (${s.change_pct > 0 ? "+" : ""}${s.change_pct}%)`;
  const streak = $("streak");
  streak.className = "streak" + (s.missed_in_row ? " warn" : "");
  streak.textContent = s.missed_in_row
    ? `Missed in a row: ${s.missed_in_row} of ${s.cancel_after}. At ${s.cancel_after} in a row, the SIP is cancelled automatically.`
    : `All instalments done so far · missed in a row: 0 of ${s.cancel_after}`;
  const copy = {
    due_soon: [`${rupee(s.amount)} goes out on the ${ord(s.sip_day)}`, "If money comes in later than usual this month, you can plan ahead now instead of finding out from your bank."],
    failed: [`This month's ${rupee(s.amount)} didn't go through`, "Your bank account didn't have enough balance on the SIP date. Your SIP is still active. See what you can do this month."],
    two_missed: [`${rupee(s.amount)} is due on the ${ord(s.sip_day)}`, `The last 2 instalments were missed. A SIP is cancelled after 3 missed instalments in a row (skips count too). See what you can do this month.`],
  }[current];
  $("nudgeTitle").textContent = copy[0];
  $("nudgeBody").textContent = copy[1];
}

function renderScenarios() {
  $("scenarios").innerHTML = "";
  Object.entries(scenarios).forEach(([k, s]) => {
    const b = document.createElement("button");
    b.className = k === current ? "on" : "";
    b.innerHTML = `${s.label}<small>${rupee(s.amount)} on the ${ord(s.sip_day)} · missed in a row ${s.missed_in_row}/3</small>`;
    b.onclick = () => { current = k; renderScenarios(); renderHome(); show("home"); };
    $("scenarios").appendChild(b);
  });
}

CHIPS.forEach((c) => {
  const b = document.createElement("button");
  b.className = "chip"; b.textContent = c;
  b.onclick = () => { const t = $("userText"); t.value = (t.value ? t.value + ". " : "") + c; t.focus(); };
  $("chips").appendChild(b);
});

$("planBtn").onclick = () => show("ask");
$("askBtn").onclick = async () => {
  const text = $("userText").value.trim();
  if (!text) { $("userText").focus(); return; }
  show("result"); $("resultBody").innerHTML = ""; $("loading").classList.remove("hidden");
  try {
    const r = await fetch("/api/assist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, scenario: current }) });
    last = await r.json();
    renderResult(last);
  } catch (e) {
    $("resultBody").innerHTML = `<div class="card">Something went wrong. Please try again.</div>`;
  } finally { $("loading").classList.add("hidden"); }
};

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

function renderResult(r) {
  const modeText = { answered: "Personalised for you", fallback: "Showing all options", declined: "Can't help with that" }[r.mode];
  const understood = r.understood ? `
    <div class="card understood">
      <div class="label">What I understood</div>
      <div>${esc(r.understood)}</div>
      ${r.income_day ? `<div class="facts">Money usually arrives around the ${ord(r.income_day)}</div>` : ""}
      <button class="fix" onclick="show('ask')">Not quite? Tell me more</button>
    </div>` : "";
  const opts = r.options.map((o, i) => `
    <label class="opt ${o.allowed ? "" : "blocked"}" data-id="${o.id}">
      <input type="radio" name="opt" value="${o.id}" ${o.allowed ? "" : "disabled"}>
      <span class="t">${esc(o.title)}</span>${o.keeps_sip_alive ? '<span class="keep">keeps SIP active</span>' : ""}
      <div class="d">${esc(o.detail)}</div>
      ${o.warning ? `<div class="w">${esc(o.warning)}</div>` : ""}
      ${o.amounts ? `<div class="chips amt">${o.amounts.map((a, j) => `<button type="button" class="chip${j === 0 ? " on" : ""}" data-amt="${a}">${rupee(a)}</button>`).join("")}</div>` : ""}
    </label>`).join("");
  const qc = Object.entries(r.quality_checks).map(([k, v]) => `<div class="${v ? "pass" : "fail"}">${QC_LABELS[k] || k}</div>`).join("");
  const src = r.sources.map((s) => `<a href="${s.url}" target="_blank" rel="noopener">${esc(s.title)} ↗</a>`).join("");
  $("resultBody").innerHTML = `
    <span class="mode ${r.mode}">${modeText}</span>
    ${understood}
    <div class="card"><div>${esc(r.message)}</div>
      <div class="facts" style="margin-top:8px"><b>About your numbers:</b> ${esc(r.returns_line)}</div>
      <div class="facts" style="margin-top:6px">Missed in a row: ${r.facts.missed_in_row} of ${r.facts.cancel_after}</div>
    </div>
    <div class="section-label">Your options this month</div>
    <form id="optForm">${opts}</form>
    <button class="btn primary" id="confirmBtn" disabled>Continue</button>
    <div class="card" style="margin-top:12px"><div class="section-label">Quality check on this reply</div><div class="qc">${qc}</div>
      ${r.mode !== "answered" ? `<div class="facts" style="margin-top:6px">${r.mode === "declined" ? "This question needs investment advice, which this tool doesn't give." : "The personalised reply was held back by a check above, so you're seeing every option in plain form. Your facts and options are unchanged."}</div>` : ""}
    </div>
    <div class="card sources"><div class="section-label">Official sources</div>${src}</div>
    <div class="disclaimer">${esc(r.disclaimer)}</div>`;
  document.querySelectorAll(".opt").forEach((l) => l.onclick = () => {
    if (l.classList.contains("blocked")) return;
    document.querySelectorAll(".opt").forEach((x) => x.classList.toggle("sel", x === l));
    l.querySelector("input").checked = true; $("confirmBtn").disabled = false;
  });
  document.querySelectorAll(".amt .chip").forEach((c) => c.onclick = (e) => {
    e.preventDefault();
    c.parentElement.querySelectorAll(".chip").forEach((x) => x.classList.toggle("on", x === c));
  });
  $("confirmBtn").onclick = async () => {
    const id = document.querySelector("input[name=opt]:checked")?.value; if (!id) return;
    const o = r.options.find((x) => x.id === id);
    const amt = document.querySelector(`.opt[data-id="${id}"] .amt .chip.on`)?.dataset.amt;
    const res = await fetch("/api/action", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: current, option_id: id, new_day: o.new_day, amount: amt ? Number(amt) : null }) }).then((x) => x.json());
    toast(res.message);
  };
}

function toast(msg) { const t = $("toast"); t.textContent = msg; t.classList.remove("hidden"); setTimeout(() => t.classList.add("hidden"), 8000); }

fetch("/api/scenarios").then((r) => r.json()).then((d) => { scenarios = d; renderScenarios(); renderHome(); });
