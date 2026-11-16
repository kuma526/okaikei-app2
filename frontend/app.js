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
    "店舗レジ現金売上",
    "店舗カード売上 (楽天ターミナル)",
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

// 支出用決済・支払元リスト (カード決済、QRコード支払い追加)
const EXPENSE_PAYMENT_METHODS = [
  "現金",
  "カード決済",
  "QRコード支払い",
  "三井住友銀行",
  "楽天銀行",
  "三菱UFJ銀行",
  "みずほ銀行",
  "ゆうちょ銀行",
  "PayPay銀行",
  "住信SBIネット銀行"
];

// 楽天ターミナル決済種別
const RAKUTEN_PAYMENT_TYPES = [
  "クレジットカード全般",
  "QRコード (楽天/au/SmartCode等)",
  "QRコード (PayPay/d払い)",
  "電子マネー (交通系/Edy/WAON等)",
  "電子マネー (QUICPay/iD)"
];

// 楽天ターミナル 決済手段別の標準手数料率 (%)
const RAKUTEN_FEE_RATES = {
  "クレジットカード全般": 3.24,
  "QRコード (楽天/au/SmartCode等)": 2.95,
  "QRコード (PayPay/d払い)": 3.24,
  "電子マネー (交通系/Edy/WAON等)": 2.95,
  "電子マネー (QUICPay/iD)": 3.24
};

// Googleドライブ等のURLをプレビュー画像URLに整形するヘルパー関数
const getDriveDisplayUrl = (url) => {
  if (!url) return "";
  if (typeof url === "string" && url.includes("drive.google.com")) {
    const match = url.match(/\/d\/([a-zA-Z0-9_-]+)/) || url.match(/id=([a-zA-Z0-9_-]+)/);
    if (match && match[1]) {
      return `https://drive.google.com/thumbnail?id=${match[1]}&sz=w1000`;
    }
  }
  return url;
};

function App() {
  const [activeTab, setActiveTab] = useState("input"); // 'input', 'list', 'export', 'settings'
  const [currentMonth, setCurrentMonth] = useState(new Date().toISOString().slice(0, 7)); // 'YYYY-MM'
  
  // トランザクション & 集計データ
  const [transactions, setTransactions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [alertMsg, setAlertMsg] = useState(null);

  // 入力フォームステート
  const [entryType, setEntryType] = useState("expense"); // 'income', 'expense', 'bank'
  const [sourceType, setSourceType] = useState("purchase"); // 'purchase', 'bank_transfer', 'manual_expense', 'store', 'uber', 'rocket', 'manual_income', 'deposit', 'withdrawal'
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

  // 店舗売上・決済方法ステート
  const [storePaymentMethod, setStorePaymentMethod] = useState("cash"); // 'cash', 'rakuten_terminal'
  const [rakutenPaymentType, setRakutenPaymentType] = useState("クレジットカード全般");
  const [cardFeeRate, setCardFeeRate] = useState("3.24"); // 手数料率 (%) デフォルト3.24%
  const [enableFeeCalc, setEnableFeeCalc] = useState(true); // 手数料自動計算

  // 画像添付・アップロード状態
  const [uploadingImage, setUploadingImage] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);
  const fileInputRef = useRef(null);

  // 設定状態
  const [settings, setSettings] = useState({
    default_bank_name: "三井住友銀行",
    card_fee_rate: "3.24"
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
      const res = await fetch(`/api/transactions?month=${currentMonth}`); const data = await res.json(); setTransactions(data); } catch (e) { console.error(e); } };  const loadSummary = async () => { try { const res = await fetch(`/api/summary/monthly?month=${currentMonth}`);
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
      if (data.card_fee_rate) {
        setCardFeeRate(data.card_fee_rate);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // 入力タイプ切り替えハンドラー
  const handleTypeChange = (type) => {
    setEntryType(type);
    if (type === "income") {
      setSourceType("store");
      setStorePaymentMethod("cash");
      setFormData(prev => ({
        ...prev,
        category: "売上高",
        payee: "店舗売上 (現金)",
        description: "",
        bank_name: "現金"
      }));
    } else if (type === "expense") {
      setSourceType("purchase");
      setFormData(prev => ({
        ...prev,
        category: "仕入高",
        payee: "",
        description: "",
        bank_name: "現金"
      }));
    } else if (type === "bank") {
      setSourceType("deposit");
      setFormData(prev => ({
        ...prev,
        category: "事業主借",
        payee: "手元現金入金",
        description: "",
        bank_name: "三井住友銀行"
      }));
    }
  };

  // ソース種別切り替え
  const handleSourceTypeChange = (st) => {
    setSourceType(st);
    if (st === "store") {
      const isCash = storePaymentMethod === "cash";
      setFormData(prev => ({
        ...prev,
        category: "売上高",
        payee: isCash ? "店舗売上 (現金)" : "店舗売上 (楽天ターミナル)",
        bank_name: isCash ? "現金" : "楽天ターミナル"
      }));
    } else if (st === "uber") {
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

  // 店舗売上の決済方法切り替え
  const handleStorePaymentMethodChange = (method) => {
    setStorePaymentMethod(method);
    if (method === "cash") {
      setFormData(prev => ({
        ...prev,
        payee: "店舗売上 (現金)",
        bank_name: "現金"
      }));
    } else {
      const defaultRate = RAKUTEN_FEE_RATES[rakutenPaymentType] !== undefined ? String(RAKUTEN_FEE_RATES[rakutenPaymentType]) : "3.24";
      setCardFeeRate(defaultRate);
      setFormData(prev => ({
        ...prev,
        payee: "店舗売上 (楽天ターミナル)",
        bank_name: "楽天ターミナル"
      }));
    }
  };

  // 楽天ターミナルの決済手段切り替え（手段ごとの手数料率を動的反映）
  const handleRakutenPaymentTypeChange = (type) => {
    setRakutenPaymentType(type);
    if (RAKUTEN_FEE_RATES[type] !== undefined) {
      setCardFeeRate(String(RAKUTEN_FEE_RATES[type]));
    }
  };

  // カード・振込の手数料リアルタイム自動計算
  const feeCalculation = useMemo(() => {
    const gross = parseInt(formData.amount, 10) || 0;
    const rate = parseFloat(cardFeeRate) || 0;
    if (gross <= 0 || rate <= 0) {
      return { gross: 0, rate: 0, fee: 0, net: 0 };
    }
    const fee = Math.round(gross * (rate / 100));
    const net = gross - fee;
    return { gross, rate, fee, net };
  }, [formData.amount, cardFeeRate]);

  // ファイルアップロード（Base64化してサーバー・Googleドライブ保存）
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadingImage(true);

    try {
      // 1. ブラウザ側で直接Base64に変換（プレビューと送信の両方に対応）
      const base64DataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = (error) => reject(error);
        reader.readAsDataURL(file);
      });

      // プレビュー表示
      setPreviewImage(base64DataUrl);

      // 2. Base64データ部を抽出してバックエンドへ送信
      const base64Content = base64DataUrl.includes(",") 
        ? base64DataUrl.split(",")[1] 
        : base64DataUrl;

      const res = await fetch("/api/upload-receipt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          filename: file.name || "receipt.jpg",
          file: base64Content
        })
      });

      const data = await res.json();

      if (data.success && data.receipt_url) {
        setFormData(prev => ({
          ...prev,
          receipt_path: data.receipt_url
        }));
        if (data.storage === "gdrive") {
          showAlert("📸 レシート画像をGoogleドライブに保存しました！");
        } else {
          showAlert("📸 レシート画像を添付・保存しました！");
        }
      } else {
        showAlert(data.message || "画像の保存に失敗しました", "error");
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
      let finalDescription = formData.description ? formData.description.trim() : "";
      let finalOcrData = formData.ocr_data ? (typeof formData.ocr_data === "object" ? { ...formData.ocr_data } : {}) : {};

      // 手数料自動計算は【店舗売上 かつ 楽天ターミナル選択時のみ】に限定（現金決済時は手数料ゼロ・受取額=総額）
      const isRakutenTerminal = (entryType === "income" && sourceType === "store" && storePaymentMethod === "rakuten_terminal");

      if (isRakutenTerminal && feeCalculation.gross > 0) {
        const pType = rakutenPaymentType;
        const breakdownMemo = `【${pType}売上内訳】総額: ¥${feeCalculation.gross.toLocaleString()} / 手数料(${feeCalculation.rate}\%): -¥${feeCalculation.fee.toLocaleString()} / 振込受取額: ¥${feeCalculation.net.toLocaleString()}`;  if (!finalDescription) { finalDescription = breakdownMemo; } else if (!finalDescription.includes("振込受取額:")) { finalDescription = `${finalDescription} ${breakdownMemo}`; }  finalOcrData.fee_calculation = { gross_amount: feeCalculation.gross, fee_rate: feeCalculation.rate, fee_amount: feeCalculation.fee, net_amount: feeCalculation.net, payment_type: pType }; }  const payload = { date: formData.date, type: entryType, source_type: sourceType, category: formData.category, amount: parseInt(formData.amount, 10), payee: formData.payee, description: finalDescription, bank_name: formData.bank_name, receipt_path: formData.receipt_path, ocr_data: Object.keys(finalOcrData).length > 0 ? finalOcrData : null };  const res = await fetch("/api/transactions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); const data = await res.json();  if (res.ok) { showAlert("✅ 取引を正常に記録しました！"); // フォーム初期化 const defaultBank = entryType === "income" ? (sourceType === "store" ? (storePaymentMethod === "cash" ? "現金" : "楽天ターミナル") : (sourceType === "uber" ? "楽天銀行" : (sourceType === "rocket" ? "三井住友銀行" : "現金"))) : "現金"; const defaultPayee = entryType === "income" ? (sourceType === "store" ? (storePaymentMethod === "cash" ? "店舗売上 (現金)" : "店舗売上 (楽天ターミナル)") : (sourceType === "uber" ? "Uber Eats (配達売上)" : (sourceType === "rocket" ? "Rocket Now (デリバリー売上)" : ""))) : "";  setFormData({ date: new Date().toISOString().slice(0, 10), amount: "", category: entryType === "income" ? "売上高" : "仕入高", payee: defaultPayee, description: "", bank_name: defaultBank, receipt_path: "", ocr_data: null }); setPreviewImage(null); if (fileInputRef.current) fileInputRef.current.value = "";  loadTransactions(); loadSummary(); } else { showAlert("登録に失敗しました: " + (data.detail \vert{}\vert{} "エラー"), "error"); } } catch (err) { showAlert("通信エラーが発生しました", "error"); } finally { setLoading(false); } };  // 取引削除 const handleDelete = async (id) => { if (!confirm("この取引記録を削除してもよろしいですか？")) return; try { const res = await fetch(`/api/transactions/${id}`, { method: "DELETE" });
      if (res.ok) {
        showAlert("取引を削除しました");
        loadTransactions();
        loadSummary();
      }
    } catch (e) {
      showAlert("削除に失敗しました", "error");
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
      if (cardFeeRate) {
        await fetch("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: "card_fee_rate", value: cardFeeRate })
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
        if (filterType === "store" && t.source_type !== "store") return false;
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
        const str = `${t.payee}${t.description} ${t.category}${t.amount}`.toLowerCase();
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
              <h1 className="text-lg font-bold leading-tight">勘太郎 ver. 1.0</h1>
              <p className="text-xs text-slate-400">個人事業主 出納帳 / 店舗売上 / Uber / Rocket Now</p>
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
        {/* TAB 1: 入力フォーム (収支・仕入れレシート画像・銀行管理) */}
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
                className={`py-2.5
