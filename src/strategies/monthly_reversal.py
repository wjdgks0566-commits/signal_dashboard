"""
월봉 3음봉 후 양봉 전환 전략
- 일봉 데이터를 월 단위로 그룹화
- 3개월 연속 음봉 + 이번달 양봉 + 거래량 폭발 시 매수
"""
import pandas as pd


class MonthlyReversalStrategy:
    """월봉 3음봉 후 양봉 전환 전략"""

    # 연속 음봉 개수 (3개월)
    BEARISH_MONTHS = 3

    # 거래량 비교 기간
    RECENT_VOLUME_DAYS = 5
    BASE_VOLUME_DAYS = 20

    # 거래량 폭발 배수
    VOLUME_MULTIPLIER = 1.5

    def __init__(self):
        pass

    def parse_date_string(self, date_str) -> pd.Timestamp:
        """일자 문자열을 datetime으로 변환 (YYYYMMDD)"""
        try:
            return pd.to_datetime(str(date_str), format="%Y%m%d")
        except (ValueError, TypeError):
            return None

    def group_by_month(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        일봉 데이터를 월봉으로 변환
        반환: 컬럼 [년월, 시가, 종가, 음양봉]
        """
        if "일자" not in df.columns or len(df) == 0:
            return pd.DataFrame()

        df = df.copy()
        df["날짜"] = df["일자"].apply(self.parse_date_string)
        df = df.dropna(subset=["날짜"])

        if df.empty:
            return pd.DataFrame()

        # 오름차순 정렬 (오래된 날짜가 앞)
        df = df.sort_values("날짜").reset_index(drop=True)
        df["년월"] = df["날짜"].dt.to_period("M")

        # 월별 그룹화
        try:
            monthly = df.groupby("년월").agg(
                시가=("시가", "first"),
                종가=("종가", "last"),
            ).reset_index()
        except KeyError:
            return pd.DataFrame()

        # 음양봉 판단
        monthly["음봉"] = monthly["종가"] < monthly["시가"]
        monthly["양봉"] = monthly["종가"] > monthly["시가"]

        return monthly

    def check_3_bearish_months(self, monthly: pd.DataFrame) -> bool:
        """직전 3개월(이번달 제외) 모두 음봉인지 확인"""
        if len(monthly) < self.BEARISH_MONTHS + 1:
            return False

        # 이번달 제외 직전 3개월
        last_three = monthly.iloc[-(self.BEARISH_MONTHS + 1):-1]

        if len(last_three) < self.BEARISH_MONTHS:
            return False

        # 3개월 모두 음봉인지
        return bool(last_three["음봉"].all())

    def check_current_month_bullish(self, monthly: pd.DataFrame) -> bool:
        """이번달 양봉 전환 확인"""
        if len(monthly) < 1:
            return False
        current = monthly.iloc[-1]
        try:
            return float(current["종가"]) > float(current["시가"])
        except (ValueError, TypeError):
            return False

    def check_volume_surge(self, df: pd.DataFrame) -> bool:
        """거래량 폭발 확인"""
        if len(df) < self.BASE_VOLUME_DAYS + self.RECENT_VOLUME_DAYS:
            return False

        try:
            # 최근 5일 평균
            recent_avg = float(df["거래량"].tail(self.RECENT_VOLUME_DAYS).mean())
            # 직전 20일 평균 (최근 5일 제외)
            base_window = df["거래량"].iloc[-(self.BASE_VOLUME_DAYS + self.RECENT_VOLUME_DAYS):-self.RECENT_VOLUME_DAYS]
            base_avg = float(base_window.mean())

            if base_avg <= 0:
                return False
            return recent_avg >= base_avg * self.VOLUME_MULTIPLIER
        except (KeyError, ValueError, TypeError):
            return False

    def generate_signal(self, df: pd.DataFrame) -> str:
        """매매 신호 생성"""
        # 데이터 충분성: 최소 4개월 + 거래량 비교용
        if len(df) < 100:
            return "HOLD"

        monthly = self.group_by_month(df)
        if monthly.empty:
            return "HOLD"

        # 조건 1: 3개월 연속 음봉
        if not self.check_3_bearish_months(monthly):
            return "HOLD"

        # 조건 2: 이번달 양봉 전환
        if not self.check_current_month_bullish(monthly):
            return "HOLD"

        # 조건 3: 거래량 폭발
        if not self.check_volume_surge(df):
            return "HOLD"

        return "BUY"

    def analyze(self, df: pd.DataFrame, stock_code: str = "") -> dict:
        """분석 결과 상세 반환"""
        if len(df) < 100:
            return {
                "전략": "월봉 3음봉",
                "종목코드": stock_code,
                "신호": "HOLD",
                "사유": "데이터 부족",
            }

        monthly = self.group_by_month(df)
        if monthly.empty:
            return {
                "전략": "월봉 3음봉",
                "종목코드": stock_code,
                "신호": "HOLD",
                "사유": "월별 그룹화 실패",
            }

        three_bearish = self.check_3_bearish_months(monthly)
        current_bullish = self.check_current_month_bullish(monthly)
        volume_surge = self.check_volume_surge(df)
        signal = self.generate_signal(df)

        # 진단 정보
        try:
            recent_avg = float(df["거래량"].tail(self.RECENT_VOLUME_DAYS).mean())
            base_window = df["거래량"].iloc[-(self.BASE_VOLUME_DAYS + self.RECENT_VOLUME_DAYS):-self.RECENT_VOLUME_DAYS]
            base_avg = float(base_window.mean())
            volume_ratio = round(recent_avg / base_avg, 2) if base_avg > 0 else 0
        except (KeyError, ValueError, TypeError):
            volume_ratio = 0

        # 최근 4개월 음양봉 정보
        last_months_info = "N/A"
        if len(monthly) >= 4:
            last_4 = monthly.tail(4)
            last_months_info = " → ".join([
                f"{str(row['년월'])[-2:]}월({'양' if row['양봉'] else '음' if row['음봉'] else '-'})"
                for _, row in last_4.iterrows()
            ])

        return {
            "전략": "월봉 3음봉",
            "종목코드": stock_code,
            "최근4개월": last_months_info,
            "3개월연속음봉": "YES" if three_bearish else "NO",
            "이번달양봉": "YES" if current_bullish else "NO",
            "거래량비율": volume_ratio,
            "거래량폭발": "YES" if volume_surge else "NO",
            "신호": signal,
        }


