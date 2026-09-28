"""
피보나치 황금비율 지지 전략
- 1년 최고/최저 기반 피보나치 되돌림 계산
- 38.2% ~ 61.8% 구간에서 반등 시 매수
- 추세 필터(60일선) + 양봉 + 거래량 증가 확인
"""
import pandas as pd


class FibonacciStrategy:
    """피보나치 황금비율 지지 전략"""

    # 피보나치 비율
    FIB_UPPER = 0.382      # 38.2% 되돌림 (매수 구간 상단)
    FIB_LOWER = 0.618      # 61.8% 되돌림 (매수 구간 하단)

    # 파동 기간 (영업일 기준 약 1년)
    WAVE_DAYS = 250

    # 거래량 평균 비교 기간
    VOLUME_MA_DAYS = 20

    # 거래량 증가 배수 기준
    VOLUME_MULTIPLIER = 1.2

    # 추세 필터 기간
    TREND_MA_DAYS = 60

    def __init__(self):
        pass

    def calculate_fibonacci_levels(self, df: pd.DataFrame) -> dict:
        """1년치 데이터에서 피보나치 되돌림 가격 계산"""
        if len(df) < self.WAVE_DAYS:
            recent = df
        else:
            recent = df.tail(self.WAVE_DAYS)

        try:
            high = float(recent["고가"].max())
            low = float(recent["저가"].min())
        except (KeyError, ValueError, TypeError):
            return {}

        wave = high - low

        if wave <= 0:
            return {}

        return {
            "high": high,
            "low": low,
            "wave": wave,
            "fib_38_2": high - wave * self.FIB_UPPER,
            "fib_50_0": high - wave * 0.500,
            "fib_61_8": high - wave * self.FIB_LOWER,
            "fib_upper_bound": high - wave * self.FIB_UPPER,    # 38.2% (위쪽)
            "fib_lower_bound": high - wave * self.FIB_LOWER,    # 61.8% (아래쪽)
        }

    def is_in_fibonacci_zone(self, current_price: float, levels: dict) -> bool:
        """현재가가 38.2% ~ 61.8% 구간 내인지 확인"""
        if not levels:
            return False
        return levels["fib_lower_bound"] <= current_price <= levels["fib_upper_bound"]

    def is_above_trend_ma(self, df: pd.DataFrame) -> bool:
        """현재가가 60일선 위에 있는지 (장기 상승 추세 확인)"""
        if len(df) < self.TREND_MA_DAYS:
            return False
        try:
            ma_60 = df["종가"].rolling(window=self.TREND_MA_DAYS).mean().iloc[-1]
            current = float(df["종가"].iloc[-1])
            if pd.isna(ma_60):
                return False
            return current > ma_60
        except (KeyError, ValueError, TypeError):
            return False

    def is_bullish_candle(self, df: pd.DataFrame) -> bool:
        """당일 양봉 여부 (종가 > 시가)"""
        if len(df) < 1:
            return False
        try:
            latest = df.iloc[-1]
            close = float(latest["종가"])
            open_price = float(latest["시가"])
            return close > open_price
        except (KeyError, ValueError, TypeError):
            return False

    def is_volume_surged(self, df: pd.DataFrame) -> bool:
        """당일 거래량이 최근 평균 대비 증가했는지"""
        if len(df) < self.VOLUME_MA_DAYS + 1:
            return False
        try:
            recent_volumes = df["거래량"].tail(self.VOLUME_MA_DAYS + 1)
            avg_volume = float(recent_volumes.iloc[:-1].mean())  # 마지막 제외한 평균
            today_volume = float(df["거래량"].iloc[-1])
            if avg_volume <= 0:
                return False
            return today_volume >= avg_volume * self.VOLUME_MULTIPLIER
        except (KeyError, ValueError, TypeError):
            return False

    def generate_signal(self, df: pd.DataFrame) -> str:
        """
        매매 신호 생성
        반환값: 'BUY' (모든 조건 충족) 또는 'HOLD'
        """
        # 데이터 충분성 체크 (최소 60일)
        if len(df) < self.TREND_MA_DAYS:
            return "HOLD"

        # 조건 1: 60일선 위 (장기 추세 확인)
        if not self.is_above_trend_ma(df):
            return "HOLD"

        # 조건 2 & 3: 피보나치 구간 내
        try:
            current_price = float(df["종가"].iloc[-1])
        except (KeyError, ValueError, TypeError):
            return "HOLD"

        levels = self.calculate_fibonacci_levels(df)
        if not self.is_in_fibonacci_zone(current_price, levels):
            return "HOLD"

        # 조건 4: 양봉 (반등 확인)
        if not self.is_bullish_candle(df):
            return "HOLD"

        # 조건 5: 거래량 증가
        if not self.is_volume_surged(df):
            return "HOLD"

        return "BUY"

    def analyze(self, df: pd.DataFrame, stock_code: str = "") -> dict:
        """분석 결과 상세 반환"""
        if len(df) < self.TREND_MA_DAYS:
            return {
                "전략": "피보나치 황금비율",
                "종목코드": stock_code,
                "신호": "HOLD",
                "사유": "데이터 부족",
            }

        try:
            current_price = float(df["종가"].iloc[-1])
        except (KeyError, ValueError, TypeError):
            return {
                "전략": "피보나치 황금비율",
                "종목코드": stock_code,
                "신호": "HOLD",
                "사유": "종가 데이터 오류",
            }

        levels = self.calculate_fibonacci_levels(df)

        trend_ok = self.is_above_trend_ma(df)
        in_zone = self.is_in_fibonacci_zone(current_price, levels)
        is_bullish = self.is_bullish_candle(df)
        vol_surged = self.is_volume_surged(df)

        signal = self.generate_signal(df)

        return {
            "전략": "피보나치 황금비율",
            "종목코드": stock_code,
            "현재가": current_price,
            "1년최고가": round(levels.get("high", 0), 2),
            "1년최저가": round(levels.get("low", 0), 2),
            "38.2%라인": round(levels.get("fib_38_2", 0), 2),
            "61.8%라인": round(levels.get("fib_61_8", 0), 2),
            "60일선위": "YES" if trend_ok else "NO",
            "구간내": "YES" if in_zone else "NO",
            "양봉": "YES" if is_bullish else "NO",
            "거래량증가": "YES" if vol_surged else "NO",
            "신호": signal,
        }


