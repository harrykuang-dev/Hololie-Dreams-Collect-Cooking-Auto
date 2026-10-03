# Hololie-Dreams-Collect-Cooking-Auto

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

hololive DREAMS 小遊戲 **Collect Cooking** 的 Windows 本機自動遊玩實驗程式。遊戲繁體名稱為 **食材妙厨房**，簡體名稱為 **拼配厨房**。儲存庫名稱保留指定拼寫 `Hololie-Dreams-Collect-Cooking-Auto`。

發布的是最新經過實戰測試的 **`e323dd962ed18ef1`**。程式結合截圖、神經網路影像辨識、持續保存狀態的三消規劃、光流追蹤及本機滑鼠輸入。遊戲迴圈不呼叫語言模型、不讀取遊戲記憶體、不注入遊戲程序，也不修改遊戲檔案。

## 目前狀態與實際成績

| 固定版本五局 | 每局完成料理數 | 平均 | 中位數 | 範圍 | 結束原因 |
| --- | --- | ---: | ---: | --- | --- |
| 最佳紀錄版 `18e2ddb6c76d8c2f` | 11、8、9、8、9 | **9.0** | 9 | 8–11 | 五局時間到 |
| 本次最新發布版 `e323dd962ed18ef1` | 10、8、6、7、9 | **8.0** | 8 | 6–10 | 四局時間到、一局爆槽 |

上述成績逐局核對了遊戲結算畫面，並非僅採用程式內部計數。開發目標是五局平均至少 **9.79 道**，即整數總和至少 49；**尚未達成**。單局十道不代表穩定每局十道。兩批隨機五局也不能證明新版本改善或造成退步。去除個人路徑後的資料見 [docs/verified-batches.json](docs/verified-batches.json)，已測執行版指紋見 [docs/tested-runtime.json](docs/tested-runtime.json)。

最新版本沿用最佳紀錄版的模型權重與主規劃器，新增時序診斷、限頻無損失敗畫面，以及局部重新定位補充路徑。該路徑在五局中實際點擊四次，三次在下一個食材輸入前觀察到目標需求減少，一次尚未確認。這只是回饋證據，不能證明遊戲碰撞系統實際選中了哪個物體。

## 安裝

已測環境：Windows、Python **3.13**、PyTorch **2.8.0+cu128**、torchvision **0.23.0+cu128**、RTX 4070 Laptop GPU。程式可自動選擇 CPU，但尚未驗證 CPU 下能獲得同等即時速度與遊戲成績。實作依賴已觀察到的 16:9 遊戲佈局，任意長寬比、UI 改版及所有語言佈局均未驗證。

在儲存庫根目錄開啟 PowerShell：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
gh release download v0.1.0 --repo harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto --pattern models.zip --dir downloads
.\.venv\Scripts\python.exe tools\install_models.py downloads\models.zip
.\.venv\Scripts\python.exe tools\check_runtime.py
```

套件版本對應實測 Python 環境；預設套件來源提供的 PyTorch 安裝包，其 CUDA 支援可能不同。偵測到可用 CUDA 就使用 GPU，否則使用 CPU。`gh` 僅用於下載權重，也可以在瀏覽器從 [Release](https://github.com/harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto/releases/tag/v0.1.0) 下載 `models.zip`，再把本機路徑交給安裝腳本。模型放在 Release 附件，不放進 Git 大檔案歷史。安裝腳本在寫入前檢查整個壓縮包與各模型的 SHA-256。

## 執行

1. 進入 **Collect Cooking／食材妙厨房**，選擇 **SCORE ATTACK**。普通模式也計時，不是十道料理的驗證模式。
2. 雙擊根目錄 `Launch.cmd`，或執行 `.\.venv\Scripts\pythonw.exe outputs\kitchen-bot\启动独立版.pyw`。
3. 選擇 1–5 局，點擊 **Start**，等待 **Ready**，切回遊戲按 **F8**。可從小遊戲結算、廚房選單或 Order 畫面開始，程式按固定佈局推進下一步。
4. 保持遊戲在前景，測試中避免同時操作滑鼠鍵盤。**F8** 暫停／恢復，**Escape** 停止。切換焦點會暫停遊戲輸入，回到遊戲按 F8 恢復。
5. 測試結束後核對結算截圖與日誌。這是開發實驗版本，不保證無人值守完成十道。

等價命令列入口：

```powershell
.\.venv\Scripts\python.exe outputs\kitchen-bot\standalone.py --point-model ../kitchen-labeler/point-classifier-human.pt --games 5 --fps 20
```

GUI 在權重安裝後自動選擇人工標注點位模型。直接用命令列時，必須像上面一樣指定它，才能重現已測版本；歷史預設 `point-classifier.pt` 是另一個模型。`--seconds` 限制每局執行時間，預設 300 秒；`--diagnostic-lossless-interval` 是失敗追蹤 PNG 對的最短保存間隔，預設 2 秒。`--replay PATH` 離線分析已有圖片，不建立桌面擷取／輸入介面；回放不能證明實際點擊成功。

## 技術細節與實作方式

### 擷取與座標

`standalone.py` 透過 Windows **GDI** 擷取遊戲客戶區，透過 **SendInput** 點擊滑鼠，在本機讀取 F8／Escape。擷取與 MP4 編碼在背景執行緒按請求 **20 FPS** 執行，與神經網路推理分離，使用條件變數發布新幀。影像統一到 **1536×864**，用實際比例與頂部偏移換算回客戶區座標。桌面區域裁切為 `(318,175)–(1215,735)`，縮放為 **448×280** 後分割。輸入前檢查遊戲焦點。

20 FPS 指請求擷取率，不代表每秒決策 20 次。記錄的擷取開始與滑鼠派發時間是主機時間，不是 Unity 影像曝光或收到輸入的精確時間。

### 影像辨識

- **可見表面分割**：`segmenter.py` 是小型 U-Net 風格編碼／解碼網路，通道 24/48/96/160，有跳躍連接，輸出 **30 種食材＋背景，共 31 類**。連通區域提取可見片段，透過信心度加權的距離轉換選內部位置，減少外框中心落在其他遮擋食材上的情況。
- **外觀分類**：`icon_classifier.py` 使用 **ResNet18** 與 31 類分類頭，輸入 96×96。圖標模型讀食譜、槽位及外框上下文；人工標注點位模型檢查點擊中心周圍的 **64×64 標準畫面裁切**。Softmax 分數是篩選門檻，並不是校準後的點擊成功機率。
- **訂單與狀態**：數字模板、顏色及連通區域讀訂單編號、剩餘數量及完成勾。固定 UI 圖形區分訂單過場、料理完成、結算、帷幕及爆槽。完成過場使用角落裝飾偵測，減少對翻譯文字的依賴，但沒有證明所有語言／佈局都適用。
- **透明容器**：豆芽罐優先尋找彩色瓶蓋，避免把透明罐身當作可靠可點擊表面。

早期訓練使用本機解包食材模型／貼圖生成合成視角，隨後用真實畫面及人工中心／輪廓標注訓練。儲存庫**不包含**完整解包、3D 模型及私有訓練標注集；Release 提供已訓練權重，並非完整可重現訓練資料集。後來困難食材的訓練候選未通過舊類別保留檢查，已被拒絕，沒有混入目前部署。僅附帶現有模板回退所需的小型食材圖標集及 UI／數字模板。

### 三消規劃與點擊驗證

`planner.py` 跨幀保存食譜、訂單、七格槽位估計、待確認點擊、近期失敗位置與抖盤狀態。優先目標食材以及補齊已有兩件的三消組；目標拾取用需求數量減少確認，渲染槽位觀察校正庫存。找不到目標時從按鈕畫面判斷抖盤是否可用，不只依賴固定冷卻時間。有足夠空間及高信心同類三件時，也可清理非目標食材。動畫期間這些回饋仍可能不明確。

`motion.py` 以 3×3 點網格進行金字塔 **Lucas–Kanade 光流**，檢查正反向一致性；追蹤點不足、運動不一致、幀間隔過舊、外推太遠或落點越界就拒絕。幾乎不變的平坦圖塊可視為靜止。外推計入畫面年齡、游標定位等待及渲染餘量。`latest_click.py` 檢查新畫面的階段／訂單，並同時分類**觀測點和預測落點**。擁擠槽位、部分窄區域與非目標清槽動作採用更嚴格門檻。有限的追加點擊也有各自的新幀驗證。

`supplemental_food.py` 在原路沒有食材動作時，用另一組人工表面模型補充 **洋蔥／炸蝦／鮪魚罐**，保留原路已批准動作，新畫面中仍須強一致性複核。

### 最新局部重新定位路徑

`guarded_local_relocation.py` 僅在原最新幀食材檢查回傳 `wait` 後啟用。只嘗試**第一個被拒絕的所需主路徑食材**，不替非目標清槽或獨立 supplement 路徑重新定位。`local_relocation.py` 在原有桌面像素尺度上重新分割對齊的 **160×160 ROI**，排除碰裁切邊緣、小／弱區域、距離過遠點及透明豆芽罐。

候選必須經過原規劃器的副本，包括近期失敗點記錄。推理結束後再明確取得**另一幀**，確認階段、訂單、需求數量與槽位不變，保持原光流和位移上限，並要求觀測／預測點分類均 **≥0.995**。驗證過程及輸入派發前檢查 **150ms 主機畫面年齡上限**；此路徑禁用追加點擊。派發前檢查之後仍有滑鼠移動等待，因此該上限並不保證遊戲中的精確畫面新鮮度。

## 檔案、權重與診斷

| 檔案／路徑 | 職責 |
| --- | --- |
| `outputs/kitchen-bot/standalone.py` | 本機擷取／輸入、固定五局與日誌 |
| `perception.py`、`segmenter.py`、`icon_classifier.py` | 表面、點位、食譜與槽位辨識 |
| `planner.py`、`shuffle_state.py` | 三消狀態管理與抖盤門控 |
| `motion.py`、`motion_click.py`、`latest_click.py` | 追蹤、外推與複核 |
| `supplemental_food.py` | 困難食材獨立補充 |
| `local_relocation.py`、`guarded_local_relocation.py` | 最新局部重新定位 |
| `outputs/kitchen-assets/textures/` | 模板比對使用的最小食材圖標集 |
| `models-manifest.json` | 權重路徑、大小與 SHA-256 |
| `tests/` | 離線座標與狀態／時間拒絕檢查 |

目前啟用權重：`segmenter-adapted.pt`、`icon-classifier.pt`、`segmenter-positive-surfaces.pt`、`point-classifier-human-paired.pt`，以及 `outputs/kitchen-labeler/point-classifier-human.pt`。壓縮包還保留歷史 `segmenter.pt` 和 `point-classifier.pt`。`render_samples.py`、`vision.py`、`worker.py` 為保留的歷史／支持模組；合成渲染器需另備本機 3D 資源。獨立版執行**不依賴 Codex 或 Computer Use**。

每次執行在 `outputs/kitchen-bot/runs/` 保存 `game.mp4`、決策 JPEG、部分無損 PNG 對、`final.jpg`、`decisions.jsonl`、`inputs.jsonl`、擷取統計及總結 JSON。批次保存原始碼／模型指紋及過場日誌。目前持續錄影，沒有實作使用者可選的錄影寫入開關。公開儲存庫不含本機執行日誌、錄影、個人檔案路徑及原始標注。

離線驗證：

```powershell
.\.venv\Scripts\python.exe tests\test_local_relocation_coordinates.py
.\.venv\Scripts\python.exe tests\test_guarded_local_relocation.py
```

檢查涵蓋座標換算、裁切邊界、原批准動作保留、過舊幀拒絕、槽位／狀態變化、追蹤失敗與嚴格點位複核。它們不能替代實戰五局。剩餘問題包括遮擋／碰撞不一致、點擊前看起來辨識正確但未拾取預期物體，以及部分食材追蹤緩慢或失敗。現有錄影缺少完整逐影片幀的擷取時間索引；精確對齊滑鼠派發與錄影是建議的後續診斷，尚未實作。

本專案為獨立實驗專案，並非 hololive DREAMS 官方產品。遊戲名稱與美術素材歸各自權利人所有。
