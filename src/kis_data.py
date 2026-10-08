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
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._merged = 0
        self._skipped = 0
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
            data.pop("_meta", None)
            self._cache = data
            print(f"[CACHE] 로드 완료: {len(self._cache)}종목 ({self._cache_path.name})")
        except Exception as e:
            print(f"[CACHE] 로드 실패 - 전체 조회로 진행: {e}")
            self._cache = {}

    def save_cache(self):
        """분석 종료 후 호출. 캐시를 파일로 저장 (과거 일봉만, 오늘 봉은 매번 합성)"""
        if not self._cache:
            return
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            payload = dict(self._cache)
            payload["_meta"] = {
                "date": self._today,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            print(f"[CACHE] 저장 완료: {len(self._cache)}종목 "
                  f"(적중 {self._hits} / 신규 {self._misses} / "
                  f"오늘봉 병합 {self._merged} / 휴장·무거래 {self._skipped})")
        except Exception as e:
            print(f"[CACHE] 저장 실패: {e}")

    # ------------------------------------------------------------------
    # 오늘 봉 합성
    # ------------------------------------------------------------------
    def _merge_today(self, rows: list, price_info: dict) -> list:
        """캐시된 과거 일봉 + 현재가로 만든 오늘 봉

        거래일 여부를 저장해두지 않고 매 실행마다 실시간 데이터로 판단한다.
        (장 시작 전 캐시가 만들어져도 장중에 정상 병합되도록)
        """
        price = price_info.get("current_price", 0)
        volume = price_info.get("volume", 0)
        high = price_info.get("high") or price
        low = price_info.get("low") or price

        # 체결가·거래량이 없으면 휴장 또는 거래정지 → 병합하지 않음
        if not price or not volume:
            with self._lock:
                self._skipped += 1
            return rows

        # 주말(토·일)은 병합하지 않음
        if datetime.now().weekday() >= 5:
            with self._lock:
                self._skipped += 1
            return rows

        # 공휴일 방어: 휴장일에는 API가 직전 거래일 값을 그대로 돌려준다.
        # 마지막 봉과 OHLCV가 전부 같으면 새 거래가 없는 것으로 보고 병합하지 않음
        # (평일 공휴일 - 한글날, 추석, 대체공휴일 등은 요일로 걸러지지 않음)
        if rows and rows[-1].get("일자") != self._today:
            last = rows[-1]
            if (last.get("종가") == price
                    and last.get("거래량") == volume
                    and last.get("고가") == high
                    and last.get("저가") == low):
                with self._lock:
                    self._skipped += 1
                return rows

        today_row = {
            "일자": self._today,
            "시가": price_info.get("open") or price,
            "고가": high,
            "저가": low,
            "종가": price,
            "거래량": volume,
        }

        with self._lock:
            self._merged += 1

        # 캐시 마지막 행이 이미 오늘이면 교체, 아니면 추가
        if rows and rows[-1].get("일자") == self._today:
            return rows[:-1] + [today_row]
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
    