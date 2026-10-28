import os
import json
from typing import Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

from backend.database import get_setting, set_setting

# Google Drive API スコープ
DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]

# デフォルトのGoogleドライブフォルダID
DEFAULT_FOLDER_ID = "1qX_mCHjCEFKQoGfuoMrIxJvOZIpWibq8"

def get_drive_folder_id() -> str:
    """設定からGoogleドライブのフォルダIDを取得"""
    return get_setting("google_drive_folder_id", DEFAULT_FOLDER_ID)

def set_drive_folder_id(folder_id: str):
    """GoogleドライブのフォルダIDを設定"""
    set_setting("google_drive_folder_id", folder_id)

def get_drive_service(credentials_path: Optional[str] = None):
    """Google Drive API サービスを初期化（環境変数 GOOGLE_CREDENTIALS_JSON または ファイルに対応）"""
    # 1. クラウドデプロイ用: 環境変数 GOOGLE_CREDENTIALS_JSON を優先チェック
    env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()
    if env_creds:
        try:
            cred_data = json.loads(env_creds)
            if cred_data.get("type") == "service_account":
                creds = service_account.Credentials.from_service_account_info(cred_data, scopes=DRIVE_SCOPES)
                return build('drive', 'v3', credentials=creds)
        except Exception as e:
            print(f"Drive env credentials parse error: {e}")

    # 2. ローカルファイル (credentials.json / service_account.json) をチェック
    creds_path = credentials_path or get_setting("google_credentials_path", "credentials.json")
    if not os.path.isabs(creds_path):
        creds_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), creds_path)

    if not os.path.exists(creds_path):
        # service_account.json も探す
        alt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "service_account.json")
        if os.path.exists(alt_path):
            creds_path = alt_path
        else:
            return None

    try:
        with open(creds_path, "r", encoding="utf-8") as f:
            cred_data = json.load(f)

        if cred_data.get("type") == "service_account":
            creds = service_account.Credentials.from_service_account_file(creds_path, scopes=DRIVE_SCOPES)
            return build('drive', 'v3', credentials=creds)
        elif "installed" in cred_data or "web" in cred_data:
            token_path = os.path.join(os.path.dirname(creds_path), "token.json")
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, DRIVE_SCOPES)
                return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Drive service initialization error: {e}")
        return None

    return None

def upload_to_google_drive(local_path: str, filename: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """
    ローカルのレシート画像をGoogleドライブの指定フォルダへアップロード
    """
    folder_id = get_drive_folder_id()
    service = get_drive_service()

    if not service:
        return {
            "success": False,
            "error": "credentials_not_found",
            "message": "Google Driveの認証キー (credentials.json または service_account.json) が配置されていません。プロジェクト直下に配置してください。",
            "folder_id": folder_id
        }

    try:
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)

        drive_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, webContentLink, thumbnailLink'
        ).execute()

        file_id = drive_file.get('id')
        web_view_link = drive_file.get('webViewLink')

        # 誰でも閲覧可能なリンク権限を設定（アプリ一覧でのプレビュー表示用）
        try:
            service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
        except Exception:
            pass # 組織ポリシー等で制限されている場合はスキップ

        # 直リンクプレビューURL (Google Drive Direct View URL)
        direct_preview_url = f"https://drive.google.com/uc?export=view&id={file_id}"

        return {
            "success": True,
            "file_id": file_id,
            "web_view_link": web_view_link,
            "direct_preview_url": direct_preview_url,
            "folder_id": folder_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": "upload_failed",
            "message": f"Googleドライブへのアップロード中にエラーが発生しました: {str(e)}",
            "folder_id": folder_id
        }

