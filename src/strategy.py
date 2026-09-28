import pandas as pd


class MAStrategy:
    """이동평균선 돌파 전략 (Moving Average Crossover)"""

    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window

    def calculate_ma(self, df: pd.DataFrame) -> pd.DataFrame:
        if "종가" not in df.columns:
            print("[ERROR] '종가' 컬럼이 없습니다.")
            return df

        df = df.copy()
        df[f"MA{self.short_window}"] = df["종가"].rolling(window=self.short_window).mean()
        df[f"MA{self.long_window}"] = df["종가"].rolling(window=self.long_window).mean()
        return df

    def generate_signal(self, df: pd.DataFrame) -> str:
        df = self.calculate_ma(df)

        if len(df) < self.long_window + 1:
            return "HOLD"

        ma_short_col = f"MA{self.short_window}"
        ma_long_col = f"MA{self.long_window}"

        yesterday_short = df[ma_short_col].iloc[-2]
        yesterday_long = df[ma_long_col].iloc[-2]
        today_short = df[ma_short_col].iloc[-1]
        today_long = df[ma_long_col].iloc[-1]

        if pd.isna(yesterday_short) or pd.isna(yesterday_long):
            return "HOLD"

        if yesterday_short <= yesterday_long and today_short > today_long:
            return "BUY"
        # 데드크로스 매도 비활성화 (수동 매도 방식)
        # if yesterday_short >= yesterday_long and today_short < today_long:
        #     return "SELL"
        return "HOLD"

    def analyze(self, df: pd.DataFrame, stock_code: str = "") -> dict:
        df = self.calculate_ma(df)
        signal = self.generate_signal(df)

        ma_short_col = f"MA{self.short_window}"
        ma_long_col = f"MA{self.long_window}"

        latest = df.iloc[-1]
        return {
            "종목코드": stock_code,
            "최근일자": latest.get("일자", "N/A"),
            "현재가": latest.get("종가", 0),
            f"{self.short_window}일선": round(latest.get(ma_short_col, 0), 2) if not pd.isna(latest.get(ma_short_col)) else None,
            f"{self.long_window}일선": round(latest.get(ma_long_col, 0), 2) if not pd.isna(latest.get(ma_long_col)) else None,
            "신호": signal,
            "추세": "상승" if latest.get(ma_short_col, 0) > latest.get(ma_long_col, 0) else "하락",
        }