# 待發布的台股分鐘 CSV（SHADOW）

將每天的 Shioaji 分鐘行情 CSV 放在此資料夾，建議使用 `sector_rotation_ohlcv_YYYY-MM-DD.csv` 命名。GitHub Actions `Publish sector rotation minute snapshot (SHADOW)` 會挑選檔名排序最新的 CSV，驗證後產生 `../data/latest.json`，供播放器自動讀取。

必要欄位：`date,minute,code,industry,open,close,volume_lots`。CSV 只能包含單一交易日。資料若有重複股票／分鐘、非法時間或無效價格，發布會失敗而不覆蓋前一份資料。

此流程**不會自行登入 Shioaji，也不會自動抓行情**；需要另行部署合法授權的行情收集器。不得上傳 API 金鑰、密碼或憑證。輸出僅是樣本相對強弱，並非全市場資金淨流入。
