"""
컵앤핸들 (Cup and Handle) 전략
- 윌리엄 오닐 (William O'Neil) CANSLIM 핵심 패턴
- U자형 컵 + 짧은 손잡이 + 돌파
"""
import pandas as pd
import numpy as np


def detect_cup_and_handle(df: pd.DataFrame) -> dict:
    """
    컵앤핸들 패턴 감지
    
    조건:
    1. 컵: U자형 조정 (15~35% 하락 후 이전 고점 근처 회복)
    2. 컵 기간: 최소 30일 이상
    3. 손잡이: 컵 오른쪽에서 짧은 조정 (5~15%)
    4. 손잡이 기간: 5~30일
    5. 현재가가 손잡이 저항선 근처 또는 돌파
    
    Returns:
        {
            "detected": bool,
            "cup_depth": float,      # 컵 깊이 (%)
            "handle_depth": float,   # 손잡이 깊이 (%)
            "breakout": bool,        # 돌파 여부
        }
    """
    result = {
        "detected": False,
        "cup_depth": 0.0,
        "handle_depth": 0.0,
        "breakout": False,
    }
    
    if df is None or len(df) < 40:
        return result
    
    # 최근 120일 데이터 (또는 있는 만큼)
    lookback = min(120, len(df))
    recent = df.tail(lookback).copy().reset_index(drop=True)
    
    if len(recent) < 40:
        return result
    
    # 1단계: 컵의 왼쪽 고점 찾기 (최근 20일 제외한 부분에서)
    # 손잡이 형성 공간을 남겨둠
    handle_area_start = len(recent) - 20  # 최근 20일은 손잡이 영역
    
    if handle_area_start < 20:
        return result
    
    cup_area = recent.iloc[:handle_area_start]
    
    # 컵 왼쪽 고점 (30~60일 전 범위에서 최고점)
    left_search_start = max(0, len(cup_area) - 60)
    left_search_end = max(0, len(cup_area) - 20)
    
    if left_search_end <= left_search_start:
        return result
    
    left_high_idx = cup_area["고가"].iloc[left_search_start:left_search_end].idxmax()
    left_high = cup_area["고가"].iloc[left_high_idx]
    
    # 2단계: 컵 바닥 찾기 (왼쪽 고점 이후 ~ 손잡이 영역 전)
    if left_high_idx >= handle_area_start - 5:
        return result
    
    bottom_area = recent.iloc[left_high_idx:handle_area_start]
    if len(bottom_area) < 15:
        return result
    
    bottom_idx = bottom_area["저가"].idxmin()
    bottom_price = recent["저가"].iloc[bottom_idx]
    
    # 컵 깊이 계산
    cup_depth = (left_high - bottom_price) / left_high * 100
    
    # 컵 깊이 조건: 15~40%
    if cup_depth < 12 or cup_depth > 40:
        return result
    
    # 3단계: 컵 오른쪽 고점 찾기 (바닥 이후 ~ 손잡이 영역 전)
    right_area = recent.iloc[bottom_idx:handle_area_start]
    if len(right_area) < 5:
        return result
    
    right_high_idx = right_area["고가"].idxmax()
    right_high = recent["고가"].iloc[right_high_idx]
    
    # 오른쪽 고점이 왼쪽 고점의 90% 이상이어야 함 (U자 회복)
    if right_high < left_high * 0.90:
        return result
    
    # 4단계: 손잡이 확인 (최근 20일)
    handle_area = recent.iloc[handle_area_start:]
    if len(handle_area) < 5:
        return result
    
    handle_high = handle_area["고가"].max()
    handle_low = handle_area["저가"].min()
    
    # 손잡이 깊이 계산
    handle_depth = (handle_high - handle_low) / handle_high * 100
    
    # 손잡이 깊이 조건: 3~15%
    if handle_depth < 3 or handle_depth > 15:
        return result
    
    # 손잡이가 컵 깊이의 절반보다 얕아야 함
    if handle_depth > cup_depth * 0.5:
        return result
    
    # 5단계: 현재가가 손잡이 저항선 근처 또는 돌파
    current_price = recent["종가"].iloc[-1]
    resistance = max(right_high, handle_high)
    
    price_to_resistance = current_price / resistance
    
    if price_to_resistance < 0.95:
        return result
    
    # 최근 거래량 확인
    recent_volume = recent["거래량"].tail(3).mean()
    avg_volume = recent["거래량"].tail(30).mean()
    volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 0
    
    # 컵앤핸들 감지 성공
    result["detected"] = True
    result["cup_depth"] = round(cup_depth, 2)
    result["handle_depth"] = round(handle_depth, 2)
    result["breakout"] = current_price >= resistance and volume_ratio > 1.2
    
    return result


def get_cup_and_handle_signal(df: pd.DataFrame) -> bool:
    """컵앤핸들 신호 여부 (단순 True/False)"""
    result = detect_cup_and_handle(df)
    return result["detected"]
