"""HTTP media server: REST API + embedded web library UI for browsing clips."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Awaitable, Callable

import aiofiles
from aiohttp import web

from .database import ClipDatabase

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedded HTML / CSS / JS  –  three-tab SPA: Library | Status | Automations
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blink Clip Library</title>
<style>
:root{
  --bg:#0d1117;--surface:#161b22;--card:#1c2128;--card2:#21262d;
  --border:#30363d;--accent:#58a6ff;--accent2:#1f6feb;--success:#3fb950;
  --danger:#f85149;--warn:#d29922;--text:#c9d1d9;--muted:#8b949e;
  --starred:#e3b341;--radius:8px;--nav-h:56px
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
     background:var(--bg);color:var(--text);height:100vh;display:flex;
     flex-direction:column;overflow:hidden}
button,input,select{font:inherit}
a{color:var(--accent);text-decoration:none}
code{background:var(--card2);border:1px solid var(--border);border-radius:4px;
     padding:.1em .4em;font-family:"SFMono-Regular",Consolas,monospace;font-size:.85em}

/* ── Navigation ──────────────────────────────────────── */
.nav{background:var(--surface);border-bottom:1px solid var(--border);
     height:var(--nav-h);display:flex;align-items:center;gap:.5rem;
     padding:0 1rem;flex-shrink:0;position:relative;z-index:10}
.nav-brand{font-size:1.05rem;font-weight:700;color:var(--accent);
           white-space:nowrap;margin-right:.5rem}
.nav-brand span{opacity:.5;font-weight:400}
.nav-tabs{display:flex;gap:.25rem;flex:1}
.nav-tab{background:transparent;border:none;color:var(--muted);
         padding:.4rem .85rem;border-radius:var(--radius);cursor:pointer;
         font-size:.88rem;font-weight:500;transition:.15s;white-space:nowrap}
.nav-tab:hover{color:var(--text);background:var(--card)}
.nav-tab.active{color:var(--accent);background:var(--card2)}
.nav-actions{display:flex;align-items:center;gap:.5rem;margin-left:auto}
.btn{background:var(--accent);color:#0d1117;border:none;border-radius:var(--radius);
     padding:.4rem .9rem;font-size:.85rem;font-weight:600;cursor:pointer;
     transition:.15s;white-space:nowrap;display:inline-flex;align-items:center;gap:.35rem}
.btn:hover:not(:disabled){filter:brightness(1.12)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn.outline{background:transparent;color:var(--accent);border:1px solid var(--accent)}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}
.btn.ghost:hover{color:var(--text);border-color:var(--text)}
.btn.danger{background:var(--danger);color:#fff}
.badge{display:inline-block;background:var(--border);border-radius:9px;
       padding:.1rem .5rem;font-size:.72rem;color:var(--muted)}
.badge.connected{background:#0d2818;color:var(--success)}
.badge.disconnected{background:#2d1313;color:var(--danger)}

/* ── Pages ────────────────────────────────────────────── */
.page{flex:1;overflow:hidden;display:none}
.page.active{display:flex}

/* ── Library layout ───────────────────────────────────── */
#page-library{flex-direction:column}
.lib-filters{background:var(--surface);border-bottom:1px solid var(--border);
             padding:.6rem 1rem;display:flex;align-items:center;gap:.6rem;
             flex-wrap:wrap;flex-shrink:0}
.search{background:var(--card);border:1px solid var(--border);
        border-radius:var(--radius);padding:.38rem .75rem;color:var(--text);
        font-size:.88rem;width:200px}
.search:focus{outline:none;border-color:var(--accent)}
.sel{background:var(--card);border:1px solid var(--border);
     border-radius:var(--radius);padding:.38rem .6rem;color:var(--text);
     font-size:.82rem;cursor:pointer}
.sel:focus{outline:none;border-color:var(--accent)}
.chk{display:flex;align-items:center;gap:.3rem;cursor:pointer;
     font-size:.82rem;white-space:nowrap;user-select:none;color:var(--muted)}
.chk input{accent-color:var(--accent)}
.lib-body{display:flex;flex:1;overflow:hidden}
.sidebar{width:200px;background:var(--surface);border-right:1px solid var(--border);
         overflow-y:auto;flex-shrink:0;padding:.75rem 0}
.sb-head{padding:.3rem 1rem .1rem;font-size:.68rem;font-weight:700;
         text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.cam-item{display:flex;justify-content:space-between;align-items:center;
          padding:.4rem 1rem;cursor:pointer;font-size:.85rem;
          border-left:3px solid transparent;transition:.1s}
.cam-item:hover{background:var(--card)}
.cam-item.active{border-left-color:var(--accent);color:var(--accent);background:var(--card2)}
.cam-badge{background:var(--border);border-radius:8px;padding:.05rem .4rem;
           font-size:.72rem;color:var(--muted)}
.lib-main{flex:1;overflow-y:auto;padding:1rem}

/* ── Stats bar ────────────────────────────────────────── */
.stats-row{display:flex;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap;align-items:center}
.stat-chip{background:var(--card);border:1px solid var(--border);
           border-radius:var(--radius);padding:.35rem .75rem;font-size:.8rem;
           white-space:nowrap}
.stat-chip strong{color:var(--accent)}
.result-info{font-size:.8rem;color:var(--muted);margin-left:auto}

/* ── Clip grid ────────────────────────────────────────── */
.clip-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.85rem}
.clip-card{background:var(--card);border:1px solid var(--border);
           border-radius:var(--radius);overflow:hidden;cursor:pointer;
           transition:.15s;position:relative;user-select:none}
.clip-card:hover{border-color:var(--accent2);transform:translateY(-2px);
                 box-shadow:0 4px 16px rgba(31,111,235,.2)}
.clip-card.selected{border-color:var(--accent);box-shadow:0 0 0 2px rgba(88,166,255,.3)}
.thumb-wrap{position:relative;aspect-ratio:16/9;background:#000;overflow:hidden}
.thumb-wrap img{width:100%;height:100%;object-fit:cover;opacity:.85;transition:.2s}
.clip-card:hover .thumb-wrap img{opacity:1}
.no-thumb{display:flex;align-items:center;justify-content:center;
          height:100%;font-size:2.5rem;opacity:.2;color:#fff}
.dur-badge{position:absolute;bottom:.35rem;right:.35rem;background:rgba(0,0,0,.8);
           color:#fff;font-size:.7rem;padding:.1rem .38rem;border-radius:4px}
.star-badge{position:absolute;top:.35rem;left:.35rem;font-size:.95rem;
            color:var(--starred);filter:drop-shadow(0 1px 2px #000)}
.sel-check{position:absolute;top:.35rem;right:.35rem;width:18px;height:18px;
           background:rgba(0,0,0,.6);border:1.5px solid rgba(255,255,255,.4);
           border-radius:4px;display:flex;align-items:center;justify-content:center;
           font-size:.7rem;color:#fff;transition:.1s}
.clip-card.selected .sel-check{background:var(--accent);border-color:var(--accent)}
.clip-info{padding:.55rem .65rem}
.clip-camera{font-size:.78rem;font-weight:600;color:var(--accent);
             overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.clip-time{font-size:.72rem;color:var(--muted);margin:.15rem 0}
.clip-meta{font-size:.7rem;color:var(--muted);display:flex;gap:.4rem;flex-wrap:wrap}
.src-pill{background:var(--card2);border-radius:3px;padding:.05rem .3rem}
.tag-pill{background:#1a3055;color:#79b8ff;border-radius:3px;padding:.05rem .3rem}

/* ── Bulk actions ─────────────────────────────────────── */
.bulk-bar{background:var(--accent2);color:#fff;padding:.5rem 1rem;
          display:flex;align-items:center;gap:.75rem;font-size:.85rem;
          flex-shrink:0;transition:.2s}
.bulk-bar.hidden{display:none}
.bulk-bar .btn{background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.3)}
.bulk-bar .btn:hover{background:rgba(255,255,255,.25)}

/* ── Load more / empty ────────────────────────────────── */
.load-more-row{display:flex;justify-content:center;padding:1.25rem 0}
.empty{text-align:center;padding:4rem 2rem;color:var(--muted)}
.empty .icon{font-size:3.5rem;display:block;margin-bottom:.75rem}
.empty h3{color:var(--text);margin-bottom:.5rem}

/* ── Modal (video player) ─────────────────────────────── */
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.88);
          z-index:100;align-items:flex-start;justify-content:center;
          padding:1rem;overflow-y:auto}
.modal-bg.open{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:12px;
       max-width:960px;width:100%;margin:auto;overflow:hidden;position:relative}
.modal-close{position:absolute;top:.75rem;right:.75rem;background:rgba(0,0,0,.5);
             border:none;color:var(--muted);font-size:1.4rem;cursor:pointer;
             line-height:1;z-index:1;border-radius:50%;width:32px;height:32px;
             display:flex;align-items:center;justify-content:center;transition:.15s}
.modal-close:hover{background:rgba(0,0,0,.8);color:var(--text)}
.video-wrap{background:#000;position:relative}
.video-wrap video{width:100%;max-height:58vh;display:block}
.video-nav{position:absolute;top:50%;transform:translateY(-50%);
           display:flex;justify-content:space-between;width:100%;
           padding:0 .5rem;pointer-events:none}
.vid-nav-btn{background:rgba(0,0,0,.55);border:none;color:#fff;
             font-size:1.4rem;cursor:pointer;border-radius:50%;
             width:36px;height:36px;display:flex;align-items:center;
             justify-content:center;pointer-events:all;transition:.15s}
.vid-nav-btn:hover{background:rgba(0,0,0,.8)}
.modal-body{padding:1rem}
.modal-title{font-size:1rem;font-weight:600;margin-bottom:.65rem}
.meta-grid{display:grid;grid-template-columns:auto 1fr auto 1fr;gap:.3rem .75rem;
           font-size:.82rem;color:var(--muted);margin-bottom:.85rem}
.meta-grid span{color:var(--text)}
.modal-actions{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin-bottom:.85rem}
.tag-input{background:var(--card);border:1px solid var(--border);
           border-radius:var(--radius);padding:.32rem .6rem;color:var(--text);
           font-size:.82rem;width:175px}
.tag-input:focus{outline:none;border-color:var(--accent)}
.tag-list{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.4rem}
.tag-item{background:#1a3055;color:#79b8ff;border-radius:4px;
          padding:.18rem .45rem;font-size:.75rem;display:flex;align-items:center;gap:.25rem}
.tag-item .rm{cursor:pointer;opacity:.6;font-size:.85rem}
.tag-item .rm:hover{opacity:1}
.kbd{background:var(--card2);border:1px solid var(--border);border-radius:4px;
     padding:.1rem .4rem;font-size:.72rem;font-family:monospace;color:var(--muted)}

/* ── Status page ──────────────────────────────────────── */
#page-status{overflow-y:auto;padding:1.5rem}
.status-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
             gap:1rem;max-width:1000px;margin:0 auto}
.status-card{background:var(--card);border:1px solid var(--border);
             border-radius:var(--radius);padding:1.1rem 1.25rem}
.status-card h3{font-size:.9rem;font-weight:600;color:var(--text);margin-bottom:.85rem;
                display:flex;align-items:center;gap:.5rem}
.status-card h3 .icon{font-size:1.1rem}
.status-row{display:flex;justify-content:space-between;align-items:center;
            padding:.3rem 0;border-bottom:1px solid var(--border);font-size:.84rem}
.status-row:last-child{border-bottom:none}
.status-row .label{color:var(--muted)}
.status-row .value{color:var(--text);text-align:right;max-width:60%;
                   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.status-row .value.ok{color:var(--success)}
.status-row .value.warn{color:var(--warn)}
.status-row .value.err{color:var(--danger)}
.prog-bar{background:var(--card2);border-radius:4px;height:6px;overflow:hidden;margin-top:.5rem}
.prog-fill{height:100%;background:var(--accent);border-radius:4px;transition:.5s}
.prog-fill.warn{background:var(--warn)}
.prog-fill.danger{background:var(--danger)}

/* ── Automations page ─────────────────────────────────── */
#page-automations{overflow-y:auto;padding:1.5rem}
.auto-content{max-width:800px;margin:0 auto}
.auto-content h2{font-size:1.1rem;font-weight:700;margin-bottom:1rem;color:var(--text)}
.auto-content h3{font-size:.92rem;font-weight:600;margin:.85rem 0 .4rem;
                 color:var(--accent);display:flex;align-items:center;gap:.4rem}
.auto-content p,.auto-content li{font-size:.88rem;color:var(--muted);line-height:1.55}
.auto-content ul{padding-left:1.25rem;margin:.35rem 0}
.code-block{background:var(--card);border:1px solid var(--border);
            border-radius:var(--radius);padding:1rem 1.1rem;
            font-family:"SFMono-Regular",Consolas,monospace;font-size:.8rem;
            color:#a9d1f7;line-height:1.5;overflow-x:auto;white-space:pre;
            position:relative;margin:.5rem 0 1.25rem}
.copy-btn{position:absolute;top:.5rem;right:.5rem;background:var(--card2);
          border:1px solid var(--border);color:var(--muted);
          border-radius:5px;padding:.2rem .55rem;font-size:.72rem;cursor:pointer}
.copy-btn:hover{color:var(--text)}
.event-table{width:100%;border-collapse:collapse;font-size:.82rem;margin:.5rem 0 1.25rem}
.event-table th{background:var(--card2);padding:.4rem .75rem;text-align:left;
                color:var(--muted);font-size:.75rem;font-weight:600;
                text-transform:uppercase;letter-spacing:.05em}
.event-table td{padding:.4rem .75rem;border-bottom:1px solid var(--border)}
.event-table code{font-size:.78rem}

/* ── Toast ────────────────────────────────────────────── */
.toast{position:fixed;bottom:1.5rem;right:1.5rem;background:#238636;
       color:#fff;padding:.6rem 1.1rem;border-radius:var(--radius);
       font-size:.85rem;z-index:500;opacity:0;transition:opacity .25s;
       pointer-events:none;max-width:300px}
.toast.show{opacity:1}
.toast.err{background:var(--danger)}

/* ── Responsive ───────────────────────────────────────── */
@media(max-width:640px){
  .sidebar{display:none}
  .nav-tab span{display:none}
  .search{width:120px}
}
</style>
</head>
<body>

<!-- ── Navigation ────────────────────────────────────────────── -->
<nav class="nav">
  <div class="nav-brand">🎥 Blink <span>Clips</span></div>
  <div class="nav-tabs">
    <button class="nav-tab active" data-tab="library">📁 <span>Library</span></button>
    <button class="nav-tab" data-tab="status">📡 <span>Status</span></button>
    <button class="nav-tab" data-tab="automations">⚡ <span>Automations</span></button>
  </div>
  <div class="nav-actions">
    <span id="conn-badge" class="badge">●</span>
    <button class="btn" id="sync-btn">⬇ Sync Now</button>
  </div>
</nav>

<!-- ── Library page ──────────────────────────────────────────── -->
<div class="page active" id="page-library">
  <!-- Filter bar -->
  <div class="lib-filters">
    <input class="search" id="search" type="search" placeholder="🔍 Search…">
    <select class="sel" id="date-range">
      <option value="">All time</option>
      <option value="today">Today</option>
      <option value="yesterday">Yesterday</option>
      <option value="week" selected>This week</option>
      <option value="month">This month</option>
      <option value="custom">Custom…</option>
    </select>
    <select class="sel" id="source-filter">
      <option value="">All sources</option>
      <option value="pir">Motion (PIR)</option>
      <option value="liveview">Liveview</option>
      <option value="snapshot">Snapshot</option>
    </select>
    <select class="sel" id="sort-order">
      <option value="newest">⬆ Newest first</option>
      <option value="oldest">⬇ Oldest first</option>
      <option value="camera">📷 By camera</option>
      <option value="size">💾 By size</option>
      <option value="duration">⏱ By duration</option>
    </select>
    <label class="chk"><input type="checkbox" id="starred-only"> ★ Starred</label>
    <button class="btn ghost" id="select-mode-btn">☐ Select</button>
    <button class="btn ghost" id="refresh-btn" title="Refresh">↻</button>
  </div>

  <!-- Bulk action bar (hidden until selection mode) -->
  <div class="bulk-bar hidden" id="bulk-bar">
    <span id="sel-count">0 selected</span>
    <button class="btn" id="bulk-star-btn">★ Star</button>
    <button class="btn" id="bulk-delete-btn">🗑 Delete</button>
    <button class="btn" style="margin-left:auto" id="bulk-cancel-btn">✕ Cancel</button>
  </div>

  <!-- Body: sidebar + main -->
  <div class="lib-body">
    <aside class="sidebar">
      <div class="sb-head">Cameras</div>
      <div id="camera-nav">
        <div class="cam-item active" data-camera="all">
          All Cameras<span class="cam-badge" id="badge-all">—</span>
        </div>
      </div>
      <div class="sb-head" style="margin-top:.85rem">Storage</div>
      <div id="storage-info" style="padding:.4rem 1rem;font-size:.78rem;color:var(--muted)"></div>
    </aside>

    <main class="lib-main">
      <div class="stats-row" id="stats-bar"></div>
      <div class="clip-grid" id="clip-grid"></div>
      <div class="load-more-row">
        <button class="btn outline" id="load-more" style="display:none">Load more…</button>
      </div>
    </main>
  </div>
</div>

<!-- ── Status page ───────────────────────────────────────────── -->
<div class="page" id="page-status">
  <div class="status-grid" id="status-grid"></div>
</div>

<!-- ── Automations page ──────────────────────────────────────── -->
<div class="page" id="page-automations">
  <div class="auto-content">
    <h2>HA Automation Examples</h2>
    <p>This add-on fires Home Assistant events and updates sensors every poll cycle.
       Use them to build powerful automations in <code>automations.yaml</code> or the
       HA automation editor.</p>

    <h3>📡 Available Events &amp; Sensors</h3>
    <table class="event-table">
      <thead><tr><th>Type</th><th>Name / Event</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td>Sensor</td><td><code>sensor.blink_downloader_status</code></td>
            <td>Total clips downloaded; attributes: session count, disk usage, last download time</td></tr>
        <tr><td>Event</td><td><code>blink_clip_downloaded</code></td>
            <td>Fired after each clip is saved. Data: <code>clip_id</code>, <code>camera</code>,
                <code>path</code>, <code>timestamp</code>, <code>size_bytes</code>,
                <code>duration</code>, <code>source</code></td></tr>
      </tbody>
    </table>

    <h3>⚡ Notify on new clip from a specific camera</h3>
    <div class="code-block" id="auto1"><button class="copy-btn" data-target="auto1">Copy</button>alias: "Blink – Front Door clip notification"
trigger:
  - platform: event
    event_type: blink_clip_downloaded
    event_data:
      camera: "Front Door"
condition: []
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "🎥 New Blink clip – Front Door"
      message: "{{ trigger.event.data.timestamp[:10] }} — {{ (trigger.event.data.size_bytes / 1048576) | round(1) }} MB"</div>

    <h3>⚡ Notify when motion clip is longer than 10 seconds</h3>
    <div class="code-block" id="auto2"><button class="copy-btn" data-target="auto2">Copy</button>alias: "Blink – Long motion clip alert"
trigger:
  - platform: event
    event_type: blink_clip_downloaded
condition:
  - condition: template
    value_template: >
      {{ trigger.event.data.source == 'pir' and
         trigger.event.data.duration | int > 10 }}
action:
  - service: notify.notify
    data:
      title: "⚠️ Long motion clip detected"
      message: >
        {{ trigger.event.data.camera }} recorded a
        {{ trigger.event.data.duration }}s clip.</div>

    <h3>⚡ Storage quota warning</h3>
    <div class="code-block" id="auto3"><button class="copy-btn" data-target="auto3">Copy</button>alias: "Blink – Storage quota warning"
trigger:
  - platform: numeric_state
    entity_id: sensor.blink_downloader_status
    attribute: used_mb
    above: 8000   # 8 GB – adjust to your quota
condition: []
action:
  - service: notify.notify
    data:
      title: "💾 Blink storage getting full"
      message: >
        {{ state_attr('sensor.blink_downloader_status','used_mb') | int }} MB used.
        Consider increasing the quota or retention period.</div>

    <h3>⚡ Daily summary notification</h3>
    <div class="code-block" id="auto4"><button class="copy-btn" data-target="auto4">Copy</button>alias: "Blink – Daily clip summary"
trigger:
  - platform: time
    at: "08:00:00"
condition: []
action:
  - service: notify.notify
    data:
      title: "📅 Blink Daily Summary"
      message: >
        {{ states('sensor.blink_downloader_status') }} total clips.
        {{ state_attr('sensor.blink_downloader_status','session_downloads') }}
        downloaded this session.</div>

    <h3>💡 Tips</h3>
    <ul>
      <li>Enable <strong>Watch HA Events</strong> in add-on settings to auto-poll within seconds of a motion event.</li>
      <li>Set <strong>Post-Motion Download Delay</strong> (default 30 s) to match how long Blink takes to upload a clip in your region.</li>
      <li>The <strong>Sync Now</strong> button on the Library page triggers an immediate download cycle.</li>
      <li>Use the <strong>Library web UI</strong> (this page) to star important clips so they're excluded from bulk delete.</li>
      <li>Download clips directly from the video player modal using the <strong>⬇ Download</strong> button.</li>
    </ul>
  </div>
</div>

<!-- ── Video player modal ─────────────────────────────────────── -->
<div class="modal-bg" id="modal-bg">
  <div class="modal">
    <button class="modal-close" id="modal-close" title="Close (Esc)">×</button>
    <div class="video-wrap">
      <video id="modal-video" controls preload="metadata"></video>
      <div class="video-nav">
        <button class="vid-nav-btn" id="vid-prev" title="Previous clip">‹</button>
        <button class="vid-nav-btn" id="vid-next" title="Next clip">›</button>
      </div>
    </div>
    <div class="modal-body">
      <div class="modal-title" id="modal-title"></div>
      <div class="meta-grid" id="modal-meta"></div>
      <div class="modal-actions">
        <button class="btn outline" id="star-btn">☆ Star</button>
        <a class="btn ghost" id="dl-link" download>⬇ Download</a>
        <button class="btn ghost" id="open-folder-btn" title="Copy file path">📋 Copy path</button>
        <button class="btn danger" id="delete-btn" style="margin-left:auto">🗑 Delete</button>
      </div>
      <div>
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.35rem">
          <input class="tag-input" id="tag-input" placeholder="Add tag + Enter">
          <span style="font-size:.75rem;color:var(--muted)">
            <span class="kbd">Space</span> play  <span class="kbd">←→</span> seek 10s
            <span class="kbd">F</span> fullscreen  <span class="kbd">M</span> mute
          </span>
        </div>
        <div class="tag-list" id="tag-list"></div>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
'use strict';
// ── State ───────────────────────────────────────────────────────────
let currentCamera='all', currentPage=0, currentClipId=null, currentTags=[];
let selectMode=false, selectedIds=new Set();
let allClipIds=[];  // ordered ids currently visible (for prev/next nav)
const PAGE_SIZE=48;

// ── DOM helpers ──────────────────────────────────────────────────────
const $=id=>document.getElementById(id);
function qs(sel,ctx=document){return ctx.querySelector(sel);}

function toast(msg,isErr=false,dur=2800){
  const el=$('toast');
  el.textContent=msg;
  el.classList.toggle('err',isErr);
  el.classList.add('show');
  clearTimeout(el._t);
  el._t=setTimeout(()=>el.classList.remove('show'),dur);
}

// ── Formatting ───────────────────────────────────────────────────────
function fmtSize(b){
  if(!b)return'';
  if(b>=1073741824)return(b/1073741824).toFixed(2)+' GB';
  if(b>=1048576)return(b/1048576).toFixed(1)+' MB';
  return(b/1024).toFixed(0)+' KB';
}
function fmtDur(s){
  if(!s)return'';
  const m=Math.floor(s/60),sec=s%60;
  return m?`${m}m ${sec}s`:`${sec}s`;
}
function fmtTs(ts){
  if(!ts)return'';
  try{return new Date(ts).toLocaleString();}catch{return ts;}
}
function fmtRelative(ts){
  if(!ts)return'';
  const diff=(Date.now()-new Date(ts))/1000;
  if(diff<60)return'just now';
  if(diff<3600)return Math.floor(diff/60)+'m ago';
  if(diff<86400)return Math.floor(diff/3600)+'h ago';
  return Math.floor(diff/86400)+'d ago';
}
function sinceDate(range){
  const d=new Date();
  if(range==='today'){d.setHours(0,0,0,0);}
  else if(range==='yesterday'){d.setDate(d.getDate()-1);d.setHours(0,0,0,0);}
  else if(range==='week'){d.setDate(d.getDate()-7);}
  else if(range==='month'){d.setDate(d.getDate()-30);}
  else return null;
  return d.toISOString();
}

// ── API ──────────────────────────────────────────────────────────────
async function api(path,opts={}){
  const r=await fetch(path,opts);
  if(!r.ok){
    const txt=await r.text().catch(()=>r.statusText);
    throw new Error(`${r.status}: ${txt}`);
  }
  return r.json();
}

// ── Tab navigation ───────────────────────────────────────────────────
document.querySelectorAll('.nav-tab').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.nav-tab').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    $('page-'+btn.dataset.tab).classList.add('active');
    if(btn.dataset.tab==='status') loadStatus();
  });
});

// ── Camera sidebar ───────────────────────────────────────────────────
async function loadCameras(){
  try{
    const cams=await api('/api/cameras');
    const total=cams.reduce((s,c)=>s+(c.total||0),0);
    $('badge-all').textContent=total;
    const nav=$('camera-nav');
    const allEl=nav.querySelector('[data-camera="all"]');
    nav.innerHTML='';
    nav.appendChild(allEl);
    cams.forEach(c=>{
      const el=document.createElement('div');
      el.className='cam-item'+(c.camera===currentCamera?' active':'');
      el.dataset.camera=c.camera;
      el.innerHTML=`<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">${c.camera}</span>`+
                   `<span class="cam-badge">${c.total||0}</span>`;
      nav.appendChild(el);
    });
    nav.querySelectorAll('.cam-item').forEach(el=>el.addEventListener('click',()=>{
      currentCamera=el.dataset.camera;
      nav.querySelectorAll('.cam-item').forEach(x=>x.classList.remove('active'));
      el.classList.add('active');
      currentPage=0;$('clip-grid').innerHTML='';loadClips(0);
    }));
  }catch(e){console.warn('loadCameras',e);}
}

// ── Stats bar ────────────────────────────────────────────────────────
async function loadStats(){
  try{
    const s=await api('/api/stats');
    const bar=$('stats-bar');
    bar.innerHTML=
      `<div class="stat-chip">Today <strong>${s.today_count??0}</strong></div>`+
      `<div class="stat-chip">Week <strong>${s.week_count??0}</strong></div>`+
      `<div class="stat-chip">Total <strong>${s.total_count??0}</strong></div>`+
      `<div class="stat-chip">★ Starred <strong>${s.starred_count??0}</strong></div>`+
      `<div class="stat-chip">Library <strong>${((s.total_size_bytes??0)/1073741824).toFixed(2)} GB</strong></div>`;
    if(s.disk){
      const pct=s.disk.quota_bytes?Math.min(100,(s.disk.used_bytes/s.disk.quota_bytes)*100):0;
      const cls=pct>90?'danger':pct>70?'warn':'';
      $('storage-info').innerHTML=
        `<div>Used: ${s.disk.used_mb} MB</div>`+
        `<div style="color:var(--text)">Free: ${s.disk.free_gb} GB</div>`+
        (s.disk.quota_bytes?
          `<div class="prog-bar" style="margin-top:.4rem"><div class="prog-fill ${cls}" style="width:${pct.toFixed(1)}%"></div></div>`
        :'');
    }
    // Update connection badge
    const badge=$('conn-badge');
    if(s.connected!=null){
      badge.className='badge '+(s.connected?'connected':'disconnected');
      badge.textContent=s.connected?'● Connected':'● Disconnected';
    }
  }catch(e){console.warn('loadStats',e);}
}

// ── Clip card builder ─────────────────────────────────────────────────
function buildCard(c){
  const div=document.createElement('div');
  div.className='clip-card'+(selectedIds.has(c.id)?' selected':'');
  div.dataset.id=c.id;
  const thumbSrc=`/api/clips/${c.id}/thumb`;
  div.innerHTML=
    `<div class="thumb-wrap">`+
    `<img src="${thumbSrc}" loading="lazy" alt="" onerror="this.style.display='none';this.nextSibling.style.display='flex'">`+
    `<div class="no-thumb" style="display:none">🎬</div>`+
    (c.duration?`<div class="dur-badge">${fmtDur(c.duration)}</div>`:'')+
    (c.starred?'<div class="star-badge">★</div>':'')+
    `<div class="sel-check">${selectedIds.has(c.id)?'✓':''}</div>`+
    `</div>`+
    `<div class="clip-info">`+
    `<div class="clip-camera">${c.camera}</div>`+
    `<div class="clip-time">${fmtTs(c.timestamp)}</div>`+
    `<div class="clip-meta">`+
    (c.source?`<span class="src-pill">${c.source}</span>`:'')+
    `<span>${fmtSize(c.size_bytes)}</span>`+
    (c.tags||[]).map(t=>`<span class="tag-pill">${t}</span>`).join('')+
    `</div></div>`;
  div.addEventListener('click',e=>{
    if(selectMode){toggleSelect(c.id,div);return;}
    openModal(c.id);
  });
  return div;
}

// ── Load clips ───────────────────────────────────────────────────────
async function loadClips(page=0){
  const grid=$('clip-grid');
  if(page===0){
    grid.innerHTML='<div style="grid-column:1/-1;padding:2rem;text-align:center;color:var(--muted)">Loading…</div>';
    allClipIds=[];
  }
  const params=new URLSearchParams({limit:PAGE_SIZE,offset:page*PAGE_SIZE});
  if(currentCamera!=='all')params.set('camera',currentCamera);
  const sr=$('search').value.trim();if(sr)params.set('search',sr);
  const dr=sinceDate($('date-range').value);if(dr)params.set('since',dr);
  if($('starred-only').checked)params.set('starred','1');
  const src=$('source-filter').value;if(src)params.set('source',src);
  const srt=$('sort-order').value;if(srt)params.set('sort',srt);
  try{
    const clips=await api(`/api/clips?${params}`);
    if(page===0)grid.innerHTML='';
    if(!clips.length&&page===0){
      grid.innerHTML='<div class="empty"><span class="icon">📭</span><h3>No clips found</h3><p>Try adjusting filters or sync to fetch new clips.</p></div>';
      $('load-more').style.display='none';
      return;
    }
    clips.forEach(c=>{
      allClipIds.push(c.id);
      grid.appendChild(buildCard(c));
    });
    $('load-more').style.display=clips.length<PAGE_SIZE?'none':'inline-flex';
    currentPage=page;
  }catch(e){
    toast('Failed to load clips',true);
    console.error(e);
  }
}

// ── Selection mode ───────────────────────────────────────────────────
function toggleSelectMode(on){
  selectMode=on;
  selectedIds.clear();
  $('bulk-bar').classList.toggle('hidden',!on);
  $('select-mode-btn').textContent=on?'☒ Selecting':'☐ Select';
  updateBulkBar();
  document.querySelectorAll('.clip-card').forEach(el=>{
    el.querySelector('.sel-check').textContent='';
    el.classList.remove('selected');
  });
}
function toggleSelect(id,el){
  if(selectedIds.has(id)){selectedIds.delete(id);el.classList.remove('selected');el.querySelector('.sel-check').textContent='';}
  else{selectedIds.add(id);el.classList.add('selected');el.querySelector('.sel-check').textContent='✓';}
  updateBulkBar();
}
function updateBulkBar(){
  $('sel-count').textContent=`${selectedIds.size} selected`;
}
$('select-mode-btn').addEventListener('click',()=>toggleSelectMode(!selectMode));
$('bulk-cancel-btn').addEventListener('click',()=>toggleSelectMode(false));
$('bulk-star-btn').addEventListener('click',async()=>{
  if(!selectedIds.size)return;
  await Promise.all([...selectedIds].map(id=>api(`/api/clips/${id}/star`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({starred:true})})));
  toast(`Starred ${selectedIds.size} clip(s)`);
  toggleSelectMode(false);loadClips(0);
});
$('bulk-delete-btn').addEventListener('click',async()=>{
  if(!selectedIds.size||!confirm(`Delete ${selectedIds.size} clip(s) permanently?`))return;
  await Promise.all([...selectedIds].map(id=>api(`/api/clips/${id}`,{method:'DELETE'}).catch(()=>{})));
  toast(`Deleted ${selectedIds.size} clip(s)`);
  toggleSelectMode(false);loadClips(0);loadStats();
});

// ── Modal ─────────────────────────────────────────────────────────────
async function openModal(clipId){
  currentClipId=clipId;
  try{
    const c=await api(`/api/clips/${clipId}`);
    currentTags=[...(c.tags||[])];
    const vid=$('modal-video');
    vid.src=`/api/clips/${clipId}/stream`;
    vid.load();
    $('modal-title').textContent=`${c.camera} — ${fmtTs(c.timestamp)}`;
    $('modal-meta').innerHTML=
      `<div>Camera</div><span>${c.camera}</span>`+
      `<div>Recorded</div><span>${fmtTs(c.timestamp)}</span>`+
      `<div>Duration</div><span>${fmtDur(c.duration)||'—'}</span>`+
      `<div>Size</div><span>${fmtSize(c.size_bytes)||'—'}</span>`+
      `<div>Source</div><span>${c.source||'—'}</span>`+
      `<div>Added</div><span>${fmtRelative(c.downloaded_at)}</span>`;
    updateStarBtn(c.starred);
    const dl=$('dl-link');
    dl.href=`/api/clips/${clipId}/stream`;
    dl.download=`${c.camera}_${(c.timestamp||'').replace(/[:.]/g,'-')}.mp4`;
    $('open-folder-btn').dataset.path=c.file_path||'';
    renderTags();
    $('modal-bg').classList.add('open');
    vid.focus();
  }catch(e){toast('Failed to load clip',true);console.error(e);}
}
function closeModal(){
  $('modal-bg').classList.remove('open');
  const vid=$('modal-video');
  vid.pause();vid.src='';
  currentClipId=null;
}
function updateStarBtn(starred){
  const btn=$('star-btn');
  btn.textContent=starred?'★ Starred':'☆ Star';
  btn.style.color=starred?'var(--starred)':'';
  btn.dataset.starred=starred?'1':'0';
}
function renderTags(){
  const list=$('tag-list');
  list.innerHTML=currentTags.map(t=>
    `<span class="tag-item">${t}<span class="rm" data-tag="${t}">×</span></span>`
  ).join('');
  list.querySelectorAll('.rm').forEach(el=>el.addEventListener('click',async()=>{
    currentTags=currentTags.filter(t=>t!==el.dataset.tag);
    await saveTags();renderTags();
  }));
}
async function saveTags(){
  if(!currentClipId)return;
  await api(`/api/clips/${currentClipId}/tags`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tags:currentTags})});
}
function navClip(dir){
  const idx=allClipIds.indexOf(currentClipId);
  const next=idx+dir;
  if(next>=0&&next<allClipIds.length)openModal(allClipIds[next]);
}

// Modal events
$('modal-close').addEventListener('click',closeModal);
$('modal-bg').addEventListener('click',e=>{if(e.target===$('modal-bg'))closeModal();});
$('vid-prev').addEventListener('click',()=>navClip(-1));
$('vid-next').addEventListener('click',()=>navClip(1));
$('star-btn').addEventListener('click',async()=>{
  if(!currentClipId)return;
  const now=$('star-btn').dataset.starred==='1';
  const starred=!now;
  await api(`/api/clips/${currentClipId}/star`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({starred})});
  updateStarBtn(starred);
  toast(starred?'Starred ★':'Unstarred');
  document.querySelectorAll(`.clip-card[data-id="${currentClipId}"]`).forEach(el=>{
    const b=el.querySelector('.star-badge');
    if(starred&&!b){const nb=document.createElement('div');nb.className='star-badge';nb.textContent='★';el.querySelector('.thumb-wrap').prepend(nb);}
    else if(!starred&&b){b.remove();}
  });
});
$('delete-btn').addEventListener('click',async()=>{
  if(!currentClipId||!confirm('Delete this clip permanently?'))return;
  const id=currentClipId;
  await api(`/api/clips/${id}`,{method:'DELETE'});
  toast('Clip deleted');
  document.querySelector(`.clip-card[data-id="${id}"]`)?.remove();
  navClip(1)||closeModal();
});
$('open-folder-btn').addEventListener('click',()=>{
  const path=$('open-folder-btn').dataset.path;
  if(path){navigator.clipboard.writeText(path).then(()=>toast('Path copied to clipboard')).catch(()=>toast('Could not copy: '+path,true));}
});
$('tag-input').addEventListener('keydown',async e=>{
  if(e.key==='Enter'){
    const v=e.target.value.trim().toLowerCase().replace(/[^a-z0-9_-]/g,'');
    if(v&&!currentTags.includes(v)){currentTags.push(v);await saveTags();renderTags();}
    e.target.value='';
  }
});

// Keyboard shortcuts for video player
document.addEventListener('keydown',e=>{
  if(!$('modal-bg').classList.contains('open'))return;
  const vid=$('modal-video');
  if(e.target.tagName==='INPUT')return;
  switch(e.key){
    case'Escape':closeModal();break;
    case'ArrowLeft':vid.currentTime=Math.max(0,vid.currentTime-10);break;
    case'ArrowRight':vid.currentTime=Math.min(vid.duration||0,vid.currentTime+10);break;
    case' ':e.preventDefault();vid.paused?vid.play():vid.pause();break;
    case'f':case'F':vid.requestFullscreen?.();break;
    case'm':case'M':vid.muted=!vid.muted;break;
    case'ArrowUp':navClip(-1);break;
    case'ArrowDown':navClip(1);break;
  }
});

// ── Sync Now ─────────────────────────────────────────────────────────
$('sync-btn').addEventListener('click',async()=>{
  const btn=$('sync-btn');
  btn.disabled=true;btn.textContent='⏳ Syncing…';
  try{
    await api('/api/download-now',{method:'POST'});
    toast('Download triggered — clips will appear shortly');
    setTimeout(()=>{currentPage=0;loadAll();},10000);
  }catch(e){toast('Failed to trigger sync',true);}
  finally{setTimeout(()=>{btn.disabled=false;btn.textContent='⬇ Sync Now';},3000);}
});
$('refresh-btn').addEventListener('click',()=>{currentPage=0;loadAll();});
$('load-more').addEventListener('click',()=>loadClips(currentPage+1));

// Debounced filter changes
let _dbt;function debounce(fn,ms=380){clearTimeout(_dbt);_dbt=setTimeout(fn,ms);}
['search','date-range','starred-only','source-filter','sort-order'].forEach(id=>{
  $(id).addEventListener(id==='search'?'input':'change',()=>{
    debounce(()=>{currentPage=0;$('clip-grid').innerHTML='';loadClips(0);});
  });
});

// ── Status page ───────────────────────────────────────────────────────
async function loadStatus(){
  const grid=$('status-grid');
  grid.innerHTML='<div style="padding:2rem;color:var(--muted)">Loading…</div>';
  try{
    const [stats,cams]=await Promise.all([api('/api/stats'),api('/api/cameras')]);
    let html='';

    // Connection card
    const conn=stats.connected;
    html+=`<div class="status-card"><h3><span class="icon">📡</span>Blink Connection</h3>`+
      `<div class="status-row"><span class="label">Status</span><span class="value ${conn?'ok':'err'}">${conn?'Connected':'Disconnected'}</span></div>`+
      (stats.account_id?`<div class="status-row"><span class="label">Account ID</span><span class="value">${stats.account_id}</span></div>`:'');

    if(stats.last_download){
      html+=`<div class="status-row"><span class="label">Last download</span><span class="value">${fmtTs(stats.last_download)}</span></div>`;
    }
    html+=`</div>`;

    // Library card
    html+=`<div class="status-card"><h3><span class="icon">📚</span>Clip Library</h3>`+
      `<div class="status-row"><span class="label">Total clips</span><span class="value">${stats.total_count??0}</span></div>`+
      `<div class="status-row"><span class="label">Today</span><span class="value">${stats.today_count??0}</span></div>`+
      `<div class="status-row"><span class="label">This week</span><span class="value">${stats.week_count??0}</span></div>`+
      `<div class="status-row"><span class="label">Starred</span><span class="value">${stats.starred_count??0}</span></div>`+
      `<div class="status-row"><span class="label">Archived</span><span class="value">${stats.archived_count??0}</span></div>`+
      `</div>`;

    // Storage card
    if(stats.disk){
      const d=stats.disk;
      const pct=d.quota_bytes?Math.min(100,(d.used_bytes/d.quota_bytes)*100):null;
      const cls=pct&&pct>90?'danger':pct&&pct>70?'warn':'';
      html+=`<div class="status-card"><h3><span class="icon">💾</span>Storage</h3>`+
        `<div class="status-row"><span class="label">Used</span><span class="value ${cls||'ok'}">${d.used_mb} MB</span></div>`+
        `<div class="status-row"><span class="label">Free (disk)</span><span class="value">${d.free_gb} GB</span></div>`+
        (d.quota_bytes?
          `<div class="status-row"><span class="label">Quota</span><span class="value">${d.quota_gb} GB</span></div>`+
          `<div class="prog-bar"><div class="prog-fill ${cls}" style="width:${(pct||0).toFixed(1)}%"></div></div>`
        :'')+
        `</div>`;
    }

    // Cameras card
    if(cams.length){
      html+=`<div class="status-card"><h3><span class="icon">📷</span>Cameras (${cams.length})</h3>`;
      cams.forEach(c=>{
        html+=`<div class="status-row"><span class="label">${c.camera}</span>`+
          `<span class="value">${c.total||0} clips — ${c.today||0} today</span></div>`;
      });
      html+=`</div>`;
    }

    grid.innerHTML=html;
  }catch(e){
    grid.innerHTML='<div style="padding:2rem;color:var(--danger)">Failed to load status. Is the library database enabled?</div>';
  }
}

// ── Copy buttons in Automations page ─────────────────────────────────
document.querySelectorAll('.copy-btn').forEach(btn=>{
  btn.addEventListener('click',e=>{
    e.stopPropagation();
    const block=document.getElementById(btn.dataset.target);
    // Get text content minus the copy button text
    const text=block.textContent.replace(/^Copy/,'').trim();
    navigator.clipboard.writeText(text)
      .then(()=>toast('Copied to clipboard'))
      .catch(()=>toast('Copy failed',true));
  });
});

// ── Boot ──────────────────────────────────────────────────────────────
async function loadAll(){
  await Promise.all([loadStats(),loadCameras(),loadClips(0)]);
}
loadAll();
// Auto-refresh every 60 s when library is visible and no modal open.
setInterval(()=>{
  if(document.querySelector('.nav-tab[data-tab="library"]').classList.contains('active')
     && !$('modal-bg').classList.contains('open')){
    loadAll();
  }
},60000);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# MediaServer class
# ---------------------------------------------------------------------------


class MediaServer:
    """aiohttp web server exposing a clip library REST API and browser UI."""

    def __init__(
        self,
        db: ClipDatabase,
        download_path: Path,
        port: int,
        trigger_download: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._db = db
        self._download_path = download_path
        self._port = port
        self._trigger_download = trigger_download
        self._runner: web.AppRunner | None = None
        # Injected by app.py after construction so status endpoint can report it.
        self.extra_status: dict = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        app = self._build_app()
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        _LOGGER.info("Media server listening on port %d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            self._runner = None

    # ------------------------------------------------------------------
    # App factory
    # ------------------------------------------------------------------

    def _build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/api/clips", self._handle_list_clips)
        app.router.add_get("/api/clips/{id}", self._handle_get_clip)
        app.router.add_delete("/api/clips/{id}", self._handle_delete_clip)
        app.router.add_put("/api/clips/{id}/star", self._handle_star_clip)
        app.router.add_put("/api/clips/{id}/tags", self._handle_set_tags)
        app.router.add_get("/api/clips/{id}/stream", self._handle_stream)
        app.router.add_get("/api/clips/{id}/thumb", self._handle_thumbnail)
        app.router.add_get("/api/cameras", self._handle_cameras)
        app.router.add_get("/api/stats", self._handle_stats)
        app.router.add_post("/api/download-now", self._handle_download_now)
        return app

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    async def _handle_index(self, _request: web.Request) -> web.Response:
        return web.Response(text=_HTML, content_type="text/html")

    async def _handle_health(self, _request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def _handle_list_clips(self, request: web.Request) -> web.Response:
        q = request.rel_url.query
        try:
            limit = min(int(q.get("limit", 48)), 200)
            offset = int(q.get("offset", 0))
        except ValueError:
            limit, offset = 48, 0

        starred_raw = q.get("starred")
        starred = True if starred_raw == "1" else False if starred_raw == "0" else None

        clips = await self._db.get_clips(
            camera=q.get("camera") or None,
            since=q.get("since") or None,
            until=q.get("until") or None,
            starred=starred,
            source=q.get("source") or None,
            tag=q.get("tag") or None,
            search=q.get("search") or None,
            sort=q.get("sort") or "newest",
            limit=limit,
            offset=offset,
        )
        return web.json_response(clips)

    async def _handle_get_clip(self, request: web.Request) -> web.Response:
        clip_id = request.match_info["id"]
        clip = await self._db.get_clip(clip_id)
        if not clip:
            raise web.HTTPNotFound(text="Clip not found")
        return web.json_response(clip)

    async def _handle_delete_clip(self, request: web.Request) -> web.Response:
        clip_id = request.match_info["id"]
        clip = await self._db.get_clip(clip_id)
        if not clip:
            raise web.HTTPNotFound(text="Clip not found")
        file_path = Path(clip["file_path"])
        if file_path.exists():
            try:
                file_path.unlink()
                thumb = file_path.with_suffix(".jpg")
                if thumb.exists():
                    thumb.unlink()
            except OSError as exc:
                _LOGGER.warning("Could not delete file %s: %s", file_path, exc)
        await self._db.delete_clip(clip_id)
        return web.json_response({"deleted": True})

    async def _handle_star_clip(self, request: web.Request) -> web.Response:
        clip_id = request.match_info["id"]
        try:
            body = await request.json()
            starred = bool(body.get("starred", True))
        except Exception:  # noqa: BLE001
            starred = True
        found = await self._db.star_clip(clip_id, starred)
        if not found:
            raise web.HTTPNotFound(text="Clip not found")
        return web.json_response({"id": clip_id, "starred": starred})

    async def _handle_set_tags(self, request: web.Request) -> web.Response:
        clip_id = request.match_info["id"]
        try:
            body = await request.json()
            tags = [str(t) for t in body.get("tags", [])]
        except Exception:  # noqa: BLE001
            raise web.HTTPBadRequest(text="Invalid JSON body")
        found = await self._db.set_tags(clip_id, tags)
        if not found:
            raise web.HTTPNotFound(text="Clip not found")
        return web.json_response({"id": clip_id, "tags": tags})

    async def _handle_stream(self, request: web.Request) -> web.StreamResponse:
        clip_id = request.match_info["id"]
        clip = await self._db.get_clip(clip_id)
        if not clip:
            raise web.HTTPNotFound(text="Clip not found")

        file_path = Path(clip["file_path"])
        if not file_path.exists():
            raise web.HTTPNotFound(text="Clip file not found on disk")

        file_size = file_path.stat().st_size
        range_header = request.headers.get("Range", "")

        if range_header:
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else file_size - 1
                end = min(end, file_size - 1)
                chunk_len = end - start + 1

                response = web.StreamResponse(
                    status=206,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Length": str(chunk_len),
                        "Accept-Ranges": "bytes",
                    },
                )
                await response.prepare(request)
                async with aiofiles.open(file_path, "rb") as fh:
                    await fh.seek(start)
                    remaining = chunk_len
                    while remaining > 0:
                        data = await fh.read(min(65_536, remaining))
                        if not data:
                            break
                        await response.write(data)
                        remaining -= len(data)
                return response

        response = web.StreamResponse(
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file_path.name}"',
            }
        )
        await response.prepare(request)
        async with aiofiles.open(file_path, "rb") as fh:
            while True:
                data = await fh.read(65_536)
                if not data:
                    break
                await response.write(data)
        return response

    async def _handle_thumbnail(self, request: web.Request) -> web.Response:
        clip_id = request.match_info["id"]
        clip = await self._db.get_clip(clip_id)
        if not clip:
            raise web.HTTPNotFound()

        thumb = Path(clip["file_path"]).with_suffix(".jpg")
        if thumb.exists():
            async with aiofiles.open(thumb, "rb") as fh:
                data = await fh.read()
            return web.Response(body=data, content_type="image/jpeg")

        raise web.HTTPNotFound(text="Thumbnail not available")

    async def _handle_cameras(self, _request: web.Request) -> web.Response:
        camera_stats = await self._db.get_camera_stats()
        return web.json_response(camera_stats)

    async def _handle_stats(self, request: web.Request) -> web.Response:
        stats = await self._db.get_stats()
        disk_stats_raw = request.app.get("disk_stats")
        if disk_stats_raw:
            stats["disk"] = disk_stats_raw
        # Merge any extra status fields (connected, account_id, last_download, etc.)
        stats.update(self.extra_status)
        return web.json_response(stats)

    async def _handle_download_now(self, _request: web.Request) -> web.Response:
        if self._trigger_download:
            await self._trigger_download()
            return web.json_response({"triggered": True})
        try:
            Path("/data/trigger_download").touch()
        except OSError:
            pass
        return web.json_response({"triggered": True})
