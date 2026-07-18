# flake8: noqa: E501
from __future__ import annotations

import html
import secrets
from pathlib import Path

from .service import KernelService


def _dashboard() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>DataBossX Command Center</title>
<style>
:root{--ink:#161b18;--paper:#f3efe3;--line:#b9b09d;--oil:#183c33;--signal:#d06b32;--muted:#6d716c}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 Georgia,serif}
header{background:var(--oil);color:#fff;padding:28px 5vw;border-bottom:7px solid var(--signal)}
h1{margin:0;font:700 34px/1 "Courier New",monospace;letter-spacing:-2px}.eyebrow{font:11px "Courier New";letter-spacing:3px;color:#d7cdb8}
.shell{max-width:1500px;margin:auto;padding:26px 5vw}.status{display:flex;gap:12px;align-items:center;margin-bottom:20px}
.lamp{width:11px;height:11px;border-radius:50%;background:#999}.lamp.ok{background:#55b978;box-shadow:0 0 0 4px #55b97833}
.grid{display:grid;grid-template-columns:330px 1fr;gap:20px}.panel{background:#fffdf7;border:1px solid var(--line);box-shadow:4px 4px 0 #d8d0be;padding:20px}
h2{font:700 15px "Courier New";text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid var(--ink);padding-bottom:8px}
button,input,textarea{font:14px "Courier New";border:1px solid var(--ink);padding:10px;background:#fff}button{cursor:pointer;background:var(--ink);color:white}
button.accent{background:var(--signal);border-color:var(--signal)}button:disabled{opacity:.45;cursor:not-allowed}
input,textarea{width:100%;margin-bottom:8px}textarea{min-height:220px}.project{border-bottom:1px solid var(--line);padding:10px 0;cursor:pointer}.project:hover{color:var(--signal)}
.project.active{font-weight:bold;color:var(--oil)}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;border-bottom:1px solid #ddd5c5;padding:7px;vertical-align:top}
th{font:700 11px "Courier New";text-transform:uppercase}.hash{font:11px "Courier New";word-break:break-all;color:var(--muted)}
.tabs{display:flex;gap:3px;margin:18px 0 0}.tabs button{background:#dcd4c2;color:var(--ink);border:0}.tabs button.active{background:var(--oil);color:#fff}
.view{display:none;margin-top:14px}.view.active{display:block}.empty{padding:30px;text-align:center;color:var(--muted);border:1px dashed var(--line)}
.badge{font:10px "Courier New";padding:3px 6px;background:#e7e0d1}.warn{color:#9c3f18}.excerpt{white-space:pre-wrap;max-width:700px}
@media(max-width:850px){.grid{grid-template-columns:1fr}h1{font-size:27px}}
</style></head><body>
<header><div class="eyebrow">LOCAL EVIDENCE / EXACT RECORD / HUMAN RELEASE</div><h1>DATABOSSX COMMAND CENTER</h1></header>
<main class="shell"><div class="status"><span id="lamp" class="lamp"></span><span id="health">Starting trusted kernel…</span></div>
<div class="grid"><aside class="panel"><h2>Projects</h2><button class="accent" onclick="createDemo()">Create safe demo</button>
<div style="height:12px"></div><input id="name" placeholder="Project name"><input id="path" placeholder="D:\\DataBoss\\Project folder">
<button onclick="addProject()">Register read-only folder</button><div id="projects"></div></aside>
<section class="panel"><h2 id="project-title">Select a project</h2><div class="toolbar">
<button id="ingest" disabled onclick="ingest()">Copy + hash evidence</button><button id="run" disabled onclick="runReport()">Build draft reports</button></div>
<div class="tabs"><button class="active" data-view="assets">Evidence</button><button data-view="search">Search</button><button data-view="title">Title Case</button><button data-view="runs">Reports</button><button data-view="audit">Audit</button></div>
<div id="assets" class="view active"></div><div id="search" class="view"><input id="query" placeholder="Search exact OCR/text evidence"><button onclick="search()">Search evidence</button><div id="results"></div></div>
<div id="title" class="view"><p>Import operator-reviewed records only. Every reviewed instrument must cite an evidence asset ID and exact character range.</p><textarea id="title-json" placeholder='{"name":"Title case","legal_description":"...","gross_acres":{"numerator":160,"denominator":1},"opening_ownership":[],"instruments":[]}'></textarea><button onclick="createTitleCase()">Import reviewed title case</button><div id="title-cases"></div><h2>Reviewer credential</h2><input id="reviewer-name" placeholder="Qualified examiner or attorney name"><input id="reviewer-new-pin" type="password" placeholder="Create PIN (6+ characters)"><button onclick="registerReviewer()">Register qualified examiner</button><div id="reviewers"></div><input id="reviewer-id" placeholder="Reviewer ID for approval"><input id="reviewer-pin" type="password" placeholder="Reviewer PIN for approval"></div>
<div id="runs" class="view"></div><div id="audit" class="view"></div></section></div></main>
<script>
const token=new URLSearchParams(location.hash.slice(1)).get('token')||sessionStorage.getItem('dbx-token')||'';
if(token)sessionStorage.setItem('dbx-token',token); history.replaceState(null,'',location.pathname);
let active=null; const headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};
async function api(path,options={}){const r=await fetch('/api/v1'+path,{...options,headers:{...headers,...options.headers}});
 if(!r.ok){let d=await r.json().catch(()=>({detail:r.statusText}));throw new Error(d.detail||'Request failed')}return r}
function busy(message){document.getElementById('health').textContent=message}
async function boot(){try{const h=await (await api('/health')).json();document.getElementById('lamp').className='lamp '+(h.status==='ok'?'ok':'');
 document.getElementById('health').textContent=`Kernel ${h.status} · audit ${h.audit_chain_valid?'verified':'FAILED'} · local only`;await loadProjects()}catch(e){busy(e.message)}}
async function loadProjects(){const items=await (await api('/projects')).json();const box=document.getElementById('projects');box.replaceChildren();for(const p of items){const item=document.createElement('div');item.className='project '+(active===p.id?'active':'');item.append(document.createTextNode(p.name),document.createElement('br'));const meta=document.createElement('span');meta.className='hash';meta.textContent=`${p.asset_count} evidence records · ${p.status}`;item.append(meta);item.addEventListener('click',()=>selectProject(p.id,p.name));box.append(item)}}
function esc(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function createDemo(){try{busy('Creating labeled synthetic project…');const p=await (await api('/projects/synthetic',{method:'POST'})).json();await loadProjects();await selectProject(p.id,p.name)}catch(e){alert(e.message)}}
async function addProject(){try{const p=await (await api('/projects',{method:'POST',body:JSON.stringify({name:name.value,source_root:path.value})})).json();await loadProjects();await selectProject(p.id,p.name)}catch(e){alert(e.message)}}
async function selectProject(id,name){active=id;document.getElementById('project-title').textContent=name;ingest.disabled=false;run.disabled=false;await loadProjects();await refresh()}
async function refresh(){if(!active)return;const [assets,runs,audit,cases,reviewers]=await Promise.all([api(`/projects/${active}/assets`).then(r=>r.json()),api(`/projects/${active}/runs`).then(r=>r.json()),api(`/projects/${active}/audit`).then(r=>r.json()),api(`/projects/${active}/title-cases`).then(r=>r.json()),api('/title-reviewers').then(r=>r.json())]);
 document.getElementById('assets').innerHTML=assets.length?`<table><tr><th>Source</th><th>Hash / custody</th><th>Extraction</th></tr>${assets.map(a=>`<tr><td>${esc(a.rel_path)}<br><span class="badge">${a.size_bytes} bytes</span><br><span class="hash">asset ${a.id}</span></td><td class="hash">${a.blob_sha256}<br>${a.custody_at}</td><td>${a.extraction_status}<br>${esc(a.extractor)} ${a.note?`<span class="warn">${esc(a.note)}</span>`:''}</td></tr>`).join('')}</table>`:'<div class="empty">No evidence ingested. Originals remain untouched.</div>';
 document.getElementById('title-cases').innerHTML=cases.map(c=>`<div class="panel"><b>${esc(c.name)}</b><br>${esc(c.legal_description)} · ${c.status}<br><button onclick="buildTitleCase('${c.id}')">Build exact examiner packet</button></div>`).join('')||'<div class="empty">No structured title case.</div>';
 document.getElementById('reviewers').innerHTML=reviewers.map(r=>`<div>${esc(r.display_name)} · ${r.role}<br><span class="hash">${r.id}</span></div>`).join('')||'<div class="empty">No credentialed reviewer. Approval is disabled.</div>';
 let html='';for(const r of runs){const arts=await api(`/runs/${r.id}/artifacts`).then(x=>x.json());let review='';if(r.pipeline==='title-examiner-packet'&&r.status==='WAITING_HUMAN'){const p=await api(`/title-packages/${r.id}`).then(x=>x.json());review=`<div>${p.blocking_defect_count} blocking defect(s) · manifest <span class="hash">${p.package_manifest_sha256}</span></div>${p.blocking_defect_count===0?`<button onclick="reviewTitle('${r.id}','${p.package_manifest_sha256}')">Approve exact hash</button>`:'<span class="warn">Approval blocked until defects are resolved.</span>'}`}html+=`<h3>${r.pipeline} · ${r.status}</h3>${review}${arts.map(a=>`<div><a href="/api/v1/artifacts/${a.id}/download" data-id="${a.id}" onclick="downloadArtifact(event,this)">${esc(a.rel_path)}</a> <span class="hash">${a.blob_sha256.slice(0,16)}…</span></div>`).join('')}`}document.getElementById('runs').innerHTML=html||'<div class="empty">No report runs yet.</div>';
 document.getElementById('audit').innerHTML=audit.length?`<table><tr><th>Sequence</th><th>Event</th><th>Object</th><th>Chain</th></tr>${audit.map(e=>`<tr><td>${e.sequence}</td><td>${e.action}<br>${e.occurred_at}</td><td>${e.object_type}<br><span class="hash">${e.object_id}</span></td><td>${e.chain_valid?'VERIFIED':'FAILED'}</td></tr>`).join('')}</table>`:'<div class="empty">No events.</div>'}
async function ingest(){try{busy('Hashing and copying evidence into immutable vault…');await api(`/projects/${active}/ingests`,{method:'POST'});await refresh();await loadProjects();busy('Ingest complete · originals unchanged')}catch(e){alert(e.message);busy(e.message)}}
async function runReport(){try{busy('Building draft reports from verified vault copies…');await api(`/projects/${active}/runs/grocery`,{method:'POST'});await refresh();busy('Draft report artifacts verified and vaulted')}catch(e){alert(e.message);busy(e.message)}}
async function createTitleCase(){try{const payload=JSON.parse(document.getElementById('title-json').value);await api(`/projects/${active}/title-cases`,{method:'POST',body:JSON.stringify(payload)});await refresh();busy('Reviewed title records imported')}catch(e){alert(e.message)}}
async function buildTitleCase(id){try{busy('Calculating exact ownership and building XLSX/PDF packet…');await api(`/title-cases/${id}/packages`,{method:'POST'});await refresh();busy('Examiner packet built · human review required')}catch(e){alert(e.message);busy(e.message)}}
async function registerReviewer(){try{const display_name=document.getElementById('reviewer-name').value;const pin=document.getElementById('reviewer-new-pin').value;const reviewer=await (await api('/title-reviewers',{method:'POST',body:JSON.stringify({display_name,role:'QUALIFIED_EXAMINER',pin})})).json();document.getElementById('reviewer-id').value=reviewer.id;document.getElementById('reviewer-new-pin').value='';await refresh();busy('Credentialed reviewer registered')}catch(e){alert(e.message)}}
async function reviewTitle(id,hash){const reviewer_id=document.getElementById('reviewer-id').value;const reviewer_pin=document.getElementById('reviewer-pin').value;if(!reviewer_id||!reviewer_pin){alert('Enter reviewer ID and PIN on the Title Case tab.');return}if(!confirm('Approve this exact package hash? This does not certify an abstract or title opinion.'))return;try{await api(`/title-packages/${id}/review`,{method:'POST',body:JSON.stringify({package_manifest_sha256:hash,reviewer_id,reviewer_pin,decision:'APPROVE',notes:'Approved in local Command Center'})});document.getElementById('reviewer-pin').value='';await refresh();busy('Exact package hash approved for export')}catch(e){alert(e.message)}}
async function search(){try{const rows=await (await api(`/projects/${active}/search?q=${encodeURIComponent(query.value)}`)).json();results.innerHTML=rows.map(r=>`<div class="panel"><b>${esc(r.rel_path)}</b><div class="excerpt">${esc(r.excerpt)}</div><div class="hash">${r.source_sha256} · chars ${r.char_start}-${r.char_end}</div></div>`).join('')||'<div class="empty">No source-supported match.</div>'}catch(e){alert(e.message)}}
async function downloadArtifact(ev,a){ev.preventDefault();const r=await api(`/artifacts/${a.dataset.id}/download`);const blob=await r.blob();const url=URL.createObjectURL(blob);const x=document.createElement('a');x.href=url;x.download=a.textContent.trim();x.click();URL.revokeObjectURL(url)}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tabs button,.view').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.view).classList.add('active')});boot();
</script></body></html>"""


def create_app(service: KernelService, token: str | None = None):
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
        from fastapi.responses import FileResponse, HTMLResponse
        from starlette.middleware.trustedhost import TrustedHostMiddleware
    except ImportError as exc:
        raise RuntimeError("Install requirements-kernel.txt to run the dashboard") from exc

    api_token = token or secrets.token_urlsafe(32)
    app = FastAPI(title="DataBossX Local Control API", version="0.1.0")
    app.state.token = api_token
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )

    def authorize(authorization: str | None = Header(default=None)) -> None:
        expected = f"Bearer {api_token}"
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Local session token required")

    def handle_error(exc: Exception) -> None:
        if isinstance(exc, KeyError):
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
        if isinstance(exc, (ValueError, RuntimeError)):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise exc

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return _dashboard()

    @app.get("/api/v1/health")
    def health(_: None = Depends(authorize)):
        return service.health()

    @app.get("/api/v1/projects")
    def projects(_: None = Depends(authorize)):
        return service.list_projects()

    @app.post("/api/v1/projects")
    def create_project(payload: dict, _: None = Depends(authorize)):
        try:
            return service.create_project(payload.get("name", ""), payload.get("source_root", ""))
        except Exception as exc:
            handle_error(exc)

    @app.post("/api/v1/projects/synthetic")
    def create_synthetic(_: None = Depends(authorize)):
        return service.create_synthetic_project()

    @app.post("/api/v1/projects/{project_id}/ingests")
    def ingest(project_id: str, _: None = Depends(authorize)):
        try:
            return service.ingest_project(project_id)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/projects/{project_id}/assets")
    def assets(project_id: str, _: None = Depends(authorize)):
        try:
            return service.list_assets(project_id)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/projects/{project_id}/search")
    def search(project_id: str, q: str, _: None = Depends(authorize)):
        try:
            return service.search(project_id, q)
        except Exception as exc:
            handle_error(exc)

    @app.post("/api/v1/projects/{project_id}/runs/grocery")
    def run_grocery(project_id: str, _: None = Depends(authorize)):
        try:
            return service.run_grocery(project_id)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/projects/{project_id}/runs")
    def runs(project_id: str, _: None = Depends(authorize)):
        try:
            return service.list_runs(project_id)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/projects/{project_id}/title-cases")
    def title_cases(project_id: str, _: None = Depends(authorize)):
        try:
            return service.list_title_cases(project_id)
        except Exception as exc:
            handle_error(exc)

    @app.post("/api/v1/projects/{project_id}/title-cases")
    def create_title_case(
        project_id: str, payload: dict, _: None = Depends(authorize)
    ):
        try:
            return service.create_title_case(project_id, payload)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/title-cases/{case_id}")
    def title_case(case_id: str, _: None = Depends(authorize)):
        try:
            return service.get_title_case(case_id)
        except Exception as exc:
            handle_error(exc)

    @app.post("/api/v1/title-cases/{case_id}/packages")
    def build_title_package(case_id: str, _: None = Depends(authorize)):
        try:
            return service.build_title_package(case_id)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/title-packages/{run_id}")
    def title_package(run_id: str, _: None = Depends(authorize)):
        try:
            return service.get_title_package(run_id)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/title-reviewers")
    def title_reviewers(_: None = Depends(authorize)):
        return service.list_title_reviewers()

    @app.post("/api/v1/title-reviewers")
    def register_title_reviewer(payload: dict, _: None = Depends(authorize)):
        try:
            return service.register_title_reviewer(
                str(payload.get("display_name", "")),
                str(payload.get("role", "")),
                str(payload.get("pin", "")),
            )
        except Exception as exc:
            handle_error(exc)

    @app.post("/api/v1/title-packages/{run_id}/review")
    def review_title_package(
        run_id: str, payload: dict, _: None = Depends(authorize)
    ):
        try:
            return service.review_title_package(
                run_id,
                str(payload.get("package_manifest_sha256", "")),
                str(payload.get("reviewer_id", "")),
                str(payload.get("reviewer_pin", "")),
                str(payload.get("decision", "")),
                str(payload.get("notes", "")),
            )
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/runs/{run_id}/artifacts")
    def artifacts(run_id: str, _: None = Depends(authorize)):
        try:
            return service.list_artifacts(run_id)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/projects/{project_id}/audit")
    def audit(project_id: str, _: None = Depends(authorize)):
        try:
            return service.audit_events(project_id)
        except Exception as exc:
            handle_error(exc)

    @app.get("/api/v1/artifacts/{artifact_id}/download")
    def download(artifact_id: str, _: None = Depends(authorize)):
        try:
            artifact, path = service.artifact(artifact_id)
            safe_name = Path(artifact["rel_path"]).name
            return FileResponse(
                path,
                media_type=artifact["media_type"],
                filename=html.escape(safe_name, quote=True),
            )
        except Exception as exc:
            handle_error(exc)

    return app
