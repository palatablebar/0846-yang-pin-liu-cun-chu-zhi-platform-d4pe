/* 库房盘点对账台前端 */
const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
  ));
}

function row(cells) {
  return `<tr>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`;
}

function emptyRow(cols, text) {
  return `<tr><td colspan="${cols}" class="empty">${text}</td></tr>`;
}

async function loadSample() {
  const profile = $("profile").value;
  const response = await fetch(`/api/stocktake/examples/${profile}`);
  if (!response.ok) {
    notify(`样例载入失败：${response.status}`, true);
    return;
  }
  $("payload").value = JSON.stringify(await response.json(), null, 2);
  $("payload-hint").textContent = `已载入 ${profile} 样例`;
}

function renderReport(data) {
  const s = data.summary || {};
  $("kpi-transit").querySelector("b").textContent = s.in_transit || 0;
  $("kpi-shortage").querySelector("b").textContent = s.shortage || 0;
  $("kpi-duplicate").querySelector("b").textContent = s.duplicate || 0;
  $("kpi-surplus").querySelector("b").textContent = s.surplus || 0;

  $("transit-body").innerHTML = data.in_transit.length
    ? data.in_transit.map((r) => row([
        esc(r.sample_id), esc(r.from_location), esc(r.to_location),
        `<span class="mono">${esc(r.due_date)}</span>`, esc(r.voucher_id),
      ])).join("")
    : emptyRow(5, "无在途样品");

  $("shortage-body").innerHTML = data.shortages.length
    ? data.shortages.map((r) => row([
        esc(r.sample_id), esc(r.location),
        `<span class="tag tag-shortage">${esc(r.reason)}</span>`, esc(r.detail),
      ])).join("")
    : emptyRow(4, "无短缺");

  $("duplicate-body").innerHTML = data.duplicates.length
    ? data.duplicates.map((r) => row([
        esc(r.sample_id), esc((r.locations || []).join("、")), esc(r.detail),
      ])).join("")
    : emptyRow(3, "无重号");

  $("surplus-body").innerHTML = data.surplus.length
    ? data.surplus.map((r) => row([
        esc(r.sample_id), esc(r.location), esc(r.detail),
      ])).join("")
    : emptyRow(3, "无多出");

  $("ignored-body").innerHTML = data.ignored_vouchers.length
    ? data.ignored_vouchers.map((r) => row([
        esc(r.sample_id), esc(r.voucher_id || "-"),
        `<span class="tag tag-ignored">${esc(r.reason)}</span>`,
      ])).join("")
    : emptyRow(3, "无不采信凭据");
}

async function submitStocktake() {
  let submission;
  try {
    submission = JSON.parse($("payload").value);
  } catch (err) {
    notify("JSON 解析失败，请检查盘点提交内容", true);
    return;
  }
  const response = await fetch("/api/stocktake/submissions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(submission),
  });
  const data = await response.json();
  if (!response.ok) {
    notify(`签发被拒绝（${data.code}）：${data.error}`, true);
    return;
  }
  renderReport(data);
  const outcomeText = data.outcome === "EXISTING"
    ? `<span class="tag tag-existing">重试 · 返回原单未重复登记</span>`
    : `<span class="tag tag-created">新签发</span>`;
  notify(`差异单 ${data.issue_id} 已签发 ${outcomeText}`, false);
  await refreshIssued();
}

async function refreshIssued() {
  const response = await fetch("/api/stocktake/issues");
  if (!response.ok) {
    notify(`已签发列表加载失败：${response.status}`, true);
    return;
  }
  const issues = (await response.json()).issues || [];
  $("issued-hint").textContent = `共 ${issues.length} 张`;
  $("issued-body").innerHTML = issues.length
    ? issues.map((r) => row([
        `<a class="st-link mono" href="/api/stocktake/issues/${encodeURIComponent(r.issue_id)}" target="_blank">${esc(r.issue_id)}</a>`,
        esc(r.stocktake_id),
        `<span class="mono">${esc(r.created_at)}</span>`,
        `<span class="mono">${esc(r.content_hash.slice(0, 12))}…</span>`,
        `<a class="st-link" href="/api/stocktake/stocktakes/${encodeURIComponent(r.stocktake_id)}" target="_blank">核对</a>`,
      ])).join("")
    : emptyRow(5, "尚未签发任何差异单");
}

function notify(text, isError) {
  const el = $("notice");
  el.innerHTML = `<span class="${isError ? "err" : "ok"}">${esc(text)}</span>`;
}

$("load-sample").addEventListener("click", loadSample);
$("submit").addEventListener("click", submitStocktake);
$("refresh").addEventListener("click", refreshIssued);
loadSample().then(refreshIssued);
