from __future__ import annotations

from typing import Any


def price_changes_body(index: dict[str, Any]) -> str:
    """Return the static shell for the multi-day price-change explorer."""
    total = int(index.get("total_changes", 0))
    distinct = int(index.get("distinct_products", 0))
    comparisons = int(index.get("comparison_days", 0))
    return f"""
<section class="change-heading" aria-labelledby="change-title">
  <div>
    <p class="eyebrow">Longitudinal regular-price evidence</p>
    <h1 id="change-title">Price changes</h1>
    <p class="lede">Compare adjacent healthy snapshots, investigate every recorded movement, and export the evidence behind a selected date range.</p>
  </div>
  <dl class="change-scope" aria-label="Price change archive scope">
    <div><dt>Recorded movements</dt><dd id="archive-change-count">{total:,}</dd></div>
    <div><dt>Distinct items</dt><dd>{distinct:,}</dd></div>
    <div><dt>Comparison intervals</dt><dd>{comparisons:,}</dd></div>
    <div><dt>Archive span</dt><dd>{index.get("from_date", "Not available")} to {index.get("to_date", "Not available")}</dd></div>
  </dl>
</section>

<section id="baseline-note" class="research-note" hidden>
  <strong>The baseline is stored; no price comparison exists yet.</strong>
  <span>Movements appear after a second distinct healthy snapshot date. Same-day reruns strengthen the baseline but do not create a new interval.</span>
</section>

<section class="range-controls" aria-labelledby="range-title">
  <div class="controls-heading">
    <div><h2 id="range-title">Comparison range</h2><p>Daily files are loaded only for the selected interval.</p></div>
    <div class="quick-ranges" aria-label="Quick date ranges">
      <button type="button" data-range="latest">Latest</button>
      <button type="button" data-range="7">7 days</button>
      <button type="button" data-range="28">28 days</button>
      <button type="button" data-range="all">All history</button>
    </div>
  </div>
  <div class="date-fields">
    <label>From <input id="change-from-date" type="date"></label>
    <label>Through <input id="change-to-date" type="date"></label>
    <button id="load-change-range" class="primary-button" type="button">Load range</button>
    <p id="range-description">Preparing available comparison dates...</p>
  </div>
</section>

<section class="catalog-controls change-filters" aria-labelledby="change-filter-title">
  <div class="controls-heading">
    <div><h2 id="change-filter-title">Filter movements</h2><p>Every filter applies to all records loaded for the date range.</p></div>
    <button id="clear-change-filters" class="text-button" type="button">Clear filters</button>
  </div>
  <div class="change-filter-grid">
    <label class="change-search">Search
      <input id="change-search" type="search" placeholder="Item, brand, category, or source ID" autocomplete="off">
    </label>
    <label>Direction
      <select id="direction-filter">
        <option value="all">Increases and decreases</option>
        <option value="increase">Increases only</option>
        <option value="decrease">Decreases only</option>
      </select>
    </label>
    <label>Department
      <select id="change-department-filter"><option value="">All departments</option></select>
    </label>
    <label>Brand
      <select id="change-brand-filter"><option value="">All brands</option></select>
    </label>
    <label>Minimum absolute change
      <div class="suffix-input"><input id="minimum-change-filter" type="number" min="0" step="0.1" inputmode="decimal" placeholder="0"><span>%</span></div>
    </label>
    <fieldset class="check-filters change-checks">
      <legend>Evidence</legend>
      <label><input id="anomaly-filter" type="checkbox"> Conservative anomalies only</label>
    </fieldset>
  </div>
</section>

<div id="change-status" class="catalog-status" role="status" aria-live="polite">Loading price-change index...</div>

<section class="change-workspace" aria-label="Price change explorer">
  <div class="results-pane change-results-pane">
    <div class="results-toolbar change-toolbar">
      <div><p id="change-result-count">Loading movements...</p><span id="loaded-intervals" class="toolbar-note"></span></div>
      <div class="toolbar-actions">
        <label>Sort
          <select id="change-sort-order">
            <option value="recent">Most recent</option>
            <option value="percent">Largest percentage</option>
            <option value="amount">Largest dollar movement</option>
            <option value="name">Item name</option>
          </select>
        </label>
        <label>Rows
          <select id="change-page-size">
            <option value="50">50</option>
            <option value="100" selected>100</option>
            <option value="250">250</option>
            <option value="all">All</option>
          </select>
        </label>
        <div class="export-actions">
          <button id="export-changes-csv" class="secondary-button" type="button">Export CSV</button>
          <button id="export-changes-json" class="secondary-button" type="button">Export JSON</button>
        </div>
      </div>
    </div>
    <div class="table-scroll">
      <table class="change-table">
        <thead><tr><th>Interval</th><th>Item</th><th>Before / after</th><th>Movement</th><th>Context</th></tr></thead>
        <tbody id="change-results"></tbody>
      </table>
      <div id="empty-changes" class="empty-state" hidden>
        <strong>No recorded movements match this view.</strong>
        <span id="empty-change-guidance">Widen the date range or clear one or more filters.</span>
      </div>
    </div>
    <nav class="pagination" aria-label="Price change pages">
      <button id="previous-change-page" class="secondary-button" type="button">Previous</button>
      <span id="change-page-indicator">Page 1 of 1</span>
      <button id="next-change-page" class="secondary-button" type="button">Next</button>
    </nav>
  </div>

  <aside id="change-detail-panel" class="detail-panel change-detail-panel" aria-label="Selected price change details" aria-live="polite">
    <button id="close-change-detail" class="detail-close" type="button" aria-label="Close selected price change">Close</button>
    <div id="change-detail" class="detail-content">
      <div class="detail-placeholder"><strong>Select a movement</strong><span>The comparison interval, source identity, category context, and loaded item timeline will appear here.</span></div>
    </div>
  </aside>
</section>

<p class="catalog-contract"><a href="data/price-changes/index.json">Download the price-change index JSON contract</a></p>
"""


PRICE_CHANGES_SCRIPT = r"""
(() => {
  'use strict';
  const indexUrl = 'data/price-changes/index.json';
  const dataBase = 'data/price-changes/';
  const ids = [
    'baseline-note', 'change-from-date', 'change-to-date', 'load-change-range', 'range-description',
    'change-search', 'direction-filter', 'change-department-filter', 'change-brand-filter',
    'minimum-change-filter', 'anomaly-filter', 'clear-change-filters', 'change-sort-order',
    'change-page-size', 'export-changes-csv', 'export-changes-json', 'change-results', 'empty-changes',
    'empty-change-guidance', 'change-result-count', 'loaded-intervals', 'previous-change-page',
    'next-change-page', 'change-page-indicator', 'change-status', 'change-detail-panel',
    'change-detail', 'close-change-detail'
  ];
  const elements = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
  const state = { index: null, loaded: [], filtered: [], page: 1, selectedEvent: null, loadToken: 0 };
  const number = new Intl.NumberFormat('en-US');
  const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
  const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const price = value => typeof value === 'number' ? money.format(value) : 'Price missing';
  const signedMoney = value => `${value > 0 ? '+' : ''}${money.format(value)}`;
  const signedPercent = value => `${value > 0 ? '+' : ''}${number.format(value)}%`;

  function option(value, label) {
    const element = document.createElement('option');
    element.value = value;
    element.textContent = label;
    return element;
  }

  function addDays(value, amount) {
    const date = new Date(`${value}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + amount);
    return date.toISOString().slice(0, 10);
  }

  function clampDate(value) {
    return value < state.index.from_date ? state.index.from_date : value > state.index.to_date ? state.index.to_date : value;
  }

  function setRange(kind) {
    const files = state.index.files;
    const end = state.index.to_date;
    if (kind === 'latest' && files.length) {
      elements['change-from-date'].value = files[files.length - 1].to_date;
      elements['change-to-date'].value = files[files.length - 1].to_date;
    } else if (kind === 'all') {
      elements['change-from-date'].value = state.index.from_date;
      elements['change-to-date'].value = end;
    } else {
      elements['change-from-date'].value = clampDate(addDays(end, -(Number(kind) - 1)));
      elements['change-to-date'].value = end;
    }
    loadRange();
  }

  function filesForRange() {
    const from = elements['change-from-date'].value;
    const to = elements['change-to-date'].value;
    return state.index.files.filter(file => file.to_date >= from && file.to_date <= to);
  }

  async function loadRange() {
    if (!state.index) return;
    const from = elements['change-from-date'].value;
    const to = elements['change-to-date'].value;
    if (!from || !to || from > to) {
      elements['range-description'].textContent = 'Choose a valid range with the start date on or before the end date.';
      return;
    }
    const token = ++state.loadToken;
    const files = filesForRange();
    elements['load-change-range'].disabled = true;
    elements['load-change-range'].textContent = 'Loading...';
    elements['range-description'].textContent = files.length
      ? `Loading ${number.format(files.length)} comparison interval${files.length === 1 ? '' : 's'}...`
      : 'No comparison interval falls inside this range.';
    try {
      const contracts = await Promise.all(files.map(async file => {
        const response = await fetch(`${dataBase}${encodeURIComponent(file.path)}`);
        if (!response.ok) throw new Error(`${file.path} returned ${response.status}`);
        return response.json();
      }));
      if (token !== state.loadToken) return;
      state.loaded = contracts.flatMap(contract => contract.changes || []);
      state.selectedEvent = null;
      elements['change-detail'].innerHTML = '<div class="detail-placeholder"><strong>Select a movement</strong><span>The comparison interval, source identity, category context, and loaded item timeline will appear here.</span></div>';
      elements['change-detail-panel'].classList.remove('is-open');
      elements['range-description'].textContent = files.length
        ? `${number.format(files.length)} comparison interval${files.length === 1 ? '' : 's'} loaded, ${from} through ${to}.`
        : state.index.status === 'baseline_established'
          ? 'Awaiting a second distinct healthy snapshot date.'
          : `No comparison interval ends between ${from} and ${to}.`;
      elements['loaded-intervals'].textContent = `${number.format(files.length)} loaded interval${files.length === 1 ? '' : 's'}`;
      applyFilters();
      selectFromHash();
      if (!state.selectedEvent && state.filtered.length && window.matchMedia('(min-width: 761px)').matches) {
        selectChange(state.filtered[0].event_key);
      }
    } catch (error) {
      elements['change-status'].textContent = `Price-change data unavailable: ${error.message}`;
      elements['range-description'].textContent = 'The selected range could not be loaded.';
    } finally {
      if (token === state.loadToken) {
        elements['load-change-range'].disabled = false;
        elements['load-change-range'].textContent = 'Load range';
      }
    }
  }

  function searchText(row) {
    return [row.name, row.brand, row.product_key, row.retailer_product_id, row.catalog_product_id,
      row.branch_product_id, ...(row.category_paths || []), ...(row.departments || [])]
      .filter(Boolean).join(' ').toLocaleLowerCase();
  }

  function applyFilters() {
    const query = elements['change-search'].value.trim().toLocaleLowerCase();
    const direction = elements['direction-filter'].value;
    const department = elements['change-department-filter'].value;
    const brand = elements['change-brand-filter'].value;
    const minimum = elements['minimum-change-filter'].value === '' ? null : Number(elements['minimum-change-filter'].value);
    const anomaliesOnly = elements['anomaly-filter'].checked;
    state.filtered = state.loaded.filter(row => (!query || searchText(row).includes(query))
      && (direction === 'all' || row.direction === direction)
      && (!department || row.departments.includes(department))
      && (!brand || row.brand === brand)
      && (minimum === null || row.absolute_change_percentage >= minimum)
      && (!anomaliesOnly || row.is_anomaly));
    if (state.selectedEvent && !state.filtered.some(row => row.event_key === state.selectedEvent)) {
      state.selectedEvent = null;
      history.replaceState(null, '', location.pathname + location.search);
      elements['change-detail'].innerHTML = '<div class="detail-placeholder"><strong>The selected movement is outside this filtered view.</strong><span>Choose a visible row to inspect its evidence.</span></div>';
      elements['change-detail-panel'].classList.remove('is-open');
    }
    sortRows();
    state.page = 1;
    renderRows();
  }

  function sortRows() {
    const comparators = {
      recent: (a, b) => collator.compare(b.to_date, a.to_date) || collator.compare(a.name || '', b.name || ''),
      percent: (a, b) => b.absolute_change_percentage - a.absolute_change_percentage || collator.compare(b.to_date, a.to_date),
      amount: (a, b) => b.absolute_change - a.absolute_change || collator.compare(b.to_date, a.to_date),
      name: (a, b) => collator.compare(a.name || '', b.name || '') || collator.compare(b.to_date, a.to_date),
    };
    state.filtered.sort(comparators[elements['change-sort-order'].value]);
  }

  function pageSize() {
    return elements['change-page-size'].value === 'all' ? Math.max(state.filtered.length, 1) : Number(elements['change-page-size'].value);
  }

  function renderRows() {
    const size = pageSize();
    const pageCount = Math.max(1, Math.ceil(state.filtered.length / size));
    state.page = Math.min(state.page, pageCount);
    const start = (state.page - 1) * size;
    const rows = state.filtered.slice(start, start + size);
    const first = state.filtered.length ? start + 1 : 0;
    const last = Math.min(start + rows.length, state.filtered.length);
    elements['change-result-count'].textContent = `Showing ${number.format(first)} to ${number.format(last)} of ${number.format(state.filtered.length)} filtered, ${number.format(state.loaded.length)} loaded`;
    elements['change-results'].innerHTML = rows.map(row => `
      <tr class="${row.event_key === state.selectedEvent ? 'selected' : ''}">
        <td><span class="interval-date">${esc(row.to_date)}</span><span class="date-note">from ${esc(row.from_date)}</span></td>
        <td><button class="change-button" type="button" data-event="${esc(row.event_key)}"><strong>${esc(row.name || 'Unnamed item')}</strong><span>${esc(row.brand || 'Unbranded')}</span></button></td>
        <td><span class="price-comparison"><span>${esc(price(row.previous_regular_price))}</span><span aria-hidden="true">→</span><strong>${esc(price(row.current_regular_price))}</strong></span></td>
        <td><span class="movement ${esc(row.direction)}">${esc(signedPercent(row.change_percentage))}</span><span class="date-note">${esc(signedMoney(row.change))}</span></td>
        <td><div class="tags">${row.is_anomaly ? '<span class="tag missing">Anomaly</span>' : ''}<span class="tag">${esc((row.departments || []).join(', ') || 'Uncategorized')}</span></div></td>
      </tr>`).join('');
    elements['empty-changes'].hidden = state.filtered.length !== 0;
    elements['empty-change-guidance'].textContent = state.index.status === 'baseline_established'
      ? 'The first healthy snapshot is stored. A second distinct date will establish the first comparison.'
      : 'Widen the date range or clear one or more filters.';
    elements['previous-change-page'].disabled = state.page <= 1;
    elements['next-change-page'].disabled = state.page >= pageCount;
    elements['change-page-indicator'].textContent = `Page ${number.format(state.page)} of ${number.format(pageCount)}`;
    elements['export-changes-csv'].disabled = state.filtered.length === 0;
    elements['export-changes-json'].disabled = state.filtered.length === 0;
    elements['change-status'].textContent = `${number.format(state.filtered.length)} price movements match the current view.`;
  }

  function selectChange(eventKey) {
    const selected = state.loaded.find(row => row.event_key === eventKey);
    if (!selected) return;
    state.selectedEvent = eventKey;
    renderRows();
    elements['change-detail-panel'].classList.add('is-open');
    history.replaceState(null, '', `#${encodeURIComponent(eventKey)}`);
    const timeline = state.loaded
      .filter(row => row.product_key === selected.product_key)
      .sort((a, b) => collator.compare(b.to_date, a.to_date));
    const categoryList = (selected.category_paths || []).map(path => `<li>${esc(path)}</li>`).join('') || '<li>Not available</li>';
    const timelineRows = timeline.map(row => `<tr><td>${esc(row.to_date)}</td><td>${esc(price(row.previous_regular_price))} → ${esc(price(row.current_regular_price))}</td><td class="${esc(row.direction)}-text">${esc(signedPercent(row.change_percentage))}</td></tr>`).join('');
    elements['change-detail'].innerHTML = `
      <div class="change-detail-heading"><p class="eyebrow">${esc(selected.brand || 'Unbranded')}</p><h2>${esc(selected.name || 'Unnamed item')}</h2><span class="movement ${esc(selected.direction)}">${esc(selected.direction)}</span></div>
      <div class="change-equation"><span>${esc(price(selected.previous_regular_price))}<small>${esc(selected.from_date)}</small></span><span aria-hidden="true">→</span><strong>${esc(price(selected.current_regular_price))}<small>${esc(selected.to_date)}</small></strong></div>
      <p class="change-summary">${esc(signedMoney(selected.change))} (${esc(signedPercent(selected.change_percentage))}) across ${number.format(selected.calendar_gap_days)} calendar day${selected.calendar_gap_days === 1 ? '' : 's'}.</p>
      <div class="detail-actions"><button id="copy-change-link" class="secondary-button" type="button">Copy change link</button><a href="catalog.html#${encodeURIComponent(selected.product_key)}">Open full item history</a></div>
      <dl class="evidence-list">
        <div><dt>Stable product key</dt><dd><code>${esc(selected.product_key)}</code></dd></div>
        <div><dt>Retailer product ID</dt><dd>${esc(selected.retailer_product_id ?? 'Not available')}</dd></div>
        <div><dt>Catalog product ID</dt><dd>${esc(selected.catalog_product_id ?? 'Not available')}</dd></div>
        <div><dt>Branch product ID</dt><dd>${esc(selected.branch_product_id ?? 'Not available')}</dd></div>
        <div><dt>Direction</dt><dd>${esc(selected.direction)}</dd></div>
        <div><dt>Conservative anomaly</dt><dd>${selected.is_anomaly ? 'Yes' : 'No'}</dd></div>
      </dl>
      <section class="category-evidence"><h3>Category context</h3><ul>${categoryList}</ul></section>
      <section class="history-evidence"><div><h3>Loaded movement timeline</h3><p>${number.format(timeline.length)} event${timeline.length === 1 ? '' : 's'} for this item inside the selected date range.</p></div>
        <div class="history-scroll"><table><thead><tr><th>Date</th><th>Regular price</th><th>Movement</th></tr></thead><tbody>${timelineRows}</tbody></table></div>
      </section>`;
    document.getElementById('copy-change-link').addEventListener('click', async event => {
      try {
        await navigator.clipboard.writeText(location.href);
        event.currentTarget.textContent = 'Link copied';
      } catch (_) {
        event.currentTarget.textContent = 'Copy unavailable';
      }
    });
  }

  function selectFromHash() {
    const eventKey = decodeURIComponent(location.hash.slice(1));
    if (eventKey && state.loaded.some(row => row.event_key === eventKey)) selectChange(eventKey);
  }

  function closeChangeDetail() {
    state.selectedEvent = null;
    elements['change-detail-panel'].classList.remove('is-open');
    elements['change-detail'].innerHTML = '<div class="detail-placeholder"><strong>Select a movement</strong><span>The comparison interval, source identity, category context, and loaded item timeline will appear here.</span></div>';
    history.replaceState(null, '', `${location.pathname}${location.search}`);
    renderRows();
  }

  function clearFilters() {
    elements['change-search'].value = '';
    elements['direction-filter'].value = 'all';
    elements['change-department-filter'].value = '';
    elements['change-brand-filter'].value = '';
    elements['minimum-change-filter'].value = '';
    elements['anomaly-filter'].checked = false;
    applyFilters();
  }

  function csvCell(value) {
    return `"${String(Array.isArray(value) ? value.join(' | ') : value ?? '').replaceAll('"', '""')}"`;
  }

  function triggerDownload(contents, mimeType, extension) {
    const blob = new Blob([contents], {type: mimeType});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `gala-freeport-price-changes-${elements['change-from-date'].value}-to-${elements['change-to-date'].value}.${extension}`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function downloadFilteredCsv() {
    const fields = ['event_key', 'from_date', 'to_date', 'product_key', 'name', 'brand', 'direction', 'previous_regular_price', 'current_regular_price', 'change', 'change_percentage', 'is_anomaly', 'departments', 'category_paths', 'retailer_product_id', 'catalog_product_id', 'branch_product_id'];
    const rows = [fields.join(','), ...state.filtered.map(row => fields.map(field => csvCell(row[field])).join(','))];
    triggerDownload(rows.join('\n'), 'text/csv;charset=utf-8', 'csv');
  }

  function downloadFilteredJson() {
    const contract = {
      schema_version: '1.0', report: 'filtered_price_changes',
      from_date: elements['change-from-date'].value, to_date: elements['change-to-date'].value,
      exported_records: state.filtered.length, changes: state.filtered,
    };
    triggerDownload(JSON.stringify(contract, null, 2), 'application/json;charset=utf-8', 'json');
  }

  function bindEvents() {
    document.querySelectorAll('[data-range]').forEach(button => button.addEventListener('click', () => setRange(button.dataset.range)));
    elements['load-change-range'].addEventListener('click', loadRange);
    ['change-search', 'direction-filter', 'change-department-filter', 'change-brand-filter', 'minimum-change-filter', 'anomaly-filter']
      .forEach(id => elements[id].addEventListener(id === 'change-search' ? 'input' : 'change', applyFilters));
    elements['clear-change-filters'].addEventListener('click', clearFilters);
    elements['change-sort-order'].addEventListener('change', () => { sortRows(); state.page = 1; renderRows(); });
    elements['change-page-size'].addEventListener('change', () => { state.page = 1; renderRows(); });
    elements['previous-change-page'].addEventListener('click', () => { state.page -= 1; renderRows(); document.querySelector('.change-results-pane').scrollIntoView(); });
    elements['next-change-page'].addEventListener('click', () => { state.page += 1; renderRows(); document.querySelector('.change-results-pane').scrollIntoView(); });
    elements['change-results'].addEventListener('click', event => {
      const button = event.target.closest('.change-button');
      if (button) selectChange(button.dataset.event);
    });
    elements['close-change-detail'].addEventListener('click', closeChangeDetail);
    elements['export-changes-csv'].addEventListener('click', downloadFilteredCsv);
    elements['export-changes-json'].addEventListener('click', downloadFilteredJson);
    window.addEventListener('hashchange', selectFromHash);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeChangeDetail();
    });
  }

  async function init() {
    bindEvents();
    try {
      const response = await fetch(indexUrl);
      if (!response.ok) throw new Error(`Price-change index returned ${response.status}`);
      state.index = await response.json();
      elements['baseline-note'].hidden = state.index.status !== 'baseline_established';
      for (const department of state.index.filters.departments) elements['change-department-filter'].append(option(department, department));
      for (const brand of state.index.filters.brands) elements['change-brand-filter'].append(option(brand, brand));
      for (const id of ['change-from-date', 'change-to-date']) {
        elements[id].min = state.index.from_date;
        elements[id].max = state.index.to_date;
      }
      elements['change-from-date'].value = clampDate(addDays(state.index.to_date, -27));
      elements['change-to-date'].value = state.index.to_date;
      await loadRange();
    } catch (error) {
      elements['change-status'].textContent = `Price-change data unavailable: ${error.message}`;
      elements['range-description'].textContent = 'The research contract could not be loaded.';
    }
  }

  init();
})();
"""
