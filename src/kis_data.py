"""
KIS API 시세 조회 모듈 (Rate Limit + 일봉 캐싱)
- 일봉 과거분은 하루 1회만 조회하고 파일 캐시에 보관
- 이후 실행은 현재가 1회만 호출해 오늘 봉을 합성
"""
import json
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from src.kis_auth import KISAuth

load_dotenv()

CACHE_DIR = Path("cache")
COLUMNS = ["일자", "시가", "고가", "저가", "종가", "거래량"]


class RateLimiter:
    """초당 요청 제한 관리 (스레드 안전)"""

    def __init__(self, max_per_second: int = 8):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self.last_request_time = 0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


_account_type = os.getenv("KIS_ACCOUNT_TYPE", "REAL")
if _account_type == "REAL":
    _rate_limiter = RateLimiter(max_per_second=8)   # 실전: 한도 10 대비 20% 여유
else:
    _rate_limiter = RateLimiter(max_per_second=1)   # 모의


class KISDataSource:
    """KIS API 시세 조회 + 일봉 캐싱"""

    def __init__(self):
        self.auth = KISAuth()
        self._today = datetime.now().strftime("%Y%m%d")
        self._cache_path = CACHE_DIR / f"daily_{self._today}.json"
        self._cache = {}
        self._is_trading_day = None
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._load_cache()

    # ------------------------------------------------------------------
    # 캐시 입출력
    # ------------------------------------------------------------------
    def _load_cache(self):
        if not self._cache_path.exists():
            print(f"[CACHE] 캐시 없음 - 전체 일봉 조회 예정 ({self._cache_path.name})")
            return
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.pop("_meta", {})
            self._is_trading_day = meta.get("is_trading_day")
            self._cache = data
            print(f"[CACHE] 로드 완료: {len(self._cache)}종목 ({self._cache_path.name})")
        except Exception as e:
            print(f"[CACHE] 로드 실패 - 전체 조회로 진행: {e}")
            self._cache = {}

    def save_cache(self):
        """분석 종료 후 호출. 캐시를 파일로 저장"""
        if not self._cache:
            return
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            payload = dict(self._cache)
            payload["_meta"] = {
                "date": self._today,
                "is_trading_day": self._is_trading_day,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            print(f"[CACHE] 저장 완료: {len(self._cache)}종목 "
                  f"(적중 {self._hits} / 신규 {self._misses})")
        except Exception as e:
            print(f"[CACHE] 저장 실패: {e}")

    # ------------------------------------------------------------------
    # 오늘 봉 합성
    # ------------------------------------------------------------------
    def _merge_today(self, rows: list, price_info: dict) -> list:
        """캐시된 과거 일봉 + 현재가로 만든 오늘 봉"""
        price = price_info.get("current_price", 0)
        if not price:
            return rows
        if self._is_trading_day is False:
            return rows

        today_row = {
            "일자": self._today,
            "시가": price_info.get("open") or price,
            "고가": price_info.get("high") or price,
            "저가": price_info.get("low") or price,
            "종가": price,
            "거래량": price_info.get("volume", 0),
        }

        if rows and rows[-1].get("일자") == self._today:
            return rows[:-1] + [today_row]
        if datetime.now().weekday() >= 5:   # 주말은 추가하지 않음
            return rows
        return rows + [today_row]

    # ------------------------------------------------------------------
    # 통합 조회 (analyzer가 호출)
    # ------------------------------------------------------------------
    def get_stock_data(self, code: str):
        """현재가 1회 + 캐시 일봉 → (DataFrame, price_info)"""
        price_info = self.get_current_price(code)

        with self._lock:
            rows = self._cache.get(code)

        if rows is not None:
            with self._lock:
                self._hits += 1
            merged = self._merge_today(rows, price_info)
            return pd.DataFrame(merged, columns=COLUMNS), price_info

        # 캐시 미스 - 전체 일봉 조회
        df = self.get_daily_dataframe(code)
        if df.empty:
            return df, price_info

        fetched = df.to_dict("records")
        with self._lock:
            self._misses += 1
            if self._is_trading_day is None:
                self._is_trading_day = bool(fetched) and fetched[-1]["일자"] == self._today
            self._cache[code] = fetched

        merged = self._merge_today(fetched, price_info)
        return pd.DataFrame(merged, columns=COLUMNS), price_info

    # ------------------------------------------------------------------
    # 원본 API
    # ------------------------------------------------------------------
    def get_daily_dataframe(self, code: str, days: int = 100) -> pd.DataFrame:
        """일봉 데이터 조회 (캐시 미스 시에만 호출)"""
        max_retries = 5
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
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    print(f"[ERROR] {code} 조회 실패: {response.text[:100]}")
                    return pd.DataFrame()

                data = response.json()

                if data.get("rt_cd") != "0":
                    if "EGW00201" in data.get("msg_cd", ""):
                        time.sleep(0.5 * (2 ** attempt))
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
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                print(f"[ERROR] {code} 예외 발생: {e}")
                return pd.DataFrame()

        return pd.DataFrame()

    def get_current_price(self, code: str) -> dict:
        """현재가 조회 (OHLCV 전체 반환, NXT/시간외 반영)"""
        max_retries = 5
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
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    return {}

                data = response.json()

                if data.get("rt_cd") != "0":
                    if "EGW00201" in data.get("msg_cd", ""):
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    return {}

                output = data.get("output", {})

                def _int(key):
                    try:
                        return int(output.get(key, 0) or 0)
                    except (TypeError, ValueError):
                        return 0

                current = _int("stck_prpr")

                return {
                    "current_price": current,
                    "open": _int("stck_oprc"),
                    "high": _int("stck_hgpr"),
                    "low": _int("stck_lwpr"),
                    "prev_close": current - _int("prdy_vrss"),
                    "change": _int("prdy_vrss"),
                    "change_pct": float(output.get("prdy_ctrt", 0) or 0),
                    "volume": _int("acml_vol"),
                }

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                print(f"[ERROR] {code} 현재가 조회 실패: {e}")
                return {}

        return {}
    