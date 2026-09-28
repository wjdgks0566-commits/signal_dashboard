"""거래량 계산 진단"""
from src.data_source import DataSource
from src.strategies.volume_spike import VolumeSpikeDetector

ds = DataSource()
detector = VolumeSpikeDetector(lookback_days=20, spike_ratio=2.0)

# 삼성전자로 테스트
code = "005930"
df = ds.get_daily_dataframe(code)

print(f"데이터 조회: {len(df)}행")
print(f"컬럼: {list(df.columns)}")
print(f"\n마지막 5일:")
print(df.tail(5))

print(f"\n거래량 정보:")
print(f"  마지막 값: {df['거래량'].iloc[-1]}")
print(f"  최근 20일 평균: {df['거래량'].iloc[-21:-1].mean():.0f}")

result = detector.analyze(df, stock_code=code)
print(f"\n감지 결과:")
for k, v in result.items():
    print(f"  {k}: {v}")