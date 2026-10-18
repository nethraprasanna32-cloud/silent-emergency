/* ================= BACKEND CONNECTION =================
 The UI uses the FastAPI service that serves this page.
 SED FastAPI endpoints (JSON):
  GET  /needs        [{id,type,x,y,area,pr,sig:[..],status:"detected"|"assigned"}]
  GET  /resources    [{id,name,type,qty,x,y,ngo}]
  GET  /volunteers   [{id,name,skill,x,y,free}]
  GET  /history      [{when,case_id,type,resource,volunteer,ngo}]
  GET  /stats        {week:[7 numbers, Mon..Sun]}
  GET  /needs/<id>/matches   [{res_id,res,ngo,vol_id,vol,km,qty,score,parts:{type,near,stock,vol}}]
  POST /scan         run need detection on the server
 POST /matches/assign {need_id,resource_id,volunteer_id,quantity,idempotency_key}
 The demo data below is used only when the backend can't be reached. */
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)],T=s=>s[0].toUpperCase()+s.slice(1),esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const API={base:(location.protocol==="file:"?"http://127.0.0.1:8000":location.origin),online:false,
 async req(p,o){const r=await fetch(this.base+p,o||{cache:"no-store"});if(!r.ok){let body={};try{body=await r.json()}catch(e){}throw Object.assign(new Error(body?.detail||body?.error?.message||`HTTP ${r.status}`),{status:r.status})}return r.status===204?null:r.json()},
 get(p){return this.req(p)},post(p,b){return this.req(p,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})})}};
const newIdempotencyKey=()=>globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}`;
/* ---------- demo data (used only when no backend answers) ---------- */
const DEMO={week:[3,5,4,9,6,2,4],
needs:[{id:1001,type:"food",x:150,y:120,area:"Ward 4, Riverside",pr:92,sig:["Elderly, lives alone","No ration pickup in 6 weeks"],status:"detected"},{id:1002,type:"medical",x:430,y:90,area:"Ward 9, Hill Colony",pr:84,sig:["Missed 3 clinic visits"],status:"detected"},{id:1003,type:"shelter",x:300,y:290,area:"Ward 2, Canal Side",pr:71,sig:["Eviction notice filed","Family of five"],status:"detected"}],
res:[{id:"r1",name:"Annapurna Food Bank",type:"food",qty:40,x:190,y:170,ngo:"Annapurna Trust"},{id:"r2",name:"Mobile Clinic Van",type:"medical",qty:6,x:380,y:140,ngo:"CareFirst NGO"},{id:"r3",name:"Night Shelter, Canal Rd",type:"shelter",qty:8,x:330,y:250,ngo:"Asha Foundation"},{id:"r4",name:"Community Kitchen",type:"food",qty:25,x:480,y:300,ngo:"Seva Samiti"},{id:"r5",name:"Pharmacy Stock Room",type:"medical",qty:12,x:120,y:260,ngo:"CareFirst NGO"},{id:"r6",name:"Relief Camp Tents",type:"shelter",qty:10,x:520,y:90,ngo:"Asha Foundation"}],
vols:[{id:"v1",name:"Meera K.",skill:"food",x:170,y:140,free:true},{id:"v2",name:"Arjun S.",skill:"medical",x:410,y:120,free:true},{id:"v3",name:"Divya R.",skill:"shelter",x:310,y:270,free:true},{id:"v4",name:"Imran A.",skill:"food",x:500,y:280,free:true},{id:"v5",name:"Lakshmi P.",skill:"medical",x:110,y:280,free:true},{id:"v6",name:"Karthik V.",skill:"shelter",x:540,y:120,free:true}],
hist:[{when:"Yesterday",case_id:998,type:"food",resource:"Community Kitchen",volunteer:"Imran A.",ngo:"Seva Samiti"},{when:"Yesterday",case_id:997,type:"medical",resource:"Mobile Clinic Van",volunteer:"Arjun S.",ngo:"CareFirst NGO"}]};
const POOL=[{id:1004,type:"food",x:520,y:260,area:"Ward 11, Market Lane",pr:66,sig:["Utility bills unpaid 3 months","School meal opt-out"],status:"detected"},{id:1005,type:"medical",x:90,y:300,area:"Ward 1, Old Town",pr:58,sig:["Prescription lapsed","Lives alone"],status:"detected"},{id:1006,type:"shelter",x:560,y:140,area:"Ward 12, Eastside",pr:77,sig:["Flood warning zone"],status:"detected"}];
let S=null,sel=null,tab={o:"detected",d:"ngos"},page="home",changeLog=[];
const COL={food:"#e9a23b",medical:"#c44d8a",shelter:"#3aa59a"},km=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y)*.075;
function toast(t){const e=$("#toast");e.textContent=t;e.classList.add("on");setTimeout(()=>e.classList.remove("on"),3200)}
function logChange(action,details){changeLog.unshift({when:new Date().toLocaleString(),action,details});changeLog=changeLog.slice(0,100);const box=$("#change-log");if(box)box.innerHTML=tb(["When","Change","Details"],changeLog.map(x=>[x.when,x.action,x.details]))}
function fillSelect(id,items,label,value=x=>x.id){const e=$(id);if(!e)return;const previous=e.value;e.innerHTML=items.map(x=>`<option value="${esc(value(x))}">${esc(label(x))}</option>`).join("");if(previous&&items.some(x=>String(value(x))===previous))e.value=previous}
function refreshForms(){
 const areas=S.areas||[],types=S.types||[],ngos=(S.dir&&S.dir.ngos)||[];
 fillSelect("#case-area",areas,a=>`${a.name} · ${a.area_type}`);fillSelect("#resource-area",areas,a=>a.name);fillSelect("#volunteer-area",areas,a=>a.name);
 fillSelect("#case-type",types,t=>t.name.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase()),t=>t.name);
 fillSelect("#resource-ngo",ngos,n=>n.name);
}
/* ---------- data loading ---------- */
async function load(){
 try{const[n,r,v,h,s,d,a,t]=await Promise.all(["/needs","/resources","/volunteers","/history","/stats","/directory","/areas","/need-types"].map(p=>API.get(p)));S={needs:n,res:r,vols:v,hist:h,week:s.week,dir:d,areas:a,types:t};API.online=true}
 catch(e){API.online=false;if(!S)S=structuredClone(DEMO)}
 refreshForms();render()}
function localMatch(n){return S.res.filter(r=>r.type===n.type&&r.qty>0).map(r=>{const d=km(n,r),v=S.vols.filter(v=>v.free&&v.skill===n.type).sort((a,b)=>km(r,a)-km(r,b))[0];
 const p={type:1,near:Math.max(0,1-d/12),stock:Math.min(1,r.qty/10),vol:v?Math.max(0,1-km(n,v)/12):0};
 return{res_id:r.id,res:r.name,ngo:r.ngo,vol_id:v?v.id:null,vol:v?v.name:null,km:d,qty:r.qty,parts:p,score:Math.round(p.type*30+p.near*35+p.stock*15+p.vol*20)}}).sort((a,b)=>b.score-a.score)}
async function getMatches(n){if(API.online){try{return await API.get(`/needs/${n.id}/matches`)}catch(e){}}return localMatch(n)}
async function assign(n,m){
 if(API.online){try{const result=await API.post("/matches/assign",{need_id:Number(n.id),resource_id:Number(m.res_id),volunteer_id:m.vol_id?Number(m.vol_id):null,quantity:1,score:m.score,score_breakdown:m.parts,idempotency_key:`ui-assign-${newIdempotencyKey()}`});$("#sql").textContent=`Assignment #${result.id} Â· ${result.need_type} need #${result.need_id} in ${result.area}\nResource: ${result.resource} (${result.ngo}) Ã— ${result.quantity}\nVolunteer: ${result.volunteer}\nRemaining stock: ${result.remaining_quantity}\nStatus: ${result.status}\n\nThe database committed the stock reservation, need status, match record and audit entry together.`;logChange(`Assignment #${result.id}`,`${result.need_type} need #${result.need_id} (${result.area}) -> ${result.resource} x ${result.quantity}; ${result.volunteer}; ${result.remaining_quantity} left.`);await load()}catch(e){toast(e.status===409?"This case or stock changed. Refresh and choose another match.":"The backend refused this assignment. Nothing was changed.");return}}
 else{n.status="assigned";const resource=S.res.find(r=>r.id===m.res_id);if(resource)resource.qty--;const v=S.vols.find(v=>v.id===m.vol_id);if(v)v.free=false;S.hist.unshift({when:"Just now",case_id:n.id,type:n.type,resource:m.res,volunteer:m.vol||"None free",ngo:m.ngo});$("#sql").textContent="Demo mode: no database transaction was made.";render()}
 toast("Assignment saved.");showMatches()}
async function scan(){
 if(API.online){try{const result=await API.post("/scan"),changed=result.needs_changed||[];await load();$("#sql").textContent=changed.length?`Detection scan processed ${result.processed} queued changes.\n\nNeeds created or updated:\n${changed.map(n=>`#${n.id} ${n.type} Â· ${n.area} Â· priority ${n.priority} Â· ${n.status} Â· confidence ${Math.round(n.confidence*100)}% Â· signals: ${n.signals.join(", ")||"none linked"}`).join("\n")}`:`Detection scan processed ${result.processed} queued changes. No needs were created or updated.`;changed.forEach(n=>logChange(`Need #${n.id} ${n.status}`,`${n.type} in ${n.area}; priority ${n.priority}; confidence ${Math.round(n.confidence*100)}%; signals: ${n.signals.join(", ")||"none linked"}.`));toast(changed.length?`${changed.length} needs updated. Open Activity for details.`:`Processed ${result.processed} changes; no needs changed.`)}catch(e){toast("Scan failed on the backend.")}return}
 const n=POOL.shift();if(!n){toast("No new patterns found in the stored data.");$("#scan").disabled=true;return}
 S.needs.push(n);S.week[new Date().getDay()?new Date().getDay()-1:6]++;render();toast(`Scan hit in ${n.area}: ${n.sig.join(" + ")}`);if(page==="match"||page==="map")pick(n.id)}
/* ---------- rendering ---------- */
let heroType="any",heroCur=null;
const NAV=[["home","Overview","Where needs meet help"],["needs","Current needs","Current needs"],["match","Match cases","Match cases"],["map","Map","Live map"],["dir","Directory","Directory"],["hist","Activity","Assistance history"],["about","About us","About us"]];
const IC={home:"M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",needs:"M12 9v4M12 17h.01M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",scan:"M21 21l-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14",match:"M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12zM12 11.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5",map:"M9 4L3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14",dir:"M16 19v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1M9.5 10a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7M21 19v-1a4 4 0 0 0-3-3.9M16 3.1a3.5 3.5 0 0 1 0 6.8",hist:"M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",bk:"M5 12a7 7 0 0 1 14 0M8 15a4 4 0 0 1 8 0M12 19h.01",about:"M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v6M12 7.5v.01"};
$("#nav").innerHTML=NAV.map(([k,t])=>`<a href="#/${k}" data-p="${k}"><svg viewBox="0 0 24 24"><path d="${IC[k]}"/></svg>${t}</a>`).join("");
function go(k){if(!NAV.some(n=>n[0]===k))k="home";page=k;$("#ptitle").textContent=NAV.find(n=>n[0]===k)[2];$$(".pg").forEach(p=>p.classList.toggle("on",p.id==="pg-"+k));$$("#nav a").forEach(a=>{a.classList.toggle("on",a.dataset.p===k);a.setAttribute("aria-current",a.dataset.p===k?"page":"false")});scrollTo(0,0);
 if((k==="match"||k==="map")&&!sel){const f=S.needs.filter(n=>n.status!=="assigned").sort((a,b)=>b.pr-a.pr)[0];if(f)pick(f.id)}}
function countTo(el,to){const from=+el.textContent||0;if(from===to||matchMedia("(prefers-reduced-motion:reduce)").matches){el.textContent=to;return}const t0=performance.now();(function f(t){const p=Math.min(1,(t-t0)/700);el.textContent=Math.round(from+(to-from)*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(f)})(t0)}
function tb(h,rows){return`<table><tr>${h.map(x=>`<th>${esc(x)}</th>`).join("")}</tr>${rows.map(r=>`<tr>${r.map(c=>`<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</table>`}
function render(){
 const open=S.needs.filter(n=>n.status!=="assigned"),done=S.needs.length-open.length;
 $("#bd").className="dot"+(API.online?" on":"");$("#bt").textContent=API.online?"Backend connected":"Demo data, no backend";
 renderNeeds();
 countTo($("#i-open"),open.length);countTo($("#i-done"),done);countTo($("#i-vol"),S.vols.filter(v=>v.free).length);countTo($("#i-stock"),S.res.reduce((a,r)=>a+r.qty,0));
 const bg=["var(--rose)","var(--mint)","var(--lav)"];
 $("#h-news").innerHTML=S.hist.length?S.hist.slice(0,3).map((h,i)=>`<article class="cd"><div class="art" style="background:${bg[i%3]};color:var(--ink)"><b>#${esc(h.case_id)}</b><span>${esc(T(h.type))} case assigned</span></div><h3>${esc(h.resource)}</h3><p>Volunteer ${esc(h.volunteer)}. ${esc(h.ngo)}, ${esc(h.when)}.</p></article>`).join(""):'<p class="muted">No assignments yet. Assign a match to see it here.</p>';
 renderHero();renderCases();drawMap();renderDir();$("#h-t").innerHTML=S.hist.length?tb(["When","Case","Need","Resource","Volunteer","NGO"],S.hist.map(h=>[h.when,"#"+h.case_id,T(h.type),h.resource,h.volunteer,h.ngo])):'<p class="muted">No assignments yet.</p>';$("#change-log").innerHTML=changeLog.length?tb(["When","Change","Details"],changeLog.map(x=>[x.when,x.action,x.details])):'<p class="muted">Imports, detected needs and assignments will appear here.</p>'}
function renderNeeds(){
 const q=($("#q").value||"").toLowerCase();
 const list=S.needs.filter(n=>(nTab==="open"?n.status!=="assigned":n.status==="assigned")&&(nType==="any"||n.type===nType)&&(!q||(n.area+n.type+n.sig.join(" ")).toLowerCase().includes(q))).sort((a,b)=>b.pr-a.pr);
 $("#h-cards").innerHTML=list.length?list.map(n=>{const d=n.status==="assigned",evidence=n.sig.length?n.sig.map(esc).join(". "):"Submitted request · ready for matching";return`<article class="cd"><div class="art" style="background:${d?"#2e9e5b":COL[n.type]||"#c44d8a"}"><b>${esc(n.pr)}</b><span>${esc(T(n.type))} ${d?"assigned":"priority"}</span></div><h3>${esc(T(n.type))} support, ${esc(n.area)}</h3><p>${evidence}.</p>${d?"":`<button class="dk sm" data-f="${esc(n.id)}">Find a match</button>`}</article>`}).join(""):'<p class="muted">Nothing matches these filters. Try another, or run a detection scan.</p>';
 $$("[data-f]").forEach(b=>b.onclick=()=>{sel=+b.dataset.f;location.hash="#/match";pick(sel)})}
async function renderHero(){
 const n=S.needs.filter(n=>n.status!=="assigned"&&(heroType==="any"||n.type===heroType)).sort((a,b)=>b.pr-a.pr)[0],g=$("#h-go");
 $$("#h-chips button").forEach(b=>b.classList.toggle("on",b.dataset.t===heroType));heroCur=n?n.id:null;
 if(!n){$("#h-body").innerHTML='<p class="muted">No open cases of this type. Try another, or run a detection scan.</p>';g.disabled=true;return}
 const evidence=n.sig.length?n.sig.map(esc).join(", "):"Submitted request";$("#h-body").innerHTML=`<b>${esc(T(n.type))} support, ${esc(n.area)}</b><p class="muted" style="margin:2px 0 8px">Priority ${esc(n.pr)}. ${evidence}.</p><p id="h-m" class="muted" style="margin:0">Finding the best match...</p>`;g.disabled=true;
 const ms=await getMatches(n),m=ms[0];if(heroCur!==n.id)return;
 $("#h-m").innerHTML=m?`Best match: <b style="display:inline">${esc(m.res)}</b>, ${Number(m.km).toFixed(1)} km away${m.vol?" with "+esc(m.vol):", no volunteer free"}. Score ${esc(m.score)}.`:"No stock left for this need.";
 g.disabled=!m;g.onclick=()=>assign(n,m)}
function renderCases(){$("#m-cases").innerHTML=[...S.needs].sort((a,b)=>(a.status==="assigned")-(b.status==="assigned")||b.pr-a.pr).map(n=>`<button class="row ${n.id===sel?"on":""}" style="${n.status==="assigned"?"opacity:.55":""}" data-n="${esc(n.id)}" aria-pressed="${n.id===sel}"><div class="av" style="background:${n.status==="assigned"?"#2e9e5b":COL[n.type]||"#c44d8a"}">${esc(T(n.type)[0])}</div><div><b>${esc(T(n.type))}</b><small>${esc(n.area)}</small></div><span class="badge ${n.pr>=80?"hot":""}">${esc(n.pr)}</span></button>`).join("");$$("#m-cases .row").forEach(r=>r.onclick=()=>pick(+r.dataset.n))}
function renderDir(){const d=S.dir||{ngos:[],volunteers:[],resources:[]},k=tab.d;
 const ngos=d.ngos||[], resources=d.resources||[], volunteers=d.volunteers||[];
 $("#d-t").innerHTML=k==="ngos"?tb(["NGO","Type","Area","Capacity","Status"],ngos.map(o=>[o.name,o.ngo_type||"NGO",o.area||"Area not set",o.capacity||0,o.active?"Active":"Inactive"])):k==="res"?tb(["Resource","Category","Quantity","Expiry","NGO","Area"],resources.map(r=>[r.item,r.category,r.quantity,r.expires_at?new Date(r.expires_at).toLocaleDateString():"—",r.ngo||"Unassigned NGO",r.area||"Area not set"])):tb(["Volunteer","Skills","Mode","Area","Status"],volunteers.map(v=>[v.name,(v.skills||[]).join(", ")||"Community",v.mode||"—",v.area||"Area not set",v.active?(v.verified?"Verified":"Active"):"Inactive"]))}
function drawMap(){let s=`<path d="M0 90C100 50 200 110 280 70S440 30 540 60 620 50 640 40V400H0Z" fill="#fbf3dc"/><path d="M0 220C120 190 210 260 330 230S520 180 640 220" stroke="#fffbee" stroke-width="18" fill="none"/>`;
 for(let i=1;i<8;i++)s+=`<path d="M${i*80} 0V400M0 ${i*50}H640" stroke="#e7d8b0" stroke-width=".6"/>`;
 const cur=S.needs.find(n=>n.id===sel),m=cur&&cur.status!=="assigned"?localMatch(cur)[0]:null;
 if(m){const r=S.res.find(r=>r.id===m.res_id),v=S.vols.find(v=>v.id===m.vol_id);s+=`<path d="M${cur.x} ${cur.y}L${r.x} ${r.y}" stroke="#6a1236" stroke-width="2.5" stroke-dasharray="6 5"/>`;if(v)s+=`<path d="M${r.x} ${r.y}L${v.x} ${v.y}" stroke="#e9a23b" stroke-width="2.5" stroke-dasharray="3 4"/>`}
 S.res.forEach(r=>s+=`<rect x="${r.x-10}" y="${r.y-10}" width="20" height="20" rx="6" fill="#470a2a"/><text x="${r.x}" y="${r.y+4}" font-size="10" text-anchor="middle" fill="#fff" font-weight="700">${r.qty}</text>`);
 S.vols.forEach(v=>s+=`<rect x="${v.x-6}" y="${v.y-6}" width="12" height="12" rx="3" transform="rotate(45 ${v.x} ${v.y})" fill="#e9a23b" opacity="${v.free?1:.3}"/>`);
 S.needs.forEach(n=>{const c=n.status==="assigned"?"#2e9e5b":"#c44d8a";if(n.status!=="assigned")s+=`<circle class="ring" cx="${n.x}" cy="${n.y}" r="10" fill="none" stroke="${c}" stroke-width="2"/>`;s+=`<circle cx="${n.x}" cy="${n.y}" r="${n.id===sel?12:9}" fill="${c}" stroke="#fffbee" stroke-width="3" data-n="${n.id}"/>`});
 $("#map").innerHTML=s;$$("#map [data-n]").forEach(e=>e.onclick=()=>pick(+e.dataset.n))}
async function showMatches(){const n=S.needs.find(x=>x.id===sel);if(!n)return;$("#m-t").textContent="Matches for #"+n.id;
 if(n.status==="assigned"){$("#m-list").innerHTML='<p class="muted">This case is already assigned.</p>';return}
 const ms=await getMatches(n);if(!ms.length){$("#m-list").innerHTML='<p class="muted">No stock left for this need. Add resources or wait for a restock.</p>';return}
 const L=["Type","Distance","Stock","Volunteer"],K=["type","near","stock","vol"];
 $("#m-list").innerHTML=ms.slice(0,3).map((m,i)=>`<div class="m ${i?"":"best"}"><div class="t"><div><b>${esc(m.res)}</b><br><small style="color:var(--mute)">${esc(m.ngo)}. ${Number(m.km).toFixed(1)} km, ${esc(m.qty)} left${m.vol?". Volunteer "+esc(m.vol):". No volunteer free"}</small></div><div class="s">${esc(m.score)}</div></div><div class="ms">${K.map((k,j)=>`<div><span><i style="width:${Math.max(0,Math.min(100,Number(m.parts[k]||0)*100))}%"></i></span><small>${L[j]}</small></div>`).join("")}</div>${i?"":`<button class="dk" style="width:100%;margin-top:12px" data-a="1">Assign this match</button>`}</div>`).join("");
 const b=$("#m-list [data-a]");if(b)b.onclick=()=>assign(n,ms[0])}
function pick(id){sel=id;renderCases();drawMap();showMatches()}
/* ---------- events ---------- */
$("#scan").onclick=scan;
const showBox=id=>$(id).hidden=false,hideBox=id=>$(id).hidden=true;
const openCase=()=>{refreshForms();hideBox("#resource-box");hideBox("#volunteer-box");$("#case-status").textContent="";$("#case-modal").hidden=false;setTimeout(()=>$("#case-person")?.focus(),0)};
$("#open-case-inline").onclick=openCase;
$("#close-case").onclick=()=>hideBox("#case-modal");
$("#case-priority").oninput=e=>$("#case-priority-value").value=e.target.value;
$("#case-form").onsubmit=async e=>{e.preventDefault();const status=$("#case-status"),button=e.target.querySelector("button[type=submit]");button.disabled=true;status.className="import-status";status.textContent="Creating case…";
 try{const type=$("#case-type").value,result=await API.post("/cases",{person_name:$("#case-person").value.trim(),need_type:type,area_id:Number($("#case-area").value),priority:Number($("#case-priority").value),notes:$("#case-notes").value.trim(),consent:$("#case-consent").checked,idempotency_key:`ui-case-${newIdempotencyKey()}`});hideBox("#case-modal");logChange(`Case #${result.id} created`,`${result.need_type} · ${$("#case-area").selectedOptions[0]?.textContent||"Area"} · priority ${result.priority}`);await load();sel=result.id;go("needs");toast(`Case #${result.id} is ready to match.`)}catch(error){status.className="import-status err";status.textContent=error.message||"The case could not be created."}finally{button.disabled=false}};
$("#open-resource").onclick=()=>{refreshForms();hideBox("#volunteer-box");showBox("#resource-box")};
$("#close-resource").onclick=()=>hideBox("#resource-box");
$("#resource-form").onsubmit=async e=>{e.preventDefault();const status=$("#resource-status"),button=e.target.querySelector("button[type=submit]");button.disabled=true;status.className="import-status";status.textContent="Saving resource…";
 try{const expiry=$("#resource-expiry").value;const result=await API.post("/resources",{resource_type:$("#resource-name").value.trim(),category:$("#resource-category").value,quantity:Number($("#resource-quantity").value),ngo_id:Number($("#resource-ngo").value),area_id:Number($("#resource-area").value),expires_at:expiry?new Date(`${expiry}T23:59:59Z`).toISOString():null,perishable:$("#resource-perishable").checked,idempotency_key:`ui-resource-${newIdempotencyKey()}`});hideBox("#resource-box");await load();tab.d="res";$$("#d-tabs button").forEach(x=>x.classList.toggle("on",x.dataset.t==="res"));renderDir();logChange(`Resource #${result.id} added`,`${result.resource_type} · ${result.quantity} units · assigned to NGO and area.`);toast("Resource saved and available for matching.")}catch(error){status.className="import-status err";status.textContent=error.message||"The resource could not be saved."}finally{button.disabled=false}};
$("#open-volunteer").onclick=()=>{refreshForms();hideBox("#resource-box");showBox("#volunteer-box")};
$("#close-volunteer").onclick=()=>hideBox("#volunteer-box");
$("#volunteer-form").onsubmit=async e=>{e.preventDefault();const status=$("#volunteer-status"),button=e.target.querySelector("button[type=submit]");button.disabled=true;status.className="import-status";status.textContent="Saving volunteer…";
 try{const result=await API.post("/volunteers",{name:$("#volunteer-name").value.trim(),pseudonym:$("#volunteer-pseudonym").value.trim(),mode:$("#volunteer-mode").value,area_id:Number($("#volunteer-area").value),skills:[$("#volunteer-skill").value],verified:$("#volunteer-verified").checked,idempotency_key:`ui-volunteer-${newIdempotencyKey()}`});hideBox("#volunteer-box");await load();tab.d="vols";$$("#d-tabs button").forEach(x=>x.classList.toggle("on",x.dataset.t==="vols"));renderDir();logChange(`Volunteer #${result.id} added`,`${result.name} · assigned area and skill.`);toast("Volunteer saved and available for matching.")}catch(error){status.className="import-status err";status.textContent=error.message||"The volunteer could not be saved."}finally{button.disabled=false}};
$("#open-import").onclick=()=>{$("#import-box").hidden=false;$("#import-status").textContent="";$("#import-status").className="import-status"};
$("#close-import").onclick=()=>$("#import-box").hidden=true;
$("#import-form").onsubmit=async event=>{
 event.preventDefault();const file=$("#import-file").files[0],source=$("#import-source").value,status=$("#import-status"),button=event.target.querySelector("button[type=submit]");
 if(!file)return;button.disabled=true;status.className="import-status";status.textContent=`Uploading ${file.name}â€¦`;
 try{const form=new FormData();form.append("source",source);form.append("file",file);const result=await API.req("/imports",{method:"POST",body:form});const report=result.report||{};await load();
 const selected={ngos:"ngos",resources:"res",volunteers:"vols"}[source];if(selected){tab.d=selected;$$("#d-tabs button").forEach(x=>x.classList.toggle("on",x.dataset.t===selected))}renderDir();
 const changes=report.changes||[],records=report.records||[];changes.forEach(x=>logChange(`Import: ${x.entity} #${x.id}`,`${x.action}: ${x.name||x.key||`quantity ${x.quantity}`}`));render();const changeHtml=changes.length?`<h4>Database changes</h4>${tb(["Action","Record","Details"],changes.map(x=>[x.action,`${x.entity} #${x.id}`,x.name||x.key||`Quantity ${x.quantity}`]))}`:"<p>No core directory rows were changed for this source.</p>";
 const recordHtml=records.length?`<details open><summary>Imported contents (${records.length} rows)</summary>${tb([...new Set(records.flatMap(x=>Object.keys(x)))],records.map(x=>[...new Set(records.flatMap(y=>Object.keys(y)))].map(k=>x[k]??"â€”")))}</details>`:"";
 const rejected=result.errors||[];const rejectHtml=rejected.length?`<h4>Rejected rows</h4>${tb(["Row","Reason"],rejected.map(x=>[x.row,x.reason]))}`:"";
 status.className="import-status ok";status.innerHTML=`<p>Batch <b>#${esc(result.batch_id||"pending")}</b> Â· ${esc(report.accepted||0)} accepted Â· ${esc(report.rejected||0)} rejected Â· ${esc(changes.length)} records changed. <a href="${API.base}/imports/${encodeURIComponent(result.batch_id)}/report" target="_blank" rel="noopener">Full report</a></p>${changeHtml}${recordHtml}${rejectHtml}`}
 catch(error){status.className="import-status err";status.textContent=error.status===413?"The file is larger than the 50 MiB limit.":`Import failed: ${error.message||"backend unavailable"}`}
 finally{button.disabled=false}
};
$$("#h-chips button").forEach(b=>b.onclick=()=>{heroType=b.dataset.t;renderHero()});
$$("#d-tabs button").forEach(b=>b.onclick=()=>{tab.d=b.dataset.t;$$("#d-tabs button").forEach(x=>x.classList.toggle("on",x===b));renderDir()});
let nTab="open",nType="any";
$$("#n-tabs button").forEach(b=>b.onclick=()=>{nTab=b.dataset.t;$$("#n-tabs button").forEach(x=>x.classList.toggle("on",x===b));renderNeeds()});
$$("#n-chips button").forEach(b=>b.onclick=()=>{nType=b.dataset.t;$$("#n-chips button").forEach(x=>x.classList.toggle("on",x===b));renderNeeds()});
$("#q").oninput=renderNeeds;
document.addEventListener("pointermove",()=>{},{passive:true});
document.body.classList.add("boot");setTimeout(()=>document.body.classList.remove("boot"),1800);
addEventListener("hashchange",()=>go(location.hash.slice(2)));
load().then(()=>go(location.hash.slice(2)));



