"""
OBV (On-Balance Volume) 매집형 다이버전스 감지
- 주가는 횡보/하락, OBV는 상승 = 세력 매집
"""
import pandas as pd


class OBVStrategy:
    """OBV 매집형 다이버전스"""

    def __init__(self, lookback_days: int = 20):
        """
        lookback_days: 다이버전스 확인 기간 (기본 20일)
        """
        self.lookback_days = lookback_days

    def _calculate_obv(self, df: pd.DataFrame) -> pd.Series:
        """OBV 계산"""
        obv = [0]
        for i in range(1, len(df)):
            if df["종가"].iloc[i] > df["종가"].iloc[i - 1]:
                obv.append(obv[-1] + df["거래량"].iloc[i])
            elif df["종가"].iloc[i] < df["종가"].iloc[i - 1]:
                obv.append(obv[-1] - df["거래량"].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=df.index)

    def analyze(self, df: pd.DataFrame, stock_code: str = "") -> dict:
        """
        OBV 매집형 다이버전스 분석
        반환:
        - 신호: BUY / HOLD
        - 주가추세: 하락/횡보/상승
        - OBV추세: 하락/횡보/상승
        - 매집형: 주가 하락 + OBV 상승 → YES
        """
        if "종가" not in df.columns or "거래량" not in df.columns:
            return {
                "전략": "OBV",
                "종목코드": stock_code,
                "신호": "HOLD",
                "주가추세": "-",
                "OBV추세": "-",
                "매집형": "NO",
            }

        if len(df) < self.lookback_days + 1:
            return {
                "전략": "OBV",
                "종목코드": stock_code,
                "신호": "HOLD",
                "주가추세": "-",
                "OBV추세": "-",
                "매집형": "NO",
            }

        # OBV 계산
        obv = self._calculate_obv(df)

        # 최근 N일 데이터
        recent_price = df["종가"].iloc[-self.lookback_days:]
        recent_obv = obv.iloc[-self.lookback_days:]

        # 추세 판정 (선형 회귀 기울기)
        price_first_half = recent_price.iloc[:len(recent_price) // 2].mean()
        price_second_half = recent_price.iloc[len(recent_price) // 2:].mean()
        obv_first_half = recent_obv.iloc[:len(recent_obv) // 2].mean()
        obv_second_half = recent_obv.iloc[len(recent_obv) // 2:].mean()

        price_change_pct = ((price_second_half - price_first_half) / price_first_half * 100) if price_first_half > 0 else 0
        obv_change = obv_second_half - obv_first_half

        # 추세 라벨
        if price_change_pct > 3:
            price_trend = "상승"
        elif price_change_pct < -3:
            price_trend = "하락"
        else:
            price_trend = "횡보"

        if obv_change > 0:
            obv_trend = "상승"
        elif obv_change < 0:
            obv_trend = "하락"
        else:
            obv_trend = "횡보"

        # 매집형: 주가 하락/횡보 + OBV 상승
        is_accumulation = (price_trend in ["하락", "횡보"]) and (obv_trend == "상승")

        return {
            "전략": "OBV",
            "종목코드": stock_code,
            "신호": "BUY" if is_accumulation else "HOLD",
            "주가추세": price_trend,
            "OBV추세": obv_trend,
            "매집형": "YES" if is_accumulation else "NO",
        }