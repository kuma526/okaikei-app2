const { useState, useEffect, useMemo, useRef } = React;

// 勘定科目リスト
const CATEGORIES = [
  "仕入高", "消耗品費", "旅費交通費", "通信費", "会議費",
  "接待交際費", "新聞図書費", "荷造運賃", "水道光熱費",
  "修繕費", "支払手数料", "地代家賃", "広告宣伝費", "雑費"
];

// よく使う品目・摘要メモの定型候補（科目別）
const COMMON_DESCRIPTIONS = {
  "仕入高": [
    "仕入れ商品一式",
    "テイクアウト用包材・容器",
    "販売用原材料・食材",
    "店舗・物販仕入れ在庫",
    "卸問屋仕入れ伝票"
  ],
  "消耗品費": [
    "文房具・事務用品一式",
    "コピー用紙 A4 500枚",
    "PC周辺サプライ・USBケーブル",
    "作業用備品・手袋・工具",
    "梱包用OPPテープ・緩衝材",
    "店舗清掃・衛生消耗品"
  ],
  "旅費交通費": [
    "配達車両 ガソリン給油",
    "コインパーキング 駐車料金",
    "高速道路通行料 (ETC)",
    "業務移動 電車・バス運賃",
    "業務連絡 タクシー利用"
  ],
  "通信費": [
    "業務連絡用 スマホ通信料",
    "事務所 光回線・インターネット代",
    "郵便切手・レターパック代",
    "業務通話・SMS利用料"
  ],
  "会議費": [
    "カフェ・喫茶店 業務打ち合わせ代",
    "コワーキングスペース ドロップイン利用料"
  ],
  "接待交際費": [
    "取引先への手土産・菓子折り",
    "取引先との会食飲食代",
    "お中元・お歳暮"
  ],
  "荷造運賃": [
    "商品発送 宅急便・ヤマト運輸送料",
    "ゆうパック・郵便送料",
    "発送用ダンボール箱"
  ],
  "水道光熱費": [
    "電気料金 (事業按分分)",
    "ガス料金 (事業按分分)",
    "水道料金 (事業按分分)"
  ],
  "修繕費": [
    "配達用バイク・車両オイル交換・整備代",
    "業務PC・スマートフォンの修理費用"
  ],
  "支払手数料": [
    "他行あて電信振込手数料",
    "決済手数料・代引手数料",
    "口座振替手数料"
  ],
  "地代家賃": [
    "事務所・作業スペース家賃 (事業按分)",
    "月極駐車場料金"
  ],
  "広告宣伝費": [
    "Web広告出稿料",
    "チラシ印刷・ポスティング費用"
  ],
  "雑費": [
    "諸雑費・手数料",
    "住民票・印鑑証明書発行手数料"
  ],
  "売上高": [
    "第1週 配達売上振込",
    "第2週 配達売上振込",
    "第3週 配達売上振込",
    "第4週 配達売上振込",
    "即時出金 振込売上",
    "商品販売売上",
    "業務委託・サービス提供報酬"
  ],
  "事業主借": [
    "手元現金より事業口座へ預入",
    "個人口座からの運転資金補填"
  ],
  "事業主貸": [
    "事業口座より生活費・手元現金引出",
    "プライベート支出の事業口座引落分"
  ]
};

// 銀行リスト
const BANKS = ["三井住友銀行", "楽天銀行", "三菱UFJ銀行", "みずほ銀行", "ゆうちょ銀行", "PayPay銀行", "住信SBIネット銀行", "現金"];

function App() {
  const [activeTab, setActiveTab] = useState("input"); // 'input', 'list', 'calendar', 'export', 'settings'
  const [currentMonth, setCurrentMonth] = useState(new Date().toISOString().slice(0, 7)); // 'YYYY-MM'
  
  // トランザクション & 集計データ
  const [transactions, setTransactions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [alertMsg, setAlertMsg] = useState(null);

  // 入力フォームステート
  const [entryType, setEntryType] = useState("expense"); // 'income', 'expense', 'bank'
  const [sourceType, setSourceType] = useState("purchase"); // 'purchase', 'bank_transfer', 'manual_expense', 'uber', 'rocket', 'manual_income', 'deposit', 'withdrawal'
  const [formData, setFormData] = useState({
    date: new Date().toISOString().slice(0, 10),
    amount: "",
    category: "仕入高",
    payee: "",
    description: "",
    bank_name: "現金",
    receipt_path: "",
    ocr_data: null
  });

  // 画像添付・アップロード状態
  const [uploadingImage, setUploadingImage] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);
  const fileInputRef = useRef(null);

  // カレンダー同期状態
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);

  // 設定状態
  const [settings, setSettings] = useState({
    default_bank_name: "三井住友銀行"
  });

  // レシート画像モーダル
  const [viewImageModal, setViewImageModal] = useState(null);

  // 一覧のフィルター
  const [filterType, setFilterType] = useState("all");
  const [filterCategory, setFilterCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  // データ初期ロード
  useEffect(() => {
    loadTransactions();
    loadSummary();
    loadSettings();
  }, [currentMonth]);

  const showAlert = (text, type = "success") => {
    setAlertMsg({ text, type });
    setTimeout(() => setAlertMsg(null), 4000);
  };

  const loadTransactions = async () => {
    try {
      const res = await fetch(`/api/transactions?month=${currentMonth}`);
      const data = await res.json();
      setTransactions(data);
    } catch (e) {
      console.error(e);
    }
  };

  const loadSummary = async () => {
    try {
      const res = await fetch(`/api/summary/monthly?month=${currentMonth}`);
      const data = await res.json();
      setSummary(data);
    } catch (e) {
      console.error(e);
    }
  };

  const loadSettings = async () => {
    try {
      const res = await fetch("/api/settings");
      const data = await res.json();
      setSettings(prev => ({ ...prev, ...data }));
    } catch (e) {
      console.error(e);
    }
  };

  // 入力タイプ切り替えハンドラー
  const handleTypeChange = (type) => {
    setEntryType(type);
    if (type === "income") {
      setSourceType("uber");
      setFormData(prev => ({
        ...prev,
        category: "売上高",
        payee: "Uber Eats",
        bank_name: "楽天銀行"
      }));
    } else if (type === "expense") {
      setSourceType("purchase");
      setFormData(prev => ({
        ...prev,
        category: "仕入高",
        payee: "",
        bank_name: "現金"
      }));
    } else if (type === "bank") {
      setSourceType("deposit");
      setFormData(prev => ({
        ...prev,
        category: "事業主借",
        payee: "手元現金入金",
        bank_name: "三井住友銀行"
      }));
    }
  };

  // ソース種別切り替え
  const handleSourceTypeChange = (st) => {
    setSourceType(st);
    if (st === "uber") {
      setFormData(prev => ({ ...prev, category: "売上高", payee: "Uber Eats (配達売上)", bank_name: "楽天銀行" }));
    } else if (st === "rocket") {
      setFormData(prev => ({ ...prev, category: "売上高", payee: "Rocket Now (デリバリー売上)", bank_name: "三井住友銀行" }));
    } else if (st === "manual_income") {
      setFormData(prev => ({ ...prev, category: "売上高", payee: "", bank_name: "現金" }));
    } else if (st === "purchase") {
      setFormData(prev => ({ ...prev, category: "仕入高" }));
    } else if (st === "bank_transfer") {
      setFormData(prev => ({ ...prev, category: "支払手数料", payee: "銀行振込" }));
    } else if (st === "deposit") {
      setFormData(prev => ({ ...prev, category: "事業主借" }));
    } else if (st === "withdrawal") {
      setFormData(prev => ({ ...prev, category: "事業主貸" }));
    }
  };

  // ファイルアップロード（即座に保存）
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadingImage(true);
    setPreviewImage(URL.createObjectURL(file));

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch("/api/upload-receipt", {
        method: "POST",
        body: form
      });
      const data = await res.json();

      if (data.success && data.receipt_url) {
        setFormData(prev => ({
          ...prev,
          receipt_path: data.receipt_url
        }));
        showAlert("📸 レシート画像を添付・保存しました！");
      } else {
        showAlert("画像の保存に失敗しました", "error");
      }
    } catch (err) {
      console.error(err);
      showAlert("画像のアップロードに失敗しました", "error");
    } finally {
      setUploadingImage(false);
    }
  };

  // 収支登録送信
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.amount || isNaN(formData.amount) || Number(formData.amount) <= 0) {
      showAlert("有効な金額を入力してください", "error");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        date: formData.date,
        type: entryType,
        source_type: sourceType,
        category: formData.category,
        amount: parseInt(formData.amount, 10),
        payee: formData.payee,
        description: formData.description,
        bank_name: formData.bank_name,
        receipt_path: formData.receipt_path,
        ocr_data: formData.ocr_data
      };

      const res = await fetch("/api/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok) {
        showAlert("✅ 取引を正常に記録しました！");
        // フォーム初期化
        setFormData({
          date: new Date().toISOString().slice(0, 10),
          amount: "",
          category: entryType === "income" ? "売上高" : "仕入高",
          payee: "",
          description: "",
          bank_name: "現金",
          receipt_path: "",
          ocr_data: null
        });
        setPreviewImage(null);
        if (fileInputRef.current) fileInputRef.current.value = "";

        loadTransactions();
        loadSummary();
      } else {
        showAlert("登録に失敗しました: " + (data.detail || "エラー"), "error");
      }
    } catch (err) {
      showAlert("通信エラーが発生しました", "error");
    } finally {
      setLoading(false);
    }
  };

  // 取引削除
  const handleDelete = async (id) => {
    if (!confirm("この取引記録を削除してもよろしいですか？")) return;
    try {
      const res = await fetch(`/api/transactions/${id}`, { method: "DELETE" });
      if (res.ok) {
        showAlert("取引を削除しました");
        loadTransactions();
        loadSummary();
      }
    } catch (e) {
      showAlert("削除に失敗しました", "error");
    }
  };

  // Googleカレンダー同期実行
  const handleCalendarSync = async (mode, targetVal) => {
    setSyncing(true);
    setSyncStatus(null);
    try {
      let endpoint = "/api/calendar/sync-day";
      let body = { date: targetVal, calendar_id: settings.google_calendar_id };

      if (mode === "month") {
        endpoint = "/api/calendar/sync-month";
        body = { month: targetVal, calendar_id: settings.google_calendar_id };
      }

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      setSyncStatus(data);
      showAlert("Googleカレンダー同期処理が完了しました！");
    } catch (e) {
      showAlert("カレンダー同期中にエラーが発生しました", "error");
    } finally {
      setSyncing(false);
    }
  };

  // 設定保存
  const handleSaveSettings = async (e) => {
    e.preventDefault();
    try {
      if (settings.default_bank_name) {
        await fetch("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: "default_bank_name", value: settings.default_bank_name })
        });
      }
      showAlert("設定を保存しました！");
      loadSettings();
    } catch (e) {
      showAlert("設定の保存に失敗しました", "error");
    }
  };

  // 取引フィルタリング
  const filteredTransactions = useMemo(() => {
    return transactions.filter(t => {
      if (filterType !== "all") {
        if (filterType === "uber" && t.source_type !== "uber") return false;
        if (filterType === "rocket" && t.source_type !== "rocket") return false;
        if (filterType === "purchase" && t.source_type !== "purchase") return false;
        if (filterType === "income" && t.type !== "income") return false;
        if (filterType === "expense" && t.type !== "expense") return false;
        if (filterType === "bank" && t.type !== "bank") return false;
      }
      if (filterCategory !== "all" && t.category !== filterCategory) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const str = `${t.payee} ${t.description} ${t.category} ${t.amount}`.toLowerCase();
        if (!str.includes(q)) return false;
      }
      return true;
    });
  }, [transactions, filterType, filterCategory, searchQuery]);

  return (
    <div className="max-w-md mx-auto sm:max-w-2xl md:max-w-4xl min-h-screen bg-slate-50 pb-24 text-slate-800">
      {/* 通知トースト */}
      {alertMsg && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full shadow-lg text-sm font-medium transition-all ${
          alertMsg.type === "error" ? "bg-red-600 text-white" : "bg-emerald-600 text-white"
        }`}>
          {alertMsg.text}
        </div>
      )}

      {/* ヘッダー */}
      <header className="bg-slate-900 text-white p-4 sticky top-0 z-30 shadow-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-xl">📊</span>
            <div>
              <h1 className="text-lg font-bold leading-tight">個人事業主 出納帳</h1>
              <p className="text-xs text-slate-400">Uber / Rocket Now / 仕入れ / 写真添付</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <input
              type="month"
              value={currentMonth}
              onChange={(e) => setCurrentMonth(e.target.value)}
              className="bg-slate-800 text-slate-200 text-xs px-2 py-1.5 rounded-lg border border-slate-700 focus:outline-none"
            />
            <button 
              onClick={() => setActiveTab("settings")}
              className={`p-1.5 rounded-lg transition-colors ${activeTab === 'settings' ? 'bg-indigo-600' : 'bg-slate-800 hover:bg-slate-700'}`}
              title="設定"
            >
              ⚙️
            </button>
          </div>
        </div>
      </header>

      {/* メインコンテンツ */}
      <main className="p-4 space-y-4">
        {/* ========================================================================= */}
        {/* TAB 1: 入力フォーム (収支・仕入れレシートOCR・銀行管理) */}
        {/* ========================================================================= */}
        {activeTab === "input" && (
          <div className="space-y-4">
            {/* 3大カテゴリ切り替えタブ */}
            <div className="grid grid-cols-3 gap-2 bg-slate-200 p-1 rounded-xl">
              <button
                type="button"
                onClick={() => handleTypeChange("expense")}
                className={`py-2.5 text-xs sm:text-sm font-bold rounded-lg transition-all flex items-center justify-center space-x-1 ${
                  entryType === "expense"
                    ? "bg-rose-500 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span>💸</span>
                <span>支出・仕入れ</span>
              </button>
              <button
                type="button"
                onClick={() => handleTypeChange("income")}
                className={`py-2.5 text-xs sm:text-sm font-bold rounded-lg transition-all flex items-center justify-center space-x-1 ${
                  entryType === "income"
                    ? "bg-emerald-600 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span>💰</span>
                <span>売上・収入</span>
              </button>
              <button
                type="button"
                onClick={() => handleTypeChange("bank")}
                className={`py-2.5 text-xs sm:text-sm font-bold rounded-lg transition-all flex items-center justify-center space-x-1 ${
                  entryType === "bank"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span>🏦</span>
                <span>銀行入出金</span>
              </button>
            </div>

            {/* サブタイプ・クイック切替 */}
            {entryType === "income" && (
              <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                <button
                  type="button"
                  onClick={() => handleSourceTypeChange("uber")}
                  className={`flex-1 min-w-[100px] py-2 px-3 rounded-lg text-xs font-bold border transition-all text-center ${
                    sourceType === "uber"
                      ? "bg-emerald-50 border-emerald-500 text-emerald-800 shadow-sm"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  🛵 Uber 振込
                </button>
                <button
                  type="button"
                  onClick={() => handleSourceTypeChange("rocket")}
                  className={`flex-1 min-w-[100px] py-2 px-3 rounded-lg text-xs font-bold border transition-all text-center ${
                    sourceType === "rocket"
                      ? "bg-emerald-50 border-emerald-500 text-emerald-800 shadow-sm"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  ⚡ Rocket Now 振込
                </button>
                <button
                  type="button"
                  onClick={() => handleSourceTypeChange("manual_income")}
                  className={`flex-1 min-w-[100px] py-2 px-3 rounded-lg text-xs font-bold border transition-all text-center ${
                    sourceType === "manual_income"
                      ? "bg-emerald-50 border-emerald-500 text-emerald-800 shadow-sm"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  ✏️ その他売上
                </button>
              </div>
            )}

            {entryType === "expense" && (
              <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                <button
                  type="button"
                  onClick={() => handleSourceTypeChange("purchase")}
                  className={`flex-1 min-w-[100px] py-2 px-3 rounded-lg text-xs font-bold border transition-all text-center ${
                    sourceType === "purchase"
                      ? "bg-rose-50 border-rose-500 text-rose-800 shadow-sm"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  📦 仕入れ (レシート)
                </button>
                <button
                  type="button"
                  onClick={() => handleSourceTypeChange("bank_transfer")}
                  className={`flex-1 min-w-[100px] py-2 px-3 rounded-lg text-xs font-bold border transition-all text-center ${
                    sourceType === "bank_transfer"
                      ? "bg-rose-50 border-rose-500 text-rose-800 shadow-sm"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  🏛️ 銀行振込
                </button>
                <button
                  type="button"
                  onClick={() => handleSourceTypeChange("manual_expense")}
                  className={`flex-1 min-w-[100px] py-2 px-3 rounded-lg text-xs font-bold border transition-all text-center ${
                    sourceType === "manual_expense"
                      ? "bg-rose-50 border-rose-500 text-rose-800 shadow-sm"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  🧾 その他経費
                </button>
              </div>
            )}

            {entryType === "bank" && (
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleSourceTypeChange("deposit")}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition-all text-center ${
                    sourceType === "deposit"
                      ? "bg-blue-50 border-blue-500 text-blue-800 shadow-sm"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  📥 預金入金 (手元→口座)
                </button>
                <button
                  type="button"
                  onClick={() => handleSourceTypeChange("withdrawal")}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition-all text-center ${
                    sourceType === "withdrawal"
                      ? "bg-blue-50 border-blue-500 text-blue-800 shadow-sm"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  📤 預金出金 (口座→手元)
                </button>
              </div>
            )}

            {/* レシート・領収書 画像添付ゾーン */}
            <div className="bg-slate-50 border-2 border-dashed border-slate-300 rounded-2xl p-4 text-center relative overflow-hidden">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment" // スマホの背面カメラ起動
                onChange={handleFileUpload}
                className="hidden"
                id="receipt-file"
              />

              {uploadingImage ? (
                <div className="py-4 space-y-2">
                  <div className="animate-spin text-2xl mx-auto w-6 h-6 border-3 border-slate-600 border-t-transparent rounded-full"></div>
                  <p className="text-xs font-bold text-slate-700">画像を保存中...</p>
                </div>
              ) : previewImage ? (
                <div className="space-y-2">
                  <div className="relative inline-block max-h-48 rounded-xl overflow-hidden shadow-sm border border-slate-200 bg-white">
                    <img src={previewImage} alt="Receipt Preview" className="h-44 object-contain mx-auto" />
                    <button
                      type="button"
                      onClick={() => {
                        setPreviewImage(null);
                        setFormData(prev => ({ ...prev, receipt_path: "" }));
                        if (fileInputRef.current) fileInputRef.current.value = "";
                      }}
                      className="absolute top-2 right-2 bg-slate-900/80 hover:bg-red-600 text-white rounded-full p-1.5 text-xs transition-colors shadow"
                      title="画像を外す"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="flex items-center justify-center space-x-2">
                    <span className="text-xs bg-emerald-100 text-emerald-800 font-bold px-2.5 py-1 rounded-full flex items-center space-x-1">
                      <span>✅</span>
                      <span>レシート画像添付済み</span>
                    </span>
                    <label
                      htmlFor="receipt-file"
                      className="cursor-pointer text-xs bg-white text-slate-700 font-bold px-3 py-1 rounded-lg border border-slate-200 hover:bg-slate-100 transition-colors shadow-2xs"
                    >
                      🔄 変更
                    </label>
                  </div>
                </div>
              ) : (
                <div className="py-2.5">
                  <div className="text-2xl mb-1">📸</div>
                  <p className="text-sm font-bold text-slate-800">
                    レシート・領収書画像を添付
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5 mb-2.5">
                    スマホのカメラで撮影または写真を選択して保存できます
                  </p>
                  <label
                    htmlFor="receipt-file"
                    className="cursor-pointer inline-flex items-center space-x-2 bg-slate-800 hover:bg-slate-900 text-white font-bold px-4 py-2 rounded-xl shadow-sm text-xs transition-transform active:scale-95"
                  >
                    <span>📷 カメラ撮影 / 写真を選択</span>
                  </label>
                </div>
              )}
            </div>

            {/* 入力フォーム */}
            <form onSubmit={handleSubmit} className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-4">
              {/* 金額入力（大きく見やすく） */}
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  金額 (円) <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-2xl font-bold text-slate-400">¥</span>
                  <input
                    type="number"
                    inputMode="numeric"
                    required
                    placeholder="0"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-300 rounded-xl text-2xl font-extrabold text-slate-900 focus:bg-white focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 outline-none transition-all"
                  />
                </div>
              </div>

              {/* 勘定科目（AI推測 + ドロップダウンで簡単修正） */}
              {entryType !== "bank" && (
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                      勘定科目 <span className="text-red-500">*</span>
                    </label>
                    <span className="text-[11px] text-indigo-600 font-medium">
                      AI推測からドロップダウンで変更可能
                    </span>
                  </div>
                  {entryType === "income" ? (
                    <input
                      type="text"
                      readOnly
                      value={formData.category}
                      className="w-full px-3 py-2.5 bg-slate-100 border border-slate-300 rounded-xl font-bold text-slate-700"
                    />
                  ) : (
                    <select
                      value={formData.category}
                      onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                      className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl font-bold text-slate-800 focus:bg-white focus:border-indigo-600 outline-none transition-all"
                    >
                      {CATEGORIES.map(cat => (
                        <option key={cat} value={cat}>{cat}</option>
                      ))}
                    </select>
                  )}
                </div>
              )}

              {/* 日付 & 取引先 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">
                    取引日 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={formData.date}
                    onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium focus:bg-white focus:border-indigo-600 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">
                    {entryType === "income" ? "入金元・取引先" : (entryType === "bank" ? "取引名" : "店舗・取引先名")}
                  </label>
                  <input
                    type="text"
                    placeholder={entryType === "income" ? "Uber / Rocket Now" : "セブンイレブン、卸問屋など"}
                    value={formData.payee}
                    onChange={(e) => setFormData({ ...formData, payee: e.target.value })}
                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium focus:bg-white focus:border-indigo-600 outline-none"
                  />
                </div>
              </div>

              {/* 口座選択 & 摘要メモ */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">
                    {entryType === "income" ? "振込入金先 口座" : (entryType === "expense" ? "決済・支払元" : "対象銀行口座")}
                  </label>
                  <select
                    value={formData.bank_name}
                    onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium focus:bg-white focus:border-indigo-600 outline-none"
                  >
                    {BANKS.map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="block text-xs font-bold text-slate-500">
                      品目・摘要メモ
                    </label>
                    <span className="text-[11px] text-indigo-600 font-bold">
                      ▼ プルダウン選択可
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {/* プルダウン選択 */}
                    <select
                      value=""
                      onChange={(e) => {
                        if (e.target.value) {
                          setFormData(prev => ({ ...prev, description: e.target.value }));
                        }
                      }}
                      className="w-full px-3 py-2 bg-indigo-50/80 border border-indigo-200 rounded-xl text-xs font-bold text-indigo-950 focus:bg-white focus:border-indigo-600 outline-none transition-all cursor-pointer shadow-xs"
                    >
                      <option value="">▼ プルダウンから品目・定型句を選択...</option>
                      
                      {/* 現在選択中の勘定科目に適した定番品目 */}
                      <optgroup label={`📋 【${formData.category || '定番'}】のよく使う品目`}>
                        {((COMMON_DESCRIPTIONS[formData.category]) || COMMON_DESCRIPTIONS["消耗品費"]).map((item, idx) => (
                          <option key={`cat-${idx}`} value={item}>{item}</option>
                        ))}
                      </optgroup>

                      {/* 収入や一般的な定番候補 */}
                      <optgroup label="📌 その他・一般的な候補">
                        {[
                          "仕入れ商品一式",
                          "配達車両 ガソリン給油",
                          "文房具・事務用品一式",
                          "業務連絡用 スマホ通信料",
                          "第1週 配達売上振込",
                          "他行あて電信振込手数料",
                          "諸雑費・手数料"
                        ].map((item, idx) => (
                          <option key={`gen-${idx}`} value={item}>{item}</option>
                        ))}
                      </optgroup>
                    </select>

                    {/* テキスト入力（自由編集・追記） */}
                    <input
                      type="text"
                      placeholder="上のプルダウンから選択、または直接入力・追記"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium focus:bg-white focus:border-indigo-600 outline-none transition-all"
                    />
                  </div>
                </div>
              </div>

              {/* 登録ボタン */}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 bg-slate-900 hover:bg-slate-800 active:scale-[0.99] text-white font-bold rounded-xl shadow-lg transition-all text-base flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <span>保存中...</span>
                ) : (
                  <>
                    <span>💾</span>
                    <span>この内容で出納帳に記録する</span>
                  </>
                )}
              </button>
            </form>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: 収支一覧・ダッシュボード */}
        {/* ========================================================================= */}
        {activeTab === "list" && (
          <div className="space-y-4">
            {/* サマリーカード */}
            {summary && (
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-2xl text-center">
                  <p className="text-[11px] font-bold text-emerald-700">総収入 (売上)</p>
                  <p className="text-base sm:text-xl font-extrabold text-emerald-900 mt-0.5">
                    ¥{summary.total_income.toLocaleString()}
                  </p>
                </div>
                <div className="bg-rose-50 border border-rose-200 p-3 rounded-2xl text-center">
                  <p className="text-[11px] font-bold text-rose-700">総支出 (経費)</p>
                  <p className="text-base sm:text-xl font-extrabold text-rose-900 mt-0.5">
                    ¥{summary.total_expense.toLocaleString()}
                  </p>
                </div>
                <div className="bg-sky-50 border border-sky-200 p-3 rounded-2xl text-center">
                  <p className="text-[11px] font-bold text-sky-700">差引利益 (粗利)</p>
                  <p className="text-base sm:text-xl font-extrabold text-sky-900 mt-0.5">
                    {summary.net_income >= 0 ? '+' : ''}¥{summary.net_income.toLocaleString()}
                  </p>
                </div>
              </div>
            )}

            {/* Uber & Rocket Now 振込サマリー */}
            {summary && summary.income_by_source && (
              <div className="bg-white p-3 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2">
                  <span className="text-lg">🛵</span>
                  <div>
                    <p className="text-slate-500 font-medium">Uber 売上</p>
                    <p className="font-extrabold text-slate-800 text-sm">
                      ¥{(summary.income_by_source.uber?.total || 0).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="h-8 w-px bg-slate-200"></div>
                <div className="flex items-center space-x-2">
                  <span className="text-lg">⚡</span>
                  <div>
                    <p className="text-slate-500 font-medium">Rocket Now 売上</p>
                    <p className="font-extrabold text-slate-800 text-sm">
                      ¥{(summary.income_by_source.rocket?.total || 0).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="h-8 w-px bg-slate-200"></div>
                <div className="flex items-center space-x-2">
                  <span className="text-lg">🏦</span>
                  <div>
                    <p className="text-slate-500 font-medium">銀行預金純増</p>
                    <p className="font-extrabold text-slate-800 text-sm">
                      ¥{(summary.bank_deposits - summary.bank_withdrawals).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* フィルター & 検索バー */}
            <div className="bg-white p-3 rounded-2xl border border-slate-200 shadow-sm space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="店名、品目、科目で検索..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 px-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg outline-none focus:bg-white"
                />
                <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  className="px-2 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg outline-none font-medium"
                >
                  <option value="all">全勘定科目</option>
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              {/* クイックフィルターピル */}
              <div className="flex gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs">
                {[
                  { id: "all", label: "全て" },
                  { id: "income", label: "💰 収入のみ" },
                  { id: "uber", label: "🛵 Uber" },
                  { id: "rocket", label: "⚡ Rocket Now" },
                  { id: "expense", label: "💸 支出のみ" },
                  { id: "purchase", label: "📦 仕入れ" },
                  { id: "bank", label: "🏦 銀行のみ" }
                ].map(f => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFilterType(f.id)}
                    className={`whitespace-nowrap px-2.5 py-1 rounded-full font-bold transition-all ${
                      filterType === f.id
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 取引明細リスト */}
            <div className="space-y-2">
              <div className="flex justify-between items-center px-1">
                <span className="text-xs font-bold text-slate-500">
                  取引一覧 ({filteredTransactions.length} 件)
                </span>
                <span className="text-xs text-slate-400">
                  タップで詳細・レシート確認
                </span>
              </div>

              {filteredTransactions.length === 0 ? (
                <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-400">
                  <p className="text-2xl mb-1">📭</p>
                  <p className="text-sm font-medium">該当する取引がありません</p>
                </div>
              ) : (
                filteredTransactions.map((t) => (
                  <div
                    key={t.id}
                    className="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-sm hover:border-slate-300 transition-all flex items-center justify-between"
                  >
                    <div className="flex items-center space-x-3">
                      {/* 種別アイコン */}
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-base shrink-0 ${
                        t.type === "income" 
                          ? (t.source_type === "uber" ? "bg-emerald-100 text-emerald-700" : "bg-emerald-100 text-emerald-700")
                          : t.type === "expense"
                            ? (t.source_type === "purchase" ? "bg-amber-100 text-amber-700" : "bg-rose-100 text-rose-700")
                            : "bg-blue-100 text-blue-700"
                      }`}>
                        {t.source_type === "uber" ? "🛵" : 
                         t.source_type === "rocket" ? "⚡" : 
                         t.source_type === "purchase" ? "📦" : 
                         t.type === "income" ? "💰" : 
                         t.type === "expense" ? "💸" : "🏦"}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center space-x-1.5">
                          <span className="text-[11px] font-bold text-slate-400">{t.date}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                            t.type === "income" ? "bg-emerald-100 text-emerald-800" :
                            t.type === "expense" ? "bg-rose-100 text-rose-800" : "bg-blue-100 text-blue-800"
                          }`}>
                            {t.category}
                          </span>
                          {t.receipt_path && (
                            <button
                              type="button"
                              onClick={() => setViewImageModal(t.receipt_path)}
                              className="text-[10px] bg-indigo-50 text-indigo-700 px-1 rounded hover:bg-indigo-100 font-bold"
                            >
                              📷 画像あり
                            </button>
                          )}
                        </div>

                        <p className="font-bold text-slate-800 text-sm truncate mt-0.5">
                          {t.payee || t.category}
                        </p>
                        {t.description && (
                          <p className="text-xs text-slate-500 truncate">
                            {t.description}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="text-right shrink-0 ml-3">
                      <p className={`text-base font-extrabold ${
                        t.type === "income" ? "text-emerald-600" :
                        t.type === "expense" ? "text-rose-600" : "text-blue-600"
                      }`}>
                        {t.type === "income" ? "+" : (t.type === "expense" ? "-" : "")}
                        ¥{t.amount.toLocaleString()}
                      </p>
                      <button
                        type="button"
                        onClick={() => handleDelete(t.id)}
                        className="text-[11px] text-slate-400 hover:text-red-500 font-medium transition-colors mt-0.5"
                      >
                        削除
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: Google カレンダー連携 */}
        {/* ========================================================================= */}
        {activeTab === "calendar" && (
          <div className="space-y-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center space-x-3">
                <span className="text-3xl">📅</span>
                <div>
                  <h2 className="text-base font-bold text-slate-900">Google カレンダー 自動同期</h2>
                  <p className="text-xs text-slate-500">1日の収支合計を非公開の終日イベントとして同期します</p>
                </div>
              </div>

              <div className="bg-indigo-50 border border-indigo-100 p-3 rounded-xl text-xs text-indigo-900 space-y-1">
                <p className="font-bold">✨ カレンダー登録イベントの仕様:</p>
                <p>・<b>タイトル</b>: 【収支】収入: ¥48,200 / 支出: ¥14,300 (差引: +¥33,900)</p>
                <p>・<b>説明</b>: Uber売上、Rocket Now売上、仕入高、消耗品費の内訳明細</p>
                <p>・<b>公開設定</b>: 非公開 (Private) の終日イベントとしてプライバシー保護</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <button
                  type="button"
                  disabled={syncing}
                  onClick={() => handleCalendarSync("day", new Date().toISOString().slice(0, 10))}
                  className="py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-md text-sm transition-all flex items-center justify-center space-x-2"
                >
                  <span>📅 本日 ({new Date().toISOString().slice(5, 10)}) の収支を同期</span>
                </button>
                <button
                  type="button"
                  disabled={syncing}
                  onClick={() => handleCalendarSync("month", currentMonth)}
                  className="py-3 px-4 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl shadow-md text-sm transition-all flex items-center justify-center space-x-2"
                >
                  <span>📆 今月 ({currentMonth}) 分を一括同期</span>
                </button>
              </div>

              {syncing && (
                <div className="py-4 text-center text-xs text-slate-500 animate-pulse">
                  カレンダー同期中...
                </div>
              )}

              {/* 同期結果プレビュー */}
              {syncStatus && (
                <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800">
                      {syncStatus.mode === "live" ? "🟢 Googleカレンダーに同期完了" : "ℹ️ カレンダー同期プレビュー"}
                    </span>
                    <span className="text-[10px] bg-slate-200 px-2 py-0.5 rounded-full font-bold">
                      {syncStatus.mode === "live" ? syncStatus.action : "Preview"}
                    </span>
                  </div>

                  {syncStatus.message && (
                    <p className="text-slate-600 text-[11px] bg-amber-50 p-2 rounded border border-amber-200">
                      {syncStatus.message}
                    </p>
                  )}

                  {syncStatus.event && (
                    <div className="bg-white p-3 rounded-lg border border-slate-200 space-y-1">
                      <p className="font-extrabold text-indigo-900 text-sm">{syncStatus.event.summary}</p>
                      <pre className="text-[11px] text-slate-600 whitespace-pre-wrap font-sans mt-1 bg-slate-50 p-2 rounded">
                        {syncStatus.event.description}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* バッチ処理の案内 */}
            <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm text-xs text-slate-600 space-y-2">
              <h3 className="font-bold text-slate-800 text-sm">💡 自動バッチ処理について</h3>
              <p>
                付属のスクリプト <code className="bg-slate-100 px-1 py-0.5 rounded font-mono">scripts/sync_calendar.py</code> を
                Windowsの「タスクスケジューラ」に登録することで、毎晩決まった時間に当日の収支を自動でGoogleカレンダーへ反映させることができます。
              </p>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: エクスポート (Excel, PDF, MF CSV, 弥生 CSV) */}
        {/* ========================================================================= */}
        {activeTab === "export" && (
          <div className="space-y-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center space-x-3">
                <span className="text-3xl">📑</span>
                <div>
                  <h2 className="text-base font-bold text-slate-900">帳票・データエクスポート</h2>
                  <p className="text-xs text-slate-500">
                    対象月: <span className="font-bold text-slate-800">{currentMonth}</span> の収支データを出力します
                  </p>
                </div>
              </div>

              {/* エクスポートボタン一覧 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                {/* Excel */}
                <a
                  href={`/api/export/excel?month=${currentMonth}`}
                  download
                  className="p-4 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-2xl flex items-center space-x-3 transition-all active:scale-[0.98]"
                >
                  <span className="text-3xl">📗</span>
                  <div className="text-left">
                    <p className="font-bold text-emerald-950 text-sm">Excel 出力 (.xlsx)</p>
                    <p className="text-[11px] text-emerald-700">月次サマリー表 ＋ 全取引明細シート</p>
                  </div>
                </a>

                {/* PDF */}
                <a
                  href={`/api/export/pdf?month=${currentMonth}`}
                  download
                  className="p-4 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-2xl flex items-center space-x-3 transition-all active:scale-[0.98]"
                >
                  <span className="text-3xl">📕</span>
                  <div className="text-left">
                    <p className="font-bold text-rose-950 text-sm">税務確認用 PDF集計表</p>
                    <p className="text-[11px] text-rose-700">青色申告・確定申告書スタイルの決算表</p>
                  </div>
                </a>

                {/* マネーフォワード */}
                <a
                  href={`/api/export/csv?month=${currentMonth}&format=moneyforward`}
                  download
                  className="p-4 bg-sky-50 hover:bg-sky-100 border border-sky-200 rounded-2xl flex items-center space-x-3 transition-all active:scale-[0.98]"
                >
                  <span className="text-3xl">📘</span>
                  <div className="text-left">
                    <p className="font-bold text-sky-950 text-sm">マネーフォワード形式 CSV</p>
                    <p className="text-[11px] text-sky-700">MFクラウド仕訳帳への一発インポート形式</p>
                  </div>
                </a>

                {/* 弥生会計 */}
                <a
                  href={`/api/export/csv?month=${currentMonth}&format=yayoi`}
                  download
                  className="p-4 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-2xl flex items-center space-x-3 transition-all active:scale-[0.98]"
                >
                  <span className="text-3xl">📙</span>
                  <div className="text-left">
                    <p className="font-bold text-purple-950 text-sm">弥生会計 / 青色申告 CSV</p>
                    <p className="text-[11px] text-purple-700">弥生の仕訳データインポート形式 (cp932)</p>
                  </div>
                </a>
              </div>
            </div>

            {/* 確定申告・会計ソフト取り込みのTips */}
            <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm text-xs text-slate-600 space-y-2">
              <h3 className="font-bold text-slate-800 text-sm">💡 会計ソフト取り込みの手順</h3>
              <ul className="list-disc list-inside space-y-1 text-slate-600">
                <li><b>マネーフォワード クラウド確定申告</b>: 「会計帳簿」→「仕訳帳」→「インポート」から上記CSVをそのまま指定してください。</li>
                <li><b>弥生会計 / やよいの青色申告</b>: 「仕訳日記帳」画面の「ファイル」→「インポート」からダウンロードしたCSVを読み込みます。</li>
              </ul>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 5: 設定 */}
        {/* ========================================================================= */}
        {activeTab === "settings" && (
          <div className="space-y-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
              <h2 className="text-base font-bold text-slate-900 flex items-center space-x-2">
                <span>⚙️</span>
                <span>システム設定</span>
              </h2>

              <form onSubmit={handleSaveSettings} className="space-y-4 text-xs">
                {/* 既定の口座 */}
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    既定の決済口座
                  </label>
                  <select
                    value={settings.default_bank_name || "三井住友銀行"}
                    onChange={(e) => setSettings({ ...settings, default_bank_name: e.target.value })}
                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium focus:bg-white outline-none"
                  >
                    {BANKS.map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>

                <button
                  type="submit"
                  className="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl shadow-md text-sm transition-all"
                >
                  設定を保存する
                </button>
              </form>
            </div>
          </div>
        )}
      </main>

      {/* レシート画像プレビューモーダル */}
      {viewImageModal && (
        <div 
          onClick={() => setViewImageModal(null)}
          className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
        >
          <div className="relative max-w-lg w-full max-h-[85vh] bg-white rounded-2xl overflow-hidden shadow-2xl p-4 text-center" onClick={(e) => e.stopPropagation()}>
            <div className="relative rounded-xl overflow-hidden bg-slate-100 flex items-center justify-center min-h-[200px] max-h-[70vh]">
              <img src={viewImageModal} alt="Receipt" className="w-full max-h-[70vh] object-contain rounded-xl" />
            </div>

            <div className="mt-3 flex items-center justify-center space-x-2">
              <a
                href={viewImageModal}
                download
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-full transition-colors flex items-center space-x-1"
              >
                <span>💾 画像ダウンロード</span>
              </a>
              <button
                onClick={() => setViewImageModal(null)}
                className="px-6 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-full transition-colors"
              >
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ボトムナビゲーションバー（モバイル・タブレット最適化） */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t border-slate-200 z-40 safe-bottom shadow-lg">
        <div className="max-w-md mx-auto sm:max-w-2xl md:max-w-4xl flex items-center justify-around py-2">
          <button
            type="button"
            onClick={() => setActiveTab("input")}
            className={`flex flex-col items-center justify-center w-20 py-1 transition-all ${
              activeTab === "input" ? "text-indigo-600 font-bold scale-105" : "text-slate-500 hover:text-slate-900"
            }`}
          >
            <span className="text-xl">✏️</span>
            <span className="text-[11px] mt-0.5">記帳・入力</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("list")}
            className={`flex flex-col items-center justify-center w-20 py-1 transition-all ${
              activeTab === "list" ? "text-indigo-600 font-bold scale-105" : "text-slate-500 hover:text-slate-900"
            }`}
          >
            <span className="text-xl">📊</span>
            <span className="text-[11px] mt-0.5">一覧・集計</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("export")}
            className={`flex flex-col items-center justify-center w-20 py-1 transition-all ${
              activeTab === "export" ? "text-indigo-600 font-bold scale-105" : "text-slate-500 hover:text-slate-900"
            }`}
          >
            <span className="text-xl">📑</span>
            <span className="text-[11px] mt-0.5">帳票出力</span>
          </button>
        </div>
      </nav>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);

