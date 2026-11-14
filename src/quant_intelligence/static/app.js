const $ = (id) => document.getElementById(id);
const state = { assets: [], rankings: [], selected: null, bars: [], signal: null, busy: false };

function setNotice(message, error = false) {
  const el = $('notice');
  el.hidden = !message;
  el.textContent = message || '';
  el.classList.toggle('error', error);
}

function setBusy(busy) {
  state.busy = busy;
  ['load-demo', 'load-live', 'check-quote', 'run-forecast', 'run-backtest', 'paper-buy', 'paper-sell'].forEach((id) => {
    $(id).disabled = busy;
  });
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { headers: { Accept: 'application/json', ...options.headers }, ...options });
  } catch (_) {
    throw new Error('Cannot reach the app. Make sure Docker is running, then refresh this page.');
  }
  let body;
  try { body = await response.json(); } catch (_) { body = null; }
  if (!response.ok) {
    let detail = body?.detail;
    if (Array.isArray(detail)) detail = detail.map((item) => item.msg).join('; ');
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`);
  }
  return body;
}

function fmtNumber(value, digits = 2) {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
    : '—';
}

function fmtMoney(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
    : '—';
}

function fmtPercent(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `${fmtNumber(value, 2)}%` : '—';
}

function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== '') node.textContent = text;
  return node;
}

function sourceLabel(source) {
  if (source === 'demo') return 'Fictional demo';
  if (source === 'alpha_vantage') return 'Alpha Vantage';
  return source ? source.replaceAll('_', ' ') : 'Unknown source';
}

function sourceTag(source) {
  return el('span', `source-tag${source === 'demo' ? ' demo' : ''}`, sourceLabel(source));
}

function renderAssets() {
  $('asset-count').textContent = String(state.assets.length);
  const query = $('asset-filter').value.trim().toUpperCase();
  const list = $('asset-list');
  list.replaceChildren();
  const filtered = state.assets.filter((item) =>
    `${item.symbol} ${item.name}`.toUpperCase().includes(query)
  );
  if (!filtered.length) {
    list.append(el('p', 'empty-side', state.assets.length ? 'No matching symbols.' : 'No data loaded yet. Use a button above to begin.'));
    return;
  }
  filtered.forEach((item) => {
    const button = el('button', `asset-button${state.selected?.symbol === item.symbol ? ' active' : ''}`);
    button.type = 'button';
    button.setAttribute('aria-label', `Explore ${item.symbol}, ${item.name}`);
    const label = el('span');
    label.append(el('span', 'asset-symbol', item.symbol), el('span', 'asset-name', item.name));
    button.append(label, el('span', `asset-source${item.source === 'demo' ? ' demo' : ''}`, item.source === 'demo' ? 'Demo' : 'Real'));
    button.addEventListener('click', () => selectAsset(item.symbol));
    list.append(button);
  });
}

function renderRankings() {
  const tbody = $('ranking-rows');
  tbody.replaceChildren();
  if (!state.rankings.length) {
    const row = el('tr');
    const cell = el('td', 'empty-cell', 'Load data to see rankings.');
    cell.colSpan = 4;
    row.append(cell);
    tbody.append(row);
    return;
  }
  state.rankings.forEach((item) => {
    const row = el('tr');
    const asset = state.assets.find((a) => a.symbol === item.symbol);
    const nameCell = el('td');
    nameCell.append(el('span', 'ranking-symbol', item.symbol), el('div', 'asset-name', asset?.name || ''));
    const sourceCell = el('td');
    sourceCell.append(sourceTag(item.source));
    const scoreCell = el('td', 'num');
    scoreCell.append(el('span', 'score-chip', `${fmtNumber(item.score, 0)} / 100`));
    row.append(nameCell, sourceCell, el('td', '', item.date || '—'), scoreCell);
    tbody.append(row);
  });
}

function renderHeading() {
  const heading = $('asset-heading');
  heading.replaceChildren();
  if (!state.selected) {
    const intro = el('div');
    intro.append(el('h2', '', 'Pick a stock to explore'), el('p', '', 'Select an asset in the watchlist after loading data.'));
    heading.append(intro);
    $('data-stamp').textContent = 'Select an asset to begin';
    $('quote-result').textContent = 'Select an imported real stock to check.';
    return;
  }
  const left = el('div');
  const title = el('div', 'asset-title-row');
  title.append(el('h2', '', state.selected.symbol), sourceTag(state.selected.source));
  left.append(title, el('p', '', state.selected.name));
  heading.append(left);
  $('quote-result').textContent = state.selected.source === 'demo'
    ? 'Quote checks are for imported real stocks. Demo assets are fictional.'
    : 'Click Check quote to request the latest quote available to your API key.';
  const latest = state.bars[0];
  if (latest) {
    const right = el('div', 'latest-close');
    right.append(el('strong', '', fmtMoney(latest.close)), el('span', '', `Last stored close · ${latest.date}`));
    heading.append(right);
    $('data-stamp').textContent = `${sourceLabel(state.selected.source)} · data through ${latest.date}`;
  } else {
    $('data-stamp').textContent = `${sourceLabel(state.selected.source)} · no bars yet`;
  }
}

function renderPriceChart() {
  const box = $('price-chart');
  box.replaceChildren();
  const bars = [...state.bars].reverse().filter((bar) => typeof bar.close === 'number');
  if (bars.length < 2) {
    box.className = 'chart-placeholder';
    box.textContent = 'Select an asset with at least two saved prices to see a chart.';
    $('chart-caption').textContent = 'Prices are historical observations.';
    return;
  }
  box.className = '';
  const width = 700, height = 210, left = 8, top = 17, bottom = 27, right = 8;
  const values = bars.map((bar) => bar.close);
  const rawMin = Math.min(...values), rawMax = Math.max(...values);
  const spread = rawMax - rawMin || Math.max(Math.abs(rawMax) * .02, 1);
  const min = rawMin - spread * .12, max = rawMax + spread * .12;
  const x = (i) => left + i / (bars.length - 1) * (width - left - right);
  const y = (v) => top + (max - v) / (max - min) * (height - top - bottom);
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('class', 'price-chart-svg');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `Historical closing price chart from ${bars[0].date} to ${bars.at(-1).date}`);
  for (let i = 0; i < 3; i++) {
    const yy = top + i * (height - top - bottom) / 2;
    const line = document.createElementNS(ns, 'line');
    [['x1', 0], ['x2', width], ['y1', yy], ['y2', yy], ['stroke', '#e8eff0'], ['stroke-dasharray', '4 5']].forEach(([key, value]) => line.setAttribute(key, String(value)));
    svg.append(line);
  }
  const points = bars.map((bar, i) => `${x(i)},${y(bar.close)}`).join(' ');
  const polygon = document.createElementNS(ns, 'polygon');
  polygon.setAttribute('points', `${left},${height - bottom} ${points} ${width - right},${height - bottom}`);
  polygon.setAttribute('fill', '#e1f2e9');
  const path = document.createElementNS(ns, 'polyline');
  path.setAttribute('points', points);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', '#33a27d');
  path.setAttribute('stroke-width', '3');
  path.setAttribute('stroke-linejoin', 'round');
  path.setAttribute('stroke-linecap', 'round');
  svg.append(polygon, path);
  box.append(svg);
  $('chart-range').textContent = `${bars.length} stored days`;
  $('chart-caption').textContent = `${bars[0].date} to ${bars.at(-1).date} · ${sourceLabel(state.selected.source)} · historical daily closes`;
}

function renderSignal() {
  const summary = $('score-summary');
  const checks = $('score-checks');
  summary.replaceChildren(); checks.replaceChildren();
  const s = state.signal;
  if (!s) { summary.className = 'score-empty'; summary.textContent = 'No score yet'; return; }
  summary.className = '';
  summary.append(el('div', 'score-number', `${fmtNumber(s.score, 0)} / 100`));
  summary.append(el('p', 'score-note', 'A count of four screening conditions. It is not a recommendation.'));
  const conditions = [
    [s.rsi_oversold, 'RSI is 30 or lower', s.rsi_14 === null ? 'not enough history' : `RSI ${fmtNumber(s.rsi_14)}`],
    [s.macd_bullish, 'MACD is above its signal line', s.macd === null ? 'not enough history' : `MACD ${fmtNumber(s.macd)}`],
    [s.sma_bullish, '20-day average is above 50-day average', s.sma_50 === null ? 'not enough history' : 'trend check'],
    [s.volume_spike, 'Volume is unusually high', s.volume_ratio_20 === null ? 'not enough history' : `${fmtNumber(s.volume_ratio_20)}× prior average`],
  ];
  conditions.forEach(([active, label, detail]) => {
    const li = el('li');
    li.append(el('span', `check-icon${active ? ' yes' : ''}`, active ? '✓' : '–'), el('span', '', `${label} · ${detail}`));
    checks.append(li);
  });
}

async function refreshAssets(preferredSymbol) {
  const [assets, rankings] = await Promise.all([request('/v1/assets'), request('/v1/rankings')]);
  state.assets = assets;
  state.rankings = rankings;
  renderRankings();
  const symbol = preferredSymbol || state.selected?.symbol;
  const found = assets.find((item) => item.symbol === symbol) || assets[0] || null;
  state.selected = found;
  renderAssets();
  if (found) await selectAsset(found.symbol);
  else { state.bars = []; state.signal = null; renderHeading(); renderPriceChart(); renderSignal(); }
}

async function selectAsset(symbol) {
  const asset = state.assets.find((item) => item.symbol === symbol);
  if (!asset) return;
  state.selected = asset;
  renderAssets();
  try {
    const [barsResult, signalResult] = await Promise.allSettled([
      request(`/v1/assets/${encodeURIComponent(symbol)}/bars?limit=500`),
      request(`/v1/assets/${encodeURIComponent(symbol)}/signals/latest`),
    ]);
    state.bars = barsResult.status === 'fulfilled' ? barsResult.value : [];
    state.signal = signalResult.status === 'fulfilled' ? signalResult.value : null;
    renderHeading(); renderPriceChart(); renderSignal();
  } catch (error) { setNotice(error.message, true); }
}

function setResult(id, message, kind = '') {
  const box = $(id);
  box.className = `result-state${kind ? ` ${kind}` : ''}`;
  box.replaceChildren();
  box.textContent = message;
}

function humanize(key) {
  const labels = { symbol: 'Asset', source: 'Source', as_of: 'Data date', last_close: 'Last stored close', predicted_close: 'No-change baseline', historical_move_band_low: 'Historical lower range', historical_move_band_high: 'Historical upper range', historical_mean_abs_move_pct: 'Average move over horizon', horizon_bars: 'Trading sessions ahead', observations: 'Past observations', initial_cash: 'Starting cash', ending_equity: 'Ending value', total_return_pct: 'Strategy return', buy_hold_return_pct: 'Buy and hold return', max_drawdown_pct: 'Largest historical drop', fee_bps: 'Fee basis points', slippage_bps: 'Slippage basis points', fees_paid: 'Trading costs', cash: 'Cash', equity: 'Account value', price_date: 'Price date', last_price: 'Last stored price' };
  return labels[key] || key.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function displayValue(key, value) {
  if (key === 'source') return sourceLabel(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') {
    if (/(cash|equity|price|close|fee|value|baseline|lower|upper)/.test(key) && !key.endsWith('_bps')) return fmtMoney(value);
    if (key.endsWith('_pct')) return fmtPercent(value);
    return fmtNumber(value, Number.isInteger(value) ? 0 : 2);
  }
  return value === null || value === undefined ? '—' : String(value);
}

function renderGenericResult(id, data, explanation) {
  const box = $(id);
  box.className = 'result-state';
  box.replaceChildren();
  const metrics = el('div', 'result-grid');
  Object.entries(data || {}).forEach(([key, value]) => {
    if (value === null || Array.isArray(value) || (typeof value === 'object' && value !== null) || ['method', 'strategy', 'limitation', 'notice', 'execution_rule'].includes(key)) return;
    const metric = el('div', 'result-metric');
    metric.append(el('span', '', humanize(key)), el('strong', '', displayValue(key, value)));
    metrics.append(metric);
  });
  if (metrics.childElementCount) box.append(metrics);
  const arrays = Object.entries(data || {}).filter(([key, value]) => Array.isArray(value) && key !== 'equity_curve');
  arrays.forEach(([key, value]) => {
    if (!value.length) return;
    const title = el('div', 'result-title', humanize(key));
    box.append(title);
    const list = el('div', 'positions');
    value.slice(0, 20).forEach((item) => {
      const line = el('p');
      line.textContent = typeof item === 'object' && item !== null
        ? Object.entries(item).map(([k, v]) => `${humanize(k)}: ${displayValue(k, v)}`).join(' · ')
        : String(item);
      list.append(line);
    });
    box.append(list);
  });
  if (data?.method || data?.strategy || data?.execution_rule) box.append(el('p', 'result-note', String(data.method || data.strategy || data.execution_rule)));
  if (data?.limitation) box.append(el('p', 'result-note', String(data.limitation)));
  box.append(el('p', 'result-note', explanation));
}

async function loadDemo() {
  setBusy(true); setNotice('Loading fictional demo data…');
  try {
    const result = await request('/v1/ingestions/demo', { method: 'POST' });
    await refreshAssets('DEMOA');
    setNotice(`Demo ready: ${result.assets} fictional assets. These prices are synthetic and dated in 2024.`);
  } catch (error) { setNotice(error.message, true); }
  finally { setBusy(false); }
}

async function loadLive(event) {
  event.preventDefault();
  const symbol = $('live-symbol').value.trim().toUpperCase();
  if (!/^[A-Z][A-Z0-9.-]{0,19}$/.test(symbol)) {
    setNotice('Enter a stock symbol such as AAPL. Letters, numbers, periods, and dashes are allowed.', true);
    return;
  }
  setBusy(true); setNotice(`Importing ${symbol} historical daily prices…`);
  try {
    const result = await request('/v1/ingestions/market', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }),
    });
    await refreshAssets(symbol);
    const latest = state.bars[0]?.date || 'unknown date';
    setNotice(`${symbol} imported from ${sourceLabel(result.source)}. Latest saved daily price: ${latest}. This is not a live quote.`);
  } catch (error) { setNotice(`Could not import ${symbol}: ${error.message}`, true); }
  finally { setBusy(false); }
}

async function checkQuote() {
  const box = $('quote-result');
  box.classList.remove('error');
  if (!state.selected || state.selected.source === 'demo') {
    box.textContent = 'Import a real stock first. Fictional demo symbols have no market quote.';
    return;
  }
  setBusy(true);
  box.textContent = 'Requesting the latest available quote…';
  try {
    const data = await request(`/v1/market/quote/${encodeURIComponent(state.selected.symbol)}`);
    const entitlement = String(data.requested_entitlement || 'unknown').replaceAll('_', ' ');
    box.textContent = `${data.symbol}: ${fmtMoney(data.price)} · trading day ${data.latest_trading_day || 'unknown'} · ${sourceLabel(data.source)} · ${entitlement} entitlement. This quote may be delayed.`;
  } catch (error) { box.classList.add('error'); box.textContent = error.message; }
  finally { setBusy(false); }
}

async function runForecast() {
  if (!state.selected) return setResult('forecast-result', 'Load and select an asset first.', 'error');
  setBusy(true); setResult('forecast-result', 'Calculating from saved historical prices…');
  try {
    const days = Number($('forecast-days').value);
    const data = await request(`/v1/assets/${encodeURIComponent(state.selected.symbol)}/forecast?horizon=${days}`);
    renderGenericResult('forecast-result', data, 'This is a last-close baseline with a historical movement band, not an AI prediction.');
  } catch (error) { setResult('forecast-result', error.message, 'error'); }
  finally { setBusy(false); }
}

async function runBacktest() {
  if (!state.selected) return setResult('backtest-result', 'Load and select an asset first.', 'error');
  const initialCash = Number($('starting-cash').value);
  if (!Number.isFinite(initialCash) || initialCash < 100) return setResult('backtest-result', 'Enter starting cash of at least $100.', 'error');
  setBusy(true); setResult('backtest-result', 'Simulating with saved historical prices…');
  try {
    const data = await request('/v1/backtests', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: state.selected.symbol, initial_cash: initialCash, fee_bps: 10 }),
    });
    renderGenericResult('backtest-result', data, 'The moving-average rule uses prior-day information and next-day opening prices. A backtest is not a promise of future performance.');
  } catch (error) { setResult('backtest-result', error.message, 'error'); }
  finally { setBusy(false); }
}

async function refreshPaper() {
  try {
    const data = await request('/v1/paper/portfolio');
    const cash = data.cash ?? data.cash_balance;
    $('paper-balance').replaceChildren(el('span', '', 'Practice cash: '), el('strong', '', fmtMoney(cash)));
    const list = $('paper-positions'); list.replaceChildren();
    if (Array.isArray(data.positions) && data.positions.length) {
      list.append(el('strong', '', 'Practice positions'));
      data.positions.forEach((position) => list.append(el('p', '', Object.entries(position).map(([key, value]) => `${humanize(key)}: ${displayValue(key, value)}`).join(' · '))));
    } else list.textContent = 'No practice positions yet.';
  } catch (error) { $('paper-balance').textContent = error.message; }
}

async function placePaperOrder(event) {
  event.preventDefault();
  if (!state.selected) return setResult('paper-result', 'Load and select an asset first.', 'error');
  const quantity = Number($('paper-quantity').value);
  if (!Number.isInteger(quantity) || quantity < 1) return setResult('paper-result', 'Enter a whole number of shares of at least 1.', 'error');
  const side = event.submitter?.dataset.side || 'buy';
  setBusy(true); setResult('paper-result', 'Recording practice order…');
  try {
    const data = await request('/v1/paper/orders', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: state.selected.symbol, side, quantity }),
    });
    renderGenericResult('paper-result', data, 'Practice order only. No real broker or money was used. The fill uses a stored daily closing price.');
    await refreshPaper();
  } catch (error) { setResult('paper-result', error.message, 'error'); }
  finally { setBusy(false); }
}

function activateTab(name) {
  document.querySelectorAll('.tab').forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle('active', active);
    if (active) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current');
  });
  document.querySelectorAll('.tab-panel').forEach((panel) => {
    const active = panel.id === `${name}-panel`;
    panel.classList.toggle('active', active);
    panel.hidden = !active;
  });
  if (name === 'paper') refreshPaper();
}

async function start() {
  $('load-demo').addEventListener('click', loadDemo);
  $('live-form').addEventListener('submit', loadLive);
  $('check-quote').addEventListener('click', checkQuote);
  $('asset-filter').addEventListener('input', renderAssets);
  $('run-forecast').addEventListener('click', runForecast);
  $('run-backtest').addEventListener('click', runBacktest);
  $('paper-order-form').addEventListener('submit', placePaperOrder);
  document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => activateTab(tab.dataset.tab)));
  try {
    await request('/v1/health');
    $('api-status').classList.add('connected');
    $('api-status').textContent = 'App connected';
    await refreshAssets();
  } catch (error) {
    $('api-status').classList.add('disconnected');
    $('api-status').textContent = 'Connection problem';
    setNotice(error.message, true);
  }
}

start();
