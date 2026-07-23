from __future__ import annotations

from typing import Any


def catalog_body(index: dict[str, Any]) -> str:
    """Return the static shell for the interactive catalog research view."""
    total = int(index.get("total_items", len(index.get("items", []))))
    total_label = f"{total:,}"
    return f"""
<section class="catalog-heading" aria-labelledby="catalog-title">
  <div>
    <p class="eyebrow">Freeport–Merrick public online catalog</p>
    <h1 id="catalog-title">Catalog</h1>
    <p class="lede">Search, filter, inspect, and export every item observed in the research archive.</p>
  </div>
  <dl class="catalog-scope" aria-label="Catalog scope">
    <div><dt>Total items</dt><dd id="total-items">{total_label}</dd></div>
    <div><dt>Latest observation</dt><dd>{index.get("to_date", "Not available")}</dd></div>
    <div><dt>History</dt><dd>{index.get("calendar_days", 0):,} calendar day</dd></div>
  </dl>
</section>

<section class="catalog-controls" aria-labelledby="filter-title">
  <div class="controls-heading">
    <div><h2 id="filter-title">Find items</h2><p>Filters work across the complete union catalog.</p></div>
    <button id="clear-filters" class="text-button" type="button">Clear filters</button>
  </div>
  <div class="filter-grid">
    <label class="search-field">Search
      <input id="catalog-search" type="search" placeholder="Name, brand, category, or source ID" autocomplete="off">
    </label>
    <label>Department
      <select id="department-filter"><option value="">All departments</option></select>
    </label>
    <label>Brand
      <select id="brand-filter"><option value="">All brands</option></select>
    </label>
    <label>Observed status
      <select id="status-filter">
        <option value="all">All items</option>
        <option value="current">Present in latest snapshot</option>
        <option value="missing">Missing from latest snapshot</option>
      </select>
    </label>
    <div class="price-filter" role="group" aria-labelledby="price-filter-label">
      <span id="price-filter-label" class="filter-legend">Latest known regular price</span>
      <div class="price-fields">
        <label>Minimum <input id="min-price" type="number" min="0" step="0.01" inputmode="decimal" placeholder="$0"></label>
        <label>Maximum <input id="max-price" type="number" min="0" step="0.01" inputmode="decimal" placeholder="Any"></label>
      </div>
    </div>
    <fieldset class="check-filters">
      <legend>Evidence</legend>
      <label><input id="promotion-filter" type="checkbox"> Promotion in latest snapshot</label>
      <label><input id="change-filter" type="checkbox"> Recorded price change</label>
    </fieldset>
  </div>
</section>

<div id="catalog-status" class="catalog-status" role="status" aria-live="polite">Loading the complete catalog index...</div>

<section class="catalog-workspace" aria-label="Catalog browser">
  <div class="results-pane">
    <div class="results-toolbar">
      <p id="result-count">Loading items...</p>
      <div class="toolbar-actions">
        <label>Sort
          <select id="sort-order">
            <option value="name">Name A to Z</option>
            <option value="brand">Brand A to Z</option>
            <option value="price-asc">Price low to high</option>
            <option value="price-desc">Price high to low</option>
            <option value="recent">Most recently seen</option>
          </select>
        </label>
        <label>Rows
          <select id="page-size">
            <option value="50">50</option>
            <option value="100" selected>100</option>
            <option value="250">250</option>
            <option value="all">All</option>
          </select>
        </label>
        <button id="export-csv" class="secondary-button" type="button">Export filtered CSV</button>
      </div>
    </div>
    <div class="table-scroll">
      <table class="catalog-table">
        <thead><tr><th>Item</th><th>Brand</th><th>Latest price</th><th>Evidence</th></tr></thead>
        <tbody id="catalog-results"></tbody>
      </table>
      <div id="empty-results" class="empty-state" hidden><strong>No items match these filters.</strong><span>Clear one or more filters to widen the result set.</span></div>
    </div>
    <nav class="pagination" aria-label="Catalog pages">
      <button id="previous-page" class="secondary-button" type="button">Previous</button>
      <span id="page-indicator">Page 1 of 1</span>
      <button id="next-page" class="secondary-button" type="button">Next</button>
    </nav>
  </div>

  <aside id="detail-panel" class="detail-panel" aria-label="Selected item details" aria-live="polite">
    <button id="close-detail" class="detail-close" type="button" aria-label="Close selected item">Close</button>
    <div id="item-detail" class="detail-content">
      <div class="detail-placeholder"><strong>Select an item</strong><span>Its source identifiers, categories, prices, promotions, and explicit history gaps will appear here.</span></div>
    </div>
  </aside>
</section>

<p class="catalog-contract"><a href="data/catalog-history/index.json">Download the catalog index JSON contract</a></p>
"""


CATALOG_SCRIPT = r"""
(() => {
  'use strict';
  const indexUrl = 'data/catalog-history/index.json';
  const shardBase = 'data/catalog-history/';
  const elements = Object.fromEntries([
    'catalog-search', 'department-filter', 'brand-filter', 'status-filter', 'min-price', 'max-price',
    'promotion-filter', 'change-filter', 'clear-filters', 'sort-order', 'page-size', 'export-csv',
    'catalog-results', 'empty-results', 'result-count', 'previous-page', 'next-page', 'page-indicator',
    'catalog-status', 'detail-panel', 'item-detail', 'close-detail'
  ].map(id => [id, document.getElementById(id)]));
  const state = { index: null, filtered: [], page: 1, selectedKey: null, shardCache: new Map() };
  const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
  const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
  const number = new Intl.NumberFormat('en-US');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const safeImageUrl = value => {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' ? url.href : '';
    } catch (_) { return ''; }
  };
  const display = value => value === null || value === undefined || value === '' ? 'Not available' : String(value);
  const price = value => typeof value === 'number' ? money.format(value) : 'Price missing';
  const latestKnown = item => item.latest_regular_price;

  function option(value, label) {
    const element = document.createElement('option');
    element.value = value;
    element.textContent = label;
    return element;
  }

  function populateFilters() {
    for (const department of state.index.filters.departments) {
      elements['department-filter'].append(option(department, department));
    }
    for (const brand of state.index.filters.brands) {
      elements['brand-filter'].append(option(brand, brand));
    }
    const range = state.index.filters.price_range;
    if (range.min !== null) elements['min-price'].placeholder = money.format(range.min);
    if (range.max !== null) elements['max-price'].placeholder = money.format(range.max);
  }

  function searchText(item) {
    return [item.name, item.brand, item.product_key, item.retailer_product_id, item.catalog_product_id,
      item.branch_product_id, ...(item.category_paths || []), ...(item.departments || [])]
      .filter(Boolean).join(' ').toLocaleLowerCase();
  }

  function applyFilters() {
    const query = elements['catalog-search'].value.trim().toLocaleLowerCase();
    const department = elements['department-filter'].value;
    const brand = elements['brand-filter'].value;
    const status = elements['status-filter'].value;
    const minimum = elements['min-price'].value === '' ? null : Number(elements['min-price'].value);
    const maximum = elements['max-price'].value === '' ? null : Number(elements['max-price'].value);
    const promotionsOnly = elements['promotion-filter'].checked;
    const changesOnly = elements['change-filter'].checked;
    state.filtered = state.index.items.filter(item => {
      const itemPrice = latestKnown(item);
      return (!query || searchText(item).includes(query))
        && (!department || item.departments.includes(department))
        && (!brand || item.brand === brand)
        && (status === 'all' || (status === 'current' ? item.is_current : !item.is_current))
        && (minimum === null || (itemPrice !== null && itemPrice >= minimum))
        && (maximum === null || (itemPrice !== null && itemPrice <= maximum))
        && (!promotionsOnly || item.latest_promotion_count > 0)
        && (!changesOnly || item.has_price_change);
    });
    if (state.selectedKey && !state.filtered.some(item => item.product_key === state.selectedKey)) {
      state.selectedKey = null;
      history.replaceState(null, '', location.pathname + location.search);
      elements['item-detail'].innerHTML = '<div class="detail-placeholder"><strong>The selected item is outside this filtered view.</strong><span>Choose a visible result to inspect its evidence.</span></div>';
      elements['detail-panel'].classList.remove('is-open');
    }
    sortItems();
    state.page = 1;
    renderResults();
  }

  function sortItems() {
    const value = elements['sort-order'].value;
    const compareText = field => (a, b) => collator.compare(a[field] || '', b[field] || '') || collator.compare(a.name || '', b.name || '');
    const comparePrice = direction => (a, b) => {
      const first = latestKnown(a), second = latestKnown(b);
      if (first === null && second === null) return collator.compare(a.name || '', b.name || '');
      if (first === null) return 1;
      if (second === null) return -1;
      return direction * (first - second) || collator.compare(a.name || '', b.name || '');
    };
    const comparators = {
      name: compareText('name'), brand: compareText('brand'),
      'price-asc': comparePrice(1), 'price-desc': comparePrice(-1),
      recent: (a, b) => collator.compare(b.last_seen || '', a.last_seen || '') || collator.compare(a.name || '', b.name || '')
    };
    state.filtered.sort(comparators[value]);
  }

  function pageSize() {
    return elements['page-size'].value === 'all' ? Math.max(state.filtered.length, 1) : Number(elements['page-size'].value);
  }

  function evidence(item) {
    const labels = [];
    if (item.latest_promotion_count) labels.push(`<span class="tag promoted">${number.format(item.latest_promotion_count)} promo</span>`);
    if (item.has_price_change) labels.push('<span class="tag">Price changed</span>');
    if (!item.is_current) labels.push('<span class="tag missing">Latest gap</span>');
    return labels.join('') || '<span class="quiet">Observed</span>';
  }

  function renderResults() {
    const size = pageSize();
    const pageCount = Math.max(1, Math.ceil(state.filtered.length / size));
    state.page = Math.min(state.page, pageCount);
    const start = (state.page - 1) * size;
    const rows = state.filtered.slice(start, start + size);
    const first = state.filtered.length ? start + 1 : 0;
    const last = Math.min(start + rows.length, state.filtered.length);
    elements['result-count'].textContent = `Showing ${number.format(first)} to ${number.format(last)} of ${number.format(state.filtered.length)} filtered, ${number.format(state.index.total_items)} total`;
    elements['catalog-results'].innerHTML = rows.map(item => `
      <tr class="${item.product_key === state.selectedKey ? 'selected' : ''}">
        <td><button class="item-button" type="button" data-key="${esc(item.product_key)}" data-shard="${esc(item.shard)}"><strong>${esc(item.name || 'Unnamed item')}</strong><span>${esc((item.departments || []).join(', ') || 'Uncategorized')}</span></button></td>
        <td>${esc(item.brand || 'Unbranded')}</td>
        <td><span class="price-value">${esc(price(latestKnown(item)))}</span><span class="date-note">Last seen ${esc(item.last_seen)}</span></td>
        <td><div class="tags">${evidence(item)}</div></td>
      </tr>`).join('');
    elements['empty-results'].hidden = state.filtered.length !== 0;
    elements['previous-page'].disabled = state.page <= 1;
    elements['next-page'].disabled = state.page >= pageCount;
    elements['page-indicator'].textContent = `Page ${number.format(state.page)} of ${number.format(pageCount)}`;
    elements['catalog-status'].textContent = `${number.format(state.filtered.length)} items match the current view.`;
  }

  async function loadDetail(key, shard) {
    state.selectedKey = key;
    renderResults();
    elements['detail-panel'].classList.add('is-open');
    elements['item-detail'].innerHTML = '<div class="detail-placeholder"><strong>Loading item evidence...</strong></div>';
    try {
      if (!state.shardCache.has(shard)) {
        const response = await fetch(`${shardBase}${encodeURIComponent(shard)}.json`);
        if (!response.ok) throw new Error(`History request returned ${response.status}`);
        state.shardCache.set(shard, await response.json());
      }
      const item = state.shardCache.get(shard).items.find(candidate => candidate.product_key === key);
      if (!item) throw new Error('Item is absent from its history shard');
      history.replaceState(null, '', `#${encodeURIComponent(key)}`);
      renderDetail(item);
    } catch (error) {
      elements['item-detail'].innerHTML = `<div class="error-state"><strong>Item history could not be loaded.</strong><span>${esc(error.message)}</span></div>`;
    }
  }

  function renderDetail(item) {
    const image = safeImageUrl(item.image_url);
    const latest = item.observations.find(observation => observation.date === state.index.to_date)?.catalog;
    const categories = (item.category_paths || []).map(path => `<li>${esc(path)}</li>`).join('') || '<li>Not available</li>';
    const historyRows = [...item.observations].reverse().map(observation => {
      const catalog = observation.catalog;
      const offers = observation.promotions || [];
      const promotionText = offers.length
        ? offers.map(offer => `<span><strong>${esc(offer.description || offer.promotion_id)}</strong>${offer.derived_effective_unit_price !== null ? ` <small>Derived effective unit price: ${esc(price(offer.derived_effective_unit_price))}; ${esc(offer.derivation_basis || '')}</small>` : ''}</span>`).join('')
        : '<span class="quiet">None recorded</span>';
      return `<tr class="${catalog ? '' : 'history-gap'}"><td>${esc(observation.date)}</td><td>${catalog ? esc(price(catalog.regular_price)) : '<span class="gap-label">Gap</span>'}</td><td>${promotionText}</td></tr>`;
    }).join('');
    elements['item-detail'].innerHTML = `
      <div class="detail-header">
        ${image ? `<img src="${esc(image)}" alt="" loading="lazy">` : '<div class="image-placeholder" aria-hidden="true">No image</div>'}
        <div><p class="eyebrow">${esc(item.brand || 'Unbranded')}</p><h2>${esc(item.name || 'Unnamed item')}</h2><p class="detail-price">${esc(price(item.latest_regular_price))}</p><p class="detail-state">${item.is_current ? `Present in latest snapshot (${esc(item.last_seen)})` : `Latest snapshot is a gap; last seen ${esc(item.last_seen)}`}</p></div>
      </div>
      <div class="detail-actions"><button id="copy-item-link" class="secondary-button" type="button">Copy item link</button><a href="${esc(item.source_url || 'https://galasupermarkets.com/Freeport-Merrick')}" rel="noreferrer">Source endpoint context</a></div>
      <dl class="evidence-list">
        <div><dt>Stable product key</dt><dd><code>${esc(item.product_key)}</code></dd></div>
        <div><dt>Retailer product ID</dt><dd>${esc(display(item.retailer_product_id))}</dd></div>
        <div><dt>Catalog product ID</dt><dd>${esc(display(item.catalog_product_id))}</dd></div>
        <div><dt>Branch product ID</dt><dd>${esc(display(item.branch_product_id))}</dd></div>
        <div><dt>First seen</dt><dd>${esc(item.first_seen)}</dd></div>
        <div><dt>Observed days</dt><dd>${number.format(item.observed_days)} of ${number.format(state.index.calendar_days)}</dd></div>
        <div><dt>Package / unit</dt><dd>${esc([item.weight, item.unit_of_measure, item.unit_resolution].filter(value => value !== null && value !== '').join(' / ') || 'Not available')}</dd></div>
        <div><dt>Variable weight</dt><dd>${item.is_weighable === null ? 'Not available' : item.is_weighable ? 'Yes' : 'No'}</dd></div>
        <div><dt>Source state</dt><dd>${latest ? `${latest.is_out_of_stock === true ? 'Out of stock' : 'Available to the public filter'}` : 'Not observed in latest snapshot'}</dd></div>
      </dl>
      <section class="category-evidence"><h3>Category memberships</h3><ul>${categories}</ul></section>
      <section class="history-evidence"><div><h3>Daily evidence</h3><p>Missing observations remain explicit gaps. A gap is not treated as a deletion or a zero price.</p></div>
        <div class="history-scroll"><table><thead><tr><th>Date</th><th>Regular price</th><th>Promotions</th></tr></thead><tbody>${historyRows}</tbody></table></div>
      </section>`;
    const productImage = elements['item-detail'].querySelector('.detail-header img');
    if (productImage) {
      productImage.addEventListener('error', () => {
        const fallback = document.createElement('div');
        fallback.className = 'image-placeholder';
        fallback.setAttribute('aria-hidden', 'true');
        fallback.textContent = 'Image unavailable';
        productImage.replaceWith(fallback);
      }, { once: true });
    }
    document.getElementById('copy-item-link').addEventListener('click', async event => {
      try {
        await navigator.clipboard.writeText(location.href);
        event.currentTarget.textContent = 'Link copied';
      } catch (_) {
        event.currentTarget.textContent = 'Copy unavailable';
      }
    });
  }

  function selectFromHash() {
    const key = decodeURIComponent(location.hash.slice(1));
    const item = state.index.items.find(candidate => candidate.product_key === key);
    if (item) loadDetail(item.product_key, item.shard);
  }

  function clearFilters() {
    elements['catalog-search'].value = '';
    elements['department-filter'].value = '';
    elements['brand-filter'].value = '';
    elements['status-filter'].value = 'all';
    elements['min-price'].value = '';
    elements['max-price'].value = '';
    elements['promotion-filter'].checked = false;
    elements['change-filter'].checked = false;
    applyFilters();
  }

  function downloadFilteredCsv() {
    const fields = ['product_key', 'name', 'brand', 'latest_regular_price', 'is_current', 'first_seen', 'last_seen', 'observed_days', 'latest_promotion_count', 'departments', 'category_paths', 'retailer_product_id', 'catalog_product_id', 'branch_product_id'];
    const csvCell = value => `"${String(Array.isArray(value) ? value.join(' | ') : value ?? '').replaceAll('"', '""')}"`;
    const rows = [fields.join(','), ...state.filtered.map(item => fields.map(field => csvCell(item[field])).join(','))];
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `gala-freeport-catalog-${state.index.to_date}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function bindEvents() {
    ['catalog-search', 'department-filter', 'brand-filter', 'status-filter', 'min-price', 'max-price', 'promotion-filter', 'change-filter']
      .forEach(id => elements[id].addEventListener(id === 'catalog-search' ? 'input' : 'change', applyFilters));
    elements['sort-order'].addEventListener('change', () => { sortItems(); state.page = 1; renderResults(); });
    elements['page-size'].addEventListener('change', () => { state.page = 1; renderResults(); });
    elements['clear-filters'].addEventListener('click', clearFilters);
    elements['export-csv'].addEventListener('click', downloadFilteredCsv);
    elements['previous-page'].addEventListener('click', () => { state.page -= 1; renderResults(); document.querySelector('.results-pane').scrollIntoView(); });
    elements['next-page'].addEventListener('click', () => { state.page += 1; renderResults(); document.querySelector('.results-pane').scrollIntoView(); });
    elements['catalog-results'].addEventListener('click', event => {
      const button = event.target.closest('.item-button');
      if (button) loadDetail(button.dataset.key, button.dataset.shard);
    });
    elements['close-detail'].addEventListener('click', () => elements['detail-panel'].classList.remove('is-open'));
    window.addEventListener('hashchange', selectFromHash);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') elements['detail-panel'].classList.remove('is-open');
    });
  }

  async function init() {
    bindEvents();
    try {
      const response = await fetch(indexUrl);
      if (!response.ok) throw new Error(`Catalog index returned ${response.status}`);
      state.index = await response.json();
      populateFilters();
      applyFilters();
      selectFromHash();
      if (!state.selectedKey && state.filtered.length && window.matchMedia('(min-width: 761px)').matches) {
        const first = state.filtered[0];
        loadDetail(first.product_key, first.shard);
      }
    } catch (error) {
      elements['catalog-status'].textContent = `Catalog data unavailable: ${error.message}`;
      elements['catalog-status'].classList.add('error-state');
    }
  }

  init();
})();
"""
