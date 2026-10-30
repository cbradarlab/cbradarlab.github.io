# 產業輪動每日資料（SHADOW）

此目錄預留 `latest.json`，供 `../minute-player.html` 在開啟時自動載入。

## 發布流程

1. 取得當日分鐘 OHLCV CSV，欄位為 `date,minute,code,industry,open,close,volume_lots`。
2. 在專案根目錄執行：
   ```bash
   python sector-rotation/build_daily_data.py input.csv sector-rotation/data/latest.json
   ```
3. 檢查輸出的 `coverage` 和 `volume_unit_verified=false`，確認資料僅為樣本且不是資金淨流入。
4. 將 `latest.json` 提交到 GitHub Pages 預設分支；網頁重新整理後會自動讀取。

**目前沒有自動抓取行情或每日排程。** 不可把沒有驗證的分鐘量單位標示為已驗證，不能把樣本等權強弱解讀成全市場資金流向。不得存放 Shioaji API 金鑰、憑證或個資。
