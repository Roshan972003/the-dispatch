"""Dashboard HTML. Plain strings (no templating) so braces in CSS/JS are safe. One page, vanilla JS, no build step."""

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>The Dispatch · Dashboard</title>
<style>
:root{--bg:#faf8f4;--ink:#1c1917;--mut:#78716c;--card:#fff;--line:#e7e2d9;--soft:#f3efe7;--acc:#b45309;--acc-soft:#fef3c7;
--ok:#15803d;--ok-soft:#dcfce7;--warn:#b45309;--warn-soft:#fef3c7;--bad:#b91c1c;--bad-soft:#fee2e2;--info:#1d4ed8;--info-soft:#dbeafe;--shadow:0 1px 2px rgba(28,25,23,.05)}
@media(prefers-color-scheme:dark){:root{--bg:#16130f;--ink:#f5f1ea;--mut:#a8a29e;--card:#201c17;--line:#36302a;--soft:#2a251f;--acc:#f59e0b;--acc-soft:#3b2a0a;
--ok:#4ade80;--ok-soft:#10301c;--warn:#fbbf24;--warn-soft:#3b2a0a;--bad:#f87171;--bad-soft:#3b1414;--info:#93c5fd;--info-soft:#14284a;--shadow:none}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
a{color:inherit}
header{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 90%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.bar{max-width:1180px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{font:700 22px Georgia,serif;letter-spacing:-.01em}.brand small{font:500 12px -apple-system,sans-serif;color:var(--mut);margin-left:8px;letter-spacing:0}
.sp{flex:1}
.pill{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:99px;font-size:12px;font-weight:600;background:var(--soft);color:var(--mut)}
.pill.ok{background:var(--ok-soft);color:var(--ok)}.pill.warn{background:var(--warn-soft);color:var(--warn)}.pill.bad{background:var(--bad-soft);color:var(--bad)}.pill.info{background:var(--info-soft);color:var(--info)}
.dot{width:7px;height:7px;border-radius:50%;background:currentColor}
nav{max-width:1180px;margin:0 auto;padding:0 20px;display:flex;gap:2px;overflow-x:auto}
nav button{background:none;border:0;border-bottom:2px solid transparent;padding:10px 14px;font:600 14px inherit;color:var(--mut);cursor:pointer;white-space:nowrap}
nav button.on{color:var(--ink);border-color:var(--acc)}
nav button .n{margin-left:6px;font-size:11px;background:var(--soft);padding:1px 7px;border-radius:99px;color:var(--mut)}
main{max-width:1180px;margin:0 auto;padding:22px 20px 80px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:var(--shadow)}
.card+.card,.grid+.card,.card+.grid,.grid+.grid{margin-top:16px}
h2{font:700 19px Georgia,serif;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin:0 0 16px}
h3{font:600 12px inherit;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);margin:0 0 12px}
.grid>.card{margin-top:0}.grid{display:grid;gap:16px;align-items:stretch}.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:900px){.g4{grid-template-columns:repeat(2,1fr)}.g3,.g2{grid-template-columns:1fr}}
.kpi .v{font:700 34px Georgia,serif;line-height:1.1;letter-spacing:-.02em}.kpi .l{font-size:13px;color:var(--mut);margin-top:4px}.kpi .d{font-size:12px;color:var(--mut);margin-top:2px}
/* stepper */
.steps{display:flex;gap:0;overflow-x:auto;padding:4px 0 2px}
.step{flex:1;min-width:104px;position:relative;text-align:center;padding:0 6px}
.step::before{content:"";position:absolute;top:15px;left:-50%;width:100%;height:2px;background:var(--line);z-index:0}
.step:first-child::before{display:none}.step.done::before,.step.active::before{background:var(--ok)}
.step .c{position:relative;z-index:1;width:32px;height:32px;margin:0 auto 8px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:13px;background:var(--card);border:2px solid var(--line);color:var(--mut)}
.step.done .c{background:var(--ok);border-color:var(--ok);color:#fff}.step.active .c{border-color:var(--acc);color:var(--acc);box-shadow:0 0 0 4px var(--acc-soft)}
.step .t{font-weight:600;font-size:13px}.step .d{font-size:11.5px;color:var(--mut);margin-top:2px;line-height:1.35}
/* bars */
.bars{display:grid;gap:9px}.bar-row{display:grid;grid-template-columns:minmax(90px,170px) 1fr 34px;gap:10px;align-items:center;font-size:13px}
.bar-row .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bar-row .tr{height:9px;background:var(--soft);border-radius:99px;overflow:hidden}.bar-row .fi{height:100%;background:var(--acc);border-radius:99px}.bar-row .ct{text-align:right;color:var(--mut);font-variant-numeric:tabular-nums}
.list{display:grid;gap:0}.list .r{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px}.list .r:last-child{border:0}.list .r span:last-child{color:var(--mut);text-align:right}
button.act{font:600 14px inherit;padding:10px 14px;border-radius:9px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
button.act:hover{border-color:var(--acc)}button.act.pri{background:var(--ink);color:var(--bg);border-color:var(--ink)}button.act:disabled{opacity:.5;cursor:wait}
.acts{display:flex;gap:10px;flex-wrap:wrap}.note{margin-top:12px;font-size:13px;padding:10px 12px;border-radius:9px;background:var(--soft);display:none}.note.show{display:block}
.guard{font-size:12.5px;color:var(--mut);margin-top:12px;display:flex;gap:8px;align-items:flex-start}
/* draft */
.story{padding:18px 0;border-bottom:1px solid var(--line)}.story:last-child{border:0;padding-bottom:0}.story:first-child{padding-top:0}
.story .top{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px}.num{font:700 15px Georgia,serif;color:var(--acc);min-width:22px}
.chip{font-size:11.5px;font-weight:600;padding:2px 9px;border-radius:99px;background:var(--soft);color:var(--mut)}.chip.t{background:var(--acc-soft);color:var(--acc)}
.story a.h{font:700 18px/1.3 Georgia,serif;text-decoration:none;display:block;margin-bottom:8px}.story a.h:hover{text-decoration:underline}
.story .cm{font:16px/1.6 Georgia,serif;margin:0 0 8px}.story .why{font-size:12.5px;color:var(--mut)}
details{margin-top:6px;font-size:13px;color:var(--mut)}summary{cursor:pointer}
.flag{margin-top:8px;font-size:12.5px;padding:7px 10px;border-radius:8px;background:var(--warn-soft);color:var(--warn)}
/* tables */
.tools{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}.tools input,.tools select,textarea{font:14px inherit;padding:9px 12px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--ink)}.tools input{flex:1;min-width:180px}
.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13.5px}th{text-align:left;font:600 11.5px inherit;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}td.ti{min-width:280px}td a{text-decoration:none}td a:hover{text-decoration:underline}.mut{color:var(--mut)}
.more{margin-top:12px;text-align:center}
.kv{display:flex;flex-wrap:wrap;gap:8px}
.empty{padding:30px;text-align:center;color:var(--mut)}
textarea{width:100%;min-height:90px;resize:vertical;font-family:ui-monospace,Menlo,monospace;font-size:13px}
.feed .r{display:grid;grid-template-columns:104px 90px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px}.feed .r:last-child{border:0}
.logout{background:none;border:0;color:var(--mut);font:600 13px inherit;cursor:pointer}
.loading{position:fixed;inset:0;display:grid;place-items:center;color:var(--mut)}
</style></head><body>
<header><div class="bar"><div class="brand">The Dispatch<small>newsletter intelligence engine</small></div><span class="sp"></span>
<span class="pill" id="wk"></span><span class="pill" id="st"></span>
</div>
<nav id="tabs"></nav></header>
<main id="main"><div class="loading">Loading…</div></main>
<script>
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let S=null, tab=(location.hash||'#overview').slice(1), F={q:'',status:'all',source:'all',limit:60};
const TABS=[['overview','Overview'],['draft','This week’s draft'],['articles','Articles'],['sources','Sources'],['subscribers','Subscribers'],['activity','Activity']];
const DAYS=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const when=iso=>{if(!iso)return '—';const d=new Date(iso.length<=16?iso+':00':iso);return isNaN(d)?iso:DAYS[d.getDay()]+' '+d.toLocaleTimeString('en-IN',{hour:'numeric',minute:'2-digit',hour12:true})+' · '+d.getDate()+' '+d.toLocaleString('en-IN',{month:'short'})};
const short=iso=>iso?iso.replace('T',' ').slice(5,16):'—';
const badge=(s)=>({new:['info','candidate'],selected:['ok','selected'],dup:['warn','duplicate'],active:['ok','active'],pending:['info','pending'],unsubscribed:['','unsubscribed'],bounced:['bad','bounced'],complained:['bad','complained'],
 drafted:['warn','awaiting Shreya'],approved:['ok','confirmed'],sending:['info','sending'],sent:['ok','sent'],collecting:['info','collecting']}[s]||['',s]);
const pill=(s)=>{const [c,l]=badge(s);return `<span class="pill ${c}">${esc(l)}</span>`};
const bars=(rows,max)=>{max=max||Math.max(1,...rows.map(r=>r[1]));return `<div class="bars">`+rows.map(([n,v])=>`<div class="bar-row"><span class="nm" title="${esc(n)}">${esc(n)}</span><span class="tr"><i class="fi" style="display:block;width:${Math.max(3,v/max*100)}%"></i></span><span class="ct">${v}</span></div>`).join('')+`</div>`};

function head(){
  $('#wk').textContent='Week of '+S.week;
  const [c,l]=badge(S.issue?S.issue.status:'collecting');
  $('#st').className='pill '+c;$('#st').innerHTML='<i class="dot"></i>'+esc(l);
  const n={draft:S.kpis.selected,articles:S.kpis.articles_week,subscribers:S.kpis.subscribers};
  $('#tabs').innerHTML=TABS.map(([k,l])=>`<button class="${k===tab?'on':''}" data-t="${k}">${l}${n[k]!=null?`<span class="n">${n[k]}</span>`:''}</button>`).join('');
}
const gate=(inner)=>inner;
const kpi=(v,l,d)=>`<div class="card kpi"><div class="v">${v}</div><div class="l">${l}</div>${d?`<div class="d">${d}</div>`:''}</div>`;

function overview(){
  const k=S.kpis,i=S.issue;
  const steps=S.stages.map((s,n)=>`<div class="step ${s.state}"><div class="c">${s.state==='done'?'✓':n+1}</div><div class="t">${esc(s.label)}</div><div class="d">${esc(s.detail)}</div></div>`).join('');
  const hrs=Math.max(0,4-0.25).toFixed(1);
  return `<div class="card"><h2>This week’s pipeline</h2><p class="sub">Monday to Wednesday collection, Wednesday selection, Shreya’s confirmation, Thursday delivery.</p><div class="steps">${steps}</div></div>
  <div class="grid g4">${kpi(k.articles_week,'articles collected',`${k.articles_total} stored in total`)}${kpi(k.duplicates,'duplicates caught','this week, plus anything already in the last 4 issues')}
  ${kpi(k.sources_ok+'/'+k.sources_total,'sources responding','RSS feeds, Google News, 3 news APIs')}${kpi(k.subscribers,'active subscribers',`${(S.sub_counts.bounced||0)} bounced · ${(S.sub_counts.unsubscribed||0)} unsubscribed`)}</div>
  <div class="grid g2">
   <div class="card"><h3>Next scheduled runs (IST)</h3><div class="list">${S.next_runs.map(r=>`<div class="r"><span>${esc(r.label)}</span><span>${when(r.at)}</span></div>`).join('')}</div></div>
   <div class="card"><h3>Run a step manually</h3>${gate(`<div class="acts">
     <button class="act" data-run="ingest">Fetch articles now</button><button class="act pri" data-run="select">Run Gemini selection</button><button class="act" data-run="draft">Re-send draft to Telegram</button></div>
     <div class="note" id="note"></div>`)}
     <div class="guard"><span>🔒</span><span>There is no send button here by design. The newsletter is emailed only after Shreya confirms the final draft in Telegram.</span></div></div></div>
  <div class="grid g2">
   <div class="card"><h3>Topic mix of this week’s picks</h3>${S.topics.length?bars(S.topics):'<div class="empty">No selection yet. It runs Wednesday 2:00 PM.</div>'}</div>
   <div class="card"><h3>Where this week’s articles came from</h3>${bars(S.sources.slice(0,8))}</div></div>
  <div class="card"><h3>What this saves Shreya</h3><div class="grid g3" style="margin:0">
    <div><div class="kpi"><div class="v">${k.articles_week}</div><div class="l">articles read and sorted by the pipeline</div></div></div>
    <div><div class="kpi"><div class="v">${k.selected||0}</div><div class="l">stories shortlisted and drafted for her</div></div></div>
    <div><div class="kpi"><div class="v">4h → review</div><div class="l">her weekly production time becomes a review pass, her judgement stays the gate</div></div></div></div></div>`;
}

function draft(){
  const sel=S.items.filter(i=>i.kind==='selected'),bk=S.items.filter(i=>i.kind==='backup');
  if(!sel.length)return `<div class="card"><div class="empty">No draft yet this week. Gemini selection runs Wednesday 2:00 PM, or use <b>Run Gemini selection</b> on the Overview tab.</div></div>`;
  const notes=(S.issue&&S.issue.selection_notes||'').split('\nFLAG:');
  return `<div class="card"><h2>Draft for the week of ${esc(S.week)}</h2><p class="sub">${esc(notes[0]||'')} ${pill(S.issue.status)} · ${S.kpis.reviewed}/${sel.length} stories ticked in Telegram · ${S.kpis.edited} edited by Shreya</p>
  ${notes[1]?`<div class="flag">⚠ ${esc(notes[1])}</div>`:''}
  ${sel.map(i=>`<div class="story"><div class="top"><span class="num">${i.position}</span><span class="chip t">${esc(i.topic)}</span><span class="chip">${esc((i.selection_filter||'').toLowerCase())}</span>
   ${i.reviewed?'<span class="pill ok">✓ kept</span>':''}${i.edited?'<span class="pill info">✎ edited by Shreya</span>':''}<span class="chip">${esc(i.source)}</span></div>
   <a class="h" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a><p class="cm">${esc(i.commentary)}</p>
   <div class="why"><b>Why Gemini picked it:</b> ${esc(i.why)}</div>
   ${i.edited&&i.draft_original?`<details><summary>See Gemini’s original draft</summary><p class="cm" style="margin-top:8px">${esc(i.draft_original)}</p></details>`:''}
   ${i.flags?`<div class="flag">Auto-check: ${esc(i.flags)}</div>`:''}</div>`).join('')}</div>
  ${bk.length?`<div class="card"><h3>Backup stories (used by the Swap button)</h3><div class="list">${bk.map(i=>`<div class="r"><span><b>${esc(i.title)}</b><br><span class="mut" style="font-size:12.5px">${esc(i.source)} · ${esc(i.topic)}</span></span><span>#${i.position}</span></div>`).join('')}</div></div>`:''}`;
}

function articles(){
  const srcs=[...new Set(S.articles.map(a=>a.source))].sort();
  let rows=S.articles.filter(a=>(F.status==='all'||a.status===F.status)&&(F.source==='all'||a.source===F.source)&&(!F.q||(a.title+a.source).toLowerCase().includes(F.q.toLowerCase())));
  const tot=rows.length;rows=rows.slice(0,F.limit);
  const c={all:S.articles.length};S.articles.forEach(a=>c[a.status]=(c[a.status]||0)+1);
  return `<div class="card"><h2>Article pool</h2><p class="sub">Every article stored this week, and what the pipeline decided about it. Duplicates are kept for the audit trail, not deleted.</p>
  <div class="tools"><input id="q" placeholder="Search titles or sources…" value="${esc(F.q)}"><select id="fs"><option value="all">All statuses (${c.all})</option>
   ${['new','selected','dup'].map(s=>`<option value="${s}" ${F.status===s?'selected':''}>${badge(s)[1]} (${c[s]||0})</option>`).join('')}</select>
   <select id="fsrc"><option value="all">All sources</option>${srcs.map(s=>`<option ${F.source===s?'selected':''}>${esc(s)}</option>`).join('')}</select></div>
  <div class="tw"><table><thead><tr><th>Headline</th><th>Source</th><th>Status</th><th>Published</th></tr></thead><tbody>
  ${rows.map(a=>`<tr><td class="ti"><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a>${a.dup_title?`<div class="mut" style="font-size:12px">duplicate of: ${esc(a.dup_title)}</div>`:''}</td><td>${esc(a.source)}</td><td>${pill(a.status)}${a.topic?` <span class="chip t">${esc(a.topic)}</span>`:''}</td><td class="mut">${esc(short(a.published_at))}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Nothing matches.</td></tr>'}</tbody></table></div>
  ${tot>F.limit?`<div class="more"><button class="act" id="more">Show more (${tot-F.limit} left)</button></div>`:''}</div>`;
}

function sources(){
  const g=S.ingest;if(!g)return `<div class="card"><div class="empty">No ingest has run yet.</div></div>`;
  const fail=Object.entries(g.sources_failed||{}),ok=Object.entries(g.per_source||{}).sort((a,b)=>b[1]-a[1]);
  const kinds=[['RSS feeds',ok.filter(x=>x[0].startsWith('rss:'))],['Google News searches',ok.filter(x=>x[0].startsWith('google:'))],['News APIs (NewsAPI, GNews, NewsData.io)',ok.filter(x=>/^(newsapi|gnews|newsdata)/.test(x[0]))],['Other',ok.filter(x=>/^(hackernews|gdelt)/.test(x[0]))]];
  const kn={ GEMINI_API_KEY:'Gemini',DATABASE_URL:'Neon',TELEGRAM_BOT_TOKEN:'Telegram',RESEND_API_KEY:'Resend',RESEND_WEBHOOK_SECRET:'Resend webhook',NEWSAPI_KEY:'NewsAPI',GNEWS_API_KEY:'GNews',NEWSDATA_API_KEY:'NewsData.io'};
  return `<div class="card"><h2>Source health</h2><p class="sub">Last ingest ${esc(short(g.at))} IST · ${g.sources_ok} of ${g.sources_total} sources returned articles · ${g.seen||0} items seen, ${g.new||0} new, ${g.dup||0} duplicates, ${g.old||0} too old, ${g.exists||0} already stored.</p>
  <div class="kv">${Object.entries(S.keys).map(([k,v])=>`<span class="pill ${v?'ok':'bad'}"><i class="dot"></i>${kn[k]||k}</span>`).join('')}<span class="pill info">Model: ${esc(S.model)}</span></div></div>
  <div class="grid g2">${kinds.filter(k=>k[1].length).map(([t,r])=>`<div class="card"><h3>${t}</h3>${bars(r.map(([n,v])=>[n.replace(/^(rss|google|newsapi|gnews|newsdata):/,''),v]),Math.max(...ok.map(x=>x[1])))}</div>`).join('')}</div>
  ${fail.length?`<div class="card"><h3>Failed on the last run</h3><div class="list">${fail.map(([n,e])=>`<div class="r"><span>${esc(n)}</span><span>${esc(e)}</span></div>`).join('')}</div></div>`:''}
  ${(g.sources_empty||[]).length?`<div class="card"><h3>Responded but returned nothing</h3><p class="sub" style="margin:0">${(g.sources_empty||[]).map(esc).join(' · ')}</p></div>`:''}`;
}

function subscribers(){
  const c=S.sub_counts,order=['active','pending','unsubscribed','bounced','complained'];
  const prob=S.subscribers.filter(s=>['bounced','complained'].includes(s.status));
  return `<div class="grid g4">${order.slice(0,4).map(s=>kpi(c[s]||0,badge(s)[1],'')).join('')}</div>
  <div class="grid g2"><div class="card"><h2>Invite subscribers</h2><p class="sub">Paste emails separated by commas, spaces or new lines. Each address gets the normal confirmation email before it can receive the newsletter (max 10 at a time). Addresses below are masked.</p>
   ${gate(`<textarea id="em" placeholder="priya@example.com&#10;arjun@example.com"></textarea><div class="acts" style="margin-top:10px"><button class="act pri" id="addsub">Send confirmation</button></div><div class="note" id="note"></div>`)}</div>
   <div class="card"><h2>List hygiene</h2><p class="sub">Handled automatically, no manual cleanup.</p><div class="list">
    <div class="r"><span>Unsubscribe link in every email</span><span>one click, also in the mail client’s header</span></div>
    <div class="r"><span>Permanent bounce (Gmail and others)</span><span>switched off by Resend webhook</span></div>
    <div class="r"><span>Spam complaint</span><span>switched off immediately</span></div>
    <div class="r"><span>New sign-ups</span><span>confirm by email first</span></div></div></div></div>
  ${prob.length?`<div class="card"><h3>Bounced or complained (never emailed again)</h3><div class="list">${prob.map(s=>`<div class="r"><span>${esc(s.email)} ${pill(s.status)}</span><span>${esc(s.note||'')} ${esc(short(s.status_changed_at))}</span></div>`).join('')}</div></div>`:''}
  <div class="card"><h3>Send log</h3><div class="tw"><table><thead><tr><th>Week</th><th>Status</th><th>Sent</th><th>Failed</th><th>Queued</th><th>When</th></tr></thead><tbody>
   ${S.sends.map(x=>`<tr><td>${esc(x.week)}</td><td>${pill(x.status)}</td><td>${x.sent||0}</td><td>${x.failed||0}</td><td>${x.queued||0}</td><td class="mut">${esc(short(x.sent_at))}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">Nothing sent yet.</td></tr>'}</tbody></table></div></div>
  <div class="card"><h3>Most recent subscribers</h3><div class="tw"><table><thead><tr><th>Email</th><th>Status</th><th>Joined</th></tr></thead><tbody>
   ${S.subscribers.slice(0,30).map(s=>`<tr><td>${esc(s.email)}${s.note==='sample'?' <span class="chip">sample</span>':''}</td><td>${pill(s.status)}</td><td class="mut">${esc(short(s.created_at))}</td></tr>`).join('')}</tbody></table></div></div>`;
}

function activity(){
  const st=S.style;
  return `<div class="grid g2"><div class="card"><h2>Shreya’s voice</h2><p class="sub">Stored style guide, injected into every Gemini call. Each version is kept so past issues stay reproducible.</p>
   <div class="list"><div class="r"><span>Active version</span><span>v${st.version}</span></div><div class="r"><span>Few-shot examples</span><span>${st.examples}</span></div><div class="r"><span>Banned phrases</span><span>${st.banned}</span></div>
   <div class="r"><span>Her edits captured</span><span>${st.edits_total} (${st.edits_pending} not yet learned)</span></div></div>
   ${gate(`<div class="acts" style="margin-top:14px"><button class="act" data-run="promote">Learn from her latest edits</button></div><div class="note" id="note"></div>`)}</div>
   <div class="card"><h3>Upcoming</h3><div class="list">${S.next_runs.map(r=>`<div class="r"><span>${esc(r.label)}</span><span>${when(r.at)}</span></div>`).join('')}</div></div></div>
  <div class="card"><h3>Activity log</h3><div class="feed">${S.events.map(e=>`<div class="r"><span class="mut">${esc(short(e.ts))}</span><span><span class="chip">${esc(e.kind)}</span></span><span class="mut">${esc(e.detail)}</span></div>`).join('')||'<div class="empty">No activity yet.</div>'}</div></div>`;
}

const V={overview,draft,articles,sources,subscribers,activity};
function render(){head();$('#main').innerHTML=V[tab]?V[tab]():V.overview()}
async function load(){
  const r=await fetch('/api/admin/state');
  S=await r.json();render();
}
document.addEventListener('click',async e=>{
  const t=e.target.closest('[data-t]');if(t){tab=t.dataset.t;location.hash=tab;render();return}
  if(e.target.id==='more'){F.limit+=100;render();return}
  const run=e.target.closest('[data-run]');
  if(run){run.disabled=true;const old=run.textContent;run.textContent='Working…';const n=$('#note');n.className='note show';n.textContent='Running — selection can take up to a minute.';
    try{const r=await fetch('/api/admin/run/'+run.dataset.run,{method:'POST'});const j=await r.json();n.textContent=(j.ok?'✓ ':'✗ ')+(j.message||j.detail||'done')}catch(x){n.textContent='✗ '+x}
    run.disabled=false;run.textContent=old;await silent();return}
  if(e.target.id==='addsub'){const n=$('#note');n.className='note show';n.textContent='Adding…';
    const r=await fetch('/api/admin/subscribers',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({emails:$('#em').value})});const j=await r.json();
    n.textContent=j.ok?`✓ ${j.added} confirmation email(s) sent${j.invalid?`, ${j.invalid} invalid`:''}.`:'✗ '+j.message;await silent();return}
});
document.addEventListener('input',e=>{if(e.target.id==='q'){F.q=e.target.value;const p=e.target.selectionStart;render();const q=$('#q');q.focus();q.setSelectionRange(p,p)}});
document.addEventListener('change',e=>{if(e.target.id==='fs'){F.status=e.target.value;F.limit=60;render()}if(e.target.id==='fsrc'){F.source=e.target.value;F.limit=60;render()}});
async function silent(){const keep=$('#note')&&$('#note').textContent;const cls=$('#note')&&$('#note').className;const r=await fetch('/api/admin/state');if(r.ok){S=await r.json();render();const n=$('#note');if(n&&keep){n.className=cls;n.textContent=keep}}}
window.addEventListener('hashchange',()=>{tab=(location.hash||'#overview').slice(1);if(S)render()});
load();setInterval(()=>{if(document.visibilityState==='visible'&&!document.activeElement.matches('input,textarea,select'))silent()},30000);
</script></body></html>"""
