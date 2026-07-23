from __future__ import annotations

from pathlib import Path
import shutil

from .analysis import build_daily_summary, build_price_change_history, build_weekly_summary
from .catalog_page import CATALOG_SCRIPT, catalog_body
from .catalog_history import build_catalog_history
from .price_changes_page import PRICE_CHANGES_SCRIPT, price_changes_body
from .storage import write_json
from .storage import snapshot_files


ANALYTICS_MEASUREMENT_ID = "G-RSVR6Y389R"
ANALYTICS_SCRIPT = f"""
(() => {{
  "use strict";

  const measurementId = "{ANALYTICS_MEASUREMENT_ID}";
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() {{
    window.dataLayer.push(arguments);
  }};

  const tag = document.createElement("script");
  tag.async = true;
  tag.src = `https://www.googletagmanager.com/gtag/js?id=${{encodeURIComponent(measurementId)}}`;
  document.head.appendChild(tag);

  window.gtag("js", new Date());
  window.gtag("config", measurementId, {{
    page_title: document.title,
    page_path: window.location.pathname,
    page_location: window.location.origin + window.location.pathname,
    traffic_context: window.self === window.top ? "direct" : "embedded",
  }});
}})();
"""


STYLE = """
:root{color-scheme:light;--paper:oklch(98.2% .006 105);--surface:oklch(99.7% .003 105);--surface-tint:oklch(96.7% .012 112);--ink:oklch(25% .025 120);--muted:oklch(48% .022 120);--line:oklch(87% .018 112);--line-strong:oklch(73% .026 112);--accent:oklch(43% .075 145);--accent-soft:oklch(94% .025 145);--warning:oklch(48% .09 63);--warning-soft:oklch(95% .03 75);--increase:oklch(46% .09 52);--increase-soft:oklch(95% .025 62);--decrease:oklch(45% .08 245);--decrease-soft:oklch(95% .02 245);--focus:oklch(60% .15 245);--radius:8px;--shadow:0 12px 34px oklch(25% .02 120/.08)}
*{box-sizing:border-box}[hidden]{display:none!important}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}button,input,select{font:inherit;color:inherit}button,select{cursor:pointer}a{color:var(--accent);text-underline-offset:3px}a:hover{text-decoration-thickness:2px}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.site-header{border-bottom:1px solid var(--line);background:color-mix(in oklch,var(--paper) 94%,white);position:sticky;top:0;z-index:20}.site-header-inner{max-width:1440px;margin:auto;min-height:62px;padding:.65rem 1.5rem;display:flex;align-items:center;justify-content:space-between;gap:2rem}.site-identity{display:flex;align-items:baseline;gap:.55rem;text-decoration:none;color:var(--ink);white-space:nowrap}.site-identity strong{font-size:1rem}.site-identity span{color:var(--muted);font-size:.8rem}.site-nav{display:flex;gap:.25rem;flex-wrap:wrap}.site-nav a{padding:.45rem .65rem;border-radius:6px;color:var(--muted);text-decoration:none}.site-nav a:hover{background:var(--surface-tint);color:var(--ink)}.site-nav a[aria-current="page"]{background:var(--accent-soft);color:var(--accent);font-weight:650}
main{max-width:1120px;margin:auto;padding:2rem 1.5rem 4rem}.catalog-page main,.changes-page main{max-width:1500px;padding-top:1.5rem}.site-footer{border-top:1px solid var(--line);color:var(--muted)}.site-footer p{max-width:1120px;margin:auto;padding:1.5rem}.hero{padding:2rem 0}.hero h1,.catalog-heading h1,.change-heading h1{margin:.15rem 0;font-size:2.75rem;line-height:1.05;letter-spacing:-.035em}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:1rem}.metric{font-size:1.8rem;font-weight:720;font-variant-numeric:tabular-nums}.muted,.quiet{color:var(--muted)}.healthy{color:var(--accent);font-weight:700}.gap{color:var(--warning)}table{width:100%;border-collapse:collapse;background:var(--surface)}th,td{text-align:left;padding:.65rem;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:.74rem;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.catalog-heading{display:flex;align-items:end;justify-content:space-between;gap:2rem;padding:1rem 0 1.5rem}.eyebrow{margin:0;color:var(--accent);font-size:.75rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase}.lede{max-width:660px;margin:.65rem 0 0;color:var(--muted);font-size:1rem}.catalog-scope{display:grid;grid-template-columns:repeat(3,minmax(105px,1fr));min-width:min(520px,48vw);margin:0;border-top:1px solid var(--line-strong);border-bottom:1px solid var(--line)}.catalog-scope div{padding:.85rem}.catalog-scope div+div{border-left:1px solid var(--line)}.catalog-scope dt{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.05em}.catalog-scope dd{margin:.2rem 0 0;font-size:1.15rem;font-weight:680;font-variant-numeric:tabular-nums}
.catalog-controls{background:var(--surface-tint);border:1px solid var(--line);border-radius:var(--radius);padding:1rem 1.1rem}.controls-heading,.results-toolbar{display:flex;align-items:center;justify-content:space-between;gap:1rem}.controls-heading h2{margin:0;font-size:1rem}.controls-heading p{margin:.15rem 0 0;color:var(--muted);font-size:.82rem}.filter-grid{display:grid;grid-template-columns:minmax(250px,1.7fr) repeat(3,minmax(140px,1fr));gap:.8rem;margin-top:.9rem}.filter-grid>label,.toolbar-actions label{display:flex;flex-direction:column;gap:.3rem;color:var(--muted);font-size:.75rem;font-weight:650}.filter-grid input,.filter-grid select,.toolbar-actions select{width:100%;min-height:40px;border:1px solid var(--line-strong);border-radius:6px;background:var(--surface);padding:.48rem .6rem}.search-field{grid-column:span 2}.price-filter,.check-filters{border:0;padding:0;margin:0;grid-column:span 2}.filter-legend,.check-filters legend{display:block;margin-bottom:.3rem;color:var(--muted);font-size:.75rem;font-weight:650}.price-fields{display:flex;gap:.75rem}.price-filter label{display:flex;flex:1;flex-direction:column;gap:.3rem;color:var(--muted);font-size:.72rem}.check-filters{display:flex;gap:.75rem;align-items:center;flex-wrap:wrap}.check-filters legend{width:100%}.check-filters label{display:flex;align-items:center;gap:.45rem;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:.55rem .65rem;font-size:.78rem}.check-filters input{width:1rem;min-height:auto;margin:0}.text-button{border:0;background:transparent;color:var(--accent);padding:.4rem}.secondary-button{border:1px solid var(--line-strong);border-radius:6px;background:var(--surface);padding:.48rem .7rem}.secondary-button:hover{border-color:var(--accent);color:var(--accent)}.secondary-button:disabled{cursor:not-allowed;opacity:.45}.catalog-status{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.catalog-workspace{display:grid;grid-template-columns:minmax(0,1fr) minmax(340px,410px);gap:1rem;align-items:start;margin-top:1rem}.results-pane,.detail-panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius)}.results-toolbar{padding:.8rem 1rem;border-bottom:1px solid var(--line)}.results-toolbar p{margin:0;font-variant-numeric:tabular-nums;font-weight:650}.toolbar-actions{display:flex;align-items:end;gap:.55rem}.toolbar-actions label{min-width:112px}.table-scroll{overflow:auto}.catalog-table{table-layout:fixed}.catalog-table th:nth-child(1){width:42%}.catalog-table th:nth-child(2){width:18%}.catalog-table th:nth-child(3){width:18%}.catalog-table th:nth-child(4){width:22%}.catalog-table td{height:74px}.catalog-table tr.selected td{background:var(--accent-soft);box-shadow:inset 0 1px var(--accent),inset 0 -1px var(--accent)}.item-button{display:flex;flex-direction:column;gap:.15rem;width:100%;padding:0;border:0;background:transparent;text-align:left;color:var(--ink)}.item-button strong{font-size:.9rem}.item-button span,.date-note{display:block;color:var(--muted);font-size:.72rem}.price-value{font-weight:700;font-variant-numeric:tabular-nums}.tags{display:flex;gap:.3rem;flex-wrap:wrap}.tag{display:inline-block;border:1px solid var(--line-strong);border-radius:999px;padding:.15rem .42rem;font-size:.68rem;white-space:nowrap}.tag.promoted{border-color:color-mix(in oklch,var(--accent),white 55%);background:var(--accent-soft);color:var(--accent)}.tag.missing{border-color:color-mix(in oklch,var(--warning),white 55%);background:var(--warning-soft);color:var(--warning)}.pagination{display:flex;align-items:center;justify-content:center;gap:.8rem;padding:.8rem;border-top:1px solid var(--line)}.pagination span{min-width:110px;text-align:center;color:var(--muted);font-size:.8rem}.empty-state,.detail-placeholder,.error-state{display:flex;flex-direction:column;gap:.35rem;align-items:center;justify-content:center;text-align:center;padding:3rem;color:var(--muted)}
.detail-panel{position:sticky;top:78px;max-height:calc(100vh - 94px);overflow:auto;box-shadow:var(--shadow)}.detail-close{display:none}.detail-content{padding:1rem}.detail-header{display:grid;grid-template-columns:92px 1fr;gap:1rem;align-items:start}.detail-header img,.image-placeholder{width:92px;height:92px;object-fit:contain;border:1px solid var(--line);border-radius:6px;background:white}.image-placeholder{display:grid;place-items:center;color:var(--muted);font-size:.72rem}.detail-header h2{margin:.22rem 0;font-size:1.25rem;line-height:1.25}.detail-price{margin:.3rem 0 0;font-size:1.45rem;font-weight:760;font-variant-numeric:tabular-nums}.detail-state{margin:.2rem 0;color:var(--muted);font-size:.76rem}.detail-actions{display:flex;align-items:center;gap:.8rem;margin:1rem 0;padding-bottom:1rem;border-bottom:1px solid var(--line);font-size:.78rem}.evidence-list{margin:0}.evidence-list div{display:grid;grid-template-columns:135px 1fr;gap:.75rem;padding:.48rem 0;border-bottom:1px solid var(--line)}.evidence-list dt{color:var(--muted);font-size:.74rem}.evidence-list dd{margin:0;font-size:.78rem;overflow-wrap:anywhere}.evidence-list code{font-size:.7rem}.category-evidence,.history-evidence{margin-top:1.2rem}.category-evidence h3,.history-evidence h3{margin:0 0 .45rem;font-size:.9rem}.category-evidence ul{margin:0;padding-left:1.1rem;color:var(--muted);font-size:.76rem}.history-evidence>div>p{margin:0 0 .7rem;color:var(--muted);font-size:.75rem}.history-scroll{max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:6px}.history-scroll table{font-size:.72rem}.history-scroll th{position:sticky;top:0;background:var(--surface-tint);z-index:1}.history-scroll td:nth-child(1){white-space:nowrap}.history-scroll td:nth-child(2){font-variant-numeric:tabular-nums;white-space:nowrap}.history-scroll td span{display:block}.history-scroll small{color:var(--muted)}.history-gap td{background:var(--warning-soft)}.gap-label{color:var(--warning);font-weight:700}.catalog-contract{margin:1rem 0 0;text-align:right;font-size:.8rem}
.change-heading{display:grid;grid-template-columns:minmax(0,1fr) minmax(600px,1.2fr);gap:2rem;align-items:end;padding:1rem 0 1.5rem}.change-scope{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));margin:0;border-top:1px solid var(--line-strong);border-bottom:1px solid var(--line)}.change-scope div{padding:.78rem}.change-scope div+div{border-left:1px solid var(--line)}.change-scope dt{color:var(--muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em}.change-scope dd{margin:.2rem 0 0;font-size:.95rem;font-weight:680;font-variant-numeric:tabular-nums}.research-note{display:flex;gap:.5rem;align-items:baseline;margin-bottom:1rem;border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--surface);padding:.8rem 1rem}.research-note span{color:var(--muted);font-size:.82rem}.range-controls{border-top:1px solid var(--line-strong);border-bottom:1px solid var(--line);padding:1rem 0}.quick-ranges{display:flex;gap:.35rem;flex-wrap:wrap}.quick-ranges button{border:1px solid var(--line);border-radius:6px;background:var(--surface);padding:.38rem .62rem;font-size:.78rem}.quick-ranges button:hover{border-color:var(--accent);color:var(--accent)}.date-fields{display:grid;grid-template-columns:180px 180px max-content 1fr;gap:.75rem;align-items:end;margin-top:.85rem}.date-fields label,.change-filter-grid>label{display:flex;flex-direction:column;gap:.3rem;color:var(--muted);font-size:.75rem;font-weight:650}.date-fields input,.change-filter-grid input,.change-filter-grid select{width:100%;min-height:40px;border:1px solid var(--line-strong);border-radius:6px;background:var(--surface);padding:.48rem .6rem}.date-fields p{margin:0 0 .5rem;color:var(--muted);font-size:.8rem}.primary-button{min-height:40px;border:1px solid var(--accent);border-radius:6px;background:var(--accent);color:var(--paper);padding:.48rem .85rem;font-weight:680}.primary-button:hover{background:color-mix(in oklch,var(--accent),var(--ink) 12%)}.primary-button:disabled{cursor:wait;opacity:.65}.change-filters{margin-top:1rem}.change-filter-grid{display:grid;grid-template-columns:minmax(260px,1.6fr) repeat(4,minmax(140px,1fr));gap:.8rem;margin-top:.9rem}.change-search{grid-column:span 2}.suffix-input{position:relative}.suffix-input input{padding-right:2rem}.suffix-input span{position:absolute;right:.7rem;top:.58rem;color:var(--muted)}.change-checks{grid-column:span 2}.change-workspace{display:grid;grid-template-columns:minmax(0,1fr) minmax(350px,410px);gap:1rem;align-items:start;margin-top:1rem}.toolbar-note{display:block;color:var(--muted);font-size:.72rem}.export-actions{display:flex;gap:.35rem}.change-table{table-layout:fixed}.change-table th:nth-child(1){width:13%}.change-table th:nth-child(2){width:29%}.change-table th:nth-child(3){width:22%}.change-table th:nth-child(4){width:15%}.change-table th:nth-child(5){width:21%}.change-table tr.selected td{background:var(--accent-soft);box-shadow:inset 0 1px var(--accent),inset 0 -1px var(--accent)}.interval-date{font-weight:680;font-variant-numeric:tabular-nums}.change-button{display:flex;flex-direction:column;gap:.15rem;width:100%;border:0;background:transparent;padding:0;text-align:left}.change-button strong{font-size:.88rem}.change-button span{color:var(--muted);font-size:.72rem}.price-comparison{display:flex;align-items:center;gap:.4rem;white-space:nowrap;font-variant-numeric:tabular-nums}.movement{display:inline-block;border-radius:999px;padding:.18rem .5rem;font-size:.75rem;font-weight:750;text-transform:capitalize;font-variant-numeric:tabular-nums}.movement.increase{background:var(--increase-soft);color:var(--increase)}.movement.decrease{background:var(--decrease-soft);color:var(--decrease)}.increase-text{color:var(--increase);font-weight:700}.decrease-text{color:var(--decrease);font-weight:700}.change-detail-heading h2{margin:.25rem 0 .6rem;font-size:1.25rem;line-height:1.25}.change-equation{display:grid;grid-template-columns:1fr auto 1fr;gap:.7rem;align-items:center;margin:1rem 0;padding:.9rem;background:var(--surface-tint);border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-size:1.05rem;font-variant-numeric:tabular-nums}.change-equation>span:first-child,.change-equation strong{display:flex;flex-direction:column}.change-equation small{color:var(--muted);font-size:.68rem;font-weight:500}.change-summary{color:var(--muted);font-size:.8rem}.change-detail-panel{box-shadow:var(--shadow)}
@media(max-width:1050px){.filter-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.search-field{grid-column:span 2}.catalog-workspace{grid-template-columns:minmax(0,1fr) 350px}.toolbar-actions{flex-wrap:wrap;justify-content:end}.catalog-table th:nth-child(2),.catalog-table td:nth-child(2){display:none}.catalog-table th:nth-child(1){width:45%}.catalog-table th:nth-child(3){width:25%}.catalog-table th:nth-child(4){width:30%}}
@media(max-width:760px){.site-header{position:static}.site-header-inner{align-items:flex-start;flex-direction:column;gap:.45rem;padding:.75rem 1rem}.site-nav{width:100%;overflow:auto;flex-wrap:nowrap}.site-nav a{white-space:nowrap}.catalog-page main,main{padding:1.1rem 1rem 3rem}.catalog-heading{align-items:start;flex-direction:column;gap:1rem}.catalog-scope{width:100%;min-width:0}.catalog-scope dd{font-size:.95rem}.filter-grid{grid-template-columns:1fr}.search-field,.price-filter,.check-filters{grid-column:span 1}.price-fields{flex-wrap:wrap}.results-toolbar{align-items:flex-start;flex-direction:column}.toolbar-actions{width:100%;justify-content:flex-start}.toolbar-actions label{flex:1}.catalog-table th:nth-child(4),.catalog-table td:nth-child(4){display:none}.catalog-table th:nth-child(1){width:62%}.catalog-table th:nth-child(3){width:38%}.catalog-workspace{display:block}.detail-panel{display:none;position:fixed;z-index:50;inset:1rem 0 0 1.5rem;max-height:none;border-radius:10px 0 0 0;box-shadow:-20px 0 60px oklch(20% .03 120/.22)}.detail-panel.is-open{display:block}.detail-close{display:block;position:sticky;top:0;z-index:2;width:100%;border:0;border-bottom:1px solid var(--line);background:var(--surface-tint);padding:.7rem;text-align:right;color:var(--accent)}.site-footer p{padding:1rem}.catalog-contract{text-align:left}}
@media(max-width:480px){.catalog-scope{grid-template-columns:1fr}.catalog-scope div+div{border-left:0;border-top:1px solid var(--line)}.toolbar-actions{display:grid;grid-template-columns:1fr 1fr}.toolbar-actions .secondary-button{grid-column:span 2}.catalog-table th:nth-child(3),.catalog-table td:nth-child(3){display:none}.catalog-table th:nth-child(1){width:100%}.detail-header{grid-template-columns:72px 1fr}.detail-header img,.image-placeholder{width:72px;height:72px}.evidence-list div{grid-template-columns:115px 1fr}}
@media(max-width:1180px){.change-heading{grid-template-columns:1fr}.change-filter-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.change-search{grid-column:span 2}.change-workspace{grid-template-columns:minmax(0,1fr) 350px}.change-table th:nth-child(5),.change-table td:nth-child(5){display:none}.change-table th:nth-child(1){width:16%}.change-table th:nth-child(2){width:34%}.change-table th:nth-child(3){width:29%}.change-table th:nth-child(4){width:21%}}
@media(max-width:760px){.change-heading{gap:1rem}.change-scope{grid-template-columns:repeat(2,1fr)}.change-scope div:nth-child(3){border-left:0;border-top:1px solid var(--line)}.change-scope div:nth-child(4){border-top:1px solid var(--line)}.research-note{align-items:flex-start;flex-direction:column}.date-fields{grid-template-columns:1fr 1fr}.date-fields .primary-button{grid-column:span 2}.date-fields p{grid-column:span 2}.change-filter-grid{grid-template-columns:1fr 1fr}.change-search{grid-column:span 2}.change-checks{grid-column:span 2}.change-workspace{display:block}.change-table th:nth-child(3),.change-table td:nth-child(3),.change-table th:nth-child(5),.change-table td:nth-child(5){display:none}.change-table th:nth-child(1){width:27%}.change-table th:nth-child(2){width:48%}.change-table th:nth-child(4){width:25%}.change-toolbar{align-items:flex-start;flex-direction:column}.change-toolbar .toolbar-actions{width:100%;flex-wrap:wrap}.export-actions{width:100%}.export-actions button{flex:1}}
@media(max-width:480px){.change-scope{grid-template-columns:1fr}.change-scope div+div{border-left:0;border-top:1px solid var(--line)}.date-fields,.change-filter-grid{grid-template-columns:1fr}.date-fields .primary-button,.date-fields p,.change-search,.change-checks{grid-column:span 1}.change-table th:nth-child(1){width:28%}.change-table th:nth-child(2){width:47%}.change-table th:nth-child(4){width:25%}.change-table td{padding:.55rem .4rem}.movement{font-size:.68rem}}
"""

NAV_ITEMS = (("Overview", "index.html", "overview"), ("Daily", "daily-report.html", "daily"), ("Weekly", "weekly-report.html", "weekly"), ("Price changes", "price-changes.html", "changes"), ("Catalog", "catalog.html", "catalog"), ("Methodology", "METHODOLOGY.html", "methodology"))


def _page(title: str, body: str, script: str = "", *, current: str = "", body_class: str = "") -> str:
    links = "".join(
        f'<a href="{href}"'
        + (' aria-current="page"' if key == current else "")
        + f">{label}</a>"
        for label, href, key in NAV_ITEMS
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f7f8f2"><title>{title}</title><link rel="stylesheet" href="assets/site.css?v=research-1.1"><script src="assets/analytics.js?v=research-1.0" defer></script></head><body class="{body_class}"><header class="site-header"><div class="site-header-inner"><a class="site-identity" href="index.html"><strong>Gala Freeport–Merrick</strong><span>catalog research</span></a><nav class="site-nav" aria-label="Research reports">{links}</nav></div></header><main>{body}</main><footer class="site-footer"><p>Independent, unaffiliated research. Source: <a href="https://galasupermarkets.com/Freeport-Merrick">Gala Supermarkets public storefront</a>. Online values are not asserted as physical shelf prices.</p></footer>{script}</body></html>"""


def _summary_script(source: str, weekly: bool = False) -> str:
    keys = "['latest_catalog_size','median_catalog_size','median_valid_price_percentage','price_increases','price_decreases','additions','returns','missing_products']" if weekly else "['catalog_size','valid_price_percentage','median_regular_price','products_with_promotions']"
    target = "data" if weekly else "data.latest"
    return f"""<script>fetch('{source}').then(r=>r.json()).then(data=>{{const source={target};const labels={{catalog_size:'Catalog products',valid_price_percentage:'Valid prices %',median_regular_price:'Median regular price',products_with_promotions:'Products promoted',latest_catalog_size:'Latest catalog',median_catalog_size:'Median catalog',median_valid_price_percentage:'Median valid prices %',price_increases:'Price increases',price_decreases:'Price decreases',additions:'Additions',returns:'Returns',missing_products:'Missing observations'}};document.querySelector('#status').textContent=data.status;document.querySelector('#metrics').innerHTML={keys}.map(k=>`<section class="card"><div class="metric">${{source[k]??'—'}}</div><div>${{labels[k]}}</div></section>`).join('');document.querySelector('#raw').href='{source}';}}).catch(e=>document.querySelector('#status').textContent='Report data unavailable');</script>"""


def _daily_script() -> str:
    return """<script>const esc=s=>String(s??'—').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));const priceRows=rows=>rows.slice(0,25).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.previous_regular_price)}</td><td>${esc(x.current_regular_price)}</td><td>${esc(x.change_percentage)}%</td></tr>`).join('')||'<tr><td colspan="4">None reported</td></tr>';fetch('data/daily-summary.json').then(r=>r.json()).then(d=>{status.textContent=d.status;const x=d.latest;metrics.innerHTML=[['Catalog products',x.catalog_size],['Valid prices %',x.valid_price_percentage],['Promoted products',x.products_with_promotions],['Prior overlap %',d.comparison?.prior_overlap_percentage??'—']].map(([k,v])=>`<section class="card"><div class="metric">${esc(v)}</div><div>${k}</div></section>`).join('');increases.innerHTML=priceRows(d.price_increases);decreases.innerHTML=priceRows(d.price_decreases);assortment.textContent=d.comparison?`${d.comparison.additions} additions; ${d.comparison.returns} returns; ${d.comparison.missing_products} missing observations`:'Comparisons begin with the second healthy snapshot.';promotions.textContent=`${d.promotion_changes.active} active; ${d.promotion_changes.start_count} starts; ${d.promotion_changes.end_count} ends; ${d.promotion_changes.change_count} changes`;anomalies.textContent=`${d.anomalies.length} conservative flags`;}).catch(()=>status.textContent='Report data unavailable')</script>"""


def _weekly_script() -> str:
    return """<script>const esc=s=>String(s??'—').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));fetch('data/weekly-summary.json').then(r=>r.json()).then(d=>{status.textContent=d.status;metrics.innerHTML=[['Latest catalog',d.latest_catalog_size],['Median catalog',d.median_catalog_size],['Median valid prices %',d.median_valid_price_percentage],['Snapshot days',d.snapshot_days]].map(([k,v])=>`<section class="card"><div class="metric">${esc(v)}</div><div>${k}</div></section>`).join('');totals.textContent=`${d.price_increases} price increases; ${d.price_decreases} decreases; ${d.additions} additions; ${d.returns} returns; ${d.missing_products} missing observations`;history.innerHTML=d.daily_history.map(x=>`<tr><td>${esc(x.snapshot_date)}</td><td>${esc(x.catalog_size)}</td><td>${esc(x.valid_price_percentage)}%</td><td>${esc(x.products_with_promotions)}</td></tr>`).join('')||'<tr><td colspan="4">Awaiting baseline</td></tr>';}).catch(()=>status.textContent='Report data unavailable')</script>"""


def build_reports(snapshot_dir: Path, docs_dir: Path) -> tuple[dict, dict]:
    data_dir = docs_dir / "data"
    assets = docs_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    has_snapshots = bool(snapshot_files(snapshot_dir, "catalog"))
    if has_snapshots:
        daily = build_daily_summary(snapshot_dir)
        weekly = build_weekly_summary(daily)
        price_index, price_shards = build_price_change_history(snapshot_dir)
    else:
        latest = {
            "snapshot_date": None,
            "catalog_size": 0,
            "valid_price_percentage": None,
            "median_regular_price": None,
            "average_regular_price": None,
            "products_with_promotions": 0,
        }
        daily = {
            "schema_version": "1.0",
            "report": "daily",
            "status": "awaiting_baseline",
            "scope": "Gala Freeport–Merrick public online catalog; not asserted as physical shelf prices",
            "latest_healthy_observation": None,
            "latest": latest,
            "previous": None,
            "comparison": None,
            "daily_history": [],
            "comparison_history": [],
            "price_increases": [],
            "price_decreases": [],
            "anomalies": [],
            "assortment_changes": {
                "additions": [],
                "returns": [],
                "missing_products": [],
            },
            "promotion_changes": {
                "starts": [],
                "ends": [],
                "changes": [],
                "start_count": 0,
                "end_count": 0,
                "change_count": 0,
                "active": 0,
            },
            "active_promotions": [],
            "category_summary": [],
            "brand_summary": [],
            "price_history_windows": [],
            "snapshot_health_history": [],
            "methodology": {
                "baseline": "Comparisons begin only after a second healthy observation."
            },
        }
        weekly = {
            "schema_version": "1.0",
            "report": "weekly",
            "status": "awaiting_baseline",
            "scope": daily["scope"],
            "from_date": None,
            "to_date": None,
            "snapshot_days": 0,
            "latest_catalog_size": 0,
            "median_catalog_size": None,
            "median_valid_price_percentage": None,
            "price_increases": 0,
            "price_decreases": 0,
            "additions": 0,
            "returns": 0,
            "missing_products": 0,
            "daily_history": [],
            "comparison_history": [],
            "category_summary": [],
            "brand_summary": [],
            "snapshot_health_history": [],
            "methodology": daily["methodology"],
        }
        price_index = {
            "schema_version": "1.0",
            "report": "price_changes",
            "status": "awaiting_baseline",
            "from_date": None,
            "to_date": None,
            "snapshot_days": 0,
            "comparison_days": 0,
            "total_changes": 0,
            "price_increases": 0,
            "price_decreases": 0,
            "distinct_products": 0,
            "files": [],
            "available_snapshot_dates": [],
            "filters": {
                "departments": [],
                "brands": [],
                "price_range": {"min": None, "max": None},
                "percentage_range": {"min": None, "max": None},
            },
            "methodology": daily["methodology"],
        }
        price_shards = {}
    write_json(data_dir / "daily-summary.json", daily)
    write_json(data_dir / "weekly-summary.json", weekly)
    price_dir = data_dir / "price-changes"
    if price_dir.exists():
        shutil.rmtree(price_dir)
    write_json(price_dir / "index.json", price_index)
    for snapshot_date, contract in sorted(price_shards.items()):
        write_json(price_dir / f"{snapshot_date}.json", contract)
    history_dir = data_dir / "catalog-history"
    if history_dir.exists():
        shutil.rmtree(history_dir)
    if has_snapshots:
        catalog_index = build_catalog_history(snapshot_dir, history_dir)
    else:
        catalog_index = {
            "schema_version": "1.1",
            "from_date": None,
            "to_date": None,
            "calendar_days": 0,
            "total_items": 0,
            "filters": {
                "departments": [],
                "brands": [],
                "price_range": {"min": None, "max": None},
            },
            "items": [],
        }
        write_json(history_dir / "index.json", catalog_index)
    (assets / "site.css").write_text(STYLE.strip() + "\n", encoding="utf-8")
    (assets / "analytics.js").write_text(ANALYTICS_SCRIPT.strip() + "\n", encoding="utf-8")
    (assets / "catalog.js").write_text(CATALOG_SCRIPT.strip() + "\n", encoding="utf-8")
    (assets / "price-changes.js").write_text(PRICE_CHANGES_SCRIPT.strip() + "\n", encoding="utf-8")
    overview = '<section class="hero"><h1>Gala Freeport–Merrick catalog research</h1><p>Daily, transparent history of the anonymously visible public online catalog.</p><p>Pipeline: <span id="status" class="healthy">Loading…</span></p></section><section id="metrics" class="grid" aria-live="polite"></section><p><a id="raw" href="data/daily-summary.json">Machine-readable daily contract</a></p>'
    (docs_dir / "index.html").write_text(_page("Gala Freeport–Merrick Research", overview, _summary_script("data/daily-summary.json"), current="overview"), encoding="utf-8")
    daily_body = '<h1>Daily report</h1><p>Latest daily changes, with missing observations preserved as gaps.</p><p><a href="price-changes.html">Explore complete multi-day price changes</a></p><p>Status: <span id="status">Loading…</span></p><section id="metrics" class="grid"></section><h2>Assortment</h2><p id="assortment"></p><h2>Promotions</h2><p id="promotions"></p><h2>Anomalies</h2><p id="anomalies"></p><h2>Regular-price increases</h2><table><thead><tr><th>Product</th><th>Previous</th><th>Current</th><th>Change</th></tr></thead><tbody id="increases"></tbody></table><h2>Regular-price decreases</h2><table><thead><tr><th>Product</th><th>Previous</th><th>Current</th><th>Change</th></tr></thead><tbody id="decreases"></tbody></table><p><a href="data/daily-summary.json">Daily JSON contract</a></p>'
    (docs_dir / "daily-report.html").write_text(_page("Daily report", daily_body, _daily_script(), current="daily"), encoding="utf-8")
    weekly_body = '<h1>Weekly report</h1><p>A less noisy seven-snapshot research readout.</p><p>Status: <span id="status">Loading…</span></p><section id="metrics" class="grid"></section><p id="totals"></p><table><thead><tr><th>Date</th><th>Catalog</th><th>Valid prices</th><th>Promoted products</th></tr></thead><tbody id="history"></tbody></table><p><a href="data/weekly-summary.json">Weekly JSON contract</a></p>'
    (docs_dir / "weekly-report.html").write_text(_page("Weekly report", weekly_body, _weekly_script(), current="weekly"), encoding="utf-8")
    price_html = _page(
        "Price changes | Gala Freeport–Merrick Research",
        price_changes_body(price_index),
        '<script src="assets/price-changes.js?v=research-1.1" defer></script>',
        current="changes",
        body_class="changes-page",
    )
    (docs_dir / "price-changes.html").write_text(price_html, encoding="utf-8")
    catalog_html = _page(
        "Catalog | Gala Freeport–Merrick Research",
        catalog_body(catalog_index),
        '<script src="assets/catalog.js?v=research-1.1" defer></script>',
        current="catalog",
        body_class="catalog-page",
    )
    (docs_dir / "catalog.html").write_text(catalog_html, encoding="utf-8")
    legacy_redirect = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0; url=catalog.html"><link rel="canonical" href="catalog.html"><title>Catalog</title></head><body><p>This page has moved to <a href="catalog.html">Catalog</a>.</p></body></html>"""
    (docs_dir / "catalog-history.html").write_text(legacy_redirect, encoding="utf-8")
    methodology_md = docs_dir / "METHODOLOGY.md"
    if methodology_md.exists():
        paragraphs = methodology_md.read_text(encoding="utf-8").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = "<h1>Methodology</h1><pre style=\"white-space:pre-wrap;font:inherit\">" + paragraphs + "</pre>"
        (docs_dir / "METHODOLOGY.html").write_text(_page("Methodology", html, current="methodology"), encoding="utf-8")
    (docs_dir / ".nojekyll").write_text("", encoding="utf-8")
    return daily, weekly
