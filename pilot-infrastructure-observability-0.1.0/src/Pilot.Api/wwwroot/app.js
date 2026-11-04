'use strict';
let apiKey = '';
const $ = id => document.getElementById(id);
function element(tag, text, className) { const e = document.createElement(tag); e.textContent = text; if (className) e.className = className; return e; }
async function get(path) { const r = await fetch('/api/v1/' + path, {headers: {'X-Pilot-Key': apiKey}}); if (!r.ok) throw new Error(r.status === 401 ? 'Invalid API key.' : 'API request failed (' + r.status + ').'); return r.json(); }
async function refresh() {
  if (!apiKey) return;
  $('refresh').disabled = true;
  try {
    const [rows, events] = await Promise.all([get('machines'), get('events')]);
    $('summary').replaceChildren();
    for (const [label, count] of [['Machines', rows.length], ['Needs attention', rows.filter(r => ['warning','critical'].includes(r.health)).length], ['Stale / unknown', rows.filter(r => ['stale','unknown'].includes(r.health)).length]]) {
      const card = element('div', '', 'stat'); card.append(element('strong', String(count)), element('span', label)); $('summary').append(card);
    }
    $('machines').replaceChildren();
    if (!rows.length) $('machines').append(element('p', 'No machines yet. Run scripts/collect-windows.ps1 or scripts/send-demo.py.'));
    for (const row of rows) {
      const m = row.machine, card = element('article', '', 'machine');
      card.append(element('span', row.health.toUpperCase(), 'badge ' + row.health), element('h3', m.name), element('p', m.os + ' · ' + m.id, 'muted'));
      for (const [key, label] of [['cpuPercent','CPU'], ['memoryPercent','Memory'], ['diskPercent','Disk']]) {
        const v = m.metrics[key], line = element('div', '', 'metric'); line.append(element('span', label), element('strong', v === undefined ? 'Not observed' : v.toFixed(1) + '%')); card.append(line);
      }
      card.append(element('p', 'Observed ' + new Date(m.observedAt).toLocaleString(), 'muted')); $('machines').append(card);
    }
    $('events').replaceChildren(...events.map(e => element('li', new Date(e.at).toLocaleString() + ' · ' + e.machineId + ' · ' + e.summary)));
    $('status').textContent = 'Updated ' + new Date().toLocaleTimeString() + ' · Refreshes every 15 seconds';
  } catch (e) { $('status').textContent = e.message + ' Displayed data may be outdated.'; }
  finally { $('refresh').disabled = false; }
}
$('connect').addEventListener('submit', e => { e.preventDefault(); apiKey = $('key').value; $('key').value = ''; refresh(); });
$('refresh').addEventListener('click', refresh);
setInterval(refresh, 15000);
