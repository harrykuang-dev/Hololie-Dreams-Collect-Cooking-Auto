# 共用模型推論版本

單一完整版同時包含TensorRT、ONNX Runtime DirectML與CPU推論，無須另下載組件。相容NVIDIA GPU優先使用TensorRT，其次使用硬體DirectML，最後使用CPU。所有後端共用五份FP32 ONNX模型，不複製權重；玩家端不載入PyTorch或torchvision。

## 模型與介面

主分割、補充分割、食譜／槽位分類、標準ResNet18與進階ResNet101均沿用既有訓練權重。標籤順序、BGR輸入、OpenCV縮放、除以255、softmax、65%露出半徑、規劃及時效保護不變。前端語言、模型選擇、快捷鍵及載入／開始分離均沿用既有版本。

所有後端固定FP32，TensorRT停用TF32，不使用FP16、INT8或量化。正常分割只傳回類別與最高信心圖，完整機率圖供離線核對。不同後端的浮點結果不保證逐位相同，發佈前需核對分類、門檻、狀態、點位及實戰成績。

## 選擇與回退

載入時核對CUDA驅動、GPU運算能力、TensorRT函式庫與引擎。TensorRT不相容或失敗時，所有模型一起切到DirectML；DirectML失敗時再切到CPU。同一批GPU輸出若含NaN／Inf，也使用下一後端重算。

DirectML透過DXGI排除軟體顯示卡，優先使用專用顯示記憶體較多的GPU。分類固定32張批次並補零後裁回實際數量；ResNet eval各樣本獨立。分割為280×448、112×112與160×160分別建立session並預熱，避免實戰改變形狀時才編譯。

TensorRT引擎保存在 `%LOCALAPPDATA%\CollectCookingAuto\engines`，快取核對模型、TensorRT版本、GPU、驅動、FP32精度與輸入範圍。反序列化失敗時重建一次，仍失敗再回退。第一次建立期間可按停止。

開發用 `COOKING_INFERENCE_BACKEND=auto|directml|cpu|tensorrt`；`COOKING_DML_DEVICE` 可指定DXGI編號。預設auto，前端不新增技術選單。CPU可以執行模型，不表示每台電腦均能通過實戰時效；效能不足可能無法持續點擊。

## 診斷與驗證

開啟開發者模式後，每局實際分數、完成料理數、確認狀態、完整事件、決策、等待原因及耗時永久保留。`round-results.jsonl`提供逐局資料，`round-screenshots/`保存每局結算圖，與一般截圖共同按容量淘汰較早圖片。每個ZIP硬上限20 MB，純文字超限時自動分成多個ZIP。未能穩定辨識的分數為null，保留原因與截圖，內部估計另列。詳細格式見 `DEVELOPMENT.md`。

離線比對使用2,588張標註裁片及每模型88張遊戲畫面。另核對AMD／NVIDIA DirectML、NVIDIA TensorRT、CPU、載入取消、回退、結果數字及超額資料保留。離線通過不等於已完成實戰驗收。

## 建置

Windows x64、Python 3.13。獨立環境安裝 `requirements-build.txt`，安裝模型後執行 `tools/check_runtime.py`、單元測試與 `CookingAuto.spec`。訓練與匯出使用另外的 `requirements-export.txt`，原始PT權重保留在開發資料中。
