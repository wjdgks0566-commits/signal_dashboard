"""
거래량 급증 감지 모듈
- 최근 20일 평균 대비 오늘 거래량 비율 계산
- 급증 여부 판정
"""
import pandas as pd


class VolumeSpikeDetector:
    """거래량 급증 감지"""

    def __init__(self, lookback_days: int = 20, spike_ratio: float = 3.0):
        """
        lookback_days: 평균 계산 기간 (기본 20일)
        spike_ratio: 급증 판정 배수 (기본 3배)
        """
        self.lookback_days = lookback_days
        self.spike_ratio = spike_ratio

    def analyze(self, df: pd.DataFrame, stock_code: str = "") -> dict:
        """
        거래량 급증 분석
        반환:
        - is_spike: 급증 여부
        - ratio: 평균 대비 배수
        - avg_volume: 평균 거래량
        - today_volume: 오늘 거래량
        """
        if "거래량" not in df.columns or len(df) < self.lookback_days + 1:
            return {
                "전략": "거래량급증",
                "종목코드": stock_code,
                "is_spike": False,
                "ratio": 0.0,
                "avg_volume": 0,
                "today_volume": 0,
                "signal": "HOLD",
            }

        # 최근 lookback_days 평균 (오늘 제외)
        avg_volume = df["거래량"].iloc[-(self.lookback_days + 1):-1].mean()
        today_volume = df["거래량"].iloc[-1]

        if avg_volume <= 0:
            return {
                "전략": "거래량급증",
                "종목코드": stock_code,
                "is_spike": False,
                "ratio": 0.0,
                "avg_volume": 0,
                "today_volume": int(today_volume),
                "signal": "HOLD",
            }

        ratio = today_volume / avg_volume
        is_spike = ratio >= self.spike_ratio

        return {
            "전략": "거래량급증",
            "종목코드": stock_code,
            "is_spike": is_spike,
            "ratio": round(ratio, 2),
            "avg_volume": int(avg_volume),
            "today_volume": int(today_volume),
            "signal": "SPIKE" if is_spike else "HOLD",
        }