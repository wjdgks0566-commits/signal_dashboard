"""
KIS API 인증 모듈
- 토큰 발급 및 관리 (24시간 유효)
"""
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class KISAuth:
    """KIS API 인증 관리"""

    def __init__(self):
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.account_type = os.getenv("KIS_ACCOUNT_TYPE", "MOCK")
        
        if self.account_type == "REAL":
            self.base_url = "https://openapi.koreainvestment.com:9443"
        else:
            self.base_url = "https://openapivts.koreainvestment.com:29443"
        
        self.token_cache_file = Path(".kis_token_cache.json")
        self._token = None
        self._token_expires = None

    def get_token(self) -> str:
        """토큰 발급 또는 캐시된 토큰 반환"""
        if self._load_cached_token():
            return self._token
        
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(body))
        
        if response.status_code != 200:
            raise Exception(f"토큰 발급 실패: {response.text}")
        
        data = response.json()
        self._token = data["access_token"]
        self._token_expires = datetime.now() + timedelta(hours=23)
        
        self._save_token_cache()
        
        print(f"[KIS] 토큰 발급 완료 (만료: {self._token_expires.strftime('%Y-%m-%d %H:%M')})")
        return self._token

    def _load_cached_token(self) -> bool:
        if not self.token_cache_file.exists():
            return False
        
        try:
            with open(self.token_cache_file, "r") as f:
                cache = json.load(f)
            
            expires = datetime.fromisoformat(cache["expires"])
            if datetime.now() >= expires:
                return False
            
            self._token = cache["token"]
            self._token_expires = expires
            return True
        except Exception:
            return False

    def _save_token_cache(self):
        with open(self.token_cache_file, "w") as f:
            json.dump({
                "token": self._token,
                "expires": self._token_expires.isoformat(),
            }, f)

    def get_headers(self, tr_id: str) -> dict:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.get_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }
    