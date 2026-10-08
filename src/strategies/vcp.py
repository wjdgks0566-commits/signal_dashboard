"""
VCP (Volatility Contraction Pattern) 전략
- 마크 미너비니 (Mark Minervini) 챔피언 기법
- 변동성 축소 패턴 감지
- 형성중 / 돌파 2단계 구분
"""
import pandas as pd
import numpy as np


def detect_vcp(df: pd.DataFrame) -> dict:
    """
    VCP 패턴 감지

    조건:
    1. 최근 60~120일 데이터에서 3회 이상의 조정
    2. 각 조정 폭이 점점 작아짐
    3. 최근 조정이 7% 이하
    4. 현재가가 저항선의 95% 이상
    5. 돌파 판정은 저항선 상향 + 거래량 1.2배 이상

    Returns:
        {
            "detected": bool,    # 패턴 성립 (형성중 포함)
            "breakout": bool,    # 저항선 돌파 + 거래량 동반
            "단계": "형성중" | "돌파",
            "contractions": list,
        }
    """
    result = {
        "detected": False,
        "contractions": [],
        "breakout": False,
    }

    if df is None or len(df) < 60:
        return result

    # 최근 120일 데이터
    recent = df.tail(120).copy().reset_index(drop=True)

    # 고점/저점 찾기 (Swing High/Low)
    highs = []
    lows = []

    window = 5  # 5일 윈도우
    for i in range(window, len(recent) - window):
        # 고점: 좌우 5일보다 높음
        if recent["고가"].iloc[i] == recent["고가"].iloc[i-window:i+window+1].max():
            highs.append({
                "index": i,
                "price": recent["고가"].iloc[i],
            })
        # 저점: 좌우 5일보다 낮음
        if recent["저가"].iloc[i] == recent["저가"].iloc[i-window:i+window+1].min():
            lows.append({
                "index": i,
                "price": recent["저가"].iloc[i],
            })

    if len(highs) < 3 or len(lows) < 3:
        return result

    # 조정 폭 계산 (고점 → 저점)
    contractions = []
    for high in highs:
        # 이 고점 이후의 저점 찾기
        next_lows = [l for l in lows if l["index"] > high["index"]]
        if not next_lows:
            continue
        next_low = next_lows[0]
        drop_pct = (high["price"] - next_low["price"]) / high["price"] * 100
        if drop_pct > 3:  # 3% 이상 하락만 조정으로 인정
            contractions.append({
                "high_idx": high["index"],
                "low_idx": next_low["index"],
                "drop_pct": drop_pct,
            })

    if len(contractions) < 3:
        return result

    # 최근 3~5개 조정만 사용
    recent_contractions = contractions[-5:]
    drop_pcts = [c["drop_pct"] for c in recent_contractions]

    # 조정 폭이 점점 작아지는지 확인 (전체적으로)
    is_contracting = True
    for i in range(1, len(drop_pcts)):
        # 완전한 감소가 아니어도 전반적 감소 인정
        if drop_pcts[i] > drop_pcts[i-1] * 1.2:  # 20% 이상 커지면 실패
            is_contracting = False
            break

    if not is_contracting:
        return result

    # 최근 조정이 매우 작음 (7% 이하)
    if drop_pcts[-1] > 7:
        return result

    # 저항선 = 오늘을 제외한 과거 30일 고점
    # (오늘 고가를 포함하면 종가가 저항선을 넘는 일이 사실상 불가능)
    resistance = recent["고가"].iloc[-31:-1].max()
    current_price = recent["종가"].iloc[-1]
    price_to_resistance = current_price / resistance if resistance > 0 else 0

    if price_to_resistance < 0.95:  # 저항선의 95% 미만이면 아직 준비 안 됨
        return result

    # 최근 거래량 증가 확인
    recent_volume = recent["거래량"].iloc[-1]
    avg_volume = recent["거래량"].tail(30).mean()
    volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 0

    # VCP 감지 성공
    is_breakout = bool(current_price >= resistance and volume_ratio > 1.2)

    result["detected"] = True
    result["contractions"] = [round(p, 2) for p in drop_pcts]
    result["breakout"] = is_breakout
    result["단계"] = "돌파" if is_breakout else "형성중"
    result["저항선"] = int(resistance)
    result["저항선대비"] = round(price_to_resistance * 100, 1)
    result["거래량비"] = round(volume_ratio, 2)

    return result


def get_vcp_signal(df: pd.DataFrame) -> bool:
    """VCP 신호 여부 (단순 True/False)"""
    result = detect_vcp(df)
    return result["detected"]


def get_vcp_breakout(df: pd.DataFrame) -> bool:
    """VCP 돌파 여부"""
    result = detect_vcp(df)
    return result["breakout"]
