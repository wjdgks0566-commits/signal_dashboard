"""
종합 매매 신호 분석기 (다중 그룹 + 병렬 처리 + 일봉 캐싱)
- 노란별 시스템 (★★★ / ★★ / ★): 기존 신호 + 스퀴즈/OBV 조합
- 빨간별 시스템 (★★ / ★): VCP + 컵앤핸들
- VCP는 형성중 / 돌파 2단계로 구분 표기
"""
import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.kis_data import KISDataSource as DataSource
from src.strategy import MAStrategy
from src.strategies.guppy import GuppyStrategy
from src.strategies.fibonacci import FibonacciStrategy
from src.strategies.divergence import DivergenceStrategy
from src.strategies.monthly_reversal import MonthlyReversalStrategy
from src.strategies.volume_spike import VolumeSpikeDetector
from src.strategies.bollinger_squeeze import BollingerSqueezeStrategy
from src.strategies.obv import OBVStrategy
from src.strategies.vcp import detect_vcp
from src.strategies.cup_and_handle import detect_cup_and_handle


MAX_WORKERS = 7


class SignalAnalyzer:
    """종합 신호 분석기"""

    SHORT_MA = 5
    LONG_MA = 20

    def __init__(self):
        self.data_source = DataSource()
        self.ma_strategy = MAStrategy(short_window=self.SHORT_MA, long_window=self.LONG_MA)
        self.guppy = GuppyStrategy()
        self.fib = FibonacciStrategy()
        self.div = DivergenceStrategy()
        self.mr = MonthlyReversalStrategy()
        self.volume_detector = VolumeSpikeDetector(lookback_days=20, spike_ratio=2.0)
        self.bollinger = BollingerSqueezeStrategy(window=20, std_multiplier=2.0, squeeze_percentile=20.0)
        self.obv = OBVStrategy(lookback_days=20)

    def analyze_stock(self, code: str, name: str, sector: str = "") -> dict:
        """단일 종목 분석"""
        try:
            # 일봉(캐시) + 현재가를 한 번에 조회
            df, price_info = self.data_source.get_stock_data(code)

            if df.empty:
                return self._error_result(code, name, sector, "데이터 조회 실패")

            # 각 전략 분석
            ma_result = self.ma_strategy.analyze(df, stock_code=code)
            guppy_result = self.guppy.analyze(df, stock_code=code)
            fib_result = self.fib.analyze(df, stock_code=code)
            div_result = self.div.analyze(df, stock_code=code)
            mr_result = self.mr.analyze(df, stock_code=code)
            volume_result = self.volume_detector.analyze(df, stock_code=code)
            bollinger_result = self.bollinger.analyze(df, stock_code=code)
            obv_result = self.obv.analyze(df, stock_code=code)

            # 신규 전략 (VCP, 컵앤핸들)
            vcp_result = detect_vcp(df)
            cup_result = detect_cup_and_handle(df)
            vcp_signal = vcp_result.get("detected", False)
            vcp_breakout = vcp_result.get("breakout", False)
            cup_signal = cup_result.get("detected", False)

            # 기존 신호 결합 (각 전략 개별 판정)
            signal_sources = []
            if ma_result.get("신호") == "BUY":
                signal_sources.append("골든크로스")
            if guppy_result.get("신호") == "BUY":
                signal_sources.append("그물망")
            if fib_result.get("신호") == "BUY":
                signal_sources.append("피보나치")
            if div_result.get("신호") == "BUY":
                signal_sources.append("다이버전스")
            if mr_result.get("신호") == "BUY":
                signal_sources.append("월봉3음봉")

            # 추가 신호 (필터)
            bollinger_buy = bollinger_result.get("신호") == "BUY"
            obv_buy = obv_result.get("신호") == "BUY"

            if bollinger_buy:
                signal_sources.append("스퀴즈")
            if obv_buy:
                signal_sources.append("OBV")

            # 신규 신호 (VCP는 단계 구분, 컵앤핸들)
            if vcp_signal:
                signal_sources.append("VCP 돌파" if vcp_breakout else "VCP 형성중")
            if cup_signal:
                signal_sources.append("컵앤핸들")

            # 기존 신호 확인
            has_base_signal = any(s in signal_sources for s in ["골든크로스", "그물망", "피보나치", "다이버전스", "월봉3음봉"])

            # 매수 신호 판정 (기존 신호 OR VCP OR 컵앤핸들)
            has_red_signal = vcp_signal or cup_signal
            final_signal = "BUY" if (has_base_signal or has_red_signal) else "HOLD"

            # 노란별 계산 (기존)
            star_grade = 0
            if has_base_signal:
                star_grade = 1  # 기본 1개
                if bollinger_buy and obv_buy:
                    star_grade = 3  # 프리미엄
                elif bollinger_buy or obv_buy:
                    star_grade = 2  # 확신

            # 빨간별 계산 (신규)
            red_star_grade = 0
            if vcp_signal and cup_signal:
                red_star_grade = 2  # VCP + 컵앤핸들 동시
            elif vcp_signal or cup_signal:
                red_star_grade = 1  # VCP 또는 컵앤핸들 단독

            # 현재가 및 등락률 (get_stock_data에서 이미 조회됨)
            current_price = price_info.get("current_price", 0)
            change_pct = price_info.get("change_pct", 0.0)

            return {
                "code": code,
                "name": name,
                "sector": sector,
                "signal": final_signal,
                "current_price": current_price,
                "change_pct": change_pct,
                "signal_source": " / ".join(signal_sources) if signal_sources else None,
                "star_grade": star_grade,
                "red_star_grade": red_star_grade,
                "vcp_signal": vcp_signal,
                "vcp_breakout": vcp_breakout,
                "cup_signal": cup_signal,
                "volume_spike": volume_result.get("is_spike", False),
                "volume_ratio": volume_result.get("ratio", 0),
                "today_volume": volume_result.get("today_volume", 0),
                "strategies": {
                    "골든크로스": ma_result,
                    "그물망": guppy_result,
                    "피보나치": fib_result,
                    "다이버전스": div_result,
                    "월봉3음봉": mr_result,
                    "볼린저스퀴즈": bollinger_result,
                    "OBV": obv_result,
                    "VCP": vcp_result,
                    "컵앤핸들": cup_result,
                    "거래량": volume_result,
                },
            }

        except Exception as e:
            return self._error_result(code, name, sector, f"분석 실패: {str(e)[:80]}")

    def _error_result(self, code, name, sector, reason):
        return {
            "code": code,
            "name": name,
            "sector": sector,
            "signal": "ERROR",
            "reason": reason,
            "current_price": 0,
            "change_pct": 0,
            "signal_source": None,
            "star_grade": 0,
            "red_star_grade": 0,
            "vcp_signal": False,
            "vcp_breakout": False,
            "cup_signal": False,
            "volume_spike": False,
            "volume_ratio": 0,
            "today_volume": 0,
            "strategies": {},
        }

    def analyze_all(self, parallel: bool = True) -> list:
        """설정 파일의 모든 종목 분석 (병렬 처리)"""
        with open("config/stocks.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        active_groups = config.get("active_groups", [])
        groups_data = config.get("groups", {})

        stock_list = []
        for group_name in active_groups:
            group = groups_data.get(group_name, {})
            for code, name in group.get("stocks", {}).items():
                stock_list.append((code, name, group_name))

        total = len(stock_list)
        print(f"[INFO] {total}개 종목 분석 시작 (병렬 워커: {MAX_WORKERS if parallel else 1})")

        start_time = datetime.now()
        results = []

        if parallel:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(self.analyze_stock, code, name, sector): (code, name)
                    for code, name, sector in stock_list
                }

                for i, future in enumerate(as_completed(futures), 1):
                    result = future.result()
                    results.append(result)

                    if i % 10 == 0 or i == total:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        print(f"  진행: {i}/{total} ({i/total*100:.0f}%) - {elapsed:.1f}초 경과")
        else:
            for i, (code, name, sector) in enumerate(stock_list, 1):
                print(f"  [{i}/{total}] {name}({code})")
                result = self.analyze_stock(code, name, sector)
                results.append(result)

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"[OK] 분석 완료: {elapsed:.1f}초 소요")

        # 일봉 캐시 저장 (다음 실행에서 재사용)
        self.data_source.save_cache()

        return results


if __name__ == "__main__":
    analyzer = SignalAnalyzer()
    results = analyzer.analyze_all()

    print("\n" + "=" * 60)
    print("[ 분석 결과 요약 ]")
    print("=" * 60)

    buy_signals = [r for r in results if r["signal"] == "BUY"]
    hold_signals = [r for r in results if r["signal"] == "HOLD"]
    errors = [r for r in results if r["signal"] == "ERROR"]

    # 빨간별 카운트
    red_double = [r for r in buy_signals if r.get("red_star_grade") == 2]
    red_single = [r for r in buy_signals if r.get("red_star_grade") == 1]
    vcp_break = [r for r in buy_signals if r.get("vcp_breakout")]

    # 노란별 카운트
    premium = [r for r in buy_signals if r.get("star_grade") == 3]
    confident = [r for r in buy_signals if r.get("star_grade") == 2]
    normal = [r for r in buy_signals if r.get("star_grade") == 1]

    print(f"\n매수 신호: {len(buy_signals)}건")
    print(f"\n[빨간별]")
    print(f"  ★★ VCP + 컵앤핸들: {len(red_double)}건")
    print(f"  ★  VCP 또는 컵앤핸들: {len(red_single)}건")
    print(f"  └ 이 중 VCP 돌파: {len(vcp_break)}건")
    print(f"\n[노란별]")
    print(f"  ★★★ 프리미엄: {len(premium)}건")
    print(f"  ★★  확신:     {len(confident)}건")
    print(f"  ★    일반:     {len(normal)}건")
    print(f"\n관망: {len(hold_signals)}건")
    print(f"오류: {len(errors)}건")
    