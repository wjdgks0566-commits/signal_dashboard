"""
FinanceDataReader 시가총액 상위로 config/stocks.json 생성
- KOSPI  상위 200
- KOSDAQ 상위 150
※ 종목코드·종목명만 수집. 시세 분석은 전부 KIS API가 담당.
"""
import json
from datetime import datetime

import FinanceDataReader as fdr

TARGET = {
    "KOSPI200": {
        "market": "KOSPI",
        "n": 200,
        "desc": "코스피 시가총액 상위 200",
        "priority": 1,
    },
    "KOSDAQ150": {
        "market": "KOSDAQ",
        "n": 150,
        "desc": "코스닥 시가총액 상위 150",
        "priority": 2,
    },
}

CAP_CANDIDATES = ["Marcap", "MarCap", "Market Cap", "시가총액"]
CODE_CANDIDATES = ["Code", "Symbol", "종목코드"]
NAME_CANDIDATES = ["Name", "종목명"]


def pick_column(df, candidates, label):
    for c in candidates:
        if c in df.columns:
            return c
    raise SystemExit(f"[ERROR] {label} 컬럼을 찾을 수 없습니다. 실제 컬럼: {list(df.columns)}")


groups = {}

for group_name, info in TARGET.items():
    df = fdr.StockListing(info["market"])
    print(f"[INFO] {info['market']} 원본 {len(df)}행")
    print(f"       컬럼: {list(df.columns)}")

    code_col = pick_column(df, CODE_CANDIDATES, "종목코드")
    name_col = pick_column(df, NAME_CANDIDATES, "종목명")
    cap_col = pick_column(df, CAP_CANDIDATES, "시가총액")

    df = df.dropna(subset=[code_col, name_col, cap_col])
    df = df.sort_values(cap_col, ascending=False).head(info["n"])

    stocks = {}
    for _, row in df.iterrows():
        code = str(row[code_col]).strip().zfill(6)
        name = str(row[name_col]).strip()
        stocks[code] = name

    groups[group_name] = {
        "description": info["desc"],
        "priority": info["priority"],
        "stocks": stocks,
    }
    print(f"[OK] {group_name}: {len(stocks)}종목\n")

total = sum(len(g["stocks"]) for g in groups.values())

config = {
    "meta": {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "FinanceDataReader 시가총액 상위 (KOSPI 200 + KOSDAQ 150)",
        "total_count": total,
    },
    "groups": groups,
    "active_groups": list(TARGET.keys()),
}

with open("config/stocks.json", "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print("=" * 50)
print(f"[OK] config/stocks.json 저장 완료 (총 {total}종목)")
print("=" * 50)
