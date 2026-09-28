"""
코스피 + 코스닥 시가총액 상위 종목 자동 로드
- 각 시장별 상위 100개씩 총 200개
- config/stocks.json에 저장
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
import FinanceDataReader as fdr


TOP_N_KOSPI = 100
TOP_N_KOSDAQ = 100


def load_market_top(market: str, n: int = 100):
    """특정 시장의 시총 상위 n개"""
    print(f"[INFO] {market} 종목 리스트 조회 중...")
    df = fdr.StockListing(market)
    
    print(f"[INFO] 전체 {market} 종목: {len(df)}개")
    print(f"[INFO] 컬럼: {list(df.columns)}")
    
    # 시총 컬럼 찾기
    marcap_col = None
    for col in ['Marcap', 'MarketCap', 'Marketcap']:
        if col in df.columns:
            marcap_col = col
            break
    
    if marcap_col:
        top = df.sort_values(marcap_col, ascending=False).head(n)
    else:
        top = df.head(n)
    
    stocks = {}
    for _, row in top.iterrows():
        code = str(row.get('Code', '')).zfill(6)
        name = str(row.get('Name', ''))
        if code and name:
            stocks[code] = name
    
    print(f"[INFO] {market} 상위 {len(stocks)}개 선정 완료")
    return stocks


def save_stocks_json(kospi_stocks: dict, kosdaq_stocks: dict, output_path: str = "config/stocks.json"):
    """stocks.json 저장 (시장별 그룹)"""
    Path("config").mkdir(exist_ok=True)
    
    groups = {
        "KOSPI100": {
            "description": "코스피 시가총액 상위 100",
            "priority": 1,
            "stocks": kospi_stocks,
        },
        "KOSDAQ100": {
            "description": "코스닥 시가총액 상위 100",
            "priority": 2,
            "stocks": kosdaq_stocks,
        },
    }
    
    active_groups = ["KOSPI100", "KOSDAQ100"]
    
    output = {
        "meta": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "KOSPI 100 + KOSDAQ 100",
            "total_count": len(kospi_stocks) + len(kosdaq_stocks),
        },
        "groups": groups,
        "active_groups": active_groups,
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] {output_path} 저장 완료")
    print(f"[OK] KOSPI: {len(kospi_stocks)}개")
    print(f"[OK] KOSDAQ: {len(kosdaq_stocks)}개")
    print(f"[OK] 총 {output['meta']['total_count']}개")


def print_preview(stocks: dict, market: str, per_group: int = 5):
    """미리보기"""
    print(f"\n[{market} 상위 {per_group}개]")
    for i, (code, name) in enumerate(list(stocks.items())[:per_group], 1):
        print(f"  {i}. {code}  {name}")


def main():
    print("=" * 60)
    print("[ 코스피 + 코스닥 시총 상위 로드 ]")
    print(f"실행시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 코스피 시총 상위
    kospi_stocks = load_market_top("KOSPI", TOP_N_KOSPI)
    
    # 코스닥 시총 상위
    kosdaq_stocks = load_market_top("KOSDAQ", TOP_N_KOSDAQ)
    
    # 미리보기
    print_preview(kospi_stocks, "KOSPI", 5)
    print_preview(kosdaq_stocks, "KOSDAQ", 5)
    
    # 저장
    save_stocks_json(kospi_stocks, kosdaq_stocks)
    
    print("\n" + "=" * 60)
    print("[ 완료 ]")
    print("=" * 60)
    print("다음: python generate_report.py 실행")


if __name__ == "__main__":
    main()
    