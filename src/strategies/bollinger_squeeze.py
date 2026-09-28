"""
볼린저 밴드 스퀴즈 감지 모듈
- 밴드 폭이 좁아진 상태(스퀴즈)에서 상단 돌파 시 매수 신호
"""
import pandas as pd


class BollingerSqueezeStrategy:
    """볼린저 밴드 스퀴즈 + 상단 돌파 감지"""

    def __init__(self, window: int = 20, std_multiplier: float = 2.0, squeeze_percentile: float = 20.0):
        """
        window: 이동평균 기간 (기본 20일)
        std_multiplier: 표준편차 배수 (기본 2배)
        squeeze_percentile: 스퀴즈 판정 백분위 (하위 X% = 스퀴즈)
        """
        self.window = window
        self.std_multiplier = std_multiplier
        self.squeeze_percentile = squeeze_percentile

    def analyze(self, df: pd.DataFrame, stock_code: str = "") -> dict:
        """
        볼린저 스퀴즈 분석
        반환:
        - 신호: BUY / HOLD
        - 스퀴즈여부: 최근 밴드폭이 하위 20% 인지
        - 상단돌파: 오늘 종가가 상단밴드 돌파 여부
        - 밴드폭: 현재 밴드 폭 (%)
        """
        if "종가" not in df.columns or len(df) < self.window + 20:
            return {
                "전략": "볼린저스퀴즈",
                "종목코드": stock_code,
                "신호": "HOLD",
                "스퀴즈여부": "NO",
                "상단돌파": "NO",
                "밴드폭": 0.0,
            }

        # 볼린저 밴드 계산
        ma = df["종가"].rolling(window=self.window).mean()
        std = df["종가"].rolling(window=self.window).std()
        upper = ma + (std * self.std_multiplier)
        lower = ma - (std * self.std_multiplier)
        bandwidth = ((upper - lower) / ma * 100).dropna()

        if len(bandwidth) < 20:
            return {
                "전략": "볼린저스퀴즈",
                "종목코드": stock_code,
                "신호": "HOLD",
                "스퀴즈여부": "NO",
                "상단돌파": "NO",
                "밴드폭": 0.0,
            }

        # 최근 밴드폭 vs 최근 20일 평균 밴드폭
        current_bandwidth = bandwidth.iloc[-1]
        recent_20 = bandwidth.iloc[-20:]
        threshold = recent_20.quantile(self.squeeze_percentile / 100)

        # 스퀴즈: 최근 밴드폭이 하위 X% 이하
        # 어제 스퀴즈였는지 확인 (오늘은 돌파 중)
        yesterday_bandwidth = bandwidth.iloc[-2] if len(bandwidth) >= 2 else current_bandwidth
        was_squeezed = yesterday_bandwidth <= threshold

        # 상단 돌파: 오늘 종가가 상단밴드 이상
        today_close = df["종가"].iloc[-1]
        today_upper = upper.iloc[-1]
        breakout = today_close > today_upper

        is_signal = was_squeezed and breakout

        return {
            "전략": "볼린저스퀴즈",
            "종목코드": stock_code,
            "신호": "BUY" if is_signal else "HOLD",
            "스퀴즈여부": "YES" if was_squeezed else "NO",
            "상단돌파": "YES" if breakout else "NO",
            "밴드폭": round(current_bandwidth, 2),
        }