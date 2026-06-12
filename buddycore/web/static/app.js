const state = {
  paused: false,
  levelFilter: "",
  selectedPlugin: "",
};

const el = (id) => document.getElementById(id);

function h(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[ch]));
}

function fmtTime(ts) {
  if (!ts) return "--:--:--";
  try { return new Date(ts).toLocaleTimeString(); } catch { return ts; }
}

function logClass(level) {
  const l = (level || "").toLowerCase();
  if (l === "event") return "log-event";
  if (l === "warn" || l === "warning") return "log-warn";
  if (l === "error" || l === "critical") return "log-error";
  if (l === "debug") return "log-debug";
  return "log-info";
}

function addConsoleLine(item) {
  if (state.paused) return;
  if (state.levelFilter && item.level !== state.levelFilter) return;
  const c = el("console");
  const source = item.plugin_id || item.source || "core";
  const event = item.event_type ? ` ${item.event_type}` : "";
  const line = `[${fmtTime(item.timestamp)}] [${item.level || "INFO"}] [${source}]${event} ${item.message || ""}`;
  const span = document.createElement("span");
  span.className = logClass(item.level);
  span.textContent = line + "\n";
  c.appendChild(span);
  while (c.childNodes.length > 500) c.removeChild(c.firstChild);
  c.scrollTop = c.scrollHeight;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  return await res.json();
}

async function loadStatus() {
  const data = await fetchJson('/api/status');
  el('buddyName').textContent = data.name || 'Buddy';
  el('version').textContent = `v${data.version}`;
  el('safeMode').textContent = data.safe_mode ? 'YES' : 'NO';
  el('pluginSummary').textContent = `${data.plugins.running}/${data.plugins.enabled} running (${data.plugins.total} installed)`;
}

async function loadPlugins() {
  const data = await fetchJson('/api/plugins');
  const box = el('plugins');
  box.innerHTML = '';
  for (const p of data.plugins || []) {
    const card = document.createElement('div');
    card.className = 'plugin';
    const status = p.status || 'installed';
    card.innerHTML = `
      <div class="plugin-top">
        <div>
          <div class="plugin-name">${p.name || p.id}</div>
          <div class="plugin-meta">${p.id} · ${p.type || 'utility'} · v${p.version}</div>
        </div>
        <div class="plugin-status ${status}">${status.toUpperCase()}</div>
      </div>
      <div class="plugin-meta">${p.description || ''}</div>
      ${p.last_error ? `<div class="plugin-status failed">Last error: ${p.last_error}</div>` : ''}
      <div class="plugin-actions">
        ${p.enabled ? `<button class="danger" data-action="disable" data-id="${p.id}">Disable</button>` : `<button class="good" data-action="enable" data-id="${p.id}">Enable</button>`}
        <button data-action="reload" data-id="${p.id}">Reload</button>
        <button data-action="details" data-id="${p.id}">Details</button>
        <button data-action="errors" data-id="${p.id}">Errors</button>
      </div>
    `;
    box.appendChild(card);
  }
}

async function pluginAction(action, id) {
  if (action === 'details') {
    await showPluginDetail(id);
    return;
  }
  if (action === 'errors') {
    const data = await fetchJson(`/api/plugins/${id}/errors`);
    addConsoleLine({level: 'INFO', source: 'webui', message: `${id} errors: ${JSON.stringify(data.errors.slice(0, 3))}`});
    return;
  }
  const data = await fetchJson(`/api/plugins/${id}/${action}`, {method: 'POST'});
  addConsoleLine({level: data.ok ? 'INFO' : 'ERROR', source: 'webui', message: `${action} ${id}: ${JSON.stringify(data)}`});
  await loadPlugins();
  await loadStatus();
  if (state.selectedPlugin === id) await showPluginDetail(id);
}

function renderDependency(dep) {
  const status = dep.installed ? 'installed' : (dep.optional ? 'optional missing' : 'missing');
  const cls = dep.installed ? 'risk-low' : (dep.optional ? 'risk-medium' : 'risk-high');
  return `
    <div class="detail-row">
      <span><code>${h(dep.package || dep.module || 'unknown')}</code> <span class="${cls}">${h(status)}</span></span>
      <span>${h(dep.module || '')}</span>
    </div>
  `;
}

function renderPermission(perm, pluginId) {
  const risk = perm.risk || 'unknown';
  const checked = perm.granted ? 'checked' : '';
  return `
    <div class="detail-row">
      <span><code>${h(perm.permission)}</code> <span class="risk-${h(risk)}">${h(risk)}</span></span>
      <label class="permission-toggle">
        <span>${perm.granted ? 'granted' : 'revoked'}</span>
        <input type="checkbox" data-permission="${h(perm.permission)}" data-plugin-id="${h(pluginId)}" ${checked} />
      </label>
    </div>
  `;
}

function renderTimeline(items, emptyText) {
  if (!items || items.length === 0) return `<div class="subtle">${h(emptyText)}</div>`;
  return `<pre class="timeline">${items.map((item) => {
    const source = item.plugin_id || item.source || item.phase || 'plugin';
    const type = item.event_type || item.error_type || item.level || '';
    const message = item.message || item.error_message || '';
    return `[${fmtTime(item.timestamp)}] [${source}] ${type} ${message}`;
  }).map(h).join('\n')}</pre>`;
}

async function showPluginDetail(id) {
  state.selectedPlugin = id;
  const data = await fetchJson(`/api/plugins/${id}`);
  const plugin = data.plugin || {};
  const permissions = data.permissions || [];
  const dependencies = data.dependencies || [];
  const configText = JSON.stringify(data.config || {}, null, 2);
  el('pluginDetail').innerHTML = `
    <div>
      <div class="plugin-name">${h(plugin.name || plugin.id)}</div>
      <div class="plugin-meta">${h(plugin.id)} · ${h(plugin.type || 'utility')} · v${h(plugin.version)} · ${h(plugin.status || 'installed')}</div>
      <div class="subtle">${h(plugin.description || '')}</div>
    </div>
    <div class="detail-section">
      <div class="detail-heading">Permissions</div>
      <div class="detail-list">${permissions.length ? permissions.map((perm) => renderPermission(perm, id)).join('') : '<div class="subtle">No permissions declared.</div>'}</div>
    </div>
    <div class="detail-section">
      <div class="detail-heading">Dependencies</div>
      <div class="detail-list">${dependencies.length ? dependencies.map(renderDependency).join('') : '<div class="subtle">No Python dependencies declared.</div>'}</div>
    </div>
    <div class="detail-section">
      <div class="detail-heading">Config</div>
      <pre class="timeline">${h(configText)}</pre>
    </div>
    <div class="detail-section">
      <div class="detail-heading">Recent Events</div>
      ${renderTimeline(data.events, 'No recent events for this plugin.')}
    </div>
    <div class="detail-section">
      <div class="detail-heading">Recent Errors</div>
      ${renderTimeline(data.errors, 'No recent errors for this plugin.')}
    </div>
  `;
}

function connectConsole() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${window.location.host}/ws/console`);
  ws.onopen = () => {
    el('connectionStatus').textContent = 'LIVE';
    el('connectionStatus').className = 'status-pill ok';
    setInterval(() => { try { ws.send('ping'); } catch {} }, 25000);
  };
  ws.onmessage = (msg) => {
    try { addConsoleLine(JSON.parse(msg.data)); } catch {}
  };
  ws.onclose = () => {
    el('connectionStatus').textContent = 'DISCONNECTED';
    el('connectionStatus').className = 'status-pill bad';
    setTimeout(connectConsole, 2000);
  };
}

async function init() {
  el('refreshBtn').addEventListener('click', async () => { await loadStatus(); await loadPlugins(); });
  el('rescanBtn').addEventListener('click', async () => {
    const data = await fetchJson('/api/plugins/rescan', {method: 'POST'});
    addConsoleLine({level: 'INFO', source: 'webui', message: `Rescan complete: ${JSON.stringify(data.discovered)}`});
    await loadPlugins();
  });
  el('debugBundleBtn').addEventListener('click', async () => {
    const data = await fetchJson('/api/debug-bundle', {method: 'POST'});
    addConsoleLine({level: data.ok ? 'INFO' : 'ERROR', source: 'webui', message: `Debug bundle: ${JSON.stringify(data)}`});
    if (data.ok && data.download_url) window.open(data.download_url, '_blank');
  });
  el('pauseConsole').addEventListener('click', () => {
    state.paused = !state.paused;
    el('pauseConsole').textContent = state.paused ? '▶ Resume' : '⏸ Pause';
  });
  el('clearConsole').addEventListener('click', () => el('console').innerHTML = '');
  el('levelFilter').addEventListener('change', (e) => state.levelFilter = e.target.value);
  el('plugins').addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    await pluginAction(btn.dataset.action, btn.dataset.id);
  });
  el('pluginDetail').addEventListener('change', async (e) => {
    const input = e.target.closest('input[data-permission]');
    if (!input) return;
    const data = await fetchJson(`/api/plugins/${input.dataset.pluginId}/permissions`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({permission: input.dataset.permission, granted: input.checked})
    });
    addConsoleLine({level: data.ok ? 'INFO' : 'ERROR', source: 'webui', message: `Permission update: ${JSON.stringify(data)}`});
    await showPluginDetail(input.dataset.pluginId);
  });
  el('githubInstallForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      repo_url: el('githubRepo').value,
      branch: el('githubBranch').value || 'main',
      subdir: el('githubSubdir').value || ''
    };
    const data = await fetchJson('/api/plugins/install/github', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    addConsoleLine({level: data.ok ? 'INFO' : 'ERROR', source: 'webui', message: `GitHub install: ${JSON.stringify(data)}`});
    await loadPlugins();
  });
  el('zipInstallForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const file = el('zipFile').files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/api/plugins/install/zip', {method: 'POST', body: form});
    const data = await res.json();
    addConsoleLine({level: data.ok ? 'INFO' : 'ERROR', source: 'webui', message: `ZIP install: ${JSON.stringify(data)}`});
    await loadPlugins();
  });
  await loadStatus();
  await loadPlugins();
  connectConsole();
}

init().catch(err => addConsoleLine({level: 'ERROR', source: 'webui', message: err.toString()}));
