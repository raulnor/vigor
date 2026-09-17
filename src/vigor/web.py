"""Local web view over the Strava export."""
import argparse
import csv
import json
import sys
from pathlib import Path

from flask import Flask, render_template_string

from vigor.db import load_activities, load_shoes
from vigor.paths import data_dir

app = Flask(__name__)


@app.get("/")
def index():
    path = data_dir() / "activities.csv"
    if not path or not Path(path).exists():
        return render_template_string(EMPTY, path=path)
    acts = load_activities(path)
    data = json.dumps(acts).replace("<", "\\u003c")
    return render_template_string(PAGE, data_json=data, n=len(acts), path=str(path))


@app.get("/shoes")
def shoes():
    path = data_dir() / "activities.csv"
    if not path or not Path(path).exists():
        return render_template_string(EMPTY, path=path)
    shoes_data = load_shoes(path)
    # Sort by newest workout (most recent first), with None values at the end
    shoes_data.sort(key=lambda s: s["newest"] or "", reverse=True)
    data_json = json.dumps(shoes_data).replace("<", "\\u003c")
    return render_template_string(SHOES_PAGE, data_json=data_json, n=len(shoes_data))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vigor web")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5006)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args(argv)
    print(f"vigor.web: http://{args.host}:{args.port}", file=sys.stderr)
    if args.debug:
        app.run(host=args.host, port=args.port, debug=True)
    else:
        from waitress import serve
        serve(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())


EMPTY = """<!doctype html><meta charset=utf-8><title>vigor</title>
<body style="font-family:system-ui;max-width:640px;margin:4rem auto;color:#1a1815">
<h1 style="font-weight:600">No activities.csv found.</h1>
<p style="color:#6e6a63">
  Checked the following location: <code>{{ path }}</code>
</p>
"""

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vigor — runs</title>
<style>
 :root{--paper:#FBFAF8;--ink:#1A1815;--muted:#6E6A63;--faint:#9A968E;
   --rule:#E8E4DC;--rule-s:#D6D0C6;--accent:#295A6B;--accent-soft:rgba(41,90,107,.09);
   --serif:"Iowan Old Style",Charter,Palatino,Georgia,serif;
   --ui:-apple-system,"SF Pro Text","Segoe UI",Roboto,system-ui,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
   font-family:var(--ui);font-size:14px;padding:0 clamp(16px,4vw,48px) 96px}
 .wrap{max-width:1080px;margin:0 auto}
 .nav{display:flex;gap:24px;padding:20px 0 0;border-bottom:1px solid var(--rule);margin-bottom:20px}
 .nav a{color:var(--muted);text-decoration:none;padding:10px 0;border-bottom:2px solid transparent;font-size:13px;font-weight:500}
 .nav a:hover{color:var(--accent)}
 .nav a.active{color:var(--ink);border-bottom-color:var(--accent)}
 .top{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;
   padding:20px 0;border-bottom:1px solid var(--rule-s);flex-wrap:wrap}
 .mark{font-family:var(--serif);font-size:clamp(26px,4vw,34px);font-weight:600;line-height:1}
 .mark small{display:block;font-family:var(--ui);font-weight:400;font-size:12px;color:var(--faint);margin-top:8px}
 .readout{display:grid;grid-template-columns:auto 1fr;gap:clamp(20px,5vw,56px);
   align-items:center;padding:22px 0 26px;border-bottom:1px solid var(--rule)}
 .stats{display:flex;gap:clamp(20px,4vw,44px);flex-wrap:wrap}
 .stat .n{font-family:var(--serif);font-size:clamp(20px,3vw,28px);line-height:1;font-variant-numeric:tabular-nums}
 .stat .k{font-size:11.5px;color:var(--faint);margin-top:6px}
 .bars svg{display:block;width:100%;height:64px;overflow:visible}
 .controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:18px 0}
 .search{flex:1 1 220px;min-width:160px;font:inherit;font-size:13px;background:#fff;
   border:1px solid var(--rule-s);border-radius:2px;padding:8px 11px;color:var(--ink)}
 select{font:inherit;font-size:13px;background:#fff;border:1px solid var(--rule-s);
   border-radius:2px;padding:8px 9px;color:var(--ink);cursor:pointer}
 .search:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}
 .toggle{display:inline-flex;border:1px solid var(--rule-s);border-radius:2px;overflow:hidden}
 .toggle button{font:inherit;font-size:12.5px;color:var(--muted);background:#fff;border:0;padding:8px 12px;cursor:pointer}
 .toggle button[aria-pressed="true"]{background:var(--accent);color:#fff}
 .tablewrap{overflow-x:auto}
 table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
 thead th{text-align:left;font-weight:500;font-size:11.5px;color:var(--muted);
   padding:9px 12px 9px 0;border-bottom:1px solid var(--rule-s);white-space:nowrap;cursor:pointer;user-select:none}
 thead th.num{text-align:right;padding-right:12px}
 th .car{color:var(--accent);font-size:10px;margin-left:3px;visibility:hidden}
 th[aria-sort] .car{visibility:visible}
 th[aria-sort="ascending"] .car::after{content:"\25B2"}
 th[aria-sort="descending"] .car::after{content:"\25BC"}
 tbody td{padding:8px 12px 8px 0;border-bottom:1px solid var(--rule);font-size:13px;white-space:nowrap}
 td.num{text-align:right;padding-right:12px;color:#33302B}
 td.dim{color:var(--faint)}
 td.name{white-space:normal;min-width:200px;max-width:340px}
 tbody tr:hover{background:var(--accent-soft)}
 td.name a{color:var(--ink);text-decoration:none;border-bottom:1px solid transparent}
 td.name a:hover{border-bottom-color:var(--accent);color:var(--accent)}
 .type-tag{font-size:12px;color:var(--muted)}
 @media (max-width:640px){.readout{grid-template-columns:1fr}.c-hide{display:none}}
</style></head>
<body><div class="wrap">
 <nav class="nav">
   <a href="/" class="active">Activities</a>
   <a href="/shoes">Shoes</a>
 </nav>
 <header class="top">
   <div class="mark">Runs<small>{{ n }} activities · {{ path }}</small></div>
 </header>
 <section class="readout">
   <div class="stats" id="stats"></div>
   <div class="bars"><svg id="yearbars" viewBox="0 0 600 64" preserveAspectRatio="none" aria-label="Distance by year"></svg></div>
 </section>
 <section class="controls">
   <input class="search" id="q" type="search" placeholder="Search name or type…" autocomplete="off">
   <select id="ftype"><option value="">All types</option></select>
   <select id="fyear"><option value="">All years</option></select>
   <select id="ftag"><option value="">All activities</option><option value="race">Races only</option></select>
   <div class="toggle" role="group" aria-label="Distance unit">
     <button id="umi" aria-pressed="true">mi</button><button id="ukm" aria-pressed="false">km</button>
   </div>
 </section>
 <div class="tablewrap"><table><thead><tr id="head"></tr></thead><tbody id="body"></tbody></table></div>
</div>
<script>
"use strict";
const DATA = {{ data_json|safe }};
const MI=1609.344, KM=1000;
let ALL=DATA.map(a=>({...a, elevM:a.elev_m, paceSecPerM:a.pace_s_per_m}));
let unit="mi", sortKey="date", sortDir=-1;
const $=id=>document.getElementById(id);
const pad=(n,w=2)=>String(n).padStart(w,"0");
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fmtPace(sp){ if(sp==null||!isFinite(sp))return "—"; const m=Math.floor(sp/60),s=Math.round(sp%60); return s===60?`${m+1}:00`:`${m}:${pad(s)}`; }
function fmtTime(sec){ if(sec==null)return "—"; sec=Math.round(sec); const h=Math.floor(sec/3600),m=Math.floor(sec%3600/60),s=sec%60; return h?`${h}:${pad(m)}:${pad(s)}`:`${m}:${pad(s)}`; }
const commas=n=>n.toLocaleString(undefined,{maximumFractionDigits:0});

const COLS=[
 {key:"date",label:"Date",num:false,cls:"",val:a=>a.ts??-Infinity,cell:a=>`<td class="${a.ts?'':'dim'}">${a.date_str}</td>`},
 {key:"name",label:"Activity",num:false,cls:"",val:a=>a.name.toLowerCase(),cell:a=>{const t=esc(a.name);const l=a.id?`https://www.strava.com/activities/${encodeURIComponent(a.id)}`:null;return `<td class="name">${l?`<a href="${l}" target="_blank" rel="noopener">${t}</a>`:t}</td>`;}},
 {key:"type",label:"Type",num:false,cls:"c-hide",val:a=>a.type.toLowerCase(),cell:a=>`<td class="c-hide"><span class="type-tag">${esc(a.type)}</span></td>`},
 {key:"dist",label:"Dist",num:true,cls:"",val:a=>a.meters??-Infinity,cell:a=>`<td class="num">${a.meters!=null?(a.meters/(unit==="mi"?MI:KM)).toFixed(2):"—"}</td>`},
 {key:"time",label:"Time",num:true,cls:"",val:a=>a.moving??-Infinity,cell:a=>`<td class="num">${fmtTime(a.moving)}</td>`},
 {key:"pace",label:"Pace",num:true,cls:"",val:a=>a.paceSecPerM??Infinity,cell:a=>`<td class="num">${fmtPace(a.paceSecPerM!=null?a.paceSecPerM*(unit==="mi"?MI:KM):null)}</td>`},
 {key:"ahr",label:"Avg HR",num:true,cls:"c-hide",val:a=>a.ahr??-Infinity,cell:a=>`<td class="num c-hide ${a.ahr==null?'dim':''}">${a.ahr!=null?Math.round(a.ahr):"—"}</td>`},
 {key:"elev",label:"Elev",num:true,cls:"c-hide",val:a=>a.elevM??-Infinity,cell:a=>{const v=a.elevM==null?null:(unit==="mi"?a.elevM*3.28084:a.elevM);return `<td class="num c-hide ${v==null?'dim':''}">${v!=null?Math.round(v):"—"}</td>`;}},
];

function currentRows(){
 const q=$("q").value.trim().toLowerCase(),ft=$("ftype").value,fy=$("fyear").value,ftag=$("ftag").value;
 let rows=ALL.filter(a=>{ if(ft&&a.type!==ft)return false; if(fy&&String(a.year)!==fy)return false;
   if(ftag==="race"&&!a.race)return false;
   if(q&&!(a.name.toLowerCase().includes(q)||a.type.toLowerCase().includes(q)))return false; return true; });
 const c=COLS.find(c=>c.key===sortKey)||COLS[0];
 rows.sort((a,b)=>{const x=c.val(a),y=c.val(b);return x<y?-sortDir:x>y?sortDir:0;});
 return rows;
}
function renderHead(){
 const eu=unit==="mi"?"ft":"m";
 $("head").innerHTML=COLS.map(c=>{let l=c.label;if(c.key==="dist")l=`Dist (${unit})`;if(c.key==="pace")l=`Pace /${unit}`;if(c.key==="elev")l=`Elev (${eu})`;
   const s=c.key===sortKey,a=s?` aria-sort="${sortDir===1?"ascending":"descending"}"`:"";
   return `<th class="${c.num?"num ":""}${c.cls}" data-key="${c.key}"${a}>${l}<span class="car"></span></th>`;}).join("");
 $("head").querySelectorAll("th").forEach(th=>th.onclick=()=>{const k=th.dataset.key;
   if(k===sortKey)sortDir*=-1;else{sortKey=k;sortDir=(k==="name"||k==="type")?1:-1;}render();});
}
function render(){
 const rows=currentRows();renderHead();
 $("body").innerHTML=rows.map(a=>`<tr>${COLS.map(c=>c.cell(a)).join("")}</tr>`).join("");
 renderStats(rows);renderBars(rows);
}
function renderStats(rows){
 const div=unit==="mi"?MI:KM;
 const tm=rows.reduce((s,a)=>s+(a.meters||0),0),tt=rows.reduce((s,a)=>s+(a.moving||0),0);
 const yrs=rows.map(a=>a.year).filter(Boolean).sort();
 const span=yrs.length?`${yrs[0]}–${yrs[yrs.length-1]}`:"—";
 const st=(n,k)=>`<div class="stat"><div class="n">${n}</div><div class="k">${k}</div></div>`;
 $("stats").innerHTML=st(commas(rows.length),"activities")+st(commas(tm/div)+" "+unit,"distance")+
   st((fmtTime(tt).split(":").slice(0,-1).join(":")||"0"),"hours (h:mm)")+st(span,"span");
}
function renderBars(rows){
 const div=unit==="mi"?MI:KM,by={};
 rows.forEach(a=>{if(a.year)by[a.year]=(by[a.year]||0)+(a.meters||0);});
 const years=Object.keys(by).map(Number).sort((a,b)=>a-b),svg=$("yearbars");
 if(!years.length){svg.innerHTML="";return;}
 const W=600,H=64,base=H-14,top=6,max=Math.max(...years.map(y=>by[y])),bw=W/years.length,iw=Math.min(bw-8,40);
 svg.innerHTML=years.map((y,i)=>{const h=max?(by[y]/max)*(base-top):0,x=i*bw+(bw-iw)/2,yt=base-h,cur=i===years.length-1;
   return `<rect x="${x.toFixed(1)}" y="${yt.toFixed(1)}" width="${iw.toFixed(1)}" height="${Math.max(h,1).toFixed(1)}" fill="${cur?"var(--accent)":"#CFC8BC"}" rx="1"></rect>`+
     `<text x="${(x+iw/2).toFixed(1)}" y="${H-2}" text-anchor="middle" font-size="9" fill="var(--faint)">${String(y).slice(2)}</text>`;}).join("");
}
(function init(){
 const types=[...new Set(ALL.map(a=>a.type))].sort();
 $("ftype").innerHTML=`<option value="">All types</option>`+types.map(t=>`<option>${esc(t)}</option>`).join("");
 const years=[...new Set(ALL.map(a=>a.year).filter(Boolean))].sort((a,b)=>b-a);
 $("fyear").innerHTML=`<option value="">All years</option>`+years.map(y=>`<option>${y}</option>`).join("");
 $("q").oninput=render;$("ftype").onchange=render;$("fyear").onchange=render;$("ftag").onchange=render;
 const su=u=>{unit=u;$("umi").setAttribute("aria-pressed",u==="mi");$("ukm").setAttribute("aria-pressed",u==="km");render();};
 $("umi").onclick=()=>su("mi");$("ukm").onclick=()=>su("km");
 render();
})();
</script>
</body></html>
"""

SHOES_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vigor — shoes</title>
<style>
 :root{--paper:#FBFAF8;--ink:#1A1815;--muted:#6E6A63;--faint:#9A968E;
   --rule:#E8E4DC;--rule-s:#D6D0C6;--accent:#295A6B;--accent-soft:rgba(41,90,107,.09);
   --serif:"Iowan Old Style",Charter,Palatino,Georgia,serif;
   --ui:-apple-system,"SF Pro Text","Segoe UI",Roboto,system-ui,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
   font-family:var(--ui);font-size:14px;padding:0 clamp(16px,4vw,48px) 96px}
 .wrap{max-width:1080px;margin:0 auto}
 .nav{display:flex;gap:24px;padding:20px 0 0;border-bottom:1px solid var(--rule);margin-bottom:20px}
 .nav a{color:var(--muted);text-decoration:none;padding:10px 0;border-bottom:2px solid transparent;font-size:13px;font-weight:500}
 .nav a:hover{color:var(--accent)}
 .nav a.active{color:var(--ink);border-bottom-color:var(--accent)}
 .top{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;
   padding:20px 0;border-bottom:1px solid var(--rule-s);flex-wrap:wrap}
 .mark{font-family:var(--serif);font-size:clamp(26px,4vw,34px);font-weight:600;line-height:1}
 .mark small{display:block;font-family:var(--ui);font-weight:400;font-size:12px;color:var(--faint);margin-top:8px}
 .controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:18px 0}
 .toggle{display:inline-flex;border:1px solid var(--rule-s);border-radius:2px;overflow:hidden}
 .toggle button{font:inherit;font-size:12.5px;color:var(--muted);background:#fff;border:0;padding:8px 12px;cursor:pointer}
 .toggle button[aria-pressed="true"]{background:var(--accent);color:#fff}
 .tablewrap{overflow-x:auto}
 table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
 thead th{text-align:left;font-weight:500;font-size:11.5px;color:var(--muted);
   padding:9px 12px 9px 0;border-bottom:1px solid var(--rule-s);white-space:nowrap}
 thead th.num{text-align:right;padding-right:12px}
 tbody td{padding:12px 12px 12px 0;border-bottom:1px solid var(--rule);font-size:13px}
 td.num{text-align:right;padding-right:12px;color:#33302B}
 td.brand{color:var(--muted);font-size:12px}
 tbody tr:hover{background:var(--accent-soft)}
</style></head>
<body><div class="wrap">
 <nav class="nav">
   <a href="/">Activities</a>
   <a href="/shoes" class="active">Shoes</a>
 </nav>
 <header class="top">
   <div class="mark">Shoes<small>{{ n }} shoes tracked</small></div>
 </header>
 <section class="controls">
   <div class="toggle" role="group" aria-label="Distance unit">
     <button id="umi" aria-pressed="true">mi</button><button id="ukm" aria-pressed="false">km</button>
   </div>
 </section>
 <div class="tablewrap">
   <table>
     <thead><tr>
       <th>Shoe</th>
       <th class="num">Distance</th>
       <th class="num">Activities</th>
       <th class="num">Oldest</th>
       <th class="num">Newest</th>
     </tr></thead>
     <tbody id="tbody"></tbody>
   </table>
 </div>
</div>
<script>
"use strict";
const DATA = {{ data_json|safe }};
const MI=1609.344, KM=1000;
let unit="mi";
const $=id=>document.getElementById(id);
const commas=n=>n.toLocaleString(undefined,{maximumFractionDigits:0});

function fmtDate(iso){
  if(!iso)return "—";
  const d=new Date(iso);
  const mon=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][d.getMonth()];
  return `${mon} ${d.getDate()}, ${d.getFullYear()}`;
}

function render(){
  const div=unit==="mi"?MI:KM;
  const rows=DATA.map(s=>{
    const dist=(s.meters/div).toFixed(0);
    return `<tr>
      <td>${esc(s.name)}</td>
      <td class="num">${commas(dist)} ${unit}</td>
      <td class="num">${commas(s.count)}</td>
      <td class="num">${fmtDate(s.oldest)}</td>
      <td class="num">${fmtDate(s.newest)}</td>
    </tr>`;
  }).join("");
  $("tbody").innerHTML=rows;
}

const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const su=u=>{unit=u;$("umi").setAttribute("aria-pressed",u==="mi");$("ukm").setAttribute("aria-pressed",u==="km");render();};
$("umi").onclick=()=>su("mi");
$("ukm").onclick=()=>su("km");
render();
</script>
</body></html>
"""