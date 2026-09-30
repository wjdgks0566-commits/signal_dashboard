"""
HOZISTOCK 대시보드 생성
"""
import json
from datetime import datetime
from pathlib import Path

from src.analyzer import SignalAnalyzer


def generate_html(results):
    today = datetime.now().strftime("%Y-%m-%d")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()]
    
    buy_signals = [r for r in results if r["signal"] == "BUY"]
    hold_signals = [r for r in results if r["signal"] == "HOLD"]
    errors = [r for r in results if r["signal"] == "ERROR"]
    
    total_count = len(results)
    up_count = sum(1 for r in results if r.get("change_pct", 0) > 0)
    down_count = sum(1 for r in results if r.get("change_pct", 0) < 0)
    volume_spike_count = sum(1 for r in results if r.get("volume_ratio", 0) and r.get("volume_ratio", 0) >= 2.0)
    
    sector_counts = {}
    for r in results:
        sector = r.get("sector", "기타")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    
    def json_default(o):
        if isinstance(o, bool):
            return o
        return str(o)
    
    stocks_json = json.dumps(results, ensure_ascii=False, default=json_default)
    sectors_json = json.dumps(sector_counts, ensure_ascii=False)
    
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="manifest" href="manifest.json">
    <link rel="apple-touch-icon" href="icon-180.png">
    <meta name="theme-color" content="#03C75A">
    <title>HOZISTOCK</title>
    <style>
        :root {
            --bg: #f6f9fc;
            --card: #ffffff;
            --border: #e3e8ee;
            --border-hover: #cbd5e1;
            --text: #0a2540;
            --text-dim: #425466;
            --text-muted: #8898aa;
            --buy: #00d97e;
            --buy-light: #e6faf3;
            --up: #ef4444;
            --up-light: #fef2f2;
            --down: #3b82f6;
            --down-light: #eff6ff;
            --accent: #635bff;
            --accent-light: #f0efff;
            --dot-strong: #991b1b;
            --dot-medium: #dc2626;
            --dot-light: #fca5a5;
            --spike: #dc2626;
            --star: #fbbf24;
            --star-red: #e03131;
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
            --shadow-md: 0 2px 8px rgba(0,0,0,0.05);
        }
        [data-theme="dark"] {
            --bg: #0a0e17;
            --card: #151a24;
            --border: #252b38;
            --border-hover: #3a4152;
            --text: #f7fafc;
            --text-dim: #cbd5e1;
            --text-muted: #64748b;
            --buy-light: rgba(0,217,126,0.15);
            --up-light: rgba(239,68,68,0.15);
            --down-light: rgba(59,130,246,0.15);
            --accent-light: rgba(99,91,255,0.2);
            --dot-strong: #fca5a5;
            --dot-medium: #ef4444;
            --dot-light: #7f1d1d;
            --spike: #ef4444;
            --star: #fcd34d;
            --star-red: #ff6b6b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Pretendard", "Malgun Gothic", sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 24px 20px;
            max-width: 1200px;
            margin: 0 auto;
            line-height: 1.5;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 28px;
        }
        h1 { 
            font-size: 24px; 
            font-weight: 800; 
            letter-spacing: 0.05em;
            color: #03C75A;
        }
        .header-right { display: flex; align-items: center; gap: 14px; }
        .header-date { 
            font-size: 13px; 
            color: var(--text-muted); 
            font-weight: 500; 
            text-align: right;
        }
        .theme-toggle {
            background: var(--card);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 8px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 12px;
            margin-bottom: 28px;
        }
        .stat-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: var(--shadow-sm);
        }
        .stat-label { 
            font-size: 12px; 
            color: var(--text-muted); 
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }
        .stat-value { font-size: 26px; font-weight: 700; }
        .stat-value.buy { color: var(--buy); }
        .stat-value.up { color: var(--up); }
        .stat-value.down { color: var(--down); }
        .stat-value.volume { color: var(--spike); }
        .sector-tabs { display: flex; gap: 6px; margin-bottom: 20px; flex-wrap: wrap; }
        .sector-tab {
            background: var(--card);
            border: 1px solid var(--border);
            color: var(--text-dim);
            padding: 7px 14px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
        }
        .sector-tab.active { background: var(--accent); border-color: var(--accent); color: white; }
        .sector-count {
            display: inline-block;
            padding: 1px 7px;
            border-radius: 10px;
            font-size: 11px;
            margin-left: 6px;
            background: var(--accent-light);
            color: var(--accent);
        }
        .sector-tab.active .sector-count { background: rgba(255,255,255,0.25); color: white; }
        .filter-bar { display: flex; gap: 8px; margin-bottom: 28px; }
        .search-input {
            flex: 1;
            background: var(--card);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 14px;
        }
        .section-title {
            font-size: 17px;
            font-weight: 700;
            margin: 32px 0 14px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section-icon {
            width: 24px;
            height: 24px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
            font-size: 14px;
        }
        .section-icon.buy { background: var(--buy-light); color: var(--buy); }
        .section-icon.hold { background: var(--accent-light); color: var(--accent); }
        .section-icon.error { background: var(--up-light); color: var(--up); }
        .section-count { font-size: 13px; color: var(--text-muted); font-weight: 500; margin-left: 4px; }
        .buy-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 10px;
            overflow: hidden;
            box-shadow: var(--shadow-sm);
        }
        .buy-card-header {
            padding: 18px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
        }
        .buy-left { display: flex; align-items: center; gap: 14px; min-width: 0; flex: 1; }
        .stock-meta { min-width: 0; }
        .stock-name-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .stars {
            color: var(--star);
            font-size: 14px;
            letter-spacing: 1px;
            font-weight: 700;
        }
        .stars-red {
            color: var(--star-red);
            font-size: 14px;
            letter-spacing: 1px;
            font-weight: 700;
        }
        .stock-name { font-size: 16px; font-weight: 600; color: var(--text); }
        .stock-tags { display: flex; gap: 6px; margin-top: 4px; flex-wrap: wrap; align-items: center; }
        .sector-tag {
            background: var(--accent-light);
            color: var(--accent);
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 500;
        }
        .signal-source-tag {
            background: var(--buy);
            color: white;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
        }
        .signal-source-tag.premium {
            background: var(--star);
            color: #78350f;
        }
        .signal-source-tag.redsig {
            background: var(--star-red);
            color: white;
        }
        .spike-tag {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: var(--spike);
            color: white;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
        }
        .spike-tag::before {
            content: '';
            display: inline-block;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: white;
        }
        .volume-dot {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-dim);
        }
        .volume-dot::before {
            content: '';
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--dot-light);
        }
        .volume-dot.medium::before { background: var(--dot-medium); }
        .volume-dot.strong::before { background: var(--dot-strong); }
        .buy-right { display: flex; align-items: center; gap: 20px; flex-shrink: 0; }
        .price-block { text-align: right; }
        .price { font-size: 17px; font-weight: 700; color: var(--text); }
        .change { font-size: 13px; font-weight: 600; margin-top: 2px; }
        .change.up { color: var(--up); }
        .change.down { color: var(--down); }
        .change.flat { color: var(--text-muted); }
        .expand-icon { color: var(--text-muted); font-size: 14px; transition: transform 0.2s; }
        .buy-card.expanded .expand-icon { transform: rotate(180deg); }
        .buy-detail {
            display: none;
            padding: 4px 20px 20px;
            border-top: 1px solid var(--border);
        }
        .buy-card.expanded .buy-detail { display: block; }
        .detail-code {
            font-size: 12px;
            color: var(--text-muted);
            margin: 12px 0;
            font-family: 'SF Mono', Consolas, monospace;
        }
        .signal-source-box {
            background: var(--buy-light);
            border-radius: 8px;
            padding: 12px 16px;
            margin: 12px 0;
            font-size: 14px;
            color: var(--text);
        }
        .signal-source-box strong { color: var(--buy); margin-right: 6px; }
        .strategy-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 10px;
            margin-top: 12px;
        }
        .strategy-box {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 14px;
        }
        .strategy-name {
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .strategy-signal {
            font-size: 10px;
            padding: 2px 7px;
            border-radius: 4px;
            font-weight: 600;
        }
        .strategy-signal.buy { background: var(--buy); color: white; }
        .strategy-signal.hold { background: var(--border); color: var(--text-muted); }
        .strategy-signal.spike { background: var(--spike); color: white; }
        .strategy-detail { font-size: 12px; color: var(--text-dim); line-height: 1.6; }
        .strategy-detail div { margin: 3px 0; }
        .yes { color: var(--buy); font-weight: 600; }
        .no { color: var(--text-muted); }
        .hold-table-wrapper {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: var(--shadow-sm);
        }
        .hold-table { width: 100%; border-collapse: collapse; font-size: 14px; }
        .hold-table thead {
            background: var(--bg);
            color: var(--text-muted);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .hold-table th {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            user-select: none;
        }
        .hold-table th:hover { color: var(--accent); }
        .hold-table th.sort-active { color: var(--accent); }
        .hold-table th .sort-icon {
            display: inline-block;
            margin-left: 4px;
            font-size: 10px;
            opacity: 0.4;
        }
        .hold-table th.sort-active .sort-icon { opacity: 1; }
        .hold-table th.text-left, .hold-table td.text-left { text-align: left; }
        .hold-table th.text-right, .hold-table td.text-right { text-align: right; }
        .hold-table td {
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            color: var(--text);
        }
        .hold-table tbody tr:hover { background: var(--bg); }
        .hold-table tbody tr:last-child td { border-bottom: none; }
        .table-stock-name { font-weight: 600; }
        .table-price { font-weight: 600; font-variant-numeric: tabular-nums; }
        td .volume-dot { justify-content: flex-end; }
        .error-item {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }
        .error-reason { color: var(--up); font-size: 13px; font-weight: 500; }
        .footer {
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-muted);
            font-size: 12px;
        }
        @media (max-width: 768px) {
            body { padding: 16px 12px; }
            h1 { font-size: 20px; }
            .stats { grid-template-columns: repeat(3, 1fr); gap: 8px; }
            .stat-card { padding: 12px 14px; }
            .stat-value { font-size: 20px; }
            .hold-table { font-size: 13px; }
            .hold-table th, .hold-table td { padding: 10px 8px; }
            .col-sector { display: none; }
            .buy-card-header { padding: 14px 16px; flex-wrap: wrap; }
            .strategy-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>HOZISTOCK</h1>
        <div class="header-right">
            <span class="header-date">__TODAY__ (__WEEKDAY__) · 갱신 __UPDATED_TIME__</span>
            <button class="theme-toggle" onclick="toggleTheme()">🌓</button>
        </div>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-label">총 종목</div>
            <div class="stat-value">__TOTAL__</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">매수 신호</div>
            <div class="stat-value buy">__BUY_COUNT__</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">관망</div>
            <div class="stat-value">__HOLD_COUNT__</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">상승</div>
            <div class="stat-value up">__UP_COUNT__</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">하락</div>
            <div class="stat-value down">__DOWN_COUNT__</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">거래량 급증</div>
            <div class="stat-value volume">__VOLUME_SPIKE_COUNT__</div>
        </div>
    </div>
    
    <div class="sector-tabs" id="sectorTabs"></div>
    
    <div class="filter-bar">
        <input type="text" class="search-input" id="searchInput" placeholder="종목명 검색" oninput="applyFilter()">
    </div>
    
    <div id="content"></div>
    
    <div class="footer">
        Generated __GENERATED_TIME__ · FinanceDataReader
    </div>
    
    <script>
        const stocks = __STOCKS_JSON__;
        const sectorCounts = __SECTORS_JSON__;
        let currentSector = 'all';
        let sortField = 'signal';
        let sortDesc = true;
        
        function toggleTheme() {
            const current = document.body.getAttribute('data-theme') || 'light';
            const next = current === 'light' ? 'dark' : 'light';
            document.body.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        }
        
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.body.setAttribute('data-theme', savedTheme);
        
        function renderSectorTabs() {
            const container = document.getElementById('sectorTabs');
            let html = '<button class="sector-tab active" data-sector="all" onclick="setSector(\\'all\\')">전체 <span class="sector-count">' + stocks.length + '</span></button>';
            const sortedSectors = Object.entries(sectorCounts).sort((a, b) => b[1] - a[1]);
            for (const [sector, count] of sortedSectors) {
                html += '<button class="sector-tab" data-sector="' + sector + '" onclick="setSector(\\'' + sector + '\\')">' + sector + ' <span class="sector-count">' + count + '</span></button>';
            }
            container.innerHTML = html;
        }
        
        function setSector(sector) {
            currentSector = sector;
            document.querySelectorAll('.sector-tab').forEach(tab => {
                tab.classList.toggle('active', tab.dataset.sector === sector);
            });
            applyFilter();
        }
        
        function sortBy(field) {
            if (sortField === field) sortDesc = !sortDesc;
            else { sortField = field; sortDesc = true; }
            applyFilter();
        }
        
        function applyFilter() {
            const search = document.getElementById('searchInput').value.toLowerCase();
            let filtered = stocks.filter(s => {
                const matchSector = currentSector === 'all' || s.sector === currentSector;
                const matchSearch = !search || s.name.toLowerCase().includes(search);
                return matchSector && matchSearch;
            });
            renderContent(filtered);
        }
        
        function sortStocks(list) {
            const sorted = [...list];
            sorted.sort((a, b) => {
                let result = 0;
                if (sortField === 'signal') {
                    const order = { 'BUY': 0, 'HOLD': 1, 'ERROR': 2 };
                    result = order[a.signal] - order[b.signal];
                } else if (sortField === 'name') result = a.name.localeCompare(b.name);
                else if (sortField === 'price') result = a.current_price - b.current_price;
                else if (sortField === 'change') result = (a.change_pct || 0) - (b.change_pct || 0);
                return sortDesc ? -result : result;
            });
            return sorted;
        }
        
        function sortBuyByStars(list) {
            // 1순위 빨간별, 2순위 노란별, 3순위 등락률
            return [...list].sort((a, b) => {
                const redDiff = (b.red_star_grade || 0) - (a.red_star_grade || 0);
                if (redDiff !== 0) return redDiff;
                const starDiff = (b.star_grade || 0) - (a.star_grade || 0);
                if (starDiff !== 0) return starDiff;
                return (b.change_pct || 0) - (a.change_pct || 0);
            });
        }
        
        function getVolumeDotClass(ratio) {
            if (ratio >= 5.0) return 'strong';
            if (ratio >= 3.0) return 'medium';
            return '';
        }
        
        function renderVolumeDot(ratio) {
            if (!ratio) return '';
            const cls = getVolumeDotClass(ratio);
            return '<span class="volume-dot ' + cls + '">' + ratio.toFixed(2) + '×</span>';
        }
        
        function renderSpikeTag(ratio) {
            if (!ratio || ratio < 2.0) return '';
            return '<span class="spike-tag">SPIKE ' + ratio.toFixed(2) + '×</span>';
        }
        
        function renderStars(grade) {
            if (!grade || grade <= 0) return '';
            const stars = '★'.repeat(grade);
            return '<span class="stars">' + stars + '</span>';
        }
        
        function renderRedStars(grade) {
            if (!grade || grade <= 0) return '';
            const stars = '★'.repeat(grade);
            return '<span class="stars-red">' + stars + '</span>';
        }
        
        function renderContent(list) {
            const container = document.getElementById('content');
            if (list.length === 0) {
                container.innerHTML = '<div style="text-align:center; padding:60px 20px; color:var(--text-muted);">조건에 맞는 종목이 없습니다.</div>';
                return;
            }
            
            const buyList = sortBuyByStars(list.filter(s => s.signal === 'BUY'));
            const holdList = sortStocks(list.filter(s => s.signal === 'HOLD'));
            const errorList = list.filter(s => s.signal === 'ERROR');
            
            let html = '';
            
            if (buyList.length > 0) {
                html += '<div class="section-title"><span class="section-icon buy">▲</span>매수 신호<span class="section-count">' + buyList.length + '건</span></div>';
                html += buyList.map(s => renderBuyCard(s)).join('');
            }
            
            if (holdList.length > 0) {
                html += '<div class="section-title"><span class="section-icon hold">●</span>관망<span class="section-count">' + holdList.length + '건</span></div>';
                html += renderHoldTable(holdList);
            }
            
            if (errorList.length > 0) {
                html += '<div class="section-title"><span class="section-icon error">✕</span>오류<span class="section-count">' + errorList.length + '건</span></div>';
                html += errorList.map(s => renderErrorItem(s)).join('');
            }
            
            container.innerHTML = html;
        }
        
        function formatChange(pct) {
            if (pct === 0 || pct === null || pct === undefined) return '<div class="change flat">0.00%</div>';
            const cls = pct > 0 ? 'up' : 'down';
            const arrow = pct > 0 ? '▲' : '▼';
            const sign = pct > 0 ? '+' : '';
            return '<div class="change ' + cls + '">' + arrow + ' ' + sign + pct.toFixed(2) + '%</div>';
        }
        
        function formatChangeInline(pct) {
            if (pct === 0 || pct === null || pct === undefined) return '<span class="change flat">0.00%</span>';
            const cls = pct > 0 ? 'up' : 'down';
            const arrow = pct > 0 ? '▲' : '▼';
            const sign = pct > 0 ? '+' : '';
            return '<span class="change ' + cls + '">' + arrow + ' ' + sign + pct.toFixed(2) + '%</span>';
        }
        
        function renderBuyCard(s) {
            const priceStr = s.current_price.toLocaleString();
            const strategies = s.strategies || {};
            let strategyDetails = '';
            for (const [name, result] of Object.entries(strategies)) {
                const sig = result['신호'] || result['signal'] || 'HOLD';
                const sigClass = sig.toLowerCase();
                let details = '';
                for (const [key, val] of Object.entries(result)) {
                    if (['신호', '전략', '종목코드', '최근일자', 'signal'].includes(key)) continue;
                    if (val === null || val === undefined || val === '') continue;
                    let displayVal = val;
                    if (val === 'YES' || val === true) displayVal = '<span class="yes">YES</span>';
                    else if (val === 'NO' || val === false) displayVal = '<span class="no">NO</span>';
                    else if (typeof val === 'number') displayVal = val.toLocaleString();
                    details += '<div>' + key + ': ' + displayVal + '</div>';
                }
                strategyDetails += '<div class="strategy-box"><div class="strategy-name">' + name + '<span class="strategy-signal ' + sigClass + '">' + sig + '</span></div><div class="strategy-detail">' + details + '</div></div>';
            }
            
            // 매수 신호 소스를 각각 별도 태그로 분리
            const sourceStr = s.signal_source || 'BUY';
            const sources = sourceStr.split(' / ');
            const premiumSignals = ['스퀴즈', 'OBV'];
            const redSignals = ['VCP', '컵앤핸들'];
            let sourceTags = '';
            for (const src of sources) {
                let cls = 'signal-source-tag';
                if (redSignals.includes(src)) cls += ' redsig';
                else if (premiumSignals.includes(src)) cls += ' premium';
                sourceTags += '<span class="' + cls + '">' + src + '</span>';
            }
            
            const spikeTag = renderSpikeTag(s.volume_ratio);
            const redStarsHtml = renderRedStars(s.red_star_grade);
            const starsHtml = renderStars(s.star_grade);
            
            return '<div class="buy-card" onclick="toggleExpand(this)"><div class="buy-card-header"><div class="buy-left"><div class="stock-meta"><div class="stock-name-row">' + redStarsHtml + starsHtml + '<div class="stock-name">' + s.name + '</div></div><div class="stock-tags"><span class="sector-tag">' + (s.sector || '기타') + '</span>' + sourceTags + spikeTag + '</div></div></div><div class="buy-right"><div class="price-block"><div class="price">' + priceStr + '원</div>' + formatChange(s.change_pct) + '</div><span class="expand-icon">▼</span></div></div><div class="buy-detail" onclick="event.stopPropagation()"><div class="detail-code">종목코드: ' + s.code + '</div><div class="signal-source-box"><strong>매수 신호:</strong>' + (s.signal_source || 'N/A') + '</div><div class="strategy-grid">' + strategyDetails + '</div></div></div>';
        }
        
        function getSortIcon(field) {
            if (sortField !== field) return '<span class="sort-icon">↕</span>';
            return '<span class="sort-icon">' + (sortDesc ? '↓' : '↑') + '</span>';
        }
        
        function getSortClass(field) {
            return sortField === field ? 'sort-active' : '';
        }
        
        function renderHoldTable(list) {
            let html = '<div class="hold-table-wrapper"><table class="hold-table"><thead><tr>';
            html += '<th class="text-left ' + getSortClass('name') + '" onclick="sortBy(\\'name\\')">종목명' + getSortIcon('name') + '</th>';
            html += '<th class="text-left col-sector">섹터</th>';
            html += '<th class="text-right ' + getSortClass('price') + '" onclick="sortBy(\\'price\\')">현재가' + getSortIcon('price') + '</th>';
            html += '<th class="text-right ' + getSortClass('change') + '" onclick="sortBy(\\'change\\')">등락률' + getSortIcon('change') + '</th>';
            html += '<th class="text-right">거래량</th>';
            html += '</tr></thead><tbody>';
            for (const s of list) {
                html += '<tr>';
                html += '<td class="text-left table-stock-name">' + s.name + '</td>';
                html += '<td class="text-left col-sector"><span class="sector-tag">' + (s.sector || '기타') + '</span></td>';
                html += '<td class="text-right table-price">' + s.current_price.toLocaleString() + '원</td>';
                html += '<td class="text-right">' + formatChangeInline(s.change_pct) + '</td>';
                html += '<td class="text-right">' + renderVolumeDot(s.volume_ratio) + '</td>';
                html += '</tr>';
            }
            html += '</tbody></table></div>';
            return html;
        }
        
        function renderErrorItem(s) {
            return '<div class="error-item"><span class="table-stock-name">' + s.name + '</span><span class="error-reason">' + (s.reason || '') + '</span></div>';
        }
        
        function toggleExpand(card) {
            card.classList.toggle('expanded');
        }
        
        renderSectorTabs();
        applyFilter();
    </script>
</body>
</html>"""
    
    html = html.replace("__TODAY__", today)
    html = html.replace("__WEEKDAY__", weekday_kr)
    html = html.replace("__TOTAL__", str(total_count))
    html = html.replace("__BUY_COUNT__", str(len(buy_signals)))
    html = html.replace("__HOLD_COUNT__", str(len(hold_signals)))
    html = html.replace("__ERROR_COUNT__", str(len(errors)))
    html = html.replace("__UP_COUNT__", str(up_count))
    html = html.replace("__DOWN_COUNT__", str(down_count))
    html = html.replace("__VOLUME_SPIKE_COUNT__", str(volume_spike_count))
    html = html.replace("__GENERATED_TIME__", generated_time)
    updated_time_short = datetime.now().strftime("%H:%M")
    html = html.replace("__UPDATED_TIME__", updated_time_short)
    html = html.replace("__STOCKS_JSON__", stocks_json)
    html = html.replace("__SECTORS_JSON__", sectors_json)
    
    return html


def save_analysis_json(results):
    today = datetime.now().strftime("%Y%m%d")
    Path("docs/history").mkdir(parents=True, exist_ok=True)
    with open("docs/history/analysis_" + today + ".json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print("[OK] JSON 저장: docs/history/analysis_" + today + ".json")


def main():
    print("=" * 60)
    print("[ HTML 대시보드 생성 ]")
    print("실행시각:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    analyzer = SignalAnalyzer()
    results = analyzer.analyze_all()
    
    html = generate_html(results)
    
    Path("docs").mkdir(exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print("\n[OK] HTML 대시보드 생성 완료: docs/index.html")
    save_analysis_json(results)
    print("=" * 60)


if __name__ == "__main__":
    main()
    