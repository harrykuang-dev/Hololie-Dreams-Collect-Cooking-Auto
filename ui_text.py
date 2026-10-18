"""Localized model selection and explicit load/start controls."""
UI = {
    '繁體中文': {
        'instructions': '先進入食材妙廚房遊戲，載入模型後再點擊「開始」',
        'load': '載入模型', 'model': '辨識模型', 'help': '辨識模型說明', 'close': '關閉',
        'resnet18': '標準', 'resnet101': '進階',
        'help18': '運算需求較低，適合優先考慮速度與資源用量的電腦。',
        'help101': '運算需求較高，適合效能較充足的電腦。',
        'idle': '等待載入模型', 'loading': '正在載入模型…',
        'ready': '模型已載入；點擊「開始」或在遊戲中按 F8',
        'starting': '準備開始…', 'waiting_focus': '等待遊戲前景；切回料理畫面後開始',
        'running': '執行中', 'paused': '已暫停；回到遊戲按 F8 繼續',
        'stopping': '正在停止…', 'finished': '已結束；可重新載入模型',
        'error': '執行失敗；請查看紀錄。',
        'shortcut': '模型載入完成後，開始快捷鍵可開始／暫停；停止快捷鍵結束執行。',
    },
    '简体中文': {
        'instructions': '先进入拼配厨房游戏，加载模型后再点击「开始」',
        'load': '加载模型', 'model': '识别模型', 'help': '识别模型说明', 'close': '关闭',
        'resnet18': '标准', 'resnet101': '进阶',
        'help18': '运算需求较低，适合优先考虑速度与资源用量的电脑。',
        'help101': '运算需求较高，适合性能较充足的电脑。',
        'idle': '等待加载模型', 'loading': '正在加载模型…',
        'ready': '模型已加载；点击「开始」或在游戏中按 F8',
        'starting': '准备开始…', 'waiting_focus': '等待游戏前台；切回料理画面后开始',
        'running': '运行中', 'paused': '已暂停；返回游戏按 F8 继续',
        'stopping': '正在停止…', 'finished': '已结束；可重新加载模型',
        'error': '运行失败；请查看记录。',
        'shortcut': '模型加载完成后，开始快捷键可开始／暂停；停止快捷键结束运行。',
    },
    'English': {
        'instructions': 'Open Collect Cooking, load a model, then click “Start”.',
        'load': 'Load model', 'model': 'Recognition model', 'help': 'Recognition models', 'close': 'Close',
        'resnet18': 'Standard', 'resnet101': 'Advanced',
        'help18': 'Lower computing requirements. Choose it when speed and resource use are the priority.',
        'help101': 'Higher computing requirements. Suitable for more powerful PCs.',
        'idle': 'Waiting to load a model', 'loading': 'Loading models…',
        'ready': 'Model loaded; click Start or press F8 in the game',
        'starting': 'Preparing to start…', 'waiting_focus': 'Waiting for the game; return to Collect Cooking to start',
        'running': 'Running', 'paused': 'Paused; return to the game and press F8',
        'stopping': 'Stopping…', 'finished': 'Finished; load a model to run again',
        'error': 'Run failed; see the log.',
        'shortcut': 'After loading, the start shortcut starts / pauses; the stop shortcut ends the run.',
    },
}

# The game names below match LangClientCommon clientId 691271528243200.
UI['日本語'] = dict(
    instructions='先に「そろえてクッキング」を開き、モデルを読み込んでから「開始」をクリック',
    load='モデルを読み込む', model='認識モデル', help='認識モデルの説明', close='閉じる',
    resnet18='標準', resnet101='高性能',
    help18='処理負荷が低く、速度とリソース使用量を優先するパソコンに適しています。',
    help101='処理負荷が高く、性能に余裕のあるパソコンに適しています。',
    idle='モデルの読み込み待ち', loading='モデルを読み込み中…',
    ready='読み込み完了。「開始」をクリックするか、ゲーム内で F8', starting='開始準備中…',
    waiting_focus='ゲームの表示待ち。「そろえてクッキング」に戻ると開始します',
    running='実行中', paused='一時停止中。ゲームに戻り F8 で再開', stopping='停止中…',
    finished='終了しました。モデルを再読み込みできます', error='実行に失敗しました。ログを確認してください。',
    shortcut='読み込み後、開始キーで開始／一時停止、停止キーで終了します。',
)
UI['한국어'] = dict(
    instructions='먼저 모아 쿠킹을 열고 모델을 불러온 뒤 「시작」을 누르세요',
    load='모델 불러오기', model='인식 모델', help='인식 모델 설명', close='닫기',
    resnet18='표준', resnet101='고급',
    help18='연산 요구량이 낮아 속도와 자원 사용량을 우선하는 컴퓨터에 적합합니다.',
    help101='연산 요구량이 높아 성능에 여유가 있는 컴퓨터에 적합합니다.',
    idle='모델 불러오기 대기 중', loading='모델을 불러오는 중…',
    ready='모델 준비 완료. 「시작」을 누르거나 게임에서 F8', starting='시작 준비 중…',
    waiting_focus='게임 대기 중. 모아 쿠킹 화면으로 돌아가면 시작합니다',
    running='실행 중', paused='일시 정지. 게임으로 돌아가 F8로 재개', stopping='중지 중…',
    finished='종료됨. 모델을 다시 불러올 수 있습니다', error='실행 실패. 기록을 확인하세요.',
    shortcut='모델을 불러온 뒤 시작 키로 시작/일시 정지하고 중지 키로 종료합니다.',
)
UI['Indonesian'] = dict(
    instructions='Buka Collect Cooking, muat model, lalu klik “Mulai”.',
    load='Muat model', model='Model pengenalan', help='Penjelasan model', close='Tutup',
    resnet18='Standar', resnet101='Lanjutan',
    help18='Kebutuhan komputasi lebih rendah. Cocok untuk komputer yang mengutamakan kecepatan dan penggunaan sumber daya.',
    help101='Kebutuhan komputasi lebih tinggi. Cocok untuk komputer dengan performa lebih tinggi.',
    idle='Menunggu model dimuat', loading='Memuat model…',
    ready='Model siap; klik “Mulai” atau tekan F8 di dalam game', starting='Bersiap memulai…',
    waiting_focus='Menunggu game; kembali ke Collect Cooking untuk memulai',
    running='Berjalan', paused='Dijeda; kembali ke game dan tekan F8', stopping='Menghentikan…',
    finished='Selesai; muat ulang model untuk menjalankan lagi', error='Gagal berjalan; lihat catatan.',
    shortcut='Setelah model dimuat, pintasan mulai untuk memulai/menjeda; pintasan berhenti untuk mengakhiri.',
)

UI['繁體中文'].update(
    title='自動料理', language='語言/Language', games='目標局數', start='開始', stop='停止',
    start_key='開始快捷鍵', stop_key='停止快捷鍵', completed='已完成：{completed} / {target} 局',
    invalid_games='局數必須是正整數。', conflict='開始與停止快捷鍵不能重疊。',
    hotkey_error='無法註冊快捷鍵 {key}（{error}）；請改用其他按鍵。',
    developer='開發者模式', developer_help='開發者模式說明',
    diagnostic_body='會儲存辨識結果、點擊時序、部分遊戲截圖及效能摘要，用於定位與排查異常。資料不會自動上傳。',
    diagnostic_folder='診斷資料位於：',
    diagnostic_detail='每次執行會建立以日期時間命名的 ZIP。如遇異常，可透過下方項目地址提交 GitHub issue，附上問題描述與診斷包。開啟開發者模式會增加效能負擔。',
    project='項目地址：', diagnostic_saved='診斷包已儲存：{path}', diagnostic_error='無法儲存診斷包：{error}',
)
UI['简体中文'].update(
    title='自动料理', language='语言/Language', games='目标局数', start='开始', stop='停止',
    start_key='开始快捷键', stop_key='停止快捷键', completed='已完成：{completed} / {target} 局',
    invalid_games='局数必须是正整数。', conflict='开始与停止快捷键不能重叠。',
    hotkey_error='无法注册快捷键 {key}（{error}）；请改用其他按键。',
    developer='开发者模式', developer_help='开发者模式说明',
    diagnostic_body='会保存识别结果、点击时序、部分游戏截图及性能摘要，用于定位与排查异常。资料不会自动上传。',
    diagnostic_folder='诊断资料位于：',
    diagnostic_detail='每次运行会建立以日期时间命名的 ZIP。如遇异常，可通过下方项目地址提交 GitHub issue，附上问题描述与诊断包。开启开发者模式会增加性能负担。',
    project='项目地址：', diagnostic_saved='诊断包已保存：{path}', diagnostic_error='无法保存诊断包：{error}',
)
UI['English'].update(
    title='Collect Cooking Auto', language='Language', games='Target games', start='Start', stop='Stop',
    start_key='Start shortcut', stop_key='Stop shortcut', completed='Completed: {completed} / {target} games',
    invalid_games='Enter a positive whole number of games.', conflict='Start and stop shortcuts must not overlap.',
    hotkey_error='Cannot register shortcut {key} ({error}). Choose another key.',
    developer='Developer mode', developer_help='Developer mode information',
    diagnostic_body='Saves recognition results, click timing, selected game screenshots and performance summaries for troubleshooting. Data is not uploaded automatically.',
    diagnostic_folder='Diagnostic files:',
    diagnostic_detail='Each run creates a dated ZIP. If a problem occurs, attach it to a GitHub issue with a description. Developer mode adds processing overhead.',
    project='Project:', diagnostic_saved='Diagnostic ZIP saved: {path}', diagnostic_error='Could not save diagnostic ZIP: {error}',
)
UI['日本語'].update(
    title='自動クッキング', language='言語/Language', games='目標プレイ回数', start='開始', stop='停止',
    start_key='開始ショートカット', stop_key='停止ショートカット', completed='完了：{completed} / {target} 回',
    invalid_games='プレイ回数は1以上の整数を入力してください。', conflict='開始と停止のショートカットは別のキーにしてください。',
    hotkey_error='ショートカット {key} を登録できません（{error}）。別のキーを選んでください。',
    developer='開発者モード', developer_help='開発者モードの説明',
    diagnostic_body='問題の調査用に認識結果、クリックのタイミング、一部のゲーム画像、処理時間の概要を保存します。自動アップロードは行いません。',
    diagnostic_folder='診断データの保存先：',
    diagnostic_detail='実行ごとに日時付きの ZIP を作成します。問題が発生した場合は、下記の GitHub issue に状況と診断 ZIP を添付してください。有効にすると処理負荷が増えます。',
    project='プロジェクト：', diagnostic_saved='診断 ZIP を保存しました：{path}', diagnostic_error='診断 ZIP を保存できません：{error}',
)
UI['한국어'].update(
    title='자동 쿠킹', language='언어/Language', games='목표 판수', start='시작', stop='중지',
    start_key='시작 단축키', stop_key='중지 단축키', completed='완료: {completed} / {target} 판',
    invalid_games='판수는 양의 정수로 입력하세요.', conflict='시작과 중지 단축키는 서로 달라야 합니다.',
    hotkey_error='단축키 {key} 등록 실패 ({error}). 다른 키를 선택하세요.',
    developer='개발자 모드', developer_help='개발자 모드 안내',
    diagnostic_body='문제 진단을 위해 인식 결과, 클릭 시점, 일부 게임 화면과 성능 요약을 저장합니다. 자료는 자동으로 업로드되지 않습니다.',
    diagnostic_folder='진단 자료 위치:',
    diagnostic_detail='실행마다 날짜와 시간이 포함된 ZIP을 만듭니다. 문제가 생기면 아래 GitHub issue에 설명과 진단 ZIP을 첨부하세요. 활성화하면 처리 부하가 늘어납니다.',
    project='프로젝트:', diagnostic_saved='진단 ZIP 저장됨: {path}', diagnostic_error='진단 ZIP 저장 실패: {error}',
)
UI['Indonesian'].update(
    title='Collect Cooking Otomatis', language='Bahasa/Language', games='Target permainan', start='Mulai', stop='Hentikan',
    start_key='Pintasan mulai', stop_key='Pintasan berhenti', completed='Selesai: {completed} / {target} permainan',
    invalid_games='Masukkan jumlah permainan berupa bilangan bulat positif.', conflict='Pintasan mulai dan berhenti tidak boleh sama.',
    hotkey_error='Tidak dapat mendaftarkan pintasan {key} ({error}). Pilih tombol lain.',
    developer='Mode pengembang', developer_help='Penjelasan mode pengembang',
    diagnostic_body='Menyimpan hasil pengenalan, waktu klik, sebagian tangkapan layar game, dan ringkasan performa untuk mendiagnosis masalah. Data tidak diunggah otomatis.',
    diagnostic_folder='Lokasi data diagnostik:',
    diagnostic_detail='Setiap sesi membuat ZIP bertanggal. Jika terjadi masalah, lampirkan ZIP dan penjelasannya pada issue GitHub di bawah. Mode ini menambah beban pemrosesan.',
    project='Proyek:', diagnostic_saved='ZIP diagnostik disimpan: {path}', diagnostic_error='Gagal menyimpan ZIP diagnostik: {error}',
)
for language,prompt in {
    'English':'Press shortcut…', '繁體中文':'請按下快捷鍵…', '简体中文':'请按下快捷键…',
    '日本語':'キーを押してください…', '한국어':'단축키를 눌러 주세요…', 'Indonesian':'Tekan pintasan…',
}.items():UI[language]['capture']=prompt

UI = {name: UI[name] for name in ('English', '繁體中文', '日本語', '한국어', 'Indonesian', '简体中文')}
