# Hololive Dreams Auto Collect Cooking — 1.1.0

[English](README.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Indonesian](README.id.md) · [简体中文](README.zh-CN.md)

Windows版《hololive Dreams》食材妙廚房的自動料理程式。透過遊戲畫面辨識食材，以一般滑鼠輸入選取食物，並在結算後接續下一局。

## 下載

前往 [GitHub Releases](https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto/releases/tag/v1.1.0)，將所有 `Collect-Cooking-Auto-v1.1.0-win64.7z.*` 分卷下載至同一資料夾。用7-Zip解壓 `.7z.001`，再執行解壓資料夾中的 `Collect-Cooking-Auto-v1.1.0.exe`。

請保留EXE旁的 `_internal` 資料夾。已包含Python、推論函式庫及五份模型權重。`SHA256SUMS.txt`用於核對下載檔案；`models.zip`供原始碼使用。GitHub自動產生的原始碼ZIP需另外安裝依賴與模型。

## 功能

- 辨識食譜食材、剩餘需求及槽位，規劃目標拾取、三消清理與抖盤。
- 提供「**標準**」（ResNet18）與「**進階**」（ResNet101）。標準運算需求較低，進階適合效能較充足的電腦。
- 模型載入與遊戲開始分開，載入的點位分類器同時驗證按需補充候選。
- 可設定目標局數，完成一局後自動接續，達標後停止。
- 支援英文、繁體中文、日文、韓文、印尼文及簡體中文，語言選擇套用於程式介面。
- 提供自訂快捷鍵、執行紀錄及可選的本機開發者診斷模式。

## 使用方法

1. 開啟遊戲，進入食材妙廚房。
2. 執行EXE，選擇程式語言及辨識模型，輸入正整數目標局數；初次使用預設5局。
3. 點擊「**載入模型**」，等待顯示模型已載入。
4. 點擊「**開始**」後，程式會嘗試還原遊戲視窗並切到前景，也可在遊戲中按 **F8**。若Windows阻止切換，請手動切回遊戲，並保持畫面無遮擋。
5. **F8**暫停／繼續，**Esc**或「**停止**」結束執行。切換焦點會暫停輸入，切回遊戲按F8繼續。切換模型前先停止，再選擇並載入另一個模型。

點擊快捷鍵框後，按下要使用的按鍵或Ctrl／Alt／Shift組合鍵。未完成輸入便離開欄位時，保留原設定；設定會保存供下次使用。

## 使用條件與限制

適用於Windows 10／11 x64及Windows版遊戲。遊戲客戶區需維持16:9，保持螢幕開啟及遊戲可見。單一完整版包含全部推論函式庫及一份共用FP32 ONNX模型。相容NVIDIA GPU自動使用TensorRT，其他支援的DirectX 12 GPU使用DirectML，最後回退CPU。CPU或效能較低的GPU可能無法通過點擊時效檢查。

解壓後的可攜資料夾約2.9 GB，另需預留下載分卷及解壓空間。介面中的已完成局數表示批次進度，料理數與成績以遊戲結算畫面為準。食材移動、遮擋、電腦效能及遊戲更新都可能影響辨識。

## 技術實作

### 畫面擷取與處理

[擷取模組](outputs/kitchen-bot/async_recording.py)以獨立執行緒透過Windows GDI取得遊戲客戶區畫面，請求頻率為每秒20幀，持續發布近期畫面供辨識，不等待影片編碼。[辨識流程](outputs/kitchen-bot/perception.py)將畫面統一至1536×864，再對448×280的桌面裁片進行分割。點位依實際縮放及頂部偏移換算回遊戲座標。

### 食材辨識與模型共用

主表面分割模型產生可見食材區域，所選點位分類器檢查點擊位置周圍的64×64裁片，縮放至96×96後推論。共用的圖標分類器讀取食譜與槽位，數字模板及固定UI圖形判斷需求數量與遊戲階段。

當主路徑準備等待或抖盤時，[補充定位器](outputs/kitchen-bot/supplemental_food.py)按需尋找洋蔥、炸蝦及鮪魚罐候選，再交給已載入的點位分類器驗證。程式只載入所選的標準或進階點位分類器。詳見 [模型說明](docs/model-options.md)。

### 規劃與抖盤間隔

[規劃器](outputs/kitchen-bot/planner.py)跨幀保存食譜、槽位估計、待確認拾取及近期失敗點，優先處理目標食材與完成三消，並依需求數量變化及可見槽位取得回饋。兩次實際按下抖盤至少間隔5秒，且需在近期畫面確認按鈕可用。

### 移動驗證與續局

[光流追蹤](outputs/kitchen-bot/motion.py)在派發點擊前估計局部位移，[新畫面複核](outputs/kitchen-bot/latest_click.py)檢查訂單、遊戲階段，以及觀測點與預測點的食材類別。追蹤失敗後，可透過受限的局部重新定位重試所需食材。[會話控制](outputs/kitchen-bot/session_flow.py)辨識右下角續局按鈕，從結算與選單接續下一局。

## 異常回報與開發者模式

辨識、點擊或續局異常，可在 [GitHub Issues](https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto/issues)提交回報。先勾選「**開發者模式**」再重現問題，程式會在本機保存辨識結果、點擊時序、遊戲截圖及效能摘要。開啟後會增加效能負擔，資料不會自動上傳。

點擊旁邊的 `?` 可查看並開啟診斷資料夾：

```text
%LOCALAPPDATA%\CollectCookingAuto\sessions\
```

每次執行結束後會產生以日期時間命名的ZIP。回報時請提供程式版本、所選模型、遊戲語言、解析度、Windows顯示縮放、問題描述及診斷ZIP。

開發者模式以JSONL永久保留每局確認後的分數、完成料理數、點擊、決策、等待原因及耗時。結算截圖與一般截圖共同按容量淘汰較早圖片；圖片是否仍保留以 `image-index.json` 為準。無法確認的結算數字標為null並保留原因。每個診斷ZIP硬上限20 MB；若純文字也超限，會分成多個ZIP，完整文字原檔仍保留於本機。

## 原始碼與授權說明

原始碼啟動、建置及測試見 [開發說明](docs/DEVELOPMENT.md)，其他內容見 [版本記錄](docs/VERSION_HISTORY.md)、[模型說明](docs/model-options.md)及 [遊戲用詞](docs/GAME_TERMS.md)。

第三方授權保留於 [third-party](third-party/README.md)。遊戲名稱與美術素材的權利歸各自權利人所有。
