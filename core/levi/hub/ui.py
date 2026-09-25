"""hub.ui: hand-rolled single-file web UI. No streamlit, no JS framework.

The original's surface was a 12-tab Streamlit app. Proven shape kept: a
tabbed console over the same organs. Machinery swapped: one HTML file,
vanilla CSS/JS, ``fetch()`` against our own API. Mobile-first — this is
how Chauncey drives the hub from his phone's browser.

Tabs: Dashboard · Agent · Alpha · Jobs · DemandPulse · Competition ·
Approvals · API. (The original's pricing tab is cut with the billing
theater; its browser-automation tab is honestly the Agent's fetch tool —
HTTP only, no fake browser.)
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hub — Alpha/Omega</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--fg:#e6edf3;--dim:#8b949e;--acc:#58a6ff;--ok:#3fb950;--warn:#d29922}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
header{padding:12px 16px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0}
nav{display:flex;gap:4px;flex-wrap:wrap;padding:8px 12px;border-bottom:1px solid var(--line)}
nav button{background:none;border:1px solid transparent;color:var(--dim);padding:8px 10px;border-radius:8px;font-size:14px}
nav button.on{color:var(--fg);border-color:var(--line);background:var(--panel)}
main{padding:14px;max-width:900px;margin:0 auto}
.tab{display:none}.tab.on{display:block}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;margin:10px 0}
input,textarea,select{width:100%;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px;font-size:15px;margin:6px 0}
button.go{background:var(--acc);color:#04121f;border:0;border-radius:8px;padding:10px 16px;font-size:15px;font-weight:600}
button.ghost{background:none;color:var(--acc);border:1px solid var(--line);border-radius:8px;padding:8px 12px}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);padding:10px;border-radius:8px;font-size:13px;max-height:50vh;overflow:auto}
.small{color:var(--dim);font-size:13px}
.pill{display:inline-block;padding:2px 8px;border-radius:20px;font-size:12px;border:1px solid var(--line);color:var(--dim)}
.pill.ok{color:var(--ok);border-color:var(--ok)}.pill.warn{color:var(--warn);border-color:var(--warn)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
#loginbar{margin-left:auto;display:flex;gap:8px;align-items:center}
#loginbar input{width:130px;margin:0;padding:8px}
</style>
</head>
<body>
<header>
<h1>&#937; Hub</h1><span class="small">Alpha/Omega &mdash; ours only</span>
<div id="loginbar">
<input id="user" placeholder="user" autocomplete="username">
<input id="pass" type="password" placeholder="password" autocomplete="current-password">
<button class="ghost" onclick="doLogin()">log in</button>
</div>
</header>
<nav id="tabs"></nav>
<main>
<div class="tab" id="t-dash"><h2>Dashboard</h2><div class="card"><button class="go" onclick="api('GET','/api/status',null,show)">status</button> <button class="go" onclick="api('POST','/api/cycle/run',{goal:''},show)">run cycle</button></div><div class="card"><h3>Result</h3><pre id="out">—</pre></div></div>
<div class="tab" id="t-agent"><h2>Agent</h2><div class="card"><input id="task" placeholder="task, e.g. fetch https://example.com"><div class="row"><button class="go" onclick="api('POST','/api/agent/run',{task:val('task')},show)">run</button><button class="ghost" onclick="api('GET','/api/agent/heartbeat',null,show)">heartbeat</button></div><p class="small">Shell runs need an approved HITL request first. Nothing consequential self-applies.</p></div><div class="card"><h3>Result</h3><pre id="out2">—</pre></div></div>
<div class="tab" id="t-alpha"><h2>Alpha &mdash; creation lab</h2><div class="card"><textarea id="prompt" rows="3" placeholder="describe the thing to build, e.g. todo list web app"></textarea><input id="dest" placeholder="build destination dir (absolute path)"><div class="row"><button class="ghost" onclick="api('POST','/api/alpha/design',{prompt:val('prompt')},show3)">design</button><button class="ghost" onclick="api('POST','/api/alpha/preview',{prompt:val('prompt')},show3)">preview</button><button class="go" onclick="api('POST','/api/alpha/create',{prompt:val('prompt'),dest:val('dest')},show3)">create (asks approval)</button></div><p class="small">Create opens a HITL approval; nothing is written until you approve it.</p></div><div class="card"><h3>Result</h3><pre id="out3">—</pre></div></div>
<div class="tab" id="t-jobs"><h2>Jobs</h2><div class="card"><input id="jq" placeholder="query, e.g. python remote"><div class="row"><button class="go" onclick="api('GET','/api/jobs/search?q='+enc(val('jq')),null,show4)">search keyless boards</button></div></div><div class="card"><h3>Result</h3><pre id="out4">—</pre></div></div>
<div class="tab" id="t-pulse"><h2>DemandPulse</h2><div class="card"><input id="pq" placeholder="scan query"><div class="row"><button class="go" onclick="api('POST','/api/pulse/scan',{query:val('pq')},show5)">scan</button><button class="ghost" onclick="api('GET','/api/pulse/heatmap',null,show5)">heatmap</button></div></div><div class="card"><h3>Result</h3><pre id="out5">—</pre></div></div>
<div class="tab" id="t-comp"><h2>Competition</h2><div class="card"><div class="row"><button class="go" onclick="api('GET','/api/competition/changes',null,show6)">changes</button><button class="ghost" onclick="api('GET','/api/competition/gaps',null,show6)">gap matrix</button><button class="ghost" onclick="api('GET','/api/competition/propose',null,show6)">propose upgrades</button></div><p class="small">Proposals are advisory HYPOTHESIS — they never self-apply.</p></div><div class="card"><h3>Result</h3><pre id="out6">—</pre></div></div>
<div class="tab" id="t-approvals"><h2>Approvals</h2><div class="card"><button class="go" onclick="api('GET','/api/hitl/pending',null,show7)">pending</button><div id="pendlist"></div></div><div class="card"><h3>Result</h3><pre id="out7">—</pre></div></div>
<div class="tab" id="t-api"><h2>API</h2><div class="card"><p class="small">JSON over HTTP. Bearer token required except <code>/</code> and <code>/api/status</code>.</p><pre>GET  /api/status  /api/agent/heartbeat  /api/jobs/search?q=
     /api/pulse/heatmap  /api/competition/changes|gaps|propose
     /api/hitl/pending
POST /api/auth/register|login|logout  /api/agent/run
     /api/alpha/design|preview|create  /api/jobs/stage
     /api/pulse/scan  /api/competition/track
     /api/hitl/decide  /api/cycle/run</pre></div></div>
</main>
<script>
let TOK=localStorage.getItem('hubtok')||'';
const TABS=[['dash','Dashboard'],['agent','Agent'],['alpha','Alpha'],['jobs','Jobs'],['pulse','DemandPulse'],['comp','Competition'],['approvals','Approvals'],['api','API']];
const nav=document.getElementById('tabs');
TABS.forEach(([id,label],i)=>{const b=document.createElement('button');b.textContent=label;b.onclick=()=>show_tab(id);if(i==0)b.classList.add('on');nav.appendChild(b);});
function show_tab(id){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));document.getElementById('t-'+id).classList.add('on');[...nav.children].forEach((b,i)=>b.classList.toggle('on',TABS[i][0]==id));if(id=='approvals')api('GET','/api/hitl/pending',null,renderPend);}
function val(id){return document.getElementById(id).value}
function enc(s){return encodeURIComponent(s)}
function show(o){document.getElementById('out').textContent=JSON.stringify(o,null,2)}
function show2(o){document.getElementById('out2').textContent=JSON.stringify(o,null,2)}
function show3(o){document.getElementById('out3').textContent=JSON.stringify(o,null,2)}
function show4(o){document.getElementById('out4').textContent=JSON.stringify(o,null,2)}
function show5(o){const e=document.getElementById('out5');e.textContent=typeof o=='string'?o.slice(0,8000):JSON.stringify(o,null,2).slice(0,8000)}
function show6(o){const e=document.getElementById('out6');e.textContent=JSON.stringify(o,null,2).slice(0,8000)}
function show7(o){document.getElementById('out7').textContent=JSON.stringify(o,null,2)}
async function api(m,p,body,cb){
  const h={'Content-Type':'application/json'};if(TOK)h['Authorization']='Bearer '+TOK;
  const r=await fetch(p,{method:m,headers:h,body:body?JSON.stringify(body):undefined});
  const t=await r.text();let o;try{o=JSON.parse(t)}catch(e){o=t}
  (cb||show)(o);
}
async function doLogin(){
  const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:val('user'),password:val('pass')})});
  const o=await r.json();
  if(o.token){TOK=o.token;localStorage.setItem('hubtok',TOK);alert('logged in as '+o.username)}else alert('login failed: '+(o.error||r.status));
}
function renderPend(o){
  const d=document.getElementById('pendlist');if(!o||!o.pending||!o.pending.length){d.innerHTML='<p class="small">nothing pending</p>';return}
  d.innerHTML=o.pending.map(p=>'<div class="card"><span class="pill warn">pending</span> <b>#'+p.id+'</b> '+p.kind+'<pre>'+JSON.stringify(p.detail,null,2).slice(0,600)+'</pre><div class="row"><button class="go" onclick="decide('+p.id+',true)">approve</button><button class="ghost" onclick="decide('+p.id+',false)">reject</button></div></div>').join('');
}
async function decide(id,ok){await api('POST','/api/hitl/decide',{id:id,approved:ok},()=>api('GET','/api/hitl/pending',null,renderPend));}
</script>
</body>
</html>
"""
