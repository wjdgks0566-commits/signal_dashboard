"""
상승 다이버전스 전략
- RSI(14) 사용
- 주가는 신저점인데 RSI는 저점 상승 (다이버전스)
- 양봉 또는 RSI 30 이하 탈출로 추세 전환 확인
"""
import pandas as pd
import numpy as np


class DivergenceStrategy:
    """상승 다이버전스 전략"""

    # RSI 기간
    RSI_PERIOD = 14

    # 저점 비교 윈도우 (영업일)
    WINDOW_DAYS = 60

    # RSI 과매도 기준
    RSI_OVERSOLD = 30

    def __init__(self):
        pass

    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """RSI(14) 계산"""
        if "종가" not in df.columns:
            return pd.Series(dtype=float)

        try:
            close = df["종가"].astype(float)
            delta = close.diff()

            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)

            # Wilder's smoothing (지수이동평균과 유사)
            avg_gain = gain.ewm(alpha=1.0 / self.RSI_PERIOD, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1.0 / self.RSI_PERIOD, adjust=False).mean()

            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50.0)  # 초기 NaN을 50으로 처리
        except (ValueError, TypeError):
            return pd.Series(dtype=float)

    def find_lowest_in_window(self, series: pd.Series) -> tuple:
        """
        시리즈의 최저점 위치와 값 반환
        반환: (위치 인덱스, 값)
        """
        if len(series) == 0:
            return (-1, None)
        try:
            idx = series.idxmin()
            return (idx, series.loc[idx])
        except (ValueError, KeyError):
            return (-1, None)

    def check_divergence(self, df: pd.DataFrame) -> dict:
        """
        다이버전스 발생 여부 확인
        반환: 분석 결과 딕셔너리
        """
        result = {
            "rsi_current": None,
            "rsi_prev_low": None,
            "rsi_recent_low": None,
            "price_prev_low": None,
            "price_recent_low": None,
            "price_new_low": False,
            "rsi_higher_low": False,
            "divergence": False,
        }

        # 데이터 충분성 체크
        min_required = self.WINDOW_DAYS * 2 + self.RSI_PERIOD
        if len(df) < min_required:
            return result

        # RSI 계산
        rsi = self.calculate_rsi(df)
        if rsi.empty:
            return result

        # 윈도우 설정
        # 최근 윈도우: 마지막 60일
        # 이전 윈도우: 그 전 60일
        recent_window = df.tail(self.WINDOW_DAYS)
        prev_window = df.iloc[-self.WINDOW_DAYS * 2:-self.WINDOW_DAYS]

        if len(recent_window) < self.WINDOW_DAYS or len(prev_window) < self.WINDOW_DAYS:
            return result

        # 주가 저점 비교
        try:
            price_recent_low = float(recent_window["저가"].min())
            price_prev_low = float(prev_window["저가"].min())
        except (KeyError, ValueError, TypeError):
            return result

        # RSI 저점 비교 (해당 윈도우의 RSI)
        rsi_recent_window = rsi.tail(self.WINDOW_DAYS)
        rsi_prev_window = rsi.iloc[-self.WINDOW_DAYS * 2:-self.WINDOW_DAYS]

        rsi_recent_low = float(rsi_recent_window.min())
        rsi_prev_low = float(rsi_prev_window.min())

        # 다이버전스 조건
        price_new_low = price_recent_low < price_prev_low
        rsi_higher_low = rsi_recent_low > rsi_prev_low

        result["rsi_current"] = float(rsi.iloc[-1])
        result["rsi_prev_low"] = rsi_prev_low
        result["rsi_recent_low"] = rsi_recent_low
        result["price_prev_low"] = price_prev_low
        result["price_recent_low"] = price_recent_low
        result["price_new_low"] = price_new_low
        result["rsi_higher_low"] = rsi_higher_low
        result["divergence"] = price_new_low and rsi_higher_low

        return result

    def is_bullish_candle(self, df: pd.DataFrame) -> bool:
        """당일 양봉 여부"""
        if len(df) < 1:
            return False
        try:
            latest = df.iloc[-1]
            return float(latest["종가"]) > float(latest["시가"])
        except (KeyError, ValueError, TypeError):
            return False

    def is_rsi_breakout(self, df: pd.DataFrame) -> bool:
        """RSI 30 이하 탈출 (어제까지 30 이하, 오늘 30 초과)"""
        rsi = self.calculate_rsi(df)
        if len(rsi) < 2:
            return False
        try:
            today_rsi = float(rsi.iloc[-1])
            yesterday_rsi = float(rsi.iloc[-2])
            # 어제 과매도 → 오늘 탈출
            return yesterday_rsi <= self.RSI_OVERSOLD and today_rsi > self.RSI_OVERSOLD
        except (ValueError, TypeError):
            return False

    def generate_signal(self, df: pd.DataFrame) -> str:
        """매매 신호 생성"""
        # 다이버전스 확인
        div_info = self.check_divergence(df)
        if not div_info["divergence"]:
            return "HOLD"

        # 추세 전환 확인: 양봉 OR RSI 30 탈출
        bullish = self.is_bullish_candle(df)
        rsi_breakout = self.is_rsi_breakout(df)

        if bullish or rsi_breakout:
            return "BUY"

        return "HOLD"

    def analyze(self, df: pd.DataFrame, stock_code: str = "") -> dict:
        """분석 결과 상세 반환"""
        min_required = self.WINDOW_DAYS * 2 + self.RSI_PERIOD
        if len(df) < min_required:
            return {
                "전략": "상승 다이버전스",
                "종목코드": stock_code,
                "신호": "HOLD",
                "사유": f"데이터 부족 ({len(df)}/{min_required}일)",
            }

        div_info = self.check_divergence(df)
        bullish = self.is_bullish_candle(df)
        rsi_breakout = self.is_rsi_breakout(df)
        signal = self.generate_signal(df)

        return {
            "전략": "상승 다이버전스",
            "종목코드": stock_code,
            "RSI현재": round(div_info.get("rsi_current") or 0, 2),
            "이전저점가": round(div_info.get("price_prev_low") or 0, 2),
            "최근저점가": round(div_info.get("price_recent_low") or 0, 2),
            "주가신저점": "YES" if div_info.get("price_new_low") else "NO",
            "이전저점RSI": round(div_info.get("rsi_prev_low") or 0, 2),
            "최근저점RSI": round(div_info.get("rsi_recent_low") or 0, 2),
            "RSI저점상승": "YES" if div_info.get("rsi_higher_low") else "NO",
            "다이버전스": "YES" if div_info.get("divergence") else "NO",
            "양봉": "YES" if bullish else "NO",
            "RSI30탈출": "YES" if rsi_breakout else "NO",
            "신호": signal,
        }


