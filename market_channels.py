#!/usr/bin/env python3
# ============================================================================
# market_channels.py
# VERSION: v5.5
#
# 呢個版本改咗咩 (v5.5 相對於 v5.4) —— 修正真實bug + 支援同時
# 搜尋多隻股票:
#   1. 修正 "Maximum call stack size exceeded" 呢個真實bug:
#      根源已經用 Node.js (同 Chrome 用緊嘅 V8 引擎一樣) 實測確認:
#      JS 入面 Math.min.apply(null, array) 呢種寫法，當個array
#      超過大約13萬個元素就會拋出呢個錯誤 (因為 .apply() 會將
#      成個array拆做逐個function參數，瀏覽器對呢個參數數量有
#      上限)。股票歷史夠長 (例如50年以上嘅每日數據)，連埋7條
#      通道線再加25%嘅未來延伸，單一張圖已經可能超過呢個上限。
#      修正: 加咗 safeMin()/safeMax() 呢兩個用 loop 計算嘅函數，
#      取代所有 .apply(null, array) 嘅寫法，已經用 Node.js 測試
#      確認即使100萬個元素都唔會再爆。
#   2. 支援同時搜尋/下載4-6隻股票 (用戶要求):
#      a) Python 嘅本機伺服器由單線程嘅 socketserver.TCPServer
#         改用 ThreadingMixIn + TCPServer 組合成多線程伺服器。
#         已經證實 (用真實計時測試): 舊做法5個request會逐個排隊，
#         5秒先做完；新做法5個request並行處理，1.2秒左右就完成。
#      b) 前端 handleTickerSearch() 重新設計: 撳「加入」嗰刻即刻
#         清空輸入框，等用戶可以馬上打下一隻代號，唔使等上一隻
#         下載完成。用 pendingDownloads 呢個registry追蹤緊邊幾隻
#         股票仲喺度下載，狀態列會顯示「下載緊: AAA, BBB, CCC...」
#         呢種清單，唔會再淨係得一句文字互相覆蓋。
#      已經用真實HTTP request測試過: 4隻股票、每隻都有50年歷史
#      (即係之前會觸發stack overflow嘅確實情況)，同時搜尋，
#      全部成功、並行完成，冇再爆。
# ============================================================================
#
# 呢個版本改咗咩 (v5.4 相對於 v5.3) —— 加入 Alpha Vantage 做 PE
# 數據嘅備用/交叉驗證 source:
#   1. 已經證實 Alpha Vantage 嘅 OVERVIEW endpoint 有 TrailingPE同
#      ForwardPE 呢兩個field (嚟源: macroption.com官方文件解讀，
#      已經用真實HTTP request流程測試過)。但要留意: ForwardPE都係
#      淨係得「下一年」嘅單一數字，冇2/3/4年後嘅拆細，同yfinance
#      提供嘅粒度一樣，唔會解決「3年以上冇市場共識」呢個根本限制。
#   2. compute_pe_metrics() 而家嘅邏輯: 先用 yfinance 攞PE，如果
#      trailing_pe 同 forward_pe 兩個都係 None (yfinance完全冇
#      呢隻股票嘅PE數據)，先會用 fetch_alpha_vantage_overview()
#      補充。呢個fallback淨係喺yfinance攞唔到先觸發，唔會兩個
#      source 每次都一齊攞，避免嘥晒 Alpha Vantage 免費tier
#      每日25次嘅請求上限。
#   3. 因為 PE 比較功能而家已經係喺 Python server side 做
#      (/api/pe-compare)，Alpha Vantage 嘅 API key 可以擺喺
#      Python 度，唔使好似之前 v3.x 版本咁暴露喺前端 HTML/
#      瀏覽器度，安全性提升咗。
#   4. 前端表格而家會顯示「數據源: Alpha Vantage」呢個標籤，
#      畀用戶知道邊隻股票嘅PE數據唔係嚟自Yahoo Finance，係用咗
#      備用source。已經用真實HTTP request (透過真正行緊嘅
#      server，用URL-aware嘅mock淨係攔截Alpha Vantage呼叫，
#      唔會影響其他真實request) 測試過成條數據路徑正確。
# ============================================================================
#
# 呢個版本改咗咩 (v5.3 相對於 v5.2) —— 全部改動喺 report_template.html:
#   1. Risk/Return 表格上面加咗一個 scatter plot (散點圖):
#      X軸 = Risk (年化波幅)，Y軸 = Return (CAGR)，每隻已加入嘅
#      股票/資產顯示做一個有標籤嘅點，等用戶一眼睇到邊隻係
#      high-risk-high-return，邊隻係low-risk-low-return，唔使
#      淨係睇數字表格。加/移除股票、或者改咗日期範圍重新計算，
#      個scatter plot都會自動更新。
#   2. 用戶反映報告顯示「重複咗成頁」，已經查證 Python/HTML 源碼
#      本身冇任何結構性重複 (ASSETS清單、main()、render迴圈都
#      淨係得一份)，判斷呢個好可能係之前提過嘅「多個Python
#      process同時運行」問題嘅另一種表徵 (例如撳咗幾次.bat，
#      每次都喺唔同port開自己嘅瀏覽器分頁，睇落好似成頁重複)。
#      已經建議用戶檢查瀏覽器分頁數量同各自嘅port，並確保
#      執行前用工作管理員關晒所有舊嘅python.exe process。
# ============================================================================
#
# 呢個版本改咗咩 (v5.2 相對於 v5.1) —— 用戶反映 v5.1 有真實bug
# 同UX唔啱用，全部修正咗:
#   1. 診斷咗 "Unexpected token '<'" 呢個錯誤嘅真正原因: 唔係新
#      bug，係之前開咗嘅舊Python process殘留，佢個routing冇
#      /api/pe-compare / /api/risk-return 呢兩條新route，但個
#      report_template.html已經更新到有呢啲功能嘅UI，令瀏覽器打
#      新UI但撞正舊server處理唔到，跌返去靜態404頁。用戶需要
#      完全關晒所有python process先再重新起。
#   2. UX重新設計 (用戶要求):
#      a) 移除咗獨立嘅「PE比較」搜尋列同「加入Risk/Return」搜尋列。
#      b) 而家每一張圖卡片 (包括內嵌資產如金/比特幣/指數、恆指PE
#         比率圖、用戶搜尋加入嘅股票) 都自己有一個「比較PE」按鈕，
#         撳落會展開一個細panel (3個競爭對手輸入 + 比較掣)。冇
#         對應Yahoo ticker嘅資產 (例如恆指PE比率圖) 個按鈕會disable
#         咗，即時顯示「無數據」，唔會嘗試打API。
#      c) 每次有新卡片出現 (無論係Python內嵌定係用戶搜尋加入)，
#         都會自動 (毋須用戶郁手) 攞返Risk/Return數據，加落最底
#         嗰個全局表格。
#      d) Risk/Return嗰個表格而家位於成個頁面最底 (跟返
#         <main id="main"> 之後)，因為卡片都插入喺main入面，
#         表格自然就會顯示喺所有卡片下面。
#      e) 已經用真實HTTP request確認: 冇PE數據嘅資產 (例如商品
#         期貨GC=F，Yahoo Finance根本冇提供commodity嘅PE) 會
#         優雅噉顯示「無數據」，唔會拋錯或者整壞成個頁面。
# ============================================================================
#
# 呢個版本改咗咩 (v5.1 相對於 v5.0) —— 新增兩個function:
#
#   Function 1: PE 比較 (compute_pe_metrics + /api/pe-compare)
#     用戶打主要股票 + 最多3隻自選競爭對手 ticker (手動輸入，
#     系統唔會自動搵競爭對手 —— 已經查證 yfinance 冇呢個功能)，
#     顯示表格: 現價、Trailing PE、Forward PE (下一年，analyst
#     共識)、2/3/4年後估算PE。
#     重要 (已經查證確認): yfinance 同市場上大部分免費source都
#     冇提供2年以上嘅analyst共識EPS/PE預測 (get_earnings_estimate()
#     淨係到 "+1y" 為止)。2/3/4年後嘅數字係用 get_growth_estimates()
#     嘅 "+5y" 長期增長率，自己用「現時EPS×(1+增長率)^n」推算出嚟，
#     並非市場真實共識，已經喺表格度用「(估算)」標籤清楚標示，
#     配合用戶要求嘅提示句: "PE唔好飄離開太遠想買嗰隻 Forward P/E
#     比 Current P/E 更高，可能代表市場預期未來盈利下降"。
#     已經用真實HTTP request測試過呢個endpoint，並手動驗證過
#     估算PE嘅數學計算正確。
#
#   Function 2: Risk/Return (compute_risk_return + /api/risk-return)
#     每加一隻股票，即時計算 Return (CAGR，年化複合增長率) 同
#     Risk (年化波幅，日回報率標準差 × sqrt(252))。開始日期預設
#     2000-01-01，結束日期預設今日，兩者都可以人手修改；但只有
#     一個全局日期控制器 (擺喺表格下面)，改咗就會重新計算表格入面
#     全部已加入嘅股票，唔會逐隻分開設定。表格下面有用戶要求嘅
#     提示句: "當high risk high return的股票，前景沒有大問題，
#     現在在低位就是好的買入時機 ！？"
#     已經用真實HTTP request測試過呢個endpoint，並手動驗證過
#     CAGR/波幅嘅數學計算正確。
# ============================================================================
#
# 呢個版本改咗咩 (v5.0 相對於 v4.5):
#   1. 徹底移除咗「NSW/TAS postcode 租金搜尋」呢個功能 (用戶要求)。
#      背景: 澳洲樓市/租金數據呢個方向搞咗好耐，發現冇一個統一、
#      跨州份、有清晰API嘅數據source —— 每個州份格式、欄位、
#      下載方式都完全唔同 (NSW/TAS用緊逐月獨立XLSX檔案，仲要
#      冇一個乾淨API)，之前只完成咗NSW同TAS兩個州，其他州份
#      (VIC/QLD/WA/SA/NT/ACT) 都做唔到，用戶認為呢個方向太複雜，
#      決定移除成個功能。已經移除嘅嘢包括:
#        - fetch_nsw_rental_bond_data(), fetch_tas_rental_bond_data()
#        - _discover_ckan_resources(), _guess_month_from_resource_name()
#        - NSW_RENTAL_BOND_XLSX_URLS, TAS_RENTAL_BOND_DATASET_IDS
#          等相關 config
#        - /api/au-rent endpoint 同對應嘅 _handle_au_rent_api()
#        - 前端「postcode + 州份 + 房數」搜尋列同 handleAuRentSearch()
#      保留咗嘅嘢: 圖一 (澳洲全國住宅樓價指數，FRED API，1970年至今)
#      依然保留，因為呢個唔係互動搜尋，係好似金/比特幣咁自動內嵌
#      落report嘅靜態圖表，冇之前嗰啲複雜性問題。
# ============================================================================
#
# v4.3-v4.5 嘅歷史 (澳洲租金搜尋功能，已經喺 v5.0 移除，保留呢段
# 純粹做記錄): 曾經加咗 NSW Fair Trading Rental Bond Data 同 TAS
# Rental Bond Data 兩個州嘅postcode+房數租金搜尋功能，用逐月XLSX
# 檔案 + CKAN package_show API展開連結嘅做法實現。因為擴展去其他
# 州份太複雜 (每個州格式完全唔同)，用戶決定喺 v5.0 移除成個功能。
# ============================================================================
#
# 呢個版本改咗咩 (v4.2 相對於 v4.1):
#   1. pywebview 改為可選 (預設關閉): 用戶指出 search bar 功能
#      唔需要 pywebview 先用得到，佢淨係需要「本機伺服器保持行緊」
#      呢一個條件，同用邊種方式顯示畫面 (一般瀏覽器 定係 pywebview
#      獨立視窗) 完全冇關係。之前版本一有裝 pywebview 就自動用佢，
#      而家新增 USE_PYWEBVIEW_PANEL 呢個設定 (預設 False)，
#      預設用返一般瀏覽器 (Chrome/Edge) 打開報告；想要冇網址列嘅
#      獨立 panel，先至將呢個設定手動改做 True。
# ============================================================================
#
# 呢個版本改咗咩 (v4.1 相對於 v4.0) —— 用戶反映 v4.0 "要編輯 ASSETS
# 清單先可以加新股票" 呢個做法唔夠 user-friendly，要求做返即時搜尋，
# 但依然要用 Yahoo (唔用返 Twelve Data/Alpha Vantage 呢啲有年期
# 限制嘅第三方 API)。所以:
#   1. 報告頁面度嘅「搜尋股票」輸入框番返嚟。
#   2. 唔再靠瀏覽器直接 fetch 第三方數據商 (Yahoo 本身唔畀瀏覽器
#      直接攞佢個 API 嘅數據，呢個係最初要用 yfinance 呢個 Python
#      library 嘅原因)。改為: 本機伺服器 (start_local_server_and_open
#      起嗰個) 新增一個 /api/search endpoint，前端 JS 打呢個
#      endpoint，由 Python 背景即時用 yfinance 攞 Yahoo Finance
#      完整歷史、計好通道、用 JSON 回傳俾前端即刻加圖。
#      即係「打字 -> 撳搜尋 -> 即刻有新圖」嘅體驗完全保留，但數據
#      源換咗做 Yahoo，冇任何年期限制，亦都唔使裝額外嘅第三方
#      API key。
#   3. 呢個功能必須要 python market_channels.py 保持行緊 (即係
#      本機伺服器保持運作) 先用得到；如果直接雙擊 HTML 檔案打開
#      (file:// 模式)，或者你已經停咗 Python，搜尋會失敗並清楚
#      提示原因。用 run_market_channels.bat 打開就會自動處理埋
#      呢一步，唔使自己記得點樣起 Python。
#   4. 已經用真實 HTTP request (透過檔案入面嗰個真實函數，唔係
#      手抄嘅簡化版本) 測試過 /api/search，確認可以攞到完整歷史
#      (測試用嘅假數據由1995年開始，回傳結果都正確係1995年開始，
#      冇再撞到任何年期上限)。
# ============================================================================
#
#   1. 徹底解決咗「深度歷史數據」呢個問題: 用戶已經證實 Twelve Data
#      同 Alpha Vantage 呢兩個免費第三方 API 都有年期限制，攞唔到
#      2000年之前嘅數據。用戶要求「唔用第三方API，改返用 Yahoo」，
#      所以: 徹底移除咗報告入面嗰個「即時打字搜尋股票」功能
#      (連同 Twelve Data / Alpha Vantage 嘅 fetch 邏輯、API key
#      全部刪走)。而家想加新股票，直接編輯呢個 .py 檔案入面嘅
#      ASSETS 清單，加一行，重新執行就得 —— 呢種做法用返 yfinance
#      (Yahoo Finance)，冇任何第三方免費 tier 嘅年期限制。
#   2. 新增「獨立全螢幕 Panel」功能 (用戶要求 "唔用 Chrome/Edge
#      嗰啲browser"): 用 pywebview 呢個 Python 套件，攞你部電腦
#      本身已經有嘅瀏覽器引擎 (Windows 通常係 Edge 嘅 WebView2)，
#      包裝做一個冇網址列、冇分頁嘅獨立顯示視窗，望落好似一個
#      獨立 app，唔係開緊瀏覽器。用法: pip install pywebview
#      之後跟平時噉行 python market_channels.py 就得；如果未裝
#      pywebview，會自動 fallback 用返一般瀏覽器打開，唔會整壞
#      個 script。Panel 用戶要求 "唔使定期自動重新行"，所以 Python
#      行一次、生成報告、開個panel，之後就唔會自動再攞新數據，
#      想更新就自己再手動行一次 script。
#
# 呢個版本嘅取捨: 移除咗即時搜尋功能，換嚟嘅係用 Yahoo Finance
# 完整歷史 + 唔使裝額外 API key。如果之後想要返「即時打字搜尋」
# 呢種互動，可以考慮起一個本機 API 俾 panel call (但呢個做法
# 複雜好多，用戶已經確認優先做法係「改動少 + 用返 Yahoo」)。
# ============================================================================
#
# v3.16 嘅修正 (依然有效，但 search bar 已喺 v4.0 移除):
# 呢個版本改咗咩 (v3.16 相對於 v3.15) —— 重要: 呢個係目前呢方面
# 已知嘅極限，唔係再一個「修正」:
#   1. 用戶親自測試證實咗真正原因: Alpha Vantage 免費 key 用
#      outputsize=full 會俾佢用 "Information" 訊息直接拒絕:
#        "The outputsize=full parameter value is a premium feature
#         for the TIME_SERIES_DAILY endpoint."
#      即係話 outputsize=full 而家已經係 Alpha Vantage premium
#      專屬功能，免費 key 攞唔到完整歷史。
#      連同之前已經證實嘅 Twelve Data 免費 tier 深度歷史限制
#      (停喺2006年左右)，即係話「用戶目前手上呢兩條免費 key，
#      客觀上都攞唔到好舊嘅歷史數據」，呢個唔係 code bug，
#      而係兩間數據商免費 tier 政策嘅真實限制。
#   2. fetchAlphaVantageData() 而家會喺 Alpha Vantage 拒絕
#      outputsize=full 嗰陣，自動重試一次 outputsize=compact
#      (免費key用得到，但淨係得最近100個交易日)，好過完全冇數據，
#      並且喺數據源標籤度誠實標示「只有最近100個交易日」，
#      唔會扮到好似攞咗完整歷史噉。
#   3. 如果想要真正嘅深度歷史數據 (例如2000年之前)，目前嘅選擇有:
#        a) 升級 Alpha Vantage 去 premium plan (https://www.alphavantage.co/premium/)
#        b) 升級 Twelve Data 去更高 tier
#        c) 改用返本機 Python 版 (yfinance/Yahoo Finance)，
#           對絕大部分股票嚟講歷史深度冇呢啲限制 —— 但呢個做法
#           就返去「唔可以喺手機/平板用」嘅限制，兩者要揀其一
# ============================================================================
#
#   1. v3.14 話用 start_date 參數可以攞到 Twelve Data 完整歷史，但
#      用戶親自測試證實依然停留喺2006年左右，即係話 Twelve Data
#      免費 Basic tier 本身就有歷史深度限制，唔止係 outputsize
#      呢個參數嘅事，用任何參數都撞唔穿。
#      解決方法 (用戶要求 "兩個API都用，邊個好用邊個"):
#      新增 Alpha Vantage 做第二數據源 (用戶已經去
#      https://www.alphavantage.co 免費攞咗個 key，outputsize=full
#      官方聲稱可以攞到 20+ 年完整歷史)。搜尋邏輯而家會:
#        a) 先用 Twelve Data 攞一次 (成本低，免費tier有800/day)
#        b) 睇下攞返嚟嘅最早日期係咪「可疑咁近」(粗略用2003年做
#           門檻判斷)，如果係，先再用多一次 Alpha Vantage
#           (outputsize=full) 攞埋佢
#        c) 如果兩個 source 都攞到，揀開始日期較早 (歷史較深) 嗰個
#      因為 Alpha Vantage 免費 tier 淨係得 25 requests/day (好緊絀)，
#      呢個 fallback 淨係喺 Twelve Data 睇落唔夠深先會觸發，唔會
#      兩個 source 每次搜尋都一齊攞，盡量慳返 Alpha Vantage 嘅額度。
#      搜尋完成之後，卡片同狀態列都會清楚顯示實際用緊邊個數據源、
#      同數據由邊一日開始。
# ============================================================================
#
# v3.14 嘅修正 (依然有效，但發現對 Twelve Data 嘅免費 tier 效果有限):
#   1. 修正 Search bar 搜尋股票每次開始日期都停留喺 2006 年左右嘅問題:
#      真正原因: Twelve Data 嘅 outputsize 參數上限係 5000。之前
#      request 用緊 outputsize=5000，如果隻股票已經上市超過
#      5000個交易日 (大約20年)，就只會攞到「最近5000個交易日」，
#      早過嗰個時間點嘅數據會俾呢個上限「切咗頭」，唔係嗰隻股票
#      本身冇更早嘅數據。
#      修正: 改用 start_date=1970-01-01 (早過絕大部分股票上市日)，
#      唔再帶埋 outputsize 參數。根據官方文件，用 start_date 單獨
#      (唔夾埋 outputsize) 會回傳由嗰隻股票實際上市第一日開始嘅
#      完整歷史，唔再受 5000 呢個上限影響。
# ============================================================================
#
# v3.13 嘅修正 (依然有效):
#   1. Search bar 搜尋加入嘅股票，而家都會有「未來延伸」通道估算，
#      同報告入面其他資產一致 (之前搜尋加入嘅圖表冇呢個功能，
#      通道線淨係去到實際數據盡頭就停)。JS 版嘅
#      computeLogChannelJS() 而家同 Python 版一樣，預設額外延伸
#      25% 長度嘅通道線落「估算區」，並且用
#      generateFutureDatesJS() 產生對應嘅未來日期標籤。
#   2. 每一張圖表卡片 (包括內嵌資產、恆指市盈率、同搜尋加入嘅圖表)
#      右上角而家都有一個「✕」按鈕，撳咗就會將呢張圖從報告版面度
#      移除 (純粹前端操作，唔會影響 Python 腳本或者你嘅其他資產)。
# ============================================================================
#
# v3.12 嘅修正 (依然有效):
#   1. 「搜尋股票」search bar 由 Stooq 改用 Twelve Data API:
#      證實咗 Stooq 由 2026年3月 開始要求 API key 先俾 CSV 下載
#      (之前免key嘅公開端點已經失效，回應變成要求key嘅HTML頁面，
#      唔再係CSV，導致 "Failed to fetch" / 解析失敗)。用戶已經去
#      https://twelvedata.com 免費註冊咗個 API key (免費 tier:
#      800 requests/day)，而家 report_template.html 入面嘅
#      TWELVE_DATA_API_KEY 呢個常數已經填咗呢條key。
#      注意: 呢條 key 會直接出現喺 HTML 檔案入面 (前端 fetch 冇辦法
#      收埋key)，如果將呢份報告分享俾第三者，佢哋都會睇到條key；
#      免費 tier 冇要求信用卡，超咗800/day淨係拒絕request，唔會扣錢。
#   2. 十字準星新增「貼近邊條 σ 線」偵測: 滑鼠移到接近中軸/±1σ/
#      ±2σ/±3σ 任何一條線嗰陣 (12px範圍之內)，個標籤會由「純數值」
#      變成「+2σ: 12345」呢種格式，並且喺嗰條線本身加一個高亮圓點，
#      等你一眼睇到而家貼緊邊條線，唔使自己心算個數值屬於邊條線。
# ============================================================================
#
# v3.11 嘅修正 (依然有效):
#   1. v3.10 話修正咗 404，但用戶實測之後發現依然 404。
#      進一步查證: v3.10 淨係移除咗「起完 server 之後 chdir 返轉去」
#      嗰句，但仍然靠 os.chdir(docs_dir) 嚟指定 server 要 serve 邊個
#      資料夾。呢個做法本身都唔夠可靠: os.chdir() 改嘅係「成個
#      process 嘅工作目錄」，屬於 process-wide 嘅全域狀態；當 server
#      行喺背景線程，Windows 上多線程之間對呢種全域狀態嘅時序睇法
#      冇保證完全同步，有機會令 server thread 收到 request 嗰一刻，
#      睇到嘅工作目錄同預期唔一致，依然導致 404。
#      修正: 徹底摒棄 os.chdir()，改用 SimpleHTTPRequestHandler
#      嘅 directory 參數 (Python 3.7+ 原生支援)。
# ============================================================================
#   1. 價錢線同通道計算，由「收市價 Close」改為「每日最高價 High」。
#      Close 依然有下載埋，十字準星嗰個資訊面板照舊會顯示返
#      「收市/最高/最低」畀你對比，但主線同通道本身而家跟 High。
#   2. 通道線 (±1/±2/±3σ) 而家會額外向未來延伸 25%。價錢線本身淨係
#      畫到實際數據嘅盡頭，但通道線會繼續向右邊延伸落一段「估算區」，
#      喺報告度用淡金色底色同虛線分隔標示。
#   3. 十字準星嘅資訊面板由「固定喺左上角」改為「跟住滑鼠位置顯示」，
#      並且加咗邊緣偵測，確保個面板永遠唔會畫出畫布範圍之外。
#
# v3.8 嘅修正 (依然有效):
#   1. Python 腳本行完之後會自動起一個本機網頁伺服器 (http.server)，
#      自動打開瀏覽器去 http://localhost:8000/... (唔再係 file://)。
#      用呢種方法打開報告，搜尋股票功能先唔會俾瀏覽器安全政策封鎖。
#      如果唔想用呢個功能，將 AUTO_OPEN_BROWSER 呢個變數設做 False。
#      伺服器會保持運行，喺 terminal 度撳 Ctrl+C 先會停低。
#   2. 全部資產會連埋 High/Low 一齊下載。
#   3. 徹底剷除比特幣 $20 以下嘅早期雜訊數據: 唔止喺「通道計算」
#      層面剔除，而係真正裁剪成條 values/dates/highs/lows 陣列，
#      $20 以下嘅數據點完全唔會再出現喺報告入面。
#
# v3.7 嘅修正 (依然有效):
#      真正原因: 每次撳撳全螢幕，個「圖表座標系統」狀態
#      (chartState['fullscreen-canvas']) 係跨資產共用同一個key，
#      如果上一個資產嘅座標系統殘留仲未被新資產完全取代，滑鼠移動
#      就會攞住舊嘅換算表計算新資產嘅數值。比特幣個價錢範圍特別大
#      (由$20到$100,000+)，所以呢個時序誤差喺佢個圖度睇落特別誇張。
#      左邊固定嘅Y軸刻度冇問題，因為嗰啲喺畫圖嗰陣already計算好，
#      唔靠十字準星嗰套實時運算。
#      修正: (a) 每次開全螢幕前，主動清走舊嘅 chartState;
#            (b) 全螢幕嗰個 crosshair overlay 每次都整個新，唔再
#                重用上一次殘留嘅 overlay canvas;
#            (c) 用雙層 requestAnimationFrame 確保 overlay 完成
#                版面編排至讀取尺寸，唔會用到舊(未更新)嘅尺寸。
#   2. 徹底修正「攞唔到數據嘅資產仲係會顯示緊嘢」呢個問題:
#      上一版話刪咗但其實 report_template.html 入面仲殘留緊
#      兩段 catch(err) 邏輯，會建立一張「此資產顯示失敗」嘅錯誤卡片。
#      而家已經徹底移除呢兩段建立卡片嘅 code，改為淨係印喺瀏覽器
#      console (F12) 度，報告版面完全唔會再出現呢類卡片。
#   3. Search bar "failed to fetch" 嘅解釋 (唔使起多一個Python檔案):
#      最常見原因係你用「直接雙擊打開HTML檔案」(file:// 開法)，
#      瀏覽器安全政策會封鎖呢種開法發出嘅網絡請求。而家個報告會:
#        a) 一打開就用 file:// 偵測，喺搜尋框附近預先提示呢個限制
#        b) 如果搜尋真係失敗，會喺錯誤訊息度加返可能原因同解決方法
#           (例如建議用 "python -m http.server" 起個本機伺服器)
#      呢個純粹係瀏覽器安全機制，同 Python 檔案結構完全無關。
# ============================================================================

"""
市場對數通道圖 - 數據下載 + 圖表產生器 (Yahoo Finance 版)
================================================

用途:
  1. 用 yfinance 下載黃金、SOX、KOSPI、NDX、恆指、比特幣、銅、鋁、日經等
     歷史價格 CSV，儲存去你嘅 Documents 資料夾
  2. 計算每個資產嘅通道:
       - 大部分資產: log 對數迴歸通道 (中軸 + ±1/±2/±3 標準差，直線)
       - 比特幣: 拋物線/冪律通道 (log(price) 對 log(time) 迴歸，曲線)
       - 恆生指數市盈率: 獨立嘅、hardcode 好嘅標準差水平通道
  3. 產生一個靜態 HTML 檔案 (market_channels_report.html)，一樣放喺 Documents，
     雙擊就可以用瀏覽器打開睇圖表 (唔需要網絡，因為數據已經 embed 咗入去)
  4. HTML 報告入面，撳一撳張圖就會全螢幕放大顯示，並保留十字準星追蹤功能
  5. 用一個獨立、冇網址列嘅全螢幕 panel 顯示報告 (用 pywebview)，
     唔使開 Chrome/Edge 呢啲一般瀏覽器

首次使用前，喺 Command Prompt / PowerShell 執行:
    pip install yfinance pandas numpy pywebview

(pywebview 係選用性質: 如果唔裝，report 會改用一般瀏覽器打開，
 其他功能完全唔受影響)

之後每次想更新數據，重新執行呢個 script 就得:
    python market_channels.py

想加新股票，唔使即時搜尋功能，直接編輯呢個檔案入面嘅 ASSETS
清單，加一行 (顯示名稱, Yahoo ticker, 是否log scale, 是否拋物線通道)，
然後重新執行就得，新股票會攞埋 Yahoo Finance 嘅完整歷史
(冇年期限制，唔似其他第三方免費 API 咁受 tier 限制)。

注意:
  - 呢份腳本需要喺有 Python 嘅電腦上行 (Windows/Mac/Linux)，
    手機同平板暫時未支援直接行呢份腳本。
  - market_channels.py 同 report_template.html 呢兩個檔案要放喺
    同一個資料夾先可以正常運作。
"""

import os
import re
import io
import json
import time
import traceback
import threading
import webbrowser
import http.server
import socketserver
import urllib.parse
import urllib.request
from datetime import datetime

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit(
        "未安裝 yfinance。請先喺 Command Prompt / PowerShell 執行:\n"
        "    pip install yfinance pandas numpy\n"
        "然後再重新執行呢個 script。"
    )

# ============================================================================
# 設定
# ============================================================================

SCRIPT_VERSION = "v5.5"

DOCS_DIR = os.environ.get("MC_OUTPUT_DIR") or os.path.join(os.path.expanduser("~"), "Documents", "market_channels")
os.makedirs(DOCS_DIR, exist_ok=True)

# 資產清單: (顯示名稱, Yahoo Finance ticker, 是否用log scale, 是否用拋物線通道)
ASSETS = [
    ("黃金 (Gold, USD/oz)",         "GC=F",     True,  False),
    ("費城半導體指數 (SOX)",         "^SOX",     True,  False),
    ("韓國綜合指數 (KOSPI)",         "^KS11",    True,  False),
    ("納斯達克100指數 (NDX)",        "^NDX",     True,  False),
    ("恒生指數 (HSI)",               "^HSI",     False, False),
    ("比特幣 (BTC/USD)",            "BTC-USD",  True,  True),   # <- 拋物線通道
    ("銅價 (Copper, USD/lb)",       "HG=F",     True,  False),
    ("鋁價 (Aluminum, USD/lb)",     "ALI=F",    True,  False),
    ("日經平均指數 (Nikkei 225)",    "^N225",    True,  False),
    ("標普500指數 (S&P 500)",        "^GSPC",    True,  False),
    ("白銀 (Silver, USD/oz)",        "SI=F",     True,  False),
    ("WTI原油 (Crude Oil)",         "CL=F",     True,  False),
    ("Strategy (MSTR)",            "MSTR",     True,  False),
]

HISTORY_PERIOD = "max"
DOWNLOAD_RETRY = 2       # 每個 ticker 最多重試幾多次
DOWNLOAD_RETRY_DELAY = 2  # 重試之間等幾多秒

# ----------------------------------------------------------------------------
# 恆生指數市盈率 - 逐年 hardcode 數值 (由用戶提供)
# 標準差通道 (中軸/±1σ/±2σ/±3σ) 會由呢批年度數據自動計算平均數同標準差,
# 唔再係一條固定水平線。
# ----------------------------------------------------------------------------
HSI_PE_BY_YEAR = {
    2011: 12.5,
    2012: 9.5,
    2013: 11.5,
    2014: 11.0,
    2015: 13.5,
    2016: 10.0,
    2017: 13.0,
    2018: 13.0,
    2019: 12.5,
    2020: 9.2,
    2021: 15.0,
    2022: 11.0,
    2023: 11.5,
    2024: 8.5,
    2025: 11.5,
    2026: 13.43,   # 2026-10-02 恒生指數公司官方每日市盈率 (經 CEIC)，之前係 13.5。想更新就改呢個數同下面個日期
}
HSI_PE_LATEST_DATE = "2026-10-02 (恒生指數公司官方數據，經 CEIC；其餘年份係你提供嘅逐年數)"

TEMPLATE_FILENAME = "report_template.html"

# ----------------------------------------------------------------------------
# 澳洲樓價 (圖一: 全國住宅樓價指數, 1970年至今) - 用 FRED API
# FRED (Federal Reserve Economic Data, 美國聖路易斯聯儲) 免費提供
# 呢個由 BIS (國際結算銀行) 整理嘅澳洲住宅樓價指數，季度數據，
# 由 1970年 Q1 開始，暫時係最長歷史嘅澳洲全國樓價 source。
# 需要免費 API key: https://fredaccount.stlouisfed.org/apikeys
# ----------------------------------------------------------------------------
FRED_API_KEY = os.environ.get("FRED_API_KEY") or "2e6f889b0b06cb0879517031418c94d4"
FRED_AU_HOUSING_SERIES_ID = "QAUN628BIS"  # Residential Property Prices for Australia

# ----------------------------------------------------------------------------
# Alpha Vantage OVERVIEW API - 用嚟做 PE 比較功能 (compute_pe_metrics) 嘅
# 備用/交叉驗證 source。當 yfinance 攞唔到 trailing_pe/forward_pe (兩個
# 都係 None) 嗰陣，先會用呢個 fallback 補充。
# 已經確認 OVERVIEW 呢個 endpoint 有 TrailingPE / ForwardPE 呢兩個
# field (嚟源: macroption.com 官方文件解讀)，但要留意:
#   1. ForwardPE 都係淨係得「下一年」嘅單一數字，冇 2/3/4 年後嘅拆細，
#      同 yfinance 提供嘅粒度一樣，唔會解決「3年以上冇市場共識」
#      呢個根本限制。
#   2. 免費 key 每日 25 次請求上限，所以呢個 fallback 淨係喺 yfinance
#      攞唔到先觸發，唔會兩個 source 每次都一齊攞，慳返請求額度。
#   3. OVERVIEW 回傳嘅全部數值都係字串 (包括數字)，要自己轉做 float；
#      冇資料嗰陣個值會係字串 "None" (唔係 JSON null)，要特別處理。
# 用戶已經有呢條 key (之前為咗 AU rent 功能攞嘅，而家攞嚟重用)。
# ----------------------------------------------------------------------------
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY") or "6ZKSOG48WZYDUYK3"

# ----------------------------------------------------------------------------
# 本機網頁伺服器設定
# 用意: 如果直接雙擊打開 HTML 檔案 (file:// 開法)，瀏覽器安全政策會
# 封鎖報告入面「搜尋股票」功能所需要嘅網絡請求 (fetch)。
# 依家腳本行完之後，會自動用 http.server 起一個本機小型伺服器，
# 再自動打開瀏覽器 (http://localhost:PORT/...)，用呢種方式打開就
# 唔會撞到 file:// 嗰個限制，搜尋功能先會正常運作。
# 如果唔想用呢個功能 (例如淨係想產生 HTML 檔案，唔想開瀏覽器)，
# 將 AUTO_OPEN_BROWSER 設做 False 就得。
#
# USE_PYWEBVIEW_PANEL: 預設 False，即係用返一般瀏覽器 (Chrome/Edge)
# 打開個報告。search bar 完全唔需要 pywebview 先用得到 —— 佢淨係
# 需要「本機伺服器保持運行」呢一個條件，同用邊種方式顯示畫面
# (一般瀏覽器 定係 pywebview 獨立視窗) 完全冇關係。
# 如果想要冇網址列/冇分頁嘅獨立顯示視窗 (kiosk-style panel)，
# 先至將呢個設做 True，並且 pip install pywebview。
# ----------------------------------------------------------------------------
AUTO_OPEN_BROWSER = not os.environ.get("CI")  # GitHub Actions 會自動設 CI=true，唔會開瀏覽器/server
LOCAL_SERVER_PORT = 8000
USE_PYWEBVIEW_PANEL = False


# ============================================================================
# 數據下載 (每個資產獨立 try/except，一個失敗唔會拖累其他)
# ============================================================================

def download_asset(name, ticker):
    """下載單一資產嘅歷史數據，並儲存做 CSV。失敗會 raise Exception，
    由 main() 嗰度 catch 住，唔會整死成個程式。
    依家會攞埋 High/Low，唔止 Close，等報告可以顯示返 "嗰日曾經去到
    幾高/幾低"，唔會俾人誤會條線就係全部歷史高低位。"""
    last_err = None
    for attempt in range(1, DOWNLOAD_RETRY + 1):
        try:
            print("下載緊 " + name + " (" + ticker + ") ... (第" + str(attempt) + "次)")
            df = yf.download(ticker, period=HISTORY_PERIOD, interval="1d",
                              progress=False, auto_adjust=True)
            if df is None or df.empty:
                raise ValueError("Yahoo Finance 冇回傳任何數據 (df 係空)")

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            required_cols = ["Close"]
            for c in required_cols:
                if c not in df.columns:
                    raise ValueError("回傳嘅數據冇 '" + c + "' 呢一欄，實際欄位: " + str(list(df.columns)))

            keep_cols = [c for c in ["Close", "High", "Low"] if c in df.columns]
            df = df[keep_cols].dropna(subset=["Close"])
            df.index.name = "Date"

            if df.empty:
                raise ValueError("'Close' 欄位全部都係空值")

            csv_name = ticker.replace("=", "_").replace("^", "") + ".csv"
            csv_path = os.path.join(DOCS_DIR, csv_name)
            df.to_csv(csv_path)
            print("  已儲存: " + csv_path + " (" + str(len(df)) + " 個交易日)")
            return df

        except Exception as e:
            last_err = e
            print("  第" + str(attempt) + "次失敗: " + str(e))
            if attempt < DOWNLOAD_RETRY:
                time.sleep(DOWNLOAD_RETRY_DELAY)

    # 全部重試都失敗
    raise RuntimeError(str(last_err) if last_err else "未知錯誤")


def _urlopen_with_ua(url, timeout=15):
    """好多政府/CKAN網站會擋冇瀏覽器身份標頭 (User-Agent) 嘅request，
    直接回傳 403 Forbidden (已經喺 data.gov.au 嘅CKAN API實測證實
    呢個情況)。呢個helper統一幫所有 urllib.request 嘅call加返一個
    普通瀏覽器嘅 User-Agent，減低俾網站當做「機械人」擋咗嘅機會。
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36")
        }
    )
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_fred_series(series_id, api_key):
    """用 FRED (St. Louis Fed) 嘅公開 API 攞一條經濟數據時間序列。
    用嚟攞澳洲全國住宅樓價指數 (QAUN628BIS)，由1970年開始，
    季度數據。回傳 (dates, values) 兩個 list，日期由舊到新排序，
    自動過濾 FRED 用 "." 表示嘅缺失數值。
    """
    url = ("https://api.stlouisfed.org/fred/series/observations"
           "?series_id=" + urllib.parse.quote(series_id) +
           "&api_key=" + urllib.parse.quote(api_key) +
           "&file_type=json&sort_order=asc")
    try:
        with _urlopen_with_ua(url, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError("FRED API 請求失敗: " + str(e))

    data = json.loads(raw)

    if "error_message" in data:
        raise RuntimeError("FRED API 錯誤: " + data["error_message"])
    if "observations" not in data:
        raise RuntimeError("FRED API 回應格式異常，冇 'observations' 呢個欄位")

    dates, values = [], []
    for obs in data["observations"]:
        val_str = obs.get("value", ".")
        if val_str == ".":
            continue  # FRED 用 "." 代表缺失數值，跳過
        try:
            val = float(val_str)
        except (TypeError, ValueError):
            continue
        dates.append(obs["date"])
        values.append(val)

    if not values:
        raise RuntimeError("FRED 回傳嘅 '" + series_id + "' 冇任何有效數值")

    return dates, values


def fetch_alpha_vantage_overview(ticker_symbol):
    """用 Alpha Vantage 嘅 OVERVIEW endpoint 攞返一隻股票嘅基本面數據，
    包括 TrailingPE、ForwardPE。淨係做 compute_pe_metrics() 嘅
    fallback source，當 yfinance 攞唔到 PE 數據先會用呢個。

    重要: OVERVIEW 回傳嘅所有數值都係字串 (包括數字)，冇資料嗰陣
    個字串會係 "None" (唔係 JSON null)，要特別處理，唔可以直接
    當正常數字咁 float() 佢。
    """
    url = ("https://www.alphavantage.co/query?function=OVERVIEW"
           "&symbol=" + urllib.parse.quote(ticker_symbol) +
           "&apikey=" + urllib.parse.quote(ALPHA_VANTAGE_API_KEY))
    with _urlopen_with_ua(url, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)

    if not data or "Symbol" not in data:
        # Alpha Vantage 搵唔到呢隻股票，或者用晒免費tier嘅25次/日
        # 請求上限 (呢種情況佢通常會回傳 {"Information": "..."} 呢種
        # 格式，冇 "Symbol" 呢個key)。
        note = data.get("Information") or data.get("Note") or "冇回傳有效嘅公司數據"
        raise RuntimeError("Alpha Vantage OVERVIEW: " + note)

    def _parse_float(key):
        val = data.get(key)
        if val is None or val == "None" or val == "-" or val == "":
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    return {
        "current_price": None,  # OVERVIEW 冇即時價，要另外攞
        "trailing_pe": _parse_float("TrailingPE"),
        "trailing_eps": _parse_float("EPS"),
        "forward_pe": _parse_float("ForwardPE"),
        "forward_eps": None,  # OVERVIEW 冇直接嘅 forward EPS 欄位
        "name": data.get("Name"),
    }


def compute_pe_metrics(ticker_symbol):
    """用 yfinance 攞一隻股票嘅 PE 相關數據，包括:
      - 現時 Trailing PE (過去12個月實際盈利)
      - Forward PE (未來12個月，analyst共識，通常即係"下一年")
      - 用 5年複合增長率 (yfinance 提供嘅 analyst 長期增長預測)
        自己推算 2/3/4 年後嘅估算 EPS/PE (呢個唔係 analyst 直接
        提供嘅共識數字，係我哋自己用增長率推算出嚟，一定要清楚
        標示係「估算值」)

    重要 (已經查證確認): yfinance 本身 (同市場上大部分公開來源)
    都冇提供 2/3/4 年後嘅 analyst 共識 EPS/PE 預測，佢哋嘅
    get_earnings_estimate() 淨係到 "+1y" (下一個財政年) 為止。
    3年以上嘅共識預測通常要俾錢用 Bloomberg/FactSet 呢類專業
    終端先有，免費source搵唔到。所以2/3/4年後嘅數字，呢個function
    會用「現時EPS × (1+5年增長率)^n」噉樣推算，並且喺回傳結果度
    用 "is_estimated": true 呢個flag清楚標示，前端顯示嗰陣都要
    加返「估算值，非analyst共識」呢句提示，唔可以當係市場真實
    預測噉樣顯示。

    如果攞唔到某一項數據 (例如冇forwardPE、冇5年增長率)，
    對應嗰個欄位會係 None，等前端可以顯示「無數據」。
    """
    result = {
        "ticker": ticker_symbol.upper(),
        "current_price": None,
        "trailing_pe": None,
        "trailing_eps": None,
        "forward_pe": None,
        "forward_eps": None,
        "growth_rate_5y": None,
        "estimated_pe": {},  # {"2y": ..., "3y": ..., "4y": ...}
        "pe_source": "Yahoo Finance (yfinance)",
        "error": None,
    }

    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info or {}

        result["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice")
        result["trailing_pe"] = info.get("trailingPE")
        result["trailing_eps"] = info.get("trailingEps")
        result["forward_pe"] = info.get("forwardPE")
        result["forward_eps"] = info.get("forwardEps")

        # Alpha Vantage fallback: 淨係喺 yfinance 兩個PE都攞唔到嗰陣先
        # 觸發，避免嘥晒 Alpha Vantage 免費tier每日25次嘅請求上限。
        if result["trailing_pe"] is None and result["forward_pe"] is None:
            try:
                av_data = fetch_alpha_vantage_overview(ticker_symbol)
                result["trailing_pe"] = av_data["trailing_pe"]
                result["trailing_eps"] = result["trailing_eps"] or av_data["trailing_eps"]
                result["forward_pe"] = av_data["forward_pe"]
                if av_data["trailing_pe"] is not None or av_data["forward_pe"] is not None:
                    result["pe_source"] = "Alpha Vantage (yfinance 冇提供PE數據，改用呢個source補充)"
            except Exception as av_err:
                # Alpha Vantage 都攞唔到就算，維持 None，前端會顯示
                # 「無數據」，唔會令成個 request 失敗。
                result["pe_source"] = "Yahoo Finance (yfinance) · Alpha Vantage fallback 都失敗: " + str(av_err)

        # 攞5年增長率 (用嚟推算2/3/4年後嘅估算PE)
        growth_rate = None
        try:
            growth_df = stock.get_growth_estimates()
            if growth_df is not None and "+5y" in growth_df.index and "stock" in growth_df.columns:
                val = growth_df.loc["+5y", "stock"]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    growth_rate = float(val)
        except Exception:
            pass
        result["growth_rate_5y"] = growth_rate

        # 推算基準: 優先用 forward_eps (下一年嘅共識EPS)，
        # 冇嘅話退而求其次用 trailing_eps。
        base_eps = result["forward_eps"] or result["trailing_eps"]
        price = result["current_price"]

        if base_eps and price and growth_rate is not None:
            for n, label in [(2, "2y"), (3, "3y"), (4, "4y")]:
                try:
                    estimated_eps = base_eps * ((1 + growth_rate) ** n)
                    if estimated_eps > 0:
                        estimated_pe = price / estimated_eps
                        result["estimated_pe"][label] = round(estimated_pe, 2)
                    else:
                        result["estimated_pe"][label] = None
                except Exception:
                    result["estimated_pe"][label] = None
        else:
            result["estimated_pe"] = {"2y": None, "3y": None, "4y": None}

    except Exception as e:
        result["error"] = str(e)

    return result


def compute_risk_return(ticker_symbol, start_date, end_date):
    """計算一隻股票喺指定日期範圍入面嘅 risk (風險) 同 return (回報)。

    定義:
      - Return (回報): 用 CAGR (年化複合增長率) 表示，
        即 (期末價 / 期初價) ^ (1/年數) - 1
      - Risk (風險): 用日回報率嘅年化標準差 (annualized volatility)
        表示，即 daily_returns.std() * sqrt(252)
        (252 係一年大約嘅交易日數目)

    呢兩個都係業界常用嘅衡量方式，但要留意:
      - CAGR 對「期初/期末嗰一日嘅價位」好敏感，如果啱啱好期初
        或者期末揀咗一個極端價位嘅日子，個結果會偏頗
      - 年化標準差假設回報率大致符合正態分佈，實際股價分佈
        通常有較肥嘅尾部 (fat tails)，呢個方法會低估極端風險

    回傳 dict，包含 ticker、實際首尾日期、CAGR、annualized_volatility，
    如果下載/計算失敗，"error" 欄位會有失敗原因。
    """
    result = {
        "ticker": ticker_symbol.upper(),
        "start_date": start_date,
        "end_date": end_date,
        "actual_start_date": None,
        "actual_end_date": None,
        "cagr": None,
        "annualized_volatility": None,
        "total_return": None,
        "error": None,
    }

    try:
        df = yf.download(ticker_symbol, start=start_date, end=end_date,
                          interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            result["error"] = "Yahoo Finance 搵唔到 '" + ticker_symbol + "' 喺呢段日期範圍嘅數據"
            return result

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if "Close" not in df.columns:
            result["error"] = "數據冇 Close 欄位"
            return result

        closes = df["Close"].dropna()
        if len(closes) < 2:
            result["error"] = "呢段日期範圍入面嘅有效數據少過2個交易日，冇辦法計算"
            return result

        start_price = float(closes.iloc[0])
        end_price = float(closes.iloc[-1])
        actual_start = closes.index[0]
        actual_end = closes.index[-1]

        result["actual_start_date"] = actual_start.strftime("%Y-%m-%d")
        result["actual_end_date"] = actual_end.strftime("%Y-%m-%d")

        years = (actual_end - actual_start).days / 365.25
        if years <= 0:
            result["error"] = "日期範圍太短，冇辦法計算年化回報"
            return result

        if start_price <= 0:
            result["error"] = "期初價格異常 (<=0)，冇辦法計算回報率"
            return result

        total_return = (end_price / start_price) - 1
        cagr = (end_price / start_price) ** (1 / years) - 1

        daily_returns = closes.pct_change().dropna()
        annualized_vol = float(daily_returns.std() * np.sqrt(252))

        result["cagr"] = round(cagr * 100, 2)  # 用百分比顯示
        result["total_return"] = round(total_return * 100, 2)
        result["annualized_volatility"] = round(annualized_vol * 100, 2)

    except Exception as e:
        result["error"] = str(e)

    return result


# ----------------------------------------------------------------------------
# MSTR 簡化 NAV 分析 (Yahoo Finance 冇提供 MSTR 嘅 NAV，因為佢係個股)。
# 下面兩個數字 Yahoo 攞唔到，係手動填 (來源: newhedge.io 快照，2026-10)。
# Strategy 差唔多逐星期買幣，想準確請按佢最新 8-K / strategy.com 更新呢兩個數。
# ----------------------------------------------------------------------------
MSTR_BTC_HELD = 845256
MSTR_SHARES_OUT = 333913000
MSTR_NAV_START = "2020-08-01"   # Strategy 開始買比特幣嘅月份


def compute_yield_curve():
    """用 FRED 嘅 DGS2 (2年期) 同 DGS10 (10年期) 美國國債孳息率 (日數據，1976年起)，
    計出倒掛 (2年期 > 10年期) 嘅時段。FRED 係實際孳息率，同期貨價格走勢一致。"""
    try:
        d2, v2 = fetch_fred_series("DGS2", FRED_API_KEY)
        d10, v10 = fetch_fred_series("DGS10", FRED_API_KEY)
        m2 = dict(zip(d2, v2))
        dates = [d for d in d10 if d in m2]
        y2 = [m2[d] for d in dates]
        m10 = dict(zip(d10, v10))
        y10 = [m10[d] for d in dates]
        ranges, start = [], None
        for i in range(len(dates)):
            inv = y2[i] > y10[i]
            if inv and start is None:
                start = i
            if (not inv) and start is not None:
                ranges.append([start, i - 1]); start = None
        if start is not None:
            ranges.append([start, len(dates) - 1])
        episodes = [{"from": dates[a], "to": dates[b], "days": b - a + 1} for a, b in ranges if b - a + 1 >= 20]
        return {"dates": dates, "y2": y2, "y10": y10, "inverted_ranges": ranges,
                "episodes": episodes[-5:], "last_date": dates[-1],
                "last_y2": y2[-1], "last_y10": y10[-1],
                "inverted_now": y2[-1] > y10[-1]}
    except Exception as e:
        return {"error": str(e)}


def compute_mstr_nav():
    """回傳 MSTR 嘅 (a) 股價 / BTC 價 比率歷史 (sats 計), (b) 最新簡化 mNAV 快照。
    簡化 mNAV = 市值 / (持幣量 x BTC價)，唔計債務、優先股同現金，
    所以同 Strategy 官方 mNAV (用企業價值) 會有出入。"""
    try:
        def close_of(t):
            d = yf.download(t, period="max", interval="1d", progress=False, auto_adjust=True)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            return d["Close"].dropna()
        m, b = close_of("MSTR"), close_of("BTC-USD")
        df = pd.concat([m.rename("m"), b.rename("b")], axis=1, join="inner")
        df = df[df.index >= MSTR_NAV_START]
        if len(df) < 10:
            return {"error": "MSTR / BTC 重疊數據不足"}
        ratio = (df["m"] / df["b"] * 1e8)
        m_last, b_last = float(df["m"].iloc[-1]), float(df["b"].iloc[-1])
        btc_value = MSTR_BTC_HELD * b_last
        mcap = MSTR_SHARES_OUT * m_last
        return {
            "dates": [d.strftime("%Y-%m-%d") for d in df.index],
            "ratio_sats": [round(float(x), 1) for x in ratio],
            "last_date": df.index[-1].strftime("%Y-%m-%d"),
            "mstr_price": round(m_last, 2), "btc_price": round(b_last, 2),
            "btc_held": MSTR_BTC_HELD, "shares_out": MSTR_SHARES_OUT,
            "btc_value": btc_value, "market_cap": mcap,
            "mnav": round(mcap / btc_value, 3),
            "nav_per_share": round(btc_value / MSTR_SHARES_OUT, 2),
        }
    except Exception as e:
        return {"error": str(e)}


def compute_log_channel(values, future_frac=0.25):
    """標準嘅對數迴歸通道 (直線帶)。
    future_frac: 通道線額外向未來延伸嘅比例 (相對於現有數據長度)。
    例如 0.25 即係喺現有數據之後，再加畫多25%長度嘅通道線，
    等用戶可以睇到「如果依家嘅趨勢線性延續，未來大約嘅價位範圍」。
    呢個純粹係將現有嘅迴歸直線/曲線向前推算，唔係另一個獨立嘅
    預測模型，所以務必喺畫面上清楚標示呢段係「延伸估算」，
    唔係實際成交數據。
    """
    ys = np.log(values)
    n = len(ys)
    xs = np.arange(n)
    slope, intercept = np.polyfit(xs, ys, 1)
    resid = ys - (slope * xs + intercept)
    sd = resid.std()

    n_future = int(round(n * future_frac))
    xs_extended = np.arange(n + n_future)

    levels = [3, 2, 1, 0, -1, -2, -3]
    bands = {}
    for k in levels:
        bands[k] = np.exp(slope * xs_extended + intercept + k * sd)
    last_bands = {}
    for k in levels:
        last_bands[k] = float(np.exp(slope * xs[-1] + intercept + k * sd))
    return bands, last_bands, n_future


def compute_linear_channel(values, future_frac=0.25):
    n = len(values)
    xs = np.arange(n)
    slope, intercept = np.polyfit(xs, values, 1)
    resid = values - (slope * xs + intercept)
    sd = resid.std()

    n_future = int(round(n * future_frac))
    xs_extended = np.arange(n + n_future)

    levels = [3, 2, 1, 0, -1, -2, -3]
    bands = {}
    for k in levels:
        bands[k] = slope * xs_extended + intercept + k * sd
    last_bands = {}
    for k in levels:
        last_bands[k] = float(slope * xs[-1] + intercept + k * sd)
    return bands, last_bands, n_future


def compute_parabolic_channel(values, future_frac=0.25):
    """拋物線/冪律通道: log(price) 對 log(time_index+1) 做迴歸。
    令通道隨時間拉闊速度遞減，畫出嚟嘅 ±標準差帶會彎曲，
    貼近報告入面比特幣個圖 (圖二十) 嘅效果。

    注意: 呢個函數假設傳入嚟嘅 values 已經喺 main() 度剷走咗早期
    接近零嘅雜訊價位 (例如比特幣 $20 以下嘅早期數據)，唔會喺呢度
    再做任何裁剪/填補，成條 values 陣列由頭到尾都會攞去做迴歸，
    通道長度同 values 完全對應。

    future_frac: 通道線額外向未來延伸嘅比例，做法同 compute_log_channel。
    """
    n = len(values)
    ys = np.log(values)
    xs = np.log(np.arange(n) + 1)
    slope, intercept = np.polyfit(xs, ys, 1)
    resid = ys - (slope * xs + intercept)
    sd = resid.std()

    n_future = int(round(n * future_frac))
    xs_extended = np.log(np.arange(n + n_future) + 1)

    levels = [3, 2, 1, 0, -1, -2, -3]
    bands = {}
    for k in levels:
        bands[k] = np.exp(slope * xs_extended + intercept + k * sd)
    last_bands = {}
    for k in levels:
        last_bands[k] = float(np.exp(slope * xs[-1] + intercept + k * sd))
    return bands, last_bands, n_future


# ============================================================================
# HTML 產生 (讀取獨立範本檔案)
# ============================================================================

def build_html(all_data, failed_assets, mstr_nav=None, yield_data=None):
    payload = {}
    for name in all_data:
        info = all_data[name]
        bands_serialized = {}
        for k, v in info["bands"].items():
            if hasattr(v, "tolist"):
                bands_serialized[str(k)] = v.tolist()
            else:
                bands_serialized[str(k)] = list(v)
        payload[name] = {
            "dates": info["dates"],
            "future_dates": info.get("future_dates", []),
            "values": info["values"],
            "closes": info.get("closes"),
            "highs": info.get("highs"),
            "lows": info.get("lows"),
            "bands": bands_serialized,
            "last_bands": info["last_bands"],
            "last_value": info["values"][-1] if info["values"] else None,
            "last_high": info["highs"][-1] if info.get("highs") else None,
            "last_low": info["lows"][-1] if info.get("lows") else None,
            "last_date": info["dates"][-1] if info["dates"] else None,
            "use_log": info["use_log"],
            "is_parabolic": info.get("is_parabolic", False),
            "ticker": info.get("ticker"),
        }

    # 下載失敗嘅資產: 唔會加入 payload，報告度會完全唔顯示呢個資產
    # (乾淨手法，冇空白/錯誤卡片)。失敗原因已經喺 terminal 印低。

    # 恆生指數市盈率通道 (獨立卡片，唔跟股價)
    # 逐年 hardcode 數值 (由用戶提供)，標準差通道由呢批數據自己計算
    pe_years = sorted(HSI_PE_BY_YEAR.keys())
    pe_dates = [str(y) for y in pe_years]
    pe_values = [HSI_PE_BY_YEAR[y] for y in pe_years]

    pe_array = np.array(pe_values, dtype=float)
    pe_center = float(pe_array.mean())
    pe_sd = float(pe_array.std())

    pe_levels = [3, 2, 1, 0, -1, -2, -3]
    pe_bands = {}
    for k in pe_levels:
        val = pe_center + k * pe_sd
        pe_bands[str(k)] = [val] * len(pe_years)

    current_pe = pe_values[-1]
    current_year = pe_years[-1]

    hsi_pe_payload = {
        "dates": pe_dates,
        "values": pe_values,
        "bands": pe_bands,
        "last_value": current_pe,
        "last_date": HSI_PE_LATEST_DATE,
        "use_log": False,
        "is_parabolic": False,
        "marker": {"index": len(pe_years) - 1, "value": current_pe,
                   "label": str(current_year) + ": " + str(current_pe)},
    }

    data_json = json.dumps(payload, ensure_ascii=False)
    hsi_pe_json = json.dumps(hsi_pe_payload, ensure_ascii=False)
    generated_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, TEMPLATE_FILENAME)
    if not os.path.exists(template_path):
        raise SystemExit(
            "搵唔到範本檔案: " + template_path + "\n"
            "請確保 " + TEMPLATE_FILENAME + " 同呢個 .py 檔放喺同一個資料夾。"
        )
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("__VERSION__", SCRIPT_VERSION)
    html = html.replace("__GENERATED_TS__", generated_ts)
    html = html.replace("__HSI_PE_CURRENT__", str(current_pe))
    html = html.replace("__HSI_PE_DATE__", HSI_PE_LATEST_DATE)
    html = html.replace("__DATA_JSON__", data_json)
    html = html.replace("__HSI_PE_JSON__", hsi_pe_json)
    html = html.replace("__MSTR_NAV_JSON__", json.dumps(mstr_nav or {"error": "未計算"}, ensure_ascii=False))
    html = html.replace("__YIELD_JSON__", json.dumps(yield_data or {"error": "未計算"}, ensure_ascii=False))
    return html


# ============================================================================
# 主程式
# ============================================================================

# ============================================================================
# 本機網頁伺服器 + 自動開瀏覽器
# ============================================================================

def start_local_server_and_open(docs_dir, port, filename):
    """喺 docs_dir 呢個資料夾度起一個本機 HTTP 伺服器，並且自動用預設
    瀏覽器打開個報告。用呢個方法打開嘅報告係 http://localhost:PORT/...，
    唔係 file://，所以報告入面「搜尋股票」功能嘅網絡請求先唔會俾
    瀏覽器嘅安全政策封鎖。

    伺服器會喺背景線程運行，唔會阻住 script 完結 (但 Python
    process 會保持行緊，等你隨時可以打開瀏覽器睇；如果想停低，
    喺 terminal 度撳 Ctrl+C 就得)。

    實作方式: 喺 QuietHandler 嘅 __init__() 入面，直接將 directory
    參數傳俾 SimpleHTTPRequestHandler 嘅父類別，唔再靠 os.chdir()。
    原因: os.chdir() 改嘅係「成個 process 嘅工作目錄」，呢個係
    process-wide 嘅全域狀態。當 server 行喺背景線程，而主線程/
    Windows 嘅線程調度有機會令 chdir 嘅效果同 server thread 實際
    處理 request 嗰一刻唔同步 (尤其係 Windows 上多線程時序本身
    就冇保證)，就會出現「表面上執行咗 chdir，但 server 收到
    request 嗰陣睇到嘅工作目錄仲係舊嘅」，導致 404。用 directory
    參數就唔涉及任何全域/跨線程狀態，每個 request 都直接、
    可靠噉喺指定嘅資料夾度搵檔案，唔會受線程時序影響。
    """
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=docs_dir, **kwargs)

        def log_message(self, fmt, *args):
            pass  # 靜音，唔喺 terminal 度洗版

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/search":
                self._handle_search_api(parsed)
                return
            if parsed.path == "/api/pe-compare":
                self._handle_pe_compare_api(parsed)
                return
            if parsed.path == "/api/risk-return":
                self._handle_risk_return_api(parsed)
                return
            # 唔係已知 API endpoint 嘅 request，交返俾原本嘅
            # SimpleHTTPRequestHandler 處理 (即係 serve 靜態檔案)。
            super().do_GET()

        def _handle_search_api(self, parsed):
            """處理報告入面「即時搜尋股票」功能嘅 request。
            用戶喺 panel 度打股票代號撳搜尋，前端 JS 會發一個
            request 去 /api/search?ticker=XXX，呢度用 yfinance
            (Yahoo Finance) 即時攞完整歷史，計算好通道，用 JSON
            格式回傳，等前端可以即刻加多張圖，唔使重新執行成個
            script，亦都唔受任何第三方免費 API tier 嘅年期限制。
            """
            qs = urllib.parse.parse_qs(parsed.query)
            ticker = (qs.get("ticker", [""])[0] or "").strip().upper()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            if not ticker:
                self.wfile.write(json.dumps({"error": "冇提供股票代號"}).encode("utf-8"))
                return

            try:
                df = yf.download(ticker, period="max", interval="1d",
                                  progress=False, auto_adjust=True)
                if df is None or df.empty:
                    self.wfile.write(json.dumps(
                        {"error": "Yahoo Finance 搵唔到 '" + ticker + "' 呢個代號嘅數據，請確認代號正確"}
                    ).encode("utf-8"))
                    return

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                if "High" not in df.columns:
                    self.wfile.write(json.dumps(
                        {"error": "'" + ticker + "' 嘅數據冇 High 欄位"}
                    ).encode("utf-8"))
                    return

                df = df[["High", "Low", "Close"]].dropna(subset=["High"])
                if df.empty:
                    self.wfile.write(json.dumps(
                        {"error": "'" + ticker + "' 冇有效嘅價錢數據"}
                    ).encode("utf-8"))
                    return

                values = df["High"].values.astype(float)
                dates = [d.strftime("%Y-%m-%d") for d in df.index]
                highs = df["High"].values.astype(float).tolist()
                lows = df["Low"].values.astype(float).tolist() if "Low" in df.columns else None
                closes = df["Close"].values.astype(float).tolist() if "Close" in df.columns else None

                use_log = True
                if (values <= 0).any():
                    use_log = False

                if use_log:
                    bands, last_bands, n_future = compute_log_channel(values)
                else:
                    bands, last_bands, n_future = compute_linear_channel(values)

                future_dates = []
                if n_future > 0 and len(dates) >= 2:
                    try:
                        last_date_obj = datetime.strptime(dates[-1], "%Y-%m-%d")
                        first_date_obj = datetime.strptime(dates[0], "%Y-%m-%d")
                        avg_gap_days = max(1, (last_date_obj - first_date_obj).days / max(1, len(dates) - 1))
                        for i in range(1, n_future + 1):
                            future_date = last_date_obj + pd.Timedelta(days=avg_gap_days * i)
                            future_dates.append(future_date.strftime("%Y-%m-%d"))
                    except Exception:
                        future_dates = ["未來+" + str(i) for i in range(1, n_future + 1)]

                bands_serialized = {}
                for k, v in bands.items():
                    bands_serialized[str(k)] = v.tolist() if hasattr(v, "tolist") else list(v)

                result = {
                    "ticker": ticker,
                    "dates": dates,
                    "future_dates": future_dates,
                    "values": values.tolist(),
                    "highs": highs,
                    "lows": lows,
                    "closes": closes,
                    "bands": bands_serialized,
                    "last_bands": last_bands,
                    "use_log": use_log,
                    "source": "Yahoo Finance (yfinance)",
                }
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))

            except Exception as e:
                self.wfile.write(json.dumps(
                    {"error": "下載或計算過程出錯: " + str(e)}
                ).encode("utf-8"))

        def _handle_pe_compare_api(self, parsed):
            """處理報告入面「PE比較」功能嘅 request。
            用戶打主要股票 + 最多3隻自選競爭對手 ticker (用戶手動
            輸入，呢個系統唔會自動幫手搵競爭對手)，呢度用
            compute_pe_metrics() 逐隻攞返 PE 相關數據，用 JSON
            回傳畀前端整表格顯示。
            """
            qs = urllib.parse.parse_qs(parsed.query)
            primary = (qs.get("primary", [""])[0] or "").strip().upper()
            competitors_raw = (qs.get("competitors", [""])[0] or "").strip()
            competitors = [c.strip().upper() for c in competitors_raw.split(",") if c.strip()][:3]

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            if not primary:
                self.wfile.write(json.dumps({"error": "請提供主要股票代號"}).encode("utf-8"))
                return

            try:
                primary_result = compute_pe_metrics(primary)
                competitor_results = []
                for comp_ticker in competitors:
                    competitor_results.append(compute_pe_metrics(comp_ticker))

                result = {
                    "primary": primary_result,
                    "competitors": competitor_results,
                    "note": "2/3/4年後嘅PE係用5年增長率自行推算嘅估算值，唔係analyst實際共識預測 " +
                            "(市場上冇免費source提供3年以上嘅共識EPS預測)。",
                }
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps(
                    {"error": "計算PE數據時出錯: " + str(e)}
                ).encode("utf-8"))

        def _handle_risk_return_api(self, parsed):
            """處理報告入面「Risk/Return」功能嘅 request。
            用戶打股票代號 + (可選) 自訂日期範圍，呢度用
            compute_risk_return() 計算 CAGR (回報) 同年化波幅 (風險)，
            用 JSON 回傳畀前端加入 risk/return 表格。
            """
            qs = urllib.parse.parse_qs(parsed.query)
            ticker = (qs.get("ticker", [""])[0] or "").strip().upper()
            start_date = (qs.get("start", ["2000-01-01"])[0] or "2000-01-01").strip()
            end_date = (qs.get("end", [""])[0] or "").strip()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            if not ticker:
                self.wfile.write(json.dumps({"error": "請提供股票代號"}).encode("utf-8"))
                return

            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            try:
                result = compute_risk_return(ticker, start_date, end_date)
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps(
                    {"error": "計算risk/return時出錯: " + str(e)}
                ).encode("utf-8"))


    actual_port = port
    httpd = None

    # 用戶要求可以同時下載4-6隻股票。用返單線程嘅 socketserver.TCPServer
    # 嘅話，Python 一次淨係處理到一個 request，就算瀏覽器同時發出咗
    # 幾個 fetch()，個 server 都會逐個逐個排隊處理，令「同時下載」
    # 名不副實，仲會拖慢晒。改用 ThreadingMixIn + TCPServer 組合成
    # 一個多線程 server，等每個 request (例如每隻股票嘅 /api/search)
    # 用自己獨立嘅線程處理，先可以真正做到同時下載。
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        daemon_threads = True  # 主程式結束時，背景線程唔會攔住

    for attempt_port in range(port, port + 10):
        try:
            httpd = ThreadingHTTPServer(("", attempt_port), QuietHandler,
                                         bind_and_activate=False)
            httpd.allow_reuse_address = True
            httpd.server_bind()
            httpd.server_activate()
            actual_port = attempt_port
            break
        except OSError:
            httpd = None
            continue

    if httpd is None:
        print("警告: 搵唔到可用嘅 port (試過 " + str(port) + "-" + str(port+9) +
              ")，冇辦法自動起本機伺服器。你依然可以直接雙擊 HTML 檔案睇report，")
        print("但搜尋股票功能會因為瀏覽器安全限制而用唔到。")
        return

    def serve_forever():
        httpd.serve_forever()

    server_thread = threading.Thread(target=serve_forever, daemon=True)
    server_thread.start()

    # 俾 server thread 少少時間完成初始化，先至打開瀏覽器，
    # 避免瀏覽器搶先過 server 真正準備好接受 request 嘅罕見情況。
    time.sleep(0.3)

    url = "http://localhost:" + str(actual_port) + "/" + filename
    print("\n本機伺服器已經開始運行: " + url)
    print("(伺服器直接指定 serve 資料夾: " + docs_dir + "，唔靠 os.chdir())")

    # USE_PYWEBVIEW_PANEL 控制想唔想用冇網址列嘅獨立視窗顯示報告。
    # 預設 False (用返一般瀏覽器)，因為 search bar 呢個功能唔需要
    # pywebview 先用得到，佢淨係需要呢個本機伺服器保持行緊。
    if USE_PYWEBVIEW_PANEL:
        try:
            import webview
            print("用 pywebview 開一個獨立全螢幕 panel (唔係一般瀏覽器)...")
            webview.create_window(
                "市場對數通道報告 " + SCRIPT_VERSION,
                url,
                fullscreen=True,
                confirm_close=False,
            )
            # webview.start() 會阻住 (block) 喺呢度，直到用戶關閉個視窗
            # 為止；用戶關閉個視窗之後，就會繼續行落去，關閉本機伺服器，
            # 然後成個程式結束 (唔會再有第二個 while True loop 攔住)。
            webview.start()
            print("\nPanel 已經關閉，正在停止伺服器...")
            httpd.shutdown()
            print("已經關閉。拜拜！")
            return
        except ImportError:
            print("USE_PYWEBVIEW_PANEL=True 但未裝 pywebview，改用返一般瀏覽器打開。")
            print("如果想要獨立 panel (冇網址列)，請執行: pip install pywebview")
        except Exception as e:
            print("pywebview 開啟失敗 (" + str(e) + ")，改用返一般瀏覽器打開。")

    try:
        webbrowser.open(url)
        print("已經自動打開瀏覽器。")
    except Exception as e:
        print("自動開瀏覽器失敗 (" + str(e) + ")，請自行複製上面個網址去瀏覽器打開。")

    print("\n伺服器會持續運行，等你隨時可以打開/重新整理個網頁。")
    print("如果想完全結束程式，返去呢個 terminal 度撳 Ctrl+C。")


    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，正在關閉伺服器...")
        httpd.shutdown()
        print("已經關閉。拜拜！")


def main():
    print("market_channels.py " + SCRIPT_VERSION + " 開始執行...")
    print("輸出資料夾: " + DOCS_DIR + "\n")

    all_data = {}
    failed_assets = {}

    for name, ticker, use_log, is_parabolic in ASSETS:
        try:
            df = download_asset(name, ticker)
        except Exception as e:
            print("  !! " + name + " (" + ticker + ") 最終下載失敗: " + str(e))
            failed_assets[name] = str(e)
            continue

        try:
            # 用戶要求: 價錢線同通道計算改用「每日最高價 (High)」，
            # 唔再用「收市價 (Close)」，等圖表可以睇到盤中最高點
            # (例如金價曾經觸及嘅高位)，唔會因為收市回落而喺圖度睇唔到。
            if "High" in df.columns:
                values = df["High"].values.astype(float)
            else:
                print("  " + name + " 冇 High 欄位，改用 Close。")
                values = df["Close"].values.astype(float)
            closes = df["Close"].values.astype(float).tolist()
            dates = [d.strftime("%Y-%m-%d") for d in df.index]
            highs = df["High"].values.astype(float).tolist() if "High" in df.columns else None
            lows = df["Low"].values.astype(float).tolist() if "Low" in df.columns else None

            actual_use_log = use_log
            actual_is_parabolic = is_parabolic
            if actual_use_log and (values <= 0).any():
                print("  " + name + " 含有非正數價格，改用線性通道。")
                actual_use_log = False
                actual_is_parabolic = False

            # 比特幣 (拋物線通道) 專用: 真正剷除首次升穿 $20 之前嘅
            # 早期數據，唔止喺通道計算層面剔除，而係連價錢線本身、
            # 日期、High/Low 都一齊裁剪，等成張圖 (包括Y軸範圍同
            # crosshair 換算) 完全唔再受呢批接近零嘅雜訊數據影響。
            if actual_is_parabolic:
                min_price_for_chart = 20.0
                trim_idx = 0
                for i, v in enumerate(values):
                    if v >= min_price_for_chart:
                        trim_idx = i
                        break
                if trim_idx > 0 and (len(values) - trim_idx) >= 10:
                    print("  " + name + ": 剷除首 " + str(trim_idx) +
                          " 個 $" + str(min_price_for_chart) + " 以下嘅早期數據點")
                    values = values[trim_idx:]
                    dates = dates[trim_idx:]
                    if highs is not None:
                        highs = highs[trim_idx:]
                    if lows is not None:
                        lows = lows[trim_idx:]

            if actual_is_parabolic:
                bands, last_bands, n_future = compute_parabolic_channel(values)
            elif actual_use_log:
                bands, last_bands, n_future = compute_log_channel(values)
            else:
                bands, last_bands, n_future = compute_linear_channel(values)

            # 幫通道嘅「未來延伸」部分產生對應嘅日期標籤 (例如喺最後
            #一個實際日期之後，按平均日距離推算落去)，等 X 軸可以
            # 連貫噉顯示埋呢段延伸區域，唔會令圖表嘅日期軸斷晒。
            future_dates = []
            if n_future > 0 and len(dates) >= 2:
                try:
                    last_date_obj = datetime.strptime(dates[-1], "%Y-%m-%d")
                    first_date_obj = datetime.strptime(dates[0], "%Y-%m-%d")
                    avg_gap_days = max(1, (last_date_obj - first_date_obj).days / max(1, len(dates) - 1))
                    for i in range(1, n_future + 1):
                        future_date = last_date_obj + pd.Timedelta(days=avg_gap_days * i)
                        future_dates.append(future_date.strftime("%Y-%m-%d"))
                except Exception:
                    future_dates = ["未來+" + str(i) for i in range(1, n_future + 1)]

            all_data[name] = {
                "dates": dates,
                "future_dates": future_dates,
                "n_future": n_future,
                "values": values.tolist(),
                "closes": closes if len(closes) == len(values) else None,
                "highs": highs,
                "lows": lows,
                "bands": bands,
                "last_bands": last_bands,
                "use_log": actual_use_log,
                "is_parabolic": actual_is_parabolic,
                "ticker": ticker,
            }
        except Exception as e:
            print("  !! " + name + " 通道計算時出錯: " + str(e))
            traceback.print_exc()
            failed_assets[name] = "通道計算時出錯: " + str(e)

    if not all_data and not failed_assets:
        raise SystemExit("所有資產都下載失敗，請檢查網絡連線後重試。")

    # ------------------------------------------------------------------
    # 澳洲全國住宅樓價指數 (圖一) - 用 FRED API，1970年至今
    # ------------------------------------------------------------------
    au_housing_name = "澳洲全國住宅樓價指數 (FRED, 1970年至今)"
    try:
        print("\n下載緊 " + au_housing_name + " ...")
        fred_dates, fred_values = fetch_fred_series(FRED_AU_HOUSING_SERIES_ID, FRED_API_KEY)
        fred_values_arr = np.array(fred_values, dtype=float)

        bands, last_bands, n_future = compute_log_channel(fred_values_arr)

        future_dates = []
        if n_future > 0 and len(fred_dates) >= 2:
            try:
                last_date_obj = datetime.strptime(fred_dates[-1], "%Y-%m-%d")
                first_date_obj = datetime.strptime(fred_dates[0], "%Y-%m-%d")
                avg_gap_days = max(1, (last_date_obj - first_date_obj).days / max(1, len(fred_dates) - 1))
                for i in range(1, n_future + 1):
                    future_date = last_date_obj + pd.Timedelta(days=avg_gap_days * i)
                    future_dates.append(future_date.strftime("%Y-%m-%d"))
            except Exception:
                future_dates = ["未來+" + str(i) for i in range(1, n_future + 1)]

        all_data[au_housing_name] = {
            "dates": fred_dates,
            "future_dates": future_dates,
            "n_future": n_future,
            "values": fred_values_arr.tolist(),
            "closes": None,
            "highs": None,
            "lows": None,
            "bands": bands,
            "last_bands": last_bands,
            "use_log": True,
            "is_parabolic": False,
        }
        print("  已攞到 " + str(len(fred_dates)) + " 個季度數據點，由 " +
              fred_dates[0] + " 至 " + fred_dates[-1])
    except Exception as e:
        print("  !! " + au_housing_name + " 攞取失敗: " + str(e))
        traceback.print_exc()
        failed_assets[au_housing_name] = str(e)

    pe_vals_preview = [HSI_PE_BY_YEAR[y] for y in sorted(HSI_PE_BY_YEAR.keys())]
    pe_mean_preview = float(np.mean(pe_vals_preview))
    pe_sd_preview = float(np.std(pe_vals_preview))
    print("\n恆生指數市盈率通道 (逐年 hardcode 數值，由用戶提供):")
    print("  年度數據: " + str(HSI_PE_BY_YEAR))
    print("  自動計算: 平均數=" + str(round(pe_mean_preview, 2)) +
          "  標準差=" + str(round(pe_sd_preview, 2)))
    print("如果想更新/新增年度數據，請編輯腳本入面嘅 HSI_PE_BY_YEAR 呢個字典。")

    if failed_assets:
        print("\n=== 以下資產下載失敗，報告入面會顯示為錯誤卡片 ===")
        for name, err in failed_assets.items():
            print("  - " + name + ": " + err)
        print("如果持續失敗，可以嘗試: (1) 檢查網絡, (2) 換個時間再試 (Yahoo Finance 有時會限流),")
        print("(3) 將呢個 ticker 用瀏覽器開 https://finance.yahoo.com/quote/<ticker> 睇下網站本身有冇呢個代號。")

    print("計算 MSTR NAV ...")
    mstr_nav = compute_mstr_nav()
    print("計算 2年期/10年期國債孳息率 ...")
    yield_data = compute_yield_curve()
    html = build_html(all_data, failed_assets, mstr_nav, yield_data)
    html_path = os.path.join(DOCS_DIR, "market_channels_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("\n完成！(版本: " + SCRIPT_VERSION + ")")
    print("CSV 檔案已儲存喺: " + DOCS_DIR)
    print("報告已產生: " + html_path)
    print("撳一撳任何一張圖就會全螢幕放大顯示 (保留十字準星追蹤)，撳右上角「X 關閉」返回。")
    print("打開之後，頁面正中間上方應該見到金色橫幅寫住「這是 " + SCRIPT_VERSION + "」。")

    if AUTO_OPEN_BROWSER:
        start_local_server_and_open(DOCS_DIR, LOCAL_SERVER_PORT, "market_channels_report.html")
    else:
        print("\n(AUTO_OPEN_BROWSER 設咗做 False，冇自動開瀏覽器。")
        print(" 雙擊個 HTML 檔案都得，但「搜尋股票」功能會因為瀏覽器安全限制而用唔到。)")


if __name__ == "__main__":
    main()
