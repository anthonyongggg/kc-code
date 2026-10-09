// 共用工具: 由 Yahoo Finance 攞歷史價錢 (等同 yfinance auto_adjust=True) + 通道計算
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

async function fetchHistory(ticker, period1, period2) {
  const url = "https://query1.finance.yahoo.com/v8/finance/chart/" + encodeURIComponent(ticker) +
    "?period1=" + period1 + "&period2=" + period2 + "&interval=1d&includeAdjustedClose=true&events=div%2Csplit";
  const resp = await fetch(url, { headers: { "User-Agent": UA, "Accept": "application/json" } });
  if (!resp.ok) {
    if (resp.status === 404) throw new Error("Yahoo Finance 搵唔到 '" + ticker + "' 呢個代號，請確認代號正確");
    throw new Error("Yahoo Finance 回應 HTTP " + resp.status + " (可能被限流，遲啲再試)");
  }
  const json = await resp.json();
  const r = json && json.chart && json.chart.result && json.chart.result[0];
  if (!r || !r.timestamp) throw new Error("Yahoo Finance 搵唔到 '" + ticker + "' 嘅數據，請確認代號正確");

  const q = r.indicators.quote[0];
  const adj = r.indicators.adjclose && r.indicators.adjclose[0] && r.indicators.adjclose[0].adjclose;
  const rows = [];
  for (let i = 0; i < r.timestamp.length; i++) {
    const h = q.high[i], l = q.low[i], c = q.close[i];
    if (h == null || c == null) continue;
    // auto_adjust: 用 adjclose/close 比例調整 high/low/close
    const f = (adj && adj[i] != null && c !== 0) ? adj[i] / c : 1;
    rows.push({
      date: new Date(r.timestamp[i] * 1000).toISOString().slice(0, 10),
      high: h * f, low: (l == null ? h : l) * f, close: c * f,
    });
  }
  if (!rows.length) throw new Error("'" + ticker + "' 冇有效嘅價錢數據");
  return rows;
}

// 最小二乘直線擬合 y = slope*x + intercept, x = 0..n-1
function polyfit1(ys) {
  const n = ys.length;
  let sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (let i = 0; i < n; i++) { sx += i; sy += ys[i]; sxx += i * i; sxy += i * ys[i]; }
  const denom = n * sxx - sx * sx;
  const slope = denom === 0 ? 0 : (n * sxy - sx * sy) / denom;
  const intercept = (sy - slope * sx) / n;
  return { slope, intercept };
}

function popStd(arr) { // 同 numpy 預設 (ddof=0) 一樣
  const n = arr.length;
  let m = 0; for (let i = 0; i < n; i++) m += arr[i]; m /= n;
  let v = 0; for (let i = 0; i < n; i++) v += (arr[i] - m) * (arr[i] - m);
  return Math.sqrt(v / n);
}

const LEVELS = [3, 2, 1, 0, -1, -2, -3];
const round7 = (x) => Number(x.toPrecision(7)); // 慳返 response 大細 (Netlify 上限 6MB)

function computeChannel(values, useLog, futureFrac) {
  futureFrac = futureFrac === undefined ? 0.25 : futureFrac;
  const n = values.length;
  const ys = useLog ? values.map(Math.log) : values;
  const { slope, intercept } = polyfit1(ys);
  const resid = new Array(n);
  for (let i = 0; i < n; i++) resid[i] = ys[i] - (slope * i + intercept);
  const sd = popStd(resid);
  const nFuture = Math.round(n * futureFrac);
  const bands = {}, lastBands = {};
  for (const k of LEVELS) {
    const arr = new Array(n + nFuture);
    for (let i = 0; i < n + nFuture; i++) {
      const y = slope * i + intercept + k * sd;
      arr[i] = round7(useLog ? Math.exp(y) : y);
    }
    bands[String(k)] = arr;
    const yl = slope * (n - 1) + intercept + k * sd;
    lastBands[String(k)] = useLog ? Math.exp(yl) : yl;
  }
  return { bands, lastBands, nFuture };
}

function futureDates(dates, nFuture) {
  const out = [];
  if (nFuture <= 0 || dates.length < 2) return out;
  const last = new Date(dates[dates.length - 1] + "T00:00:00Z");
  const first = new Date(dates[0] + "T00:00:00Z");
  const avgGap = Math.max(1, (last - first) / 86400000 / Math.max(1, dates.length - 1));
  for (let i = 1; i <= nFuture; i++) {
    out.push(new Date(last.getTime() + avgGap * i * 86400000).toISOString().slice(0, 10));
  }
  return out;
}

function json(obj, status) {
  return {
    statusCode: status || 200,
    headers: { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" },
    body: JSON.stringify(obj),
  };
}

module.exports = { fetchHistory, computeChannel, futureDates, round7, popStd, json };
