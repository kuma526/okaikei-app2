"""
出納帳Webアプリ 起動エントリーポイント
"""
import uvicorn
import os
import sys

# パス追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("=" * 60)
    print(f" 個人事業主向け 出納帳 Webアプリケーション 起動中 (Port: {port})...")
    print(f" PCブラウザ: http://localhost:{port}")
    print(f" スマホ・タブレット（同一Wi-Fi内）: http://[PCのIPアドレス]:{port}")
    print("=" * 60)
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=False)

