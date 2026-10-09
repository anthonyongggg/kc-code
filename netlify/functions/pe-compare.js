// PE 比較: 網站版暫時未支援 (Yahoo 嘅 PE 數據要 cookie 驗證，serverless 環境好易失效)
const { json } = require("./_lib");
exports.handler = async () =>
  json({ error: "網站版暫時未支援 PE 比較 (只有本機 Python 版可用)" });
