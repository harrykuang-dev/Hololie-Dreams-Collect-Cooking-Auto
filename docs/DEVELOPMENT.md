# 開發說明

玩家端的單一完整版包含TensorRT、ONNX Runtime DirectML與CPU備援，不依賴PyTorch。模型格式、FP32精度、快取與自動切換機制見 [共用模型推論版本](TENSORRT.md)。

## 環境與模型

使用Windows x64與Python 3.13，在獨立環境安裝建置依賴，並取得與本版本模型清單相符的 `models.zip`。

```powershell
py -3.13 -m venv .venv-runtime
.\.venv-runtime\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-runtime\Scripts\python.exe tools\install_models.py models.zip
.\.venv-runtime\Scripts\python.exe tools\check_runtime.py
```

安裝工具核對壓縮包、五個ONNX與同名JSON的SHA-256、檔案大小及允許路徑，再寫入缺少的檔案。既有PT權重保留供訓練與匯出，來源指紋另存於 `tools/checkpoints-manifest.json`。

## 啟動、測試與建置

```powershell
.\.venv-runtime\Scripts\pythonw.exe gui.py
.\.venv-runtime\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.\.venv-runtime\Scripts\Activate.ps1
.\build.ps1
```

產物為 `dist/Collect-Cooking-Auto-v1.1.0/`，EXE與 `_internal` 需一起保留。建置環境不應安裝PyTorch；封裝時亦明確排除PyTorch、torchvision與訓練模型定義。

封裝程式可只載入與暖機模型，核對後退出：

```powershell
.\Collect-Cooking-Auto-v1.1.0.exe --worker --model resnet18 --check-model-only --games 1 --output .\model-check\runs --control-file .\model-check\stop
```

將 `resnet18` 改成 `resnet101` 可核對進階模型。環境變數 `COOKING_INFERENCE_BACKEND=cpu` 可核對CPU路徑。結果包含實際後端、精度、GPU、暖機狀態與PyTorch載入檢查；此命令不建立遊戲擷取或輸入介面。

## 診斷格式

GUI開發者模式在正常停止或例外結束後產生ZIP，每個ZIP硬上限20,000,000位元組（包含ZIP檔頭、索引及中繼資料）。事件、決策及逐局結果完整保留；結算圖與一般截圖共同按容量淘汰較早圖片。純文字超限時分成多個獨立ZIP，全部解壓到同一資料夾；若出現 `NAME.parts/000001` 等檔案，按編號順序以原始位元組串接以重建NAME，分段可能切開UTF-8字元或JSON行。完整JSONL原檔始終保留在本機。內容包含：

- `diagnostic.json`：版本、模型、環境、動作與等待原因統計、各食材累計分析耗時及刪減計數。
- `trace.jsonl`：完整辨識、規劃與耗時紀錄，以 `stream` 區分每局來源。
- `inputs.jsonl`：完整輸入、補點及過場紀錄，以 `stream` 區分每局來源。
- `round-results.jsonl`：每局實際分數、完成料理數、確認狀態、執行時間、實際後端、點擊數、等待原因及耗時摘要。無法確認數字時保存null及原因，不用內部估計或歷史最佳分數代替。
- `image-index.json`：原畫面參照、JPEG路徑、原尺寸與儲存尺寸。
- `round-screenshots/`：逐局結算截圖，立即寫入磁碟，與一般截圖共用100張／10 MB容量限制，較早圖片先淘汰。逐局文字中的圖片路徑是原始參照，可能指向已淘汰的圖片；現存圖片以 `image-index.json` 為準。
- `screenshots/`：近期採樣畫面及失敗追蹤畫面，與結算圖共用容量限制。
- `metadata/`：逐局摘要、執行檔案與模型指紋、擷取效能摘要。
- `launcher-tail.txt`：近期啟動紀錄。

截圖最長邊1536像素，以JPEG壓縮。一般畫面最多每2秒保留一張；超出張數、記憶體或ZIP預算時先淘汰較早截圖。詳細內容以 `outputs/kitchen-bot/diagnostic_store.py` 的容量設定為準。診斷包不包含完整影片、權重、原始碼副本或設定檔；Windows帳號路徑會替換為匿名參照。

一般模式不保存詳細截圖或辨識紀錄，結束後移除該次暫存資料。開發者模式的JSONL每筆寫入磁碟，打包後仍保留原檔；結算圖獨立寫入磁碟，容量淘汰時也會移除對應原檔。強制結束時，已寫入資料仍可讀取；尚在記憶體的一般截圖不保證保留。程式不會自動清除此模式的歷史明細。

開發用直接CLI保留完整記錄入口：

```powershell
.\.venv\Scripts\python.exe outputs\kitchen-bot\standalone.py --point-model models/inference/point-classifier-resnet18.onnx --games 5
```

此入口預設保存原生尺寸錄影及完整逐幀資料，容量需求與GUI診斷包不同。
