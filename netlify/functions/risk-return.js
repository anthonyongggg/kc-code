// 取代 Python 嘅 /api/risk-return
const { fetchHistory, popStd, json } = require("./_lib");

exports.handler = async (event) => {
  const qs = event.queryStringParameters || {};
  const ticker = (qs.ticker || "").trim().toUpperCase();
  const start = (qs.start || "2000-01-01").trim();
  const end = (qs.end || new Date().toISOString().slice(0, 10)).trim();
  const result = {
    ticker, start_date: start, end_date: end,
    actual_start_date: null, actual_end_date: null,
    cagr: null, annualized_volatility: null, total_return: null, error: null,
  };
  if (!ticker) { result.error = "冇提供股票代號"; return json(result); }
  try {
    const p1 = Math.floor(new Date(start + "T00:00:00Z").getTime() / 1000);
    const p2 = Math.floor(new Date(end + "T00:00:00Z").getTime() / 1000);
    const rows = await fetchHistory(ticker, p1, p2);
    if (rows.length < 2) { result.error = "呢段日期範圍入面嘅有效數據少過2個交易日，冇辦法計算"; return json(result); }
    const closes = rows.map((r) => r.close);
    const startPrice = closes[0], endPrice = closes[closes.length - 1];
    result.actual_start_date = rows[0].date;
    result.actual_end_date = rows[rows.length - 1].date;
    const years = (new Date(result.actual_end_date) - new Date(result.actual_start_date)) / 86400000 / 365.25;
    if (years <= 0) { result.error = "日期範圍太短，冇辦法計算年化回報"; return json(result); }
    if (startPrice <= 0) { result.error = "期初價格異常 (<=0)，冇辦法計算回報率"; return json(result); }
    const rets = [];
    for (let i = 1; i < closes.length; i++) rets.push(closes[i] / closes[i - 1] - 1);
    // pandas std() 用 ddof=1 (樣本標準差)
    const n = rets.length;
    const sampleStd = popStd(rets) * Math.sqrt(n / (n - 1));
    result.cagr = Math.round((Math.pow(endPrice / startPrice, 1 / years) - 1) * 10000) / 100;
    result.total_return = Math.round((endPrice / startPrice - 1) * 10000) / 100;
    result.annualized_volatility = Math.round(sampleStd * Math.sqrt(252) * 10000) / 100;
  } catch (e) {
    result.error = e.message;
  }
  return json(result);
};
