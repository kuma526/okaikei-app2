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
        setFormData(prev => ({
