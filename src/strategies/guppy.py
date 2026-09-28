"""
그물망 추세 돌파 전략 (Guppy Multiple Moving Average)
- 다수의 EMA를 사용한 추세 추종
- 정배열 + 가격 안착 + 부채꼴 발산 시 매수
"""
from time import time

import pandas as pd


class GuppyStrategy:
    """그물망 추세 돌파 전략"""

    # EMA 기간 (20일~60일, 4일 간격 11개)
    EMA_PERIODS = [20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60]

    def __init__(self):
        pass

    def calculate_emas(self, df: pd.DataFrame) -> pd.DataFrame:
        """모든 EMA 계산하여 컬럼 추가"""
        if "종가" not in df.columns:
            print("[ERROR] '종가' 컬럼이 없습니다.")
            return df

        df = df.copy()
        for period in self.EMA_PERIODS:
            df[f"EMA{period}"] = df["종가"].ewm(span=period, adjust=False).mean()
        return df

    def is_aligned(self, row) -> bool:
        """정배열 여부 (EMA 20 > 24 > 28 > ... > 60)"""
        try:
            values = [row[f"EMA{p}"] for p in self.EMA_PERIODS]
            # 짧은 EMA가 항상 긴 EMA보다 위에 있어야 함
            for i in range(len(values) - 1):
                if values[i] <= values[i + 1]:
                    return False
            return True
        except (KeyError, TypeError):
            return False

    def get_band_width(self, row) -> float:
        """그물망 폭 (EMA 20 - EMA 60)"""
        try:
            return row[f"EMA{self.EMA_PERIODS[0]}"] - row[f"EMA{self.EMA_PERIODS[-1]}"]
        except (KeyError, TypeError):
            return 0.0

    def generate_signal(self, df: pd.DataFrame) -> str:
        """
        매매 신호 생성
        반환값: 'BUY' (그물망 돌파) 또는 'HOLD'
        """
        df = self.calculate_emas(df)

        # 데이터 충분성 체크
        if len(df) < max(self.EMA_PERIODS) + 5:
            return "HOLD"

        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        two_days_ago = df.iloc[-3]

        # 조건 1: 오늘 정배열
        if not self.is_aligned(today):
            return "HOLD"

        # 조건 2: 가격 안착 (종가 > 최상단 EMA)
        if today["종가"] <= today[f"EMA{self.EMA_PERIODS[0]}"]:
            return "HOLD"

        # 조건 3: 부채꼴 발산 (그물망 폭 확대)
        today_width = self.get_band_width(today)
        yesterday_width = self.get_band_width(yesterday)
        if today_width <= yesterday_width:
            return "HOLD"

        # 조건 4: 초입 신호 (어제 또는 그제는 정배열 아니었을 것)
        if self.is_aligned(yesterday) and self.is_aligned(two_days_ago):
            # 이미 정배열이 며칠 지속됨 → 추격 매수 방지
            return "HOLD"

        return "BUY"

    def analyze(self, df: pd.DataFrame, stock_code: str = "") -> dict:
        """분석 결과 상세 반환"""
        df = self.calculate_emas(df)

        if len(df) < max(self.EMA_PERIODS) + 5:
            return {
                "전략": "그물망 추세 돌파",
                "종목코드": stock_code,
                "신호": "HOLD",
                "사유": "데이터 부족",
            }

        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        two_days_ago = df.iloc[-3]

        signal = self.generate_signal(df)

        # 진단 정보
        is_today_aligned = self.is_aligned(today)
        today_width = self.get_band_width(today)
        yesterday_width = self.get_band_width(yesterday)

        return {
            "전략": "그물망 추세 돌파",
            "종목코드": stock_code,
            "최근일자": today.get("일자", "N/A"),
            "현재가": today.get("종가", 0),
            "EMA20": round(today.get("EMA20", 0), 2),
            "EMA40": round(today.get("EMA40", 0), 2),
            "EMA60": round(today.get("EMA60", 0), 2),
            "정배열": "YES" if is_today_aligned else "NO",
            "그물망폭(오늘)": round(today_width, 2),
            "그물망폭(어제)": round(yesterday_width, 2),
            "발산여부": "YES" if today_width > yesterday_width else "NO",
            "신호": signal,
        }



