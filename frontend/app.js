const { useState, useEffect, useMemo, useRef } = React;

const LOCAL_BACKUP_KEY = "kantaro_transactions_backup_v1";

const CATEGORIES = [
  "仕入高", "消耗品費", "旅費交通費", "通信費", "会議費",
  "接待交際費", "新聞図書費", "荷造運賃", "水道光熱費",
  "修繕費", "支払手数料", "地代家賃", "広告宣伝費", "雑費"
];

const COMMON_DESCRIPTIONS = {
  "仕入高": ["仕入れ商品一式", "テイクアウト用包材・容器", "販売用原材料・食材", "店舗・物販仕入れ在庫", "卸問屋仕入れ伝票"],
  "消耗品費": ["文房具・事務用品一式", "コピー用紙 A4 500枚", "PC周辺サプライ・USBケーブル", "作業用備品・手袋・工具", "梱包用OPPテープ・緩衝材", "店舗清掃・衛生消耗品"],
  "旅費交通費": ["配達車両 ガソリン給油", "コインパーキング 駐車料金", "高速道路通行料 (ETC)", "業務移動 電車・バス運賃", "業務連絡 タクシー利用"],
  "通信費": ["業務連絡用 スマホ通信料", "事務所 光回線・インターネット代", "郵便切手・レターパック代", "業務通話・SMS利用料"],
  "会議費": ["カフェ・喫茶店 業務打ち合わせ代", "コワーキングスペース ドロップイン利用料"],
  "接待交際費": ["取引先への手土産・菓子折り", "取引先との会食飲食代", "お中元・お歳暮"],
  "荷造運賃": ["商品発送 宅急便・ヤマト運輸送料", "ゆうパック・郵便送料", "発送用ダンボール箱"],
  "水道光熱費": ["電気料金 (事業按分分)", "ガス料金 (事業按分分)", "水道料金 (事業按分分)"],
  "修繕費": ["配達用バイク・車両オイル交換・整備代", "業務PC・スマートフォンの修理費用"],
  "支払手数料": ["他行あて電信振込手数料", "決済手数料・代引手数料", "口座振替手数料"],
  "地代家賃": ["事務所・作業スペース家賃 (事業按分)", "月極駐車場料金"],
  "広告宣伝費": ["Web広告出稿料", "チラシ印刷・ポスティング費用"],
  "雑費": ["諸雑費・手数料", "住民票・印鑑証明書発行手数料"],
  "売上高": ["店舗レジ現金売上", "店舗カード売上 (楽天ターミナル)", "第1週 配達売上振込", "第2週 配達売上振込", "第3週 配達売上振込", "第4週 配達売上振込", "即時出金 振込売上"],
  "事業主借": ["手元現金より事業口座へ預入", "個人口座からの運転資金補填"],
  "事業主貸": ["事業口座より生活費・手元現金引出", "プライベート支出の事業口座引落分"]
};

const BANKS = ["三井住友銀行", "楽天銀行", "三菱UFJ銀行", "みずほ銀行", "ゆうちょ銀行", "PayPay銀行", "住信SBIネット銀行", "現金"];

const EXPENSE_PAYMENT_METHODS = [
  "現金", "カード決済", "QRコード支払い", "三井住友銀行", "楽天銀行",
  "三菱UFJ銀行", "みずほ銀行", "ゆうちょ銀行", "PayPay銀行", "住信SBIネット銀行"
];

const RAKUTEN_PAYMENT_TYPES = [
  "クレジットカード全般",
  "QRコード (楽天/au/SmartCode等)",
  "QRコード (PayPay/d払い)",
  "電子マネー (交通系/Edy/WAON等)",
  "電子マネー (QUICPay/iD)"
];

const RAKUTEN_FEE_RATES = {
  "クレジットカード全般": 3.24,
  "QRコード (楽天/au/SmartCode等)": 2.95,
  "QRコード (PayPay/d払い)": 3.24,
  "電子マネー (交通系/Edy/WAON等)": 2.95,
  "電子マネー (QUICPay/iD)": 3.24
};

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
  const [activeTab, setActiveTab] = useState("input");
  const [currentMonth, setCurrentMonth] = useState(new Date().toISOString().slice(0, 7));
  
  const [transactions, setTransactions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [alertMsg, setAlertMsg] = useState(null);
  const [editingId, setEditingId] = useState(null);

  const [entryType, setEntryType] = useState("expense");
  const [sourceType, setSourceType] = useState("purchase");
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

  const [storePaymentMethod, setStorePaymentMethod] = useState("cash");
  const [rakutenPaymentType, setRakutenPaymentType] = useState("クレジットカード全般");
  const [cardFeeRate, setCardFeeRate] = useState("3.24");

  const [uploadingImage, setUploadingImage] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);
  const fileInputRef = useRef(null);
  const backupInputRef = useRef(null);

  const [settings, setSettings] = useState({
    default_bank_name: "三井住友銀行",
    card_fee_rate: "3.24"
  });

  const [viewImageModal, setViewImageModal] = useState(null);
  const [filterType, setFilterType] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  // 初回起動時にブラウザのバックアップとサーバーを自動同期
  useEffect(() => {
    syncWithLocalBackup().then(() => {
      loadTransactions();
      loadSummary();
      loadSettings();
    });
  }, []);

  useEffect(() => {
    loadTransactions();
    loadSummary();
  }, [currentMonth]);

  const showAlert = (text, type = "success") => {
    setAlertMsg({ text, type });
    setTimeout(() => setAlertMsg(null), 4000);
  };

  const syncWithLocalBackup = async () => {
    try {
      const saved = localStorage.getItem(LOCAL_BACKUP_KEY);
      const localTxs = saved ? JSON.parse(saved) : [];
      const res = await fetch("/api/transactions/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(localTxs)
      });
      if (res.ok) {
        const data = await res.json();
        if (data.transactions) {
          localStorage.setItem(LOCAL_BACKUP_KEY, JSON.stringify(data.transactions));
        }
      }
    } catch (e) {
      console.error("Sync error:", e);
    }
  };

  const updateLocalBackup = async () => {
    try {
      const res = await fetch("/api/transactions");
      if (res.ok) {
        const allTxs = await res.json();
        localStorage.setItem(LOCAL_BACKUP_KEY, JSON.stringify(allTxs));
      }
    } catch (e) {
      console.error(e);
    }
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
      if (data.card_fee_rate) {
        setCardFeeRate(data.card_fee_rate);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleTypeChange = (type) => {
    setEntryType(type);
    if (type === "income") {
      setSourceType("store");
      setStorePaymentMethod("cash");
      setFormData(prev => ({ ...prev, category: "売上高", payee: "店舗売上 (現金)", description: "", bank_name: "現金" }));
    } else if (type === "expense") {
      setSourceType("purchase");
      setFormData(prev => ({ ...prev, category: "仕入高", payee: "", description: "", bank_name: "現金" }));
    } else if (type === "bank") {
      setSourceType("deposit");
      setFormData(prev => ({ ...prev, category: "事業主借", payee: "手元現金入金", description: "", bank_name: "三井住友銀行" }));
    }
  };

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

  const handleStorePaymentMethodChange = (method) => {
    setStorePaymentMethod(method);
    if (method === "cash") {
      setFormData(prev => ({ ...prev, payee: "店舗売上 (現金)", bank_name: "現金" }));
    } else {
      const defaultRate = RAKUTEN_FEE_RATES[rakutenPaymentType] !== undefined ? String(RAKUTEN_FEE_RATES[rakutenPaymentType]) : "3.24";
      setCardFeeRate(defaultRate);
      setFormData(prev => ({ ...prev, payee: "店舗売上 (楽天ターミナル)", bank_name: "楽天ターミナル" }));
    }
  };

  const handleRakutenPaymentTypeChange = (type) => {
    setRakutenPaymentType(type);
    if (RAKUTEN_FEE_RATES[type] !== undefined) {
      setCardFeeRate(String(RAKUTEN_FEE_RATES[type]));
    }
  };

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

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadingImage(true);
    try {
      const base64DataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = (error) => reject(error);
        reader.readAsDataURL(file);
      });

      setPreviewImage(base64DataUrl);
      const base64Content = base64DataUrl.includes(",") ? base64DataUrl.split(",")[1] : base64DataUrl;

      const res = await fetch("/api/upload-receipt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: file.name || "receipt.jpg",
          date: formData.date,
          file: base64Content
        })
      });

      const data = await res.json();
      if (data.success && data.receipt_url) {
        setFormData(prev => ({ ...prev, receipt_path: data.receipt_url }));
        showAlert(`📸 ${data.filename || 'レシート'} を保存しました！`);
      } else {
        showAlert("画像の保存に失敗しました", "error");
      }
    } catch (err) {
      showAlert("画像のアップロードに失敗しました", "error");
    } finally {
      setUploadingImage(false);
    }
  };

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

      const isRakutenTerminal = (entryType === "income" && sourceType === "store" && storePaymentMethod === "rakuten_terminal");

      if (isRakutenTerminal && feeCalculation.gross > 0) {
        const pType = rakutenPaymentType;
        const breakdownMemo = `【${pType}売上内訳】総額: ¥${feeCalculation.gross.toLocaleString()} / 手数料(${feeCalculation.rate}%): -¥${feeCalculation.fee.toLocaleString()} / 振込受取額: ¥${feeCalculation.net.toLocaleString()}`;
        if (!finalDescription) {
          finalDescription = breakdownMemo;
        } else if (!finalDescription.includes("振込受取額:")) {
          finalDescription = `${finalDescription} ${breakdownMemo}`;
        }
        finalOcrData.fee_calculation = {
          gross_amount: feeCalculation.gross,
          fee_rate: feeCalculation.rate,
          fee_amount: feeCalculation.fee,
          net_amount: feeCalculation.net,
          payment_type: pType
        };
      }

      const payload = {
        date: formData.date,
        type: entryType,
        source_type: sourceType,
        category: formData.category,
        amount: parseInt(formData.amount, 10),
        payee: formData.payee,
        description: finalDescription,
        bank_name: formData.bank_name,
        receipt_path: formData.receipt_path,
        ocr_data: Object.keys(finalOcrData).length > 0 ? finalOcrData : null
      };

      const url = editingId ? `/api/transactions/${editingId}` : "/api/transactions";
      const method = editingId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showAlert(editingId ? "✅ 取引を更新しました！" : "✅ 取引を記録しました！");
        setEditingId(null);
        setFormData(prev => ({
          ...prev,
          amount: "",
          description: "",
          receipt_path: "",
          ocr_data: null
        }));
        setPreviewImage(null);
        if (fileInputRef.current) fileInputRef.current.value = "";

        await updateLocalBackup();
        loadTransactions();
        loadSummary();
      } else {
        showAlert("登録に失敗しました", "error");
      }
    } catch (err) {
      showAlert("通信エラーが発生しました", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (t) => {
    setEditingId(t.id);
    setEntryType(t.type || "expense");
    setSourceType(t.source_type || "purchase");
    setFormData({
      date: t.date,
      amount: String(t.amount),
      category: t.category,
      payee: t.payee || "",
      description: t.description || "",
      bank_name: t.bank_name || "現金",
      receipt_path: t.receipt_path || "",
      ocr_data: t.ocr_data || null
    });
    setActiveTab("input");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (id) => {
    if (!confirm("この取引記録を削除してもよろしいですか？")) return;
    try {
      const res = await fetch(`/api/transactions/${id}`, { method: "DELETE" });
      if (res.ok) {
        const saved = localStorage.getItem(LOCAL_BACKUP_KEY);
        if (saved) {
          const filtered = JSON.parse(saved).filter(t => t.id !== id);
          localStorage.setItem(LOCAL_BACKUP_KEY, JSON.stringify(filtered));
        }
        showAlert("取引を削除しました");
        loadTransactions();
        loadSummary();
      }
    } catch (e) {
      showAlert("削除に失敗しました", "error");
    }
  };

  const handleDownloadBackup = async () => {
    try {
      const res = await fetch("/api/transactions");
      const allTxs = await res.json();
      const blob = new Blob([JSON.stringify(allTxs, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `kantaro_backup_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
    } catch (e) {
      showAlert("バックアップ作成に失敗しました", "error");
    }
  };

  const handleRestoreBackup = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const text = await file.text();
      const imported = JSON.parse(text);
      if (Array.isArray(imported)) {
        await fetch("/api/transactions/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(imported)
        });
        await updateLocalBackup();
        loadTransactions();
        loadSummary();
        showAlert("✅ バックアップからデータを復元しました！");
      }
    } catch (err) {
      showAlert("ファイルの読み込みに失敗しました", "error");
    }
  };

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    try {
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: "default_bank_name", value: settings.default_bank_name })
      });
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: "card_fee_rate", value: cardFeeRate })
      });
      showAlert("設定を保存しました！");
    } catch (e) {
      showAlert("設定の保存に失敗しました", "error");
    }
  };

  const filteredTransactions = useMemo(() => {
    return transactions.filter(t => {
      if (filterType !== "all" && t.type !== filterType) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const str = `${t.payee} ${t.description} ${t.category} ${t.amount}`.toLowerCase();
        if (!str.includes(q)) return false;
      }
      return true;
    });
  }, [transactions, filterType, searchQuery]);

  return (
    <div className="max-w-md mx-auto sm:max-w-2xl md:max-w-4xl min-h-screen bg-slate-50 pb-24 text-slate-800">
      {alertMsg && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full shadow-lg text-sm font-medium transition-all ${
          alertMsg.type === "error" ? "bg-red-600 text-white" : "bg-emerald-600 text-white"
        }`}>
          {alertMsg.text}
        </div>
      )}

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

      <main className="p-4 space-y-4">
        {activeTab === "input" && (
          <div className="space-y-4">
            {editingId && (
              <div className="bg-amber-100 border border-amber-400 text-amber-900 px-3 py-2 rounded-xl flex justify-between items-center text-xs font-bold">
                <span>✏️ 取引データを編集中です</span>
                <button
                  type="button"
                  onClick={() => setEditingId(null)}
                  className="bg-white px-2.5 py-1 rounded-lg border border-amber-300"
                >
                  キャンセル
                </button>
              </div>
            )}

            <div className="grid grid-cols-3 gap-2 bg-slate-200 p-1 rounded-xl">
              <button
                type="button"
                onClick={() => handleTypeChange("expense")}
                className={`py-2.5 text-xs sm:text-sm font-bold rounded-lg transition-all flex items-center justify-center space-x-1 ${
                  entryType === "expense" ? "bg-rose-500 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span>💸</span><span>支出・仕入れ</span>
              </button>
              <button
                type="button"
                onClick={() => handleTypeChange("income")}
                className={`py-2.5 text-xs sm:text-sm font-bold rounded-lg transition-all flex items-center justify-center space-x-1 ${
                  entryType === "income" ? "bg-emerald-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span>💰</span><span>売上・収入</span>
              </button>
              <button
                type="button"
                onClick={() => handleTypeChange("bank")}
                className={`py-2.5 text-xs sm:text-sm font-bold rounded-lg transition-all flex items-center justify-center space-x-1 ${
                  entryType === "bank" ? "bg-blue-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span>🏦</span><span>銀行入出金</span>
              </button>
            </div>

            {entryType === "income" && (
              <div className="space-y-2">
                <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                  <button type="button" onClick={() => handleSourceTypeChange("store")} className={`flex-1 min-w-[105px] py-2 px-3 rounded-lg text-xs font-bold border ${sourceType === "store" ? "bg-emerald-50 border-emerald-500 text-emerald-800" : "bg-white border-slate-200 text-slate-600"}`}>🏪 1. 店舗売上</button>
                  <button type="button" onClick={() => handleSourceTypeChange("uber")} className={`flex-1 min-w-[105px] py-2 px-3 rounded-lg text-xs font-bold border ${sourceType === "uber" ? "bg-emerald-50 border-emerald-500 text-emerald-800" : "bg-white border-slate-200 text-slate-600"}`}>🛵 2. UBER振込</button>
                  <button type="button" onClick={() => handleSourceTypeChange("rocket")} className={`flex-1 min-w-[125px] py-2 px-3 rounded-lg text-xs font-bold border ${sourceType === "rocket" ? "bg-emerald-50 border-emerald-500 text-emerald-800" : "bg-white border-slate-200 text-slate-600"}`}>⚡ 3. ROCKET NOW振込</button>
                  <button type="button" onClick={() => handleSourceTypeChange("manual_income")} className={`flex-1 min-w-[100px] py-2 px-3 rounded-lg text-xs font-bold border ${sourceType === "manual_income" ? "bg-emerald-50 border-emerald-500 text-emerald-800" : "bg-white border-slate-200 text-slate-600"}`}>✏️ その他売上</button>
                </div>

                {sourceType === "store" && (
                  <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-2.5">
                    <div className="grid grid-cols-2 gap-2">
                      <button type="button" onClick={() => handleStorePaymentMethodChange("cash")} className={`py-2 px-3 rounded-lg text-xs font-bold border ${storePaymentMethod === "cash" ? "bg-emerald-600 text-white border-emerald-600" : "bg-white text-slate-700 border-emerald-200"}`}>💵 現金売上</button>
                      <button type="button" onClick={() => handleStorePaymentMethodChange("rakuten_terminal")} className={`py-2 px-3 rounded-lg text-xs font-bold border ${storePaymentMethod === "rakuten_terminal" ? "bg-rose-600 text-white border-rose-600" : "bg-white text-slate-700 border-emerald-200"}`}>🔴 楽天ターミナル</button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {entryType === "expense" && (
              <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                <button type="button" onClick={() => handleSourceTypeChange("purchase")} className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border ${sourceType === "purchase" ? "bg-rose-50 border-rose-500 text-rose-800" : "bg-white border-slate-200 text-slate-600"}`}>📦 仕入れ (レシート)</button>
                <button type="button" onClick={() => handleSourceTypeChange("bank_transfer")} className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border ${sourceType === "bank_transfer" ? "bg-rose-50 border-rose-500 text-rose-800" : "bg-white border-slate-200 text-slate-600"}`}>🏛️ 銀行振込</button>
                <button type="button" onClick={() => handleSourceTypeChange("manual_expense")} className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border ${sourceType === "manual_expense" ? "bg-rose-50 border-rose-500 text-rose-800" : "bg-white border-slate-200 text-slate-600"}`}>🧾 その他経費</button>
              </div>
            )}

            <div className="bg-slate-50 border-2 border-dashed border-slate-300 rounded-2xl p-4 text-center">
              <input ref={fileInputRef} type="file" accept="image/*" capture="environment" onChange={handleFileUpload} className="hidden" id="receipt-file" />
              {uploadingImage ? (
                <p className="text-xs font-bold text-slate-700 py-3">画像を保存中...</p>
              ) : previewImage ? (
                <div className="space-y-2">
                  <img src={previewImage} alt="Preview" className="h-36 object-contain mx-auto rounded-lg" />
                  <p className="text-xs text-emerald-700 font-bold">✅ レシート添付済み（日付つきで自動保存）</p>
                </div>
              ) : (
                <div className="py-2">
                  <div className="text-2xl mb-1">📸</div>
                  <p className="text-sm font-bold text-slate-800">レシート・領収書画像を添付</p>
                  <p className="text-xs text-slate-500 mt-0.5 mb-2.5">取引日入りの名前（receipt_日付.jpg）でGoogleドライブに保存されます</p>
                  <label htmlFor="receipt-file" className="cursor-pointer inline-flex items-center space-x-2 bg-slate-800 text-white font-bold px-4 py-2 rounded-xl text-xs">
                    <span>📷 カメラ撮影 / 写真を選択</span>
                  </label>
                </div>
              )}
            </div>

            <form onSubmit={handleSubmit} className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">金額 (円) *</label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-2xl font-bold text-slate-400">¥</span>
                  <input
                    type="number"
                    inputMode="numeric"
                    required
                    placeholder="0"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-300 rounded-xl text-2xl font-extrabold text-slate-900 outline-none"
                  />
                </div>
              </div>

              {entryType === "income" && sourceType === "store" && storePaymentMethod === "rakuten_terminal" && (
                <div className="bg-amber-50 border border-amber-300 rounded-xl p-3 space-y-2 text-xs">
                  <div className="flex justify-between font-bold text-amber-900">
                    <span>🧮 楽天ターミナル手数料 ({feeCalculation.rate}%)</span>
                    <span>手数料: -¥{feeCalculation.fee.toLocaleString()} / 受取額: ¥{feeCalculation.net.toLocaleString()}</span>
                  </div>
                </div>
              )}

              {entryType !== "bank" && (
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">勘定科目 *</label>
                  {entryType === "income" ? (
                    <input type="text" readOnly value={formData.category} className="w-full px-3 py-2.5 bg-slate-100 border border-slate-300 rounded-xl font-bold text-slate-700" />
                  ) : (
                    <select value={formData.category} onChange={(e) => setFormData({ ...formData, category: e.target.value })} className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl font-bold text-slate-800">
                      {CATEGORIES.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                    </select>
                  )}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">取引日 *</label>
                  <input type="date" required value={formData.date} onChange={(e) => setFormData({ ...formData, date: e.target.value })} className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">店舗・取引先名</label>
                  <input type="text" placeholder="セブンイレブン、卸問屋など" value={formData.payee} onChange={(e) => setFormData({ ...formData, payee: e.target.value })} className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium" />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">決済手段 / 口座</label>
                  <select value={formData.bank_name} onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })} className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium">
                    <option value="現金">現金</option>
                    <option value="楽天ターミナル">楽天ターミナル</option>
                    {EXPENSE_PAYMENT_METHODS.filter(m => m !== "現金").map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">品目・摘要メモ</label>
                  <input type="text" placeholder="品目やメモを入力" value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className="w-full px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium" />
                </div>
              </div>

              <button type="submit" disabled={loading} className="w-full py-3.5 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl shadow-lg text-base">
                {loading ? "保存中..." : (editingId ? "💾 変更を保存する" : "💾 この内容で出納帳に記録する")}
              </button>
            </form>
          </div>
        )}

        {activeTab === "list" && (
          <div className="space-y-4">
            {summary && (
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-2xl text-center">
                  <p className="text-[11px] font-bold text-emerald-700">総収入 (売上)</p>
                  <p className="text-base sm:text-xl font-extrabold text-emerald-900 mt-0.5">¥{summary.total_income.toLocaleString()}</p>
                </div>
                <div className="bg-rose-50 border border-rose-200 p-3 rounded-2xl text-center">
                  <p className="text-[11px] font-bold text-rose-700">総支出 (経費)</p>
                  <p className="text-base sm:text-xl font-extrabold text-rose-900 mt-0.5">¥{summary.total_expense.toLocaleString()}</p>
                </div>
                <div className="bg-sky-50 border border-sky-200 p-3 rounded-2xl text-center">
                  <p className="text-[11px] font-bold text-sky-700">差引利益 (粗利)</p>
                  <p className="text-base sm:text-xl font-extrabold text-sky-900 mt-0.5">{summary.net_income >= 0 ? '+' : ''}¥{summary.net_income.toLocaleString()}</p>
                </div>
              </div>
            )}

            <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-3">
              <div className="flex flex-col sm:flex-row gap-2 justify-between items-center">
                <h2 className="text-xs font-bold text-slate-500">📋 記録一覧 ({filteredTransactions.length}件)</h2>
                <div className="w-full sm:w-auto flex gap-2">
                  <input type="text" placeholder="キーワード検索..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full sm:w-40 px-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg" />
                  <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="px-2 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg font-bold">
                    <option value="all">すべて表示</option>
                    <option value="income">売上のみ</option>
                    <option value="expense">支出のみ</option>
                  </select>
                </div>
              </div>

              <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
                {filteredTransactions.length === 0 ? (
                  <p className="text-center py-8 text-xs text-slate-400">該当する取引データはありません</p>
                ) : (
                  filteredTransactions.map(t => (
                    <div key={t.id} className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between gap-2 text-xs">
                      <div className="space-y-0.5">
                        <div className="flex items-center space-x-1.5">
                          <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${t.type === 'income' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                            {t.category}
                          </span>
                          <span className="text-slate-400">{t.date}</span>
                          <span className="text-slate-600 font-medium">({t.bank_name})</span>
                        </div>
                        <div className="font-bold text-slate-800 text-sm">
                          {t.payee || '摘要なし'} {t.description && <span className="text-slate-500 font-normal text-xs">/ {t.description}</span>}
                        </div>
                        {t.receipt_path && (
                          <button type="button" onClick={() => setViewImageModal(getDriveDisplayUrl(t.receipt_path))} className="inline-flex items-center space-x-1 text-indigo-600 font-bold mt-1">
                            <span>📸 レシート画像を表示</span>
                          </button>
                        )}
                      </div>
                      <div className="text-right flex items-center space-x-1">
                        <p className={`text-base font-extrabold mr-1 ${t.type === 'income' ? 'text-emerald-700' : 'text-rose-700'}`}>
                          {t.type === 'income' ? '+' : '-'}¥{t.amount.toLocaleString()}
                        </p>
                        <button type="button" onClick={() => handleEdit(t)} className="p-1.5 text-slate-500 hover:bg-slate-200 rounded-lg" title="編集">✏️</button>
                        <button type="button" onClick={() => handleDelete(t.id)} className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg" title="削除">🗑️</button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "export" && (
          <div className="space-y-4">
            <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-3">
              <h2 className="text-xs font-bold text-slate-500">📤 月次帳票・確定申告用出力 ({currentMonth})</h2>
              <div className="grid grid-cols-2 gap-2">
                <a href={`/api/export/excel?month=${currentMonth}`} className="p-3 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-xl text-center block">
                  <div className="text-xl mb-0.5">📊</div>
                  <div className="text-xs font-bold text-emerald-900">Excel出納帳</div>
                  <div className="text-[10px] text-emerald-700">エクセル形式で保存</div>
                </a>
                <a href={`/api/export/pdf?month=${currentMonth}`} className="p-3 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-xl text-center block">
                  <div className="text-xl mb-0.5">📄</div>
                  <div className="text-xs font-bold text-rose-900">PDF月次レポート</div>
                  <div className="text-[10px] text-rose-700">日本語フォント対応</div>
                </a>
                <a href={`/api/export/csv/mf?month=${currentMonth}`} className="p-3 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-xl text-center block">
                  <div className="text-xl mb-0.5">📥</div>
                  <div className="text-xs font-bold text-blue-900">MFクラウド用 CSV</div>
                  <div className="text-[10px] text-blue-700">マネーフォワード形式</div>
                </a>
                <a href={`/api/export/csv/yayoi?month=${currentMonth}`} className="p-3 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-xl text-center block">
                  <div className="text-xl mb-0.5">📥</div>
                  <div className="text-xs font-bold text-indigo-900">弥生会計用 CSV</div>
                  <div className="text-[10px] text-indigo-700">弥生インポート形式</div>
                </a>
              </div>
              <a href={`/api/export/csv/tax?month=${currentMonth}`} className="p-3 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-xl text-center block">
                <div className="text-xs font-bold text-amber-900">📑 確定申告・汎用一覧 CSV出力</div>
                <div className="text-[10px] text-amber-700">全項目を網羅した標準CSV</div>
              </a>
            </div>

            <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-3">
              <h2 className="text-xs font-bold text-slate-500">🛡️ データのバックアップ・復元 (消滅防止)</h2>
              <p className="text-xs text-slate-500">ブラウザ内にも自動保存されていますが、ファイルとして手元に保存しておくと100%安全です。</p>
              <div className="grid grid-cols-2 gap-2">
                <button type="button" onClick={handleDownloadBackup} className="p-2.5 bg-slate-800 text-white rounded-xl text-xs font-bold">
                  💾 全データを保存
                </button>
                <label className="p-2.5 bg-slate-100 border border-slate-300 text-slate-700 rounded-xl text-xs font-bold text-center cursor-pointer">
                  📂 ファイルから復元
                  <input ref={backupInputRef} type="file" accept=".json" onChange={handleRestoreBackup} className="hidden" />
                </label>
              </div>
            </div>
          </div>
        )}
      </main>

      <nav className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t border-slate-200 z-40 shadow-lg">
        <div className="max-w-md mx-auto sm:max-w-2xl md:max-w-4xl flex items-center justify-around py-2">
          <button type="button" onClick={() => setActiveTab("input")} className={`flex flex-col items-center justify-center w-20 py-1 ${activeTab === "input" ? "text-indigo-600 font-bold" : "text-slate-500"}`}>
            <span className="text-xl">✏️</span><span className="text-[11px] mt-0.5">記帳・入力</span>
          </button>
          <button type="button" onClick={() => setActiveTab("list")} className={`flex flex-col items-center justify-center w-20 py-1 ${activeTab === "list" ? "text-indigo-600 font-bold" : "text-slate-500"}`}>
            <span className="text-xl">📊</span><span className="text-[11px] mt-0.5">一覧・集計</span>
          </button>
          <button type="button" onClick={() => setActiveTab("export")} className={`flex flex-col items-center justify-center w-20 py-1 ${activeTab === "export" ? "text-indigo-600 font-bold" : "text-slate-500"}`}>
            <span className="text-xl">📄</span><span className="text-[11px] mt-0.5">帳票出力</span>
          </button>
        </div>
      </nav>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
