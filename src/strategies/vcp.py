"""
VCP (Volatility Contraction Pattern) 전략
- 마크 미너비니 (Mark Minervini) 챔피언 기법
- 변동성 축소 패턴 감지
"""
import pandas as pd
import numpy as np


def detect_vcp(df: pd.DataFrame) -> dict:
    """
    VCP 패턴 감지
    
    조건:
    1. 최근 60~120일 데이터에서 3회 이상의 조정
    2. 각 조정 폭이 점점 작아짐
    3. 최근 조정이 5% 이하
    4. 현재가가 저항선 근처 또는 돌파
    5. 최근 거래량 증가
    
    Returns:
        {
            "detected": bool,
            "contractions": list,  # 조정 폭 리스트
            "breakout": bool,  # 돌파 여부
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
    
    # 현재가가 저항선 근처
    resistance = recent["고가"].tail(30).max()
    current_price = recent["종가"].iloc[-1]
    price_to_resistance = current_price / resistance
    
    if price_to_resistance < 0.95:  # 저항선의 95% 미만이면 아직 준비 안 됨
        return result
    
    # 최근 거래량 증가 확인
    recent_volume = recent["거래량"].tail(3).mean()
    avg_volume = recent["거래량"].tail(30).mean()
    volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 0
    
    # VCP 감지 성공
    result["detected"] = True
    result["contractions"] = drop_pcts
    result["breakout"] = current_price >= resistance and volume_ratio > 1.2
    
    return result


def get_vcp_signal(df: pd.DataFrame) -> bool:
    """VCP 신호 여부 (단순 True/False)"""
    result = detect_vcp(df)
    return result["detected"]