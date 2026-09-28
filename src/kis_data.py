"""
KIS API 시세 조회 모듈 (Rate Limit 처리 포함)
- 실전 계정 최적화
"""
import time
import threading
import pandas as pd
import requests
from datetime import datetime, timedelta
from src.kis_auth import KISAuth


# 전역 Rate Limiter (스레드 안전)
class RateLimiter:
    """초당 요청 제한 관리"""
    
    def __init__(self, max_per_second: int = 15):
        """
        max_per_second: 초당 최대 요청 수
        - 실전: 20 (안전하게 15로)
        - 모의: 2 (안전하게 1로)
        """
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self.last_request_time = 0
        self.lock = threading.Lock()
    
    def wait(self):
        """요청 전 필요한 만큼 대기"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


# 계정 유형에 따라 자동 조정
import os
from dotenv import load_dotenv
load_dotenv()

_account_type = os.getenv("KIS_ACCOUNT_TYPE", "REAL")
if _account_type == "REAL":
    _rate_limiter = RateLimiter(max_per_second=10)  # 실전: 초당 15회 (안전)
else:
    _rate_limiter = RateLimiter(max_per_second=1)   # 모의: 초당 1회


class KISDataSource:
    """KIS API로 일봉 데이터 조회"""

    def __init__(self):
        self.auth = KISAuth()

    def get_daily_dataframe(self, code: str, days: int = 100) -> pd.DataFrame:
        """일봉 데이터 조회"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                _rate_limiter.wait()
                
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
                
                url = f"{self.auth.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
                headers = self.auth.get_headers(tr_id="FHKST03010100")
                
                params = {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": code,
                    "FID_INPUT_DATE_1": start_date,
                    "FID_INPUT_DATE_2": end_date,
                    "FID_PERIOD_DIV_CODE": "D",
                    "FID_ORG_ADJ_PRC": "0",
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code != 200:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    print(f"[ERROR] {code} 조회 실패: {response.text[:100]}")
                    return pd.DataFrame()
                
                data = response.json()
                
                if data.get("rt_cd") != "0":
                    # Rate limit 오류 시 대기 후 재시도
                    if "EGW00201" in data.get("msg_cd", ""):
                        time.sleep(1 + attempt)  # 재시도마다 대기 시간 증가
                        continue
                    print(f"[ERROR] {code} 응답 오류: {data.get('msg1')}")
                    return pd.DataFrame()
                
                daily_data = data.get("output2", [])
                
                if not daily_data:
                    return pd.DataFrame()
                
                rows = []
                for item in daily_data:
                    if not item.get("stck_bsop_date"):
                        continue
                    rows.append({
                        "일자": item["stck_bsop_date"],
                        "시가": int(item["stck_oprc"]),
                        "고가": int(item["stck_hgpr"]),
                        "저가": int(item["stck_lwpr"]),
                        "종가": int(item["stck_clpr"]),
                        "거래량": int(item["acml_vol"]),
                    })
                
                df = pd.DataFrame(rows)
                df = df.sort_values("일자").reset_index(drop=True)
                
                return df
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                print(f"[ERROR] {code} 예외 발생: {e}")
                return pd.DataFrame()
        
        return pd.DataFrame()

    def get_current_price(self, code: str) -> dict:
        """현재가 조회 (등락률 포함, NXT/시간외 반영)"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                _rate_limiter.wait()
                
                url = f"{self.auth.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
                headers = self.auth.get_headers(tr_id="FHKST01010100")
                
                params = {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": code,
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code != 200:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return {}
                
                data = response.json()
                
                if data.get("rt_cd") != "0":
                    # Rate limit 오류 시 대기 후 재시도
                    if "EGW00201" in data.get("msg_cd", ""):
                        time.sleep(1 + attempt)
                        continue
                    return {}
                
                output = data.get("output", {})
                
                return {
                    "current_price": int(output.get("stck_prpr", 0)),
                    "prev_close": int(output.get("stck_prpr", 0)) - int(output.get("prdy_vrss", 0)),
                    "change": int(output.get("prdy_vrss", 0)),
                    "change_pct": float(output.get("prdy_ctrt", 0)),
                    "volume": int(output.get("acml_vol", 0)),
                }
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                print(f"[ERROR] {code} 현재가 조회 실패: {e}")
                return {}
        
        return {}
    