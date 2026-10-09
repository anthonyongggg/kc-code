// 取代 Python 嘅 /api/search
const { fetchHistory, computeChannel, futureDates, round7, json } = require("./_lib");

exports.handler = async (event) => {
  const ticker = ((event.queryStringParameters || {}).ticker || "").trim().toUpperCase();
  if (!ticker) return json({ error: "冇提供股票代號" });
  try {
    const rows = await fetchHistory(ticker, -2208988800, Math.floor(Date.now() / 1000));
    const values = rows.map((r) => r.high);
    const dates = rows.map((r) => r.date);
    const useLog = !values.some((v) => v <= 0);
    const { bands, lastBands, nFuture } = computeChannel(values, useLog, 0.25);
    const vals = values.map(round7);
    return json({
      ticker,
      dates,
      future_dates: futureDates(dates, nFuture),
      values: vals,
      highs: vals,
      lows: rows.map((r) => round7(r.low)),
      closes: rows.map((r) => round7(r.close)),
      bands,
      last_bands: lastBands,
      use_log: useLog,
      source: "Yahoo Finance (Netlify Function)",
    });
  } catch (e) {
    return json({ error: "下載或計算過程出錯: " + e.message });
  }
};
