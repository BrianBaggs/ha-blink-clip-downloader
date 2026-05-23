"""HTTP media server: REST API + embedded web library UI for browsing clips."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Awaitable

import aiofiles
from aiohttp import web

from .database import ClipDatabase

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedded HTML / CSS / JS library UI
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blink Clip Library</title>
<style>
:root{--bg:#0d1117;--surface:#161b22;--card:#1c2128;--border:#30363d;
      --accent:#58a6ff;--danger:#f85149;--text:#c9d1d9;--muted:#8b949e;
      --starred:#e3b341;--radius:8px}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     background:var(--bg);color:var(--text);height:100vh;display:flex;
     flex-direction:column;overflow:hidden}
a{color:var(--accent);text-decoration:none}

/* ── Top bar ─────────────────────────────────────────────── */
.topbar{background:var(--surface);border-bottom:1px solid var(--border);
        padding:.75rem 1rem;display:flex;align-items:center;gap:.75rem;
        flex-wrap:wrap;flex-shrink:0}
.topbar h1{font-size:1.1rem;font-weight:600;white-space:nowrap;
           color:var(--accent)}
.topbar h1 span{opacity:.5;font-weight:400}
.search{flex:1;min-width:160px;background:var(--card);border:1px solid var(--border);
        border-radius:var(--radius);padding:.4rem .75rem;color:var(--text);
        font-size:.9rem}
.search:focus{outline:none;border-color:var(--accent)}
.select{background:var(--card);border:1px solid var(--border);
        border-radius:var(--radius);padding:.4rem .6rem;color:var(--text);
        font-size:.85rem;cursor:pointer}
.btn{background:var(--accent);color:#0d1117;border:none;
     border-radius:var(--radius);padding:.4rem .85rem;font-size:.85rem;
     font-weight:600;cursor:pointer;white-space:nowrap;transition:.15s}
.btn:hover{filter:brightness(1.15)}
.btn.outline{background:transparent;color:var(--accent);
             border:1px solid var(--accent)}
.btn.danger{background:var(--danger);color:#fff}
.chk{display:flex;align-items:center;gap:.35rem;cursor:pointer;
     font-size:.85rem;white-space:nowrap;user-select:none}

/* ── Layout ──────────────────────────────────────────────── */
.layout{display:flex;flex:1;overflow:hidden}
.sidebar{width:220px;background:var(--surface);border-right:1px solid var(--border);
         overflow-y:auto;flex-shrink:0;padding:.75rem 0}
.main{flex:1;overflow-y:auto;padding:1rem}

/* ── Stats bar ───────────────────────────────────────────── */
.stats-bar{display:flex;gap:1.25rem;margin-bottom:1rem;flex-wrap:wrap}
.stat-chip{background:var(--card);border:1px solid var(--border);
           border-radius:var(--radius);padding:.4rem .85rem;font-size:.82rem}
.stat-chip strong{color:var(--accent)}

/* ── Sidebar cameras ─────────────────────────────────────── */
.sidebar-section{padding:.5rem 1rem .25rem;font-size:.7rem;font-weight:600;
                 text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.cam-item{display:flex;justify-content:space-between;align-items:center;
          padding:.45rem 1rem;cursor:pointer;font-size:.88rem;
          border-left:3px solid transparent;transition:.12s}
.cam-item:hover{background:var(--card)}
.cam-item.active{border-left-color:var(--accent);color:var(--accent);
                 background:var(--card)}
.cam-badge{background:var(--border);border-radius:9px;padding:.1rem .45rem;
           font-size:.75rem;color:var(--muted)}

/* ── Clip grid ───────────────────────────────────────────── */
.clip-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
           gap:1rem}
.clip-card{background:var(--card);border:1px solid var(--border);
           border-radius:var(--radius);overflow:hidden;cursor:pointer;
           transition:.15s;position:relative}
.clip-card:hover{border-color:var(--accent);transform:translateY(-2px)}
.thumb-wrap{position:relative;aspect-ratio:16/9;background:#000;overflow:hidden}
.thumb-wrap img{width:100%;height:100%;object-fit:cover;opacity:.9}
.thumb-wrap .no-thumb{display:flex;align-items:center;justify-content:center;
                      height:100%;font-size:2.5rem;opacity:.25}
.clip-duration{position:absolute;bottom:.4rem;right:.4rem;background:rgba(0,0,0,.75);
               color:#fff;font-size:.72rem;padding:.15rem .4rem;
               border-radius:4px}
.star-badge{position:absolute;top:.4rem;left:.4rem;font-size:1rem;
            color:var(--starred);filter:drop-shadow(0 1px 2px #000)}
.clip-info{padding:.65rem}
.clip-camera{font-size:.78rem;font-weight:600;color:var(--accent);
             text-overflow:ellipsis;overflow:hidden;white-space:nowrap}
.clip-time{font-size:.75rem;color:var(--muted);margin:.2rem 0}
.clip-meta{font-size:.72rem;color:var(--muted);display:flex;gap:.5rem}
.source-pill{background:var(--border);border-radius:4px;padding:.05rem .35rem}
.tag-pill{background:#1a3055;color:#58a6ff;border-radius:4px;
          padding:.05rem .35rem;font-size:.68rem}

/* ── Load more ───────────────────────────────────────────── */
.load-more-row{display:flex;justify-content:center;padding:1.5rem 0}

/* ── Empty state ─────────────────────────────────────────── */
.empty{text-align:center;padding:4rem 2rem;color:var(--muted)}
.empty .icon{font-size:3rem;display:block;margin-bottom:.75rem}

/* ── Modal ───────────────────────────────────────────────── */
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);
          z-index:200;align-items:center;justify-content:center;padding:1rem}
.modal-bg.open{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);
       border-radius:12px;max-width:900px;width:100%;max-height:90vh;
       overflow-y:auto;position:relative}
.modal-close{position:absolute;top:.75rem;right:.75rem;background:transparent;
             border:none;color:var(--muted);font-size:1.4rem;cursor:pointer;
             line-height:1;z-index:1}
.modal-close:hover{color:var(--text)}
.modal-video-wrap{background:#000;border-radius:12px 12px 0 0;overflow:hidden}
.modal-video-wrap video{width:100%;max-height:55vh;display:block}
.modal-body{padding:1rem}
.modal-title{font-size:1.05rem;font-weight:600;margin-bottom:.5rem}
.meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:.35rem;
           font-size:.83rem;color:var(--muted);margin-bottom:.85rem}
.meta-grid span{color:var(--text)}
.modal-actions{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;
               margin-bottom:.85rem}
.tag-input{background:var(--card);border:1px solid var(--border);
           border-radius:var(--radius);padding:.35rem .65rem;color:var(--text);
           font-size:.83rem;width:180px}
.tag-input:focus{outline:none;border-color:var(--accent)}
.tag-list{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.4rem}
.tag-item{background:#1a3055;color:var(--accent);border-radius:4px;
          padding:.2rem .5rem;font-size:.78rem;display:flex;align-items:center;gap:.3rem}
.tag-item .rm{cursor:pointer;opacity:.6}
.tag-item .rm:hover{opacity:1}
.download-link{color:var(--accent);font-size:.83rem;display:inline-flex;
               align-items:center;gap:.3rem}

/* ── Notification toast ──────────────────────────────────── */
.toast{position:fixed;bottom:1.25rem;right:1.25rem;background:#238636;
       color:#fff;padding:.65rem 1.1rem;border-radius:var(--radius);
       font-size:.85rem;z-index:300;opacity:0;
       transition:opacity .3s;pointer-events:none}
.toast.show{opacity:1}
</style>
</head>
<body>

<div class="topbar">
  <h1>🎥 Blink <span>Clip Library</span></h1>
  <input class="search" id="search" type="search" placeholder="Search cameras…">
  <select class="select" id="date-range">
    <option value="">All time</option>
    <option value="today">Today</option>
    <option value="yesterday">Yesterday</option>
    <option value="week" selected>This week</option>
    <option value="month">This month</option>
  </select>
  <label class="chk"><input type="checkbox" id="starred-only"> ★ Starred</label>
  <select class="select" id="source-filter">
    <option value="">All sources</option>
    <option value="pir">Motion (PIR)</option>
    <option value="liveview">Liveview</option>
    <option value="snapshot">Snapshot</option>
  </select>
  <button class="btn outline" id="refresh-btn">↻ Refresh</button>
  <button class="btn" id="sync-btn">⬇ Sync Now</button>
</div>

<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-section">Cameras</div>
    <div id="camera-nav">
      <div class="cam-item active" data-camera="all">All Cameras <span class="cam-badge" id="badge-all">—</span></div>
    </div>
    <div class="sidebar-section" style="margin-top:.75rem">Storage</div>
    <div id="storage-info" style="padding:.5rem 1rem;font-size:.78rem;color:var(--muted)"></div>
  </aside>

  <main class="main">
    <div class="stats-bar" id="stats-bar"></div>
    <div class="clip-grid" id="clip-grid"></div>
    <div class="load-more-row">
      <button class="btn outline" id="load-more" style="display:none">Load more…</button>
    </div>
  </main>
</div>

<!-- Modal -->
<div class="modal-bg" id="modal-bg">
  <div class="modal">
    <button class="modal-close" id="modal-close">×</button>
    <div class="modal-video-wrap">
      <video id="modal-video" controls preload="metadata"></video>
    </div>
    <div class="modal-body">
      <div class="modal-title" id="modal-title"></div>
      <div class="meta-grid" id="modal-meta"></div>
      <div class="modal-actions">
        <button class="btn outline" id="star-btn">☆ Star</button>
        <a class="download-link" id="dl-link" download>⬇ Download</a>
        <button class="btn danger" id="delete-btn" style="margin-left:auto">🗑 Delete</button>
      </div>
      <div>
        <input class="tag-input" id="tag-input" placeholder="Add tag + Enter">
        <div class="tag-list" id="tag-list"></div>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const BASE = '';
let currentCamera = 'all', currentPage = 0, currentClipId = null, currentTags = [];
const PAGE_SIZE = 48;

// ── Utilities ───────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
function toast(msg, dur=2500){
  const el=$('toast'); el.textContent=msg; el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'),dur);
}
function fmt_size(b){if(!b)return''; if(b>1048576)return(b/1048576).toFixed(1)+' MB'; return(b/1024).toFixed(0)+' KB';}
function fmt_dur(s){if(!s)return''; const m=Math.floor(s/60),sec=s%60; return m?`${m}m ${sec}s`:`${sec}s`;}
function fmt_ts(ts){if(!ts)return''; try{const d=new Date(ts);return d.toLocaleString();}catch{return ts;}}
function since_date(range){
  const d=new Date();
  if(range==='today'){d.setHours(0,0,0,0);}
  else if(range==='yesterday'){d.setDate(d.getDate()-1);d.setHours(0,0,0,0);}
  else if(range==='week'){d.setDate(d.getDate()-7);}
  else if(range==='month'){d.setDate(d.getDate()-30);}
  else return null;
  return d.toISOString();
}

// ── API helpers ──────────────────────────────────────────────────────────
async function api(path,opts={}){
  const r=await fetch(BASE+path,opts);
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

// ── Load cameras sidebar ─────────────────────────────────────────────────
async function loadCameras(){
  try{
    const cameras=await api('/api/cameras');
    const nav=$('camera-nav');
    const total=cameras.reduce((s,c)=>s+c.total,0);
    $('badge-all').textContent=total;
    // keep "All" item, rebuild the rest
    const existingAll=nav.querySelector('[data-camera="all"]');
    nav.innerHTML='';
    nav.appendChild(existingAll);
    cameras.forEach(c=>{
      const el=document.createElement('div');
      el.className='cam-item'+(c.camera===currentCamera?' active':'');
      el.dataset.camera=c.camera;
      el.innerHTML=`<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.camera}</span>`+
                   `<span class="cam-badge">${c.total}</span>`;
      nav.appendChild(el);
    });
    nav.querySelectorAll('.cam-item').forEach(el=>el.addEventListener('click',()=>{
      currentCamera=el.dataset.camera;
      nav.querySelectorAll('.cam-item').forEach(x=>x.classList.remove('active'));
      el.classList.add('active');
      currentPage=0; $('clip-grid').innerHTML=''; loadClips(0);
    }));
  }catch(e){console.warn('loadCameras',e);}
}

// ── Load stats bar ────────────────────────────────────────────────────────
async function loadStats(){
  try{
    const s=await api('/api/stats');
    const bar=$('stats-bar');
    bar.innerHTML=
      `<div class="stat-chip">Today <strong>${s.today_count??0}</strong></div>`+
      `<div class="stat-chip">This week <strong>${s.week_count??0}</strong></div>`+
      `<div class="stat-chip">Total <strong>${s.total_count??0}</strong></div>`+
      `<div class="stat-chip">Starred <strong>${s.starred_count??0}</strong></div>`+
      `<div class="stat-chip">Library <strong>${((s.total_size_bytes??0)/1073741824).toFixed(2)} GB</strong></div>`;
    const di=$('storage-info');
    if(s.disk){
      di.innerHTML=`Used: ${s.disk.used_mb} MB<br>Free: ${s.disk.free_gb} GB`;
    }
  }catch(e){console.warn('loadStats',e);}
}

// ── Build clip card ────────────────────────────────────────────────────────
function clipCard(c){
  const thumb=c.id?`${BASE}/api/clips/${c.id}/thumb`:'';
  const starBadge=c.starred?'<div class="star-badge">★</div>':'';
  const dur=c.duration?`<div class="clip-duration">${fmt_dur(c.duration)}</div>`:'';
  const tags=(c.tags||[]).map(t=>`<span class="tag-pill">${t}</span>`).join('');
  const src=c.source?`<span class="source-pill">${c.source}</span>`:'';
  const ts=fmt_ts(c.timestamp);
  return `
<div class="clip-card" data-id="${c.id}">
  <div class="thumb-wrap">
    ${thumb?`<img src="${thumb}" loading="lazy" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
     <div class="no-thumb" style="display:none">🎬</div>`
           :`<div class="no-thumb">🎬</div>`}
    ${dur}${starBadge}
  </div>
  <div class="clip-info">
    <div class="clip-camera">${c.camera}</div>
    <div class="clip-time">${ts}</div>
    <div class="clip-meta">${src}<span>${fmt_size(c.size_bytes)}</span>${tags}</div>
  </div>
</div>`;
}

// ── Load clips grid ────────────────────────────────────────────────────────
async function loadClips(page=0){
  if(page===0) $('clip-grid').innerHTML='<div style="grid-column:1/-1;padding:2rem;text-align:center;color:var(--muted)">Loading…</div>';
  const params=new URLSearchParams({limit:PAGE_SIZE,offset:page*PAGE_SIZE});
  if(currentCamera!=='all') params.set('camera',currentCamera);
  const sr=$('search').value.trim(); if(sr) params.set('search',sr);
  const dr=since_date($('date-range').value); if(dr) params.set('since',dr);
  if($('starred-only').checked) params.set('starred','1');
  const src=$('source-filter').value; if(src) params.set('source',src);
  try{
    const clips=await api(`/api/clips?${params}`);
    const grid=$('clip-grid');
    if(page===0) grid.innerHTML='';
    if(!clips.length&&page===0){
      grid.innerHTML='<div class="empty"><span class="icon">📭</span>No clips found</div>';
      $('load-more').style.display='none'; return;
    }
    clips.forEach(c=>{ const tmp=document.createElement('div'); tmp.innerHTML=clipCard(c); grid.appendChild(tmp.firstElementChild); });
    grid.querySelectorAll('.clip-card:not([data-bound])').forEach(el=>{
      el.dataset.bound='1';
      el.addEventListener('click',()=>openModal(el.dataset.id));
    });
    $('load-more').style.display=clips.length<PAGE_SIZE?'none':'inline-flex';
    currentPage=page;
  }catch(e){console.error('loadClips',e);}
}

// ── Modal ──────────────────────────────────────────────────────────────────
async function openModal(clipId){
  currentClipId=clipId;
  try{
    const c=await api(`/api/clips/${clipId}`);
    currentTags=[...(c.tags||[])];
    const vid=$('modal-video');
    vid.src=`${BASE}/api/clips/${clipId}/stream`;
    vid.load();
    $('modal-title').textContent=`${c.camera} — ${fmt_ts(c.timestamp)}`;
    $('modal-meta').innerHTML=
      `<div>Camera</div><span>${c.camera}</span>`+
      `<div>Recorded</div><span>${fmt_ts(c.timestamp)}</span>`+
      `<div>Duration</div><span>${fmt_dur(c.duration)||'—'}</span>`+
      `<div>Size</div><span>${fmt_size(c.size_bytes)||'—'}</span>`+
      `<div>Source</div><span>${c.source||'—'}</span>`+
      `<div>Clip ID</div><span style="font-size:.75rem;word-break:break-all">${c.id}</span>`;
    updateStarBtn(c.starred);
    const dlLink=$('dl-link');
    dlLink.href=`${BASE}/api/clips/${clipId}/stream`;
    dlLink.download=`${c.camera}_${(c.timestamp||'').replace(/[:.]/g,'-')}.mp4`;
    renderTags();
    $('modal-bg').classList.add('open');
  }catch(e){console.error('openModal',e);}
}
function closeModal(){
  $('modal-bg').classList.remove('open');
  $('modal-video').pause();
  $('modal-video').src='';
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
    await saveTags(); renderTags();
  }));
}
async function saveTags(){
  if(!currentClipId) return;
  await api(`/api/clips/${currentClipId}/tags`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tags:currentTags})});
}

// ── Event listeners ─────────────────────────────────────────────────────
$('modal-close').addEventListener('click',closeModal);
$('modal-bg').addEventListener('click',e=>{if(e.target===$('modal-bg'))closeModal();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});

$('star-btn').addEventListener('click',async()=>{
  if(!currentClipId) return;
  const now=$('star-btn').dataset.starred==='1';
  const starred=!now;
  await api(`/api/clips/${currentClipId}/star`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({starred})});
  updateStarBtn(starred);
  toast(starred?'Starred ★':'Unstarred');
  // Refresh card in grid
  document.querySelectorAll(`.clip-card[data-id="${currentClipId}"]`).forEach(el=>{
    const badge=el.querySelector('.star-badge');
    if(starred&&!badge){const b=document.createElement('div');b.className='star-badge';b.textContent='★';el.querySelector('.thumb-wrap').prepend(b);}
    else if(!starred&&badge){badge.remove();}
  });
});

$('delete-btn').addEventListener('click',async()=>{
  if(!currentClipId||!confirm('Delete this clip permanently?')) return;
  await api(`/api/clips/${currentClipId}`,{method:'DELETE'});
  toast('Clip deleted');
  closeModal();
  document.querySelector(`.clip-card[data-id="${currentClipId}"]`)?.remove();
});

$('tag-input').addEventListener('keydown',async e=>{
  if(e.key==='Enter'){
    const v=e.target.value.trim();
    if(v&&!currentTags.includes(v)){currentTags.push(v); await saveTags(); renderTags();}
    e.target.value='';
  }
});

$('sync-btn').addEventListener('click',async()=>{
  $('sync-btn').disabled=true; $('sync-btn').textContent='Syncing…';
  try{
    await api('/api/download-now',{method:'POST'});
    toast('Download triggered — clips will appear shortly');
    setTimeout(()=>{ currentPage=0; loadClips(0); loadStats(); loadCameras(); },8000);
  }catch(e){toast('Failed to trigger sync');}
  finally{setTimeout(()=>{$('sync-btn').disabled=false;$('sync-btn').textContent='⬇ Sync Now';},3000);}
});

$('refresh-btn').addEventListener('click',()=>{ currentPage=0; loadAll(); });
$('load-more').addEventListener('click',()=>loadClips(currentPage+1));

// Debounced search / filter listeners
let _debounce; function debounce(fn){clearTimeout(_debounce);_debounce=setTimeout(fn,400);}
['search','date-range','starred-only','source-filter'].forEach(id=>{
  $(id).addEventListener(id==='search'?'input':'change',()=>{
    debounce(()=>{currentPage=0;$('clip-grid').innerHTML='';loadClips(0);});
  });
});

// ── Boot ────────────────────────────────────────────────────────────────
async function loadAll(){
  await Promise.all([loadStats(), loadCameras(), loadClips(0)]);
}
loadAll();
// Auto-refresh every 60 seconds.
setInterval(()=>{if(!$('modal-bg').classList.contains('open'))loadAll();},60000);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Media server class
# ---------------------------------------------------------------------------


class MediaServer:
    """aiohttp web server exposing a clip library API and browser UI."""

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
        starred = (
            True if starred_raw == "1"
            else False if starred_raw == "0"
            else None
        )

        clips = await self._db.get_clips(
            camera=q.get("camera") or None,
            since=q.get("since") or None,
            until=q.get("until") or None,
            starred=starred,
            source=q.get("source") or None,
            tag=q.get("tag") or None,
            search=q.get("search") or None,
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
        # Delete file from disk
        file_path = Path(clip["file_path"])
        if file_path.exists():
            try:
                file_path.unlink()
                # Also delete thumbnail if present
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
        except Exception:
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
        except Exception:
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
        # Inject disk stats if available
        disk_stats_raw = request.app.get("disk_stats")
        if disk_stats_raw:
            stats["disk"] = disk_stats_raw
        return web.json_response(stats)

    async def _handle_download_now(self, _request: web.Request) -> web.Response:
        if self._trigger_download:
            await self._trigger_download()
            return web.json_response({"triggered": True})
        # Fall back to touching the trigger file.
        try:
            Path("/data/trigger_download").touch()
        except OSError:
            pass
        return web.json_response({"triggered": True})
