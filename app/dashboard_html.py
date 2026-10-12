"""Dashboard HTML ("Obsidian Editorial" theme). Plain string, no templating; vanilla JS, no build step.
Everything that could alter Shreya's draft or send mail is preview-only here: those actions live in Telegram."""

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>The Dispatch · Command Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Newsreader:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
<script>try{var t=localStorage.getItem('dispatch-theme')}catch(e){}document.documentElement.dataset.theme=t||(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark')</script>
<style>
:root{--bg:#0B0C0E;--ink:#ECECEE;--mut:#8B8F98;--card:rgba(255,255,255,.035);--card2:rgba(255,255,255,.06);--line:#1F2937;--soft:rgba(255,255,255,.055);
--acc:#F59E0B;--acc-soft:rgba(245,158,11,.14);--ok:#10B981;--ok-soft:rgba(16,185,129,.14);--bad:#EF4444;--bad-soft:rgba(239,68,68,.15);--info:#60A5FA;--info-soft:rgba(96,165,250,.14);
--serif:"Newsreader",Georgia,serif;--sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--mono:"JetBrains Mono",ui-monospace,Menlo,monospace;--glow:0 0 0 1px rgba(255,255,255,.02) inset}
[data-theme=light]{--bg:#FAF9F6;--ink:#1B1A17;--mut:#6B675F;--card:rgba(255,255,255,.75);--card2:#fff;--line:#E4DFD3;--soft:rgba(27,26,23,.05);
--acc:#D97706;--acc-soft:rgba(217,119,6,.12);--ok:#059669;--ok-soft:rgba(5,150,105,.12);--bad:#DC2626;--bad-soft:rgba(220,38,38,.1);--info:#2563EB;--info-soft:rgba(37,99,235,.1);--glow:none}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:14.5px/1.55 var(--sans);-webkit-font-smoothing:antialiased;
 background-image:radial-gradient(900px 400px at 85% -10%,rgba(245,158,11,.07),transparent 60%),radial-gradient(700px 380px at -10% 0%,rgba(16,185,129,.05),transparent 60%);background-attachment:fixed}
a{color:inherit}button{font-family:inherit}
header{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.bar{max-width:1240px;margin:0 auto;padding:11px 22px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.brand{font:600 23px var(--serif);letter-spacing:-.01em}.brand small{font:500 11px var(--mono);color:var(--mut);margin-left:10px;letter-spacing:.04em;text-transform:uppercase}.sp{flex:1}
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:99px;font:500 11.5px var(--mono);background:var(--soft);color:var(--mut);white-space:nowrap}
.pill.ok{background:var(--ok-soft);color:var(--ok)}.pill.warn{background:var(--acc-soft);color:var(--acc)}.pill.bad{background:var(--bad-soft);color:var(--bad)}.pill.info{background:var(--info-soft);color:var(--info)}
.dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.ibtn{background:var(--soft);border:1px solid var(--line);color:var(--ink);border-radius:9px;width:34px;height:30px;cursor:pointer;font-size:14px}
.banner{max-width:1240px;margin:0 auto;padding:0 22px 10px}.bn{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:10px 14px;border-radius:12px;border:1px solid var(--line);background:var(--card)}
.bn.amber{border-color:rgba(245,158,11,.4);background:var(--acc-soft)}.bn.green{border-color:rgba(16,185,129,.4);background:var(--ok-soft)}.bn.red{border-color:rgba(239,68,68,.45);background:var(--bad-soft)}
.bn .tt{font-weight:600}.bn .cd{font:600 20px var(--mono);letter-spacing:.02em}.bn .grow{flex:1;min-width:160px}.bn small{color:var(--mut)}
nav{max-width:1240px;margin:0 auto;padding:0 22px;display:flex;gap:2px;overflow-x:auto}
nav button{background:none;border:0;border-bottom:2px solid transparent;padding:9px 13px;font:500 13.5px var(--sans);color:var(--mut);cursor:pointer;white-space:nowrap}
nav button.on{color:var(--ink);border-color:var(--acc)}nav button .n{margin-left:6px;font:500 10.5px var(--mono);background:var(--soft);padding:1px 7px;border-radius:99px}
main{max-width:1240px;margin:0 auto;padding:22px 22px 90px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;backdrop-filter:blur(8px);box-shadow:var(--glow)}
h2{font:600 21px var(--serif);margin:0 0 4px;letter-spacing:-.005em}.sub{color:var(--mut);font-size:13px;margin:0 0 16px}
h3{font:500 11px var(--mono);text-transform:uppercase;letter-spacing:.09em;color:var(--mut);margin:0 0 12px}
.grid{display:grid;gap:16px;margin-top:16px}.grid>.card{margin-top:0}.stack>*+*{margin-top:16px}
.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(4,1fr)}.g6{grid-template-columns:repeat(6,1fr)}.g21{grid-template-columns:2fr 1fr}.g12{grid-template-columns:1fr 2fr}
@media(max-width:980px){.g4,.g6{grid-template-columns:repeat(2,1fr)}.g3,.g2,.g21,.g12{grid-template-columns:1fr}}
.kpi .v{font:600 34px var(--serif);line-height:1.05}.kpi .l{font-size:12.5px;color:var(--mut);margin-top:4px}.kpi .d{font:11.5px var(--mono);color:var(--mut);margin-top:2px}
.mono{font-family:var(--mono)}.mut{color:var(--mut)}.serif{font-family:var(--serif)}
.appr{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}@media(max-width:900px){.appr{grid-template-columns:1fr 1fr}}
.ap{border:1px solid var(--line);border-radius:12px;padding:12px 14px;opacity:.55}.ap.done,.ap.queued{opacity:1}.ap .k{font:600 11px var(--mono);letter-spacing:.06em;display:flex;align-items:center;gap:7px}
.ap .t{font:12px var(--mono);margin-top:6px;color:var(--mut)}.ap .nt{font-size:12px;color:var(--mut);margin-top:2px}
.ap.c-amber .k{color:var(--acc)}.ap.c-amber.done{background:var(--acc-soft);border-color:rgba(245,158,11,.4)}.ap.c-blue .k{color:var(--info)}.ap.c-blue.done{background:var(--info-soft);border-color:rgba(96,165,250,.4)}
.ap.c-red .k{color:var(--bad)}.ap.c-red.queued,.ap.c-red.done{background:var(--bad-soft);border-color:rgba(239,68,68,.4)}.ap.c-green .k{color:var(--ok)}.ap.c-green.done{background:var(--ok-soft);border-color:rgba(16,185,129,.4)}
.steps{display:flex;overflow-x:auto;padding:4px 0 2px}.step{flex:1;min-width:100px;position:relative;text-align:center;padding:0 6px}
.step::before{content:"";position:absolute;top:15px;left:-50%;width:100%;height:2px;background:var(--line)}.step:first-child::before{display:none}.step.done::before,.step.active::before{background:var(--ok)}
.step .c{position:relative;z-index:1;width:32px;height:32px;margin:0 auto 8px;border-radius:50%;display:grid;place-items:center;font:600 12px var(--mono);background:var(--bg);border:2px solid var(--line);color:var(--mut)}
.step.done .c{background:var(--ok);border-color:var(--ok);color:#04130d}.step.active .c{border-color:var(--acc);color:var(--acc);box-shadow:0 0 0 4px var(--acc-soft)}
.step .t{font-weight:600;font-size:12.5px}.step .d{font-size:11px;color:var(--mut);margin-top:2px;line-height:1.35}
.bars{display:grid;gap:9px}.br{display:grid;grid-template-columns:minmax(90px,170px) 1fr 34px;gap:10px;align-items:center;font-size:12.5px}
.br .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.br .tr{height:7px;background:var(--soft);border-radius:99px;overflow:hidden}.br .fi{height:100%;background:var(--acc);border-radius:99px;display:block}.br .ct{text-align:right;color:var(--mut);font-family:var(--mono)}
.list .r{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13.5px}.list .r:last-child{border:0}.list .r span:last-child{color:var(--mut);text-align:right}
.act{font:500 13px var(--sans);padding:8px 13px;border-radius:9px;border:1px solid var(--line);background:var(--card2);color:var(--ink);cursor:pointer}.act:hover{border-color:var(--acc)}
.act.pri{background:var(--acc);color:#1a1100;border-color:var(--acc);font-weight:600}.act.sm{padding:5px 10px;font-size:12px}.act:disabled{opacity:.5;cursor:wait}.act.ghost{background:transparent}
.acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.note{margin-top:10px;font-size:12.5px;padding:9px 12px;border-radius:9px;background:var(--soft);display:none;font-family:var(--mono)}.note.show{display:block}
.guard{font-size:12px;color:var(--mut);margin-top:12px;display:flex;gap:8px}
.chip{font:500 11px var(--mono);padding:2px 8px;border-radius:99px;background:var(--soft);color:var(--mut)}.chip.t{background:var(--acc-soft);color:var(--acc)}.chip.ok{background:var(--ok-soft);color:var(--ok)}.chip.bad{background:var(--bad-soft);color:var(--bad)}
.rc{display:grid;grid-template-columns:1fr 1.25fr .9fr;gap:0;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:var(--card)}.rc+.rc{margin-top:14px}
@media(max-width:980px){.rc{grid-template-columns:1fr}}
.rc>div{padding:16px 18px}.rc>div+div{border-left:1px solid var(--line)}@media(max-width:980px){.rc>div+div{border-left:0;border-top:1px solid var(--line)}}
.rc h4{font:500 10.5px var(--mono);text-transform:uppercase;letter-spacing:.09em;color:var(--mut);margin:0 0 8px}
.rc .raw a{font:600 15px/1.35 var(--serif);text-decoration:none;display:block;margin-bottom:6px}.rc .raw a:hover{text-decoration:underline}.rc .raw p{font-size:12.5px;color:var(--mut);margin:0 0 8px}
.rc .cm{overflow-wrap:anywhere;font:17px/1.6 var(--serif);margin:0 0 10px}.rc .why{font:12px/1.55 var(--mono);color:var(--mut)}
.ring{width:74px;height:74px}.ck{display:grid;gap:4px;margin-top:8px}.ck div{display:flex;gap:7px;font:11.5px var(--mono)}.ck .y{color:var(--ok)}.ck .n{color:var(--bad)}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.rv{margin-top:10px;padding:11px 13px;border-radius:10px;border:1px dashed var(--acc);background:var(--acc-soft);font:15px/1.55 var(--serif)}
.rv small{display:block;font:11px var(--mono);color:var(--mut);margin-top:6px}
.edw{position:relative}.edw .hl,.edw textarea{font:17px/1.6 var(--serif);padding:14px;border-radius:11px;white-space:pre-wrap;word-wrap:break-word;width:100%;min-height:130px}
.edw .hl{position:absolute;inset:0;color:transparent;pointer-events:none;border:1px solid transparent;overflow:hidden}.edw .hl mark{background:rgba(239,68,68,.35);color:transparent;border-bottom:2px solid var(--bad);border-radius:3px}
.edw textarea{position:relative;background:transparent;border:1px solid var(--line);color:var(--ink);resize:vertical;outline:none;display:block}.edw textarea:focus{border-color:var(--acc)}
.sl{display:grid;gap:4px;margin-bottom:16px}.sl .lab{display:flex;justify-content:space-between;font:12px var(--mono);color:var(--mut)}.sl .lab b{color:var(--ink);font-weight:500}
input[type=range]{width:100%;accent-color:var(--acc)}
.dr{position:fixed;top:0;right:0;bottom:0;width:min(460px,100vw);background:var(--bg);border-left:1px solid var(--line);z-index:40;transform:translateX(105%);transition:transform .25s;overflow:auto;padding:22px;box-shadow:-20px 0 60px rgba(0,0,0,.35)}
.dr.open{transform:none}.scrim{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:30;display:none}.scrim.open{display:block}
.ru{border:1px solid var(--line);border-radius:12px;padding:13px;margin-top:12px;background:var(--card)}.ru b{font:600 15px/1.35 var(--serif);display:block}
.tools{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}.tools input,.tools select,textarea.ta,.inp{font:13.5px var(--sans);padding:8px 11px;border:1px solid var(--line);border-radius:9px;background:var(--card2);color:var(--ink)}.tools input{flex:1;min-width:180px}
.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;font:500 10.5px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--mut);padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}td.ti{min-width:260px}td a{text-decoration:none;overflow-wrap:anywhere}td a:hover{text-decoration:underline}
.sig{display:flex;align-items:center;gap:8px;font:12px var(--mono);min-width:96px}.sig i{display:block;height:6px;border-radius:9px;background:var(--mut);opacity:.5}.sig i.hi{background:var(--acc);opacity:1}
.more{margin-top:12px;text-align:center}.kv{display:flex;flex-wrap:wrap;gap:8px}.empty{padding:26px;text-align:center;color:var(--mut)}
textarea.ta{width:100%;min-height:90px;resize:vertical;font-family:var(--mono);font-size:12.5px}
.feed .r{display:grid;grid-template-columns:100px 90px 1fr;gap:10px;padding:7px 0;border-bottom:1px solid var(--line);font:12px var(--mono)}.feed .r:last-child{border:0}
.hm{display:grid;gap:3px;font:11.5px var(--mono)}.hm .hd{color:var(--mut);padding:4px 2px;text-align:center}.hm .rn{padding:6px 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hm .cell{height:30px;border-radius:6px;display:grid;place-items:center;background:var(--soft);color:var(--mut)}
.cl{display:grid;grid-template-columns:minmax(150px,1.3fr) repeat(var(--n),1fr) 50px;gap:3px;align-items:center;margin-bottom:3px;font-size:12px}.cl .nm{padding-right:8px}
.gsvg{width:100%;height:auto;background:radial-gradient(circle at 50% 50%,var(--soft),transparent 70%);border-radius:12px}.gsvg text{font:10px var(--mono);fill:var(--mut)}.gsvg .nd{cursor:pointer}.gsvg .nd:hover circle{stroke:var(--ink);stroke-width:2}
.phone{width:350px;max-width:100%;margin:0 auto;border-radius:34px;border:8px solid #1c1c21;background:#0e1621;box-shadow:0 24px 60px rgba(0,0,0,.45);overflow:hidden;color:#e8eef5;font:13.5px/1.45 var(--sans)}
.phone .ph{background:#17212b;padding:12px 14px;display:flex;gap:10px;align-items:center;border-bottom:1px solid #0b121a}.phone .av{width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#f59e0b,#b45309);display:grid;place-items:center;font-weight:700;color:#1a1100}
.phone .ph b{display:block;font-size:14px}.phone .ph small{color:#6d7f91;font-size:11.5px}.phone .body{height:560px;overflow:auto;padding:12px 10px;display:flex;flex-direction:column;gap:8px;background:#0e1621}
.msg{max-width:94%;background:#182533;border-radius:14px 14px 14px 4px;padding:9px 11px;align-self:flex-start}.msg.me{align-self:flex-end;background:#2b5278;border-radius:14px 14px 4px 14px}.msg a{color:#6ab3f3}
.kb{display:flex;gap:4px;margin-top:6px}.kb button{flex:1;background:#223142;border:0;color:#6ab3f3;border-radius:8px;padding:7px 4px;font:500 12px var(--sans);cursor:pointer}.kb button:hover{background:#2b4056}.kb.one button{width:100%}
.phone .ft{background:#17212b;padding:8px 12px;font-size:11px;color:#6d7f91;text-align:center;border-top:1px solid #0b121a}
.phone textarea{width:100%;background:#0e1621;border:1px solid #2b4056;color:#e8eef5;border-radius:8px;padding:7px;font:13px var(--sans);min-height:64px}
.tl{position:relative;padding-left:22px}.tl::before{content:"";position:absolute;left:6px;top:6px;bottom:6px;width:2px;background:var(--line)}.tl .i{position:relative;padding:0 0 18px}.tl .i::before{content:"";position:absolute;left:-21px;top:5px;width:12px;height:12px;border-radius:50%;background:var(--bg);border:2px solid var(--line)}
.tl .i.done::before{background:var(--ok);border-color:var(--ok)}.tl .i.queued::before{border-color:var(--bad)}
.lp{display:flex;gap:18px;align-items:center;flex-wrap:wrap}.lamp{width:78px;height:78px;border-radius:50%;display:grid;place-items:center;font-size:30px;border:2px solid var(--line)}
.lamp.safe{background:var(--acc-soft);border-color:var(--acc);box-shadow:0 0 36px rgba(245,158,11,.25)}.lamp.armed{background:var(--ok-soft);border-color:var(--ok);box-shadow:0 0 36px rgba(16,185,129,.3)}
.sw{width:46px;height:26px;border-radius:99px;background:var(--soft);border:1px solid var(--line);position:relative;display:inline-block;vertical-align:middle}.sw::after{content:"";position:absolute;top:2px;left:2px;width:20px;height:20px;border-radius:50%;background:var(--mut);transition:.2s}.sw.on{background:var(--ok-soft);border-color:var(--ok)}.sw.on::after{left:22px;background:var(--ok)}
.pv{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}.pvh{padding:10px 14px;background:#f5f5f4;color:#1b1a17;border-bottom:1px solid #e4dfd3;font-size:12.5px}.pvh .mut{color:#6b675f}.pvh b{font-weight:600}
.pvf{display:block;border:0;margin:0 auto;background:#f5f5f4;height:640px;transition:width .25s}.dk .pvf{filter:invert(.92) hue-rotate(180deg)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}.seg button{background:transparent;border:0;color:var(--mut);padding:6px 12px;font:500 12px var(--sans);cursor:pointer}.seg button.on{background:var(--acc-soft);color:var(--acc)}
.soc{overflow-wrap:anywhere;white-space:pre-wrap;font:13px/1.55 var(--sans);background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:12px}.tw1{margin-bottom:10px}
.fun{display:grid;gap:10px}.fun .row{display:grid;grid-template-columns:170px 1fr;gap:14px;align-items:center}.fun .lab{font:600 13px var(--sans)}.fun .lab small{display:block;font:11px var(--mono);color:var(--mut);font-weight:400}
.fun .bar{height:30px;border-radius:8px;background:linear-gradient(90deg,var(--acc),rgba(245,158,11,.45));display:flex;align-items:center;padding:0 12px;font:600 13px var(--mono);color:#1a1100;min-width:46px;position:relative}
.fun .drop{font:11.5px var(--mono);color:var(--bad);margin:-4px 0 2px 184px}@media(max-width:700px){.fun .row{grid-template-columns:1fr}.fun .drop{margin-left:0}}
.src{overflow-wrap:anywhere;font:13.5px/1.6 var(--serif);color:var(--ink);max-height:150px;overflow:auto;padding-right:4px}.src mark{background:rgba(245,158,11,.3);color:inherit;border-radius:3px;padding:0 2px}
.why-d{font:11.5px/1.45 var(--mono);color:var(--mut);margin-top:3px}
.dv{margin-top:10px;font-size:13px}.dv summary{cursor:pointer;color:var(--ink);font-weight:500}.dv ul{margin:8px 0 4px;padding-left:18px;color:var(--ink)}.dv li{margin:4px 0}
.pal{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:60;display:none;align-items:flex-start;justify-content:center;padding-top:12vh}.pal.open{display:flex}
.pbox{width:min(620px,94vw);background:var(--bg);border:1px solid var(--line);border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,.5);overflow:hidden}
.pbox input{width:100%;padding:16px 18px;font:16px var(--sans);background:transparent;border:0;border-bottom:1px solid var(--line);color:var(--ink);outline:none}
#pall{max-height:52vh;overflow:auto;padding:6px}.pg{font:500 10.5px var(--mono);text-transform:uppercase;letter-spacing:.09em;color:var(--mut);padding:10px 12px 4px}
.pi{display:flex;justify-content:space-between;gap:10px;padding:9px 12px;border-radius:9px;cursor:pointer;font-size:14px}.pi.on,.pi:hover{background:var(--acc-soft)}.pi small{color:var(--mut);font:11px var(--mono)}
.pft{padding:8px 14px;border-top:1px solid var(--line);font:11px var(--mono);color:var(--mut)}
.fz{position:relative;display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:6px;touch-action:none}@media(max-width:700px){.fz{grid-template-columns:1fr 1fr}}
.fnode{border:1px solid var(--line);background:var(--card2);border-radius:12px;padding:10px 12px;cursor:crosshair;user-select:none;font-size:12.5px;line-height:1.4;position:relative;z-index:2}.fnode b{font:600 11px var(--mono);color:var(--acc);display:block;margin-bottom:3px}
.fnode:hover,.fnode.on{border-color:var(--acc);background:var(--acc-soft)}.fzsvg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
.flag{margin-top:8px;font:12px var(--mono);padding:7px 10px;border-radius:8px;background:var(--acc-soft);color:var(--acc)}
</style></head><body>
<header><div class="bar"><div class="brand">The Dispatch<small>command center</small></div><span class="sp"></span><span class="pill" id="wk"></span><span class="pill" id="st"></span><button class="act sm" id="kbtn" style="font-family:var(--mono)" title="Command palette">⌘K</button><button class="ibtn" id="theme" title="Light / dark">◐</button></div>
<div class="banner" id="banner"></div><nav id="tabs"></nav></header>
<main id="main"><div class="empty">Loading…</div></main>
<div class="scrim" id="scrim"></div><aside class="dr" id="drawer"></aside>
<div class="pal" id="pal"><div class="pbox"><input id="palq" placeholder="Search stories, jump to a view, run an action…  try  >  or  /" autocomplete="off"><div id="pall"></div><div class="pft">↑↓ move · ↵ run · esc close · &gt; actions · / filters</div></div></div>
<script>
const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let S=null,fetchedAt=Date.now(),tab=(location.hash||'#command').slice(1),F={q:'',status:'all',source:'all',limit:60,sort:'time',filter:'',topic:''},fz=null,fzDrag=null,pal={open:false,q:'',sel:0,items:[]},ed={text:'',item:''},sim=null,gSel=null,pvDev='desktop',pvDark=false,socTab='x',rv={},ru={},openDrawer=false;
const TABS=[['command','Command'],['curation','Curation'],['intelligence','Intelligence'],['telegram','Telegram lab'],['delivery','Delivery'],['subscribers','Subscribers'],['articles','Articles'],['sources','Sources']];
const DAYS=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const when=iso=>{if(!iso)return '—';const d=new Date(iso.length<=16?iso+':00':iso);return isNaN(d)?iso:DAYS[d.getDay()]+' '+d.toLocaleTimeString('en-IN',{hour:'numeric',minute:'2-digit',hour12:true})+' · '+d.getDate()+' '+d.toLocaleString('en-IN',{month:'short'})};
const short=iso=>iso?iso.replace('T',' ').slice(5,16):'—';
const badge=s=>({new:['info','candidate'],selected:['ok','selected'],dup:['warn','duplicate'],active:['ok','active'],pending:['info','pending'],unsubscribed:['','unsubscribed'],bounced:['bad','bounced'],complained:['bad','complained'],drafted:['warn','awaiting you'],approved:['ok','confirmed'],sending:['info','sending'],sent:['ok','sent'],collecting:['info','collecting']}[s]||['',s]);
const pill=s=>{const[c,l]=badge(s);return `<span class="pill ${c}">${esc(l)}</span>`};
const bars=(rows,max)=>{max=max||Math.max(1,...rows.map(r=>r[1]));return `<div class="bars">`+rows.map(([n,v])=>`<div class="br"><span class="nm" title="${esc(n)}">${esc(n)}</span><span class="tr"><i class="fi" style="width:${Math.max(3,v/max*100)}%"></i></span><span class="ct">${v}</span></div>`).join('')+`</div>`};
const kpi=(v,l,d)=>`<div class="card kpi"><div class="v">${v}</div><div class="l">${l}</div>${d?`<div class="d">${d}</div>`:''}</div>`;
const sel=()=>S.items.filter(i=>i.kind==='selected'),bk=()=>S.items.filter(i=>i.kind==='backup');
const post=(u,b)=>fetch(u,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b||{})}).then(r=>r.json());
const checks=c=>`<div class="ck">${c.map(x=>`<div class="${x.ok?'y':'n'}"><span>${x.ok?'✓':'✗'}</span><span>${esc(x.rule)}<span class="mut"> · ${esc(x.detail)}</span></span></div>`).join('')}</div>`;
const copyBtn=(id,l)=>`<button class="act sm" data-copy="${id}">${l||'Copy'}</button>`;

function head(){
  $('#wk').textContent='week of '+S.week;
  const[c,l]=badge(S.issue?S.issue.status:'collecting');$('#st').className='pill '+c;$('#st').innerHTML='<i class="dot"></i>'+esc(l);
  const n={curation:S.kpis.selected,articles:S.kpis.articles_week,subscribers:S.kpis.subscribers};
  $('#tabs').innerHTML=TABS.map(([k,l])=>`<button class="${k===tab?'on':''}" data-t="${k}">${l}${n[k]!=null?`<span class="n">${n[k]}</span>`:''}</button>`).join('');
  banner();
}
function remaining(){const r=S.reminder;const base=new Date(S.now+':00').getTime()+(Date.now()-fetchedAt);return new Date(r.deadline+':00').getTime()-base}
const fmt=ms=>{const s=Math.max(0,Math.floor(ms/1000)),d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60),x=s%60;return (d?d+'d ':'')+String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(x).padStart(2,'0')};
function banner(){
  const r=S.reminder,el=$('#banner');let cls='',body='';
  if(S.viewing_past){el.innerHTML=`<div class="bn"><span class="tt">Showing the latest edition: week of ${esc(S.week)}</span><span class="grow"><small>The new week’s pipeline starts Monday 8:00 AM IST. Everything below is that edition’s real data.</small></span></div><div class="note" id="bnote"></div>`;return}
  const ctl=`<div class="acts"><button class="act sm" data-run="ping">Remind me now</button><button class="act sm" data-snooze="30">Snooze 30m</button><button class="act sm" data-snooze="60">Snooze 1h</button></div>`;
  if(r.confirmed){cls='green';body=`<span class="tt">✓ You confirmed this draft</span><span class="grow"><small>Fail-safe armed. The email goes out Thursday 8:00 AM IST.</small></span>`}
  else if(!r.has_draft){cls='';body=`<span class="tt">Waiting for the draft</span><span class="grow"><small>Gemini selection runs Wednesday 2:00 PM IST; the 10 PM confirmation deadline starts after that.</small></span>`}
  else if(remaining()>0){cls='amber';body=`<span class="tt">Confirmation deadline · Wed 10:00 PM IST</span><span class="cd" id="cd">${fmt(remaining())}</span><span class="grow"><small>${r.snooze_until?'Reminder snoozed until '+esc(r.snooze_until.slice(11))+' IST. ':'You get an automatic Telegram reminder at the deadline. '}Nothing is sent without your confirmation.</small></span>${ctl}`}
  else{cls='red';body=`<span class="tt">Deadline passed, still unconfirmed</span><span class="grow"><small>${r.reminder_sent?'Reminder already sent to Telegram. ':'Reminder is due. '}Nothing is emailed until you confirm.</small></span>${ctl}`}
  el.innerHTML=`<div class="bn ${cls}">${body}</div><div class="note" id="bnote"></div>`;
}
setInterval(()=>{const c=$('#cd');if(c&&S)c.textContent=fmt(remaining())},1000);

function radar(axes){
  const N=axes.length,cx=150,cy=140,R=95,mx=Math.max(3,...axes.map(a=>a.n)),pt=(i,v)=>{const a=-Math.PI/2+2*Math.PI*i/N;return[cx+Math.cos(a)*R*v,cy+Math.sin(a)*R*v]};
  const ring=k=>axes.map((_,i)=>pt(i,k).join(',')).join(' ');
  const poly=axes.map((a,i)=>pt(i,a.n/mx).join(',')).join(' ');
  return `<svg viewBox="0 0 300 285" style="width:100%;max-width:340px"><g fill="none" stroke="var(--line)">${[.33,.66,1].map(k=>`<polygon points="${ring(k)}"/>`).join('')}${axes.map((_,i)=>`<line x1="${cx}" y1="${cy}" x2="${pt(i,1)[0]}" y2="${pt(i,1)[1]}"/>`).join('')}</g>
  <polygon points="${poly}" fill="rgba(245,158,11,.25)" stroke="var(--acc)" stroke-width="2"/>${axes.map((a,i)=>{const[x,y]=pt(i,a.n/mx);return a.n?`<circle cx="${x}" cy="${y}" r="3.5" fill="var(--acc)"/>`:''}).join('')}
  ${axes.map((a,i)=>{const[x,y]=pt(i,1.2);return `<text x="${x}" y="${y}" font-size="8.5" text-anchor="middle" dominant-baseline="middle" fill="${a.n?'var(--ink)':'var(--mut)'}" font-family="var(--mono)">${esc(a.topic.split(' ')[0].replace('&',''))}${a.n?' · '+a.n:''}</text>`}).join('')}</svg>`;
}
function gauge(v,bench){
  const arc=p=>{const a=Math.PI*(1-p/100);return[100+80*Math.cos(a),100-80*Math.sin(a)]};const[bx,by]=arc(bench);const[ex,ey]=arc(v==null?0:Math.min(100,v));
  return `<svg viewBox="0 0 200 125" style="width:100%;max-width:260px"><path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="var(--soft)" stroke-width="14" stroke-linecap="round"/>
  ${v!=null?`<path d="M20 100 A80 80 0 0 1 ${ex} ${ey}" fill="none" stroke="var(--ok)" stroke-width="14" stroke-linecap="round"/>`:''}
  <line x1="${bx}" y1="${by}" x2="${100+60*Math.cos(Math.PI*(1-bench/100))}" y2="${100-60*Math.sin(Math.PI*(1-bench/100))}" stroke="var(--acc)" stroke-width="3"/>
  <text x="100" y="92" text-anchor="middle" font-size="26" font-family="var(--serif)" fill="var(--ink)">${v==null?'—':v+'%'}</text><text x="100" y="112" text-anchor="middle" font-size="9" font-family="var(--mono)" fill="var(--mut)">benchmark ${bench}% (your average)</text></svg>`;
}
function sigRing(v){const c=v==null?'var(--mut)':v>=70?'var(--acc)':'var(--mut)',p=v==null?0:v,r=30,L=2*Math.PI*r;
  return `<svg class="ring" viewBox="0 0 74 74"><circle cx="37" cy="37" r="${r}" fill="none" stroke="var(--soft)" stroke-width="7"/><circle cx="37" cy="37" r="${r}" fill="none" stroke="${c}" stroke-width="7" stroke-linecap="round" stroke-dasharray="${L*p/100} ${L}" transform="rotate(-90 37 37)"/><text x="37" y="42" text-anchor="middle" font-size="17" font-family="var(--serif)" fill="var(--ink)">${v==null?'—':v}</text></svg>`}

function funnel(){
  const F=S.funnel,mx=Math.max(1,F[0].n);
  return `<div class="fun">`+F.map((f,i)=>{const lost=i?F[i-1].n-f.n:0;return `<div class="row"><div class="lab">${esc(f.label)}<small>${esc(f.note)}</small></div><div class="bar" style="width:${Math.max(6,f.n/mx*100)}%">${f.n}</div></div>${lost>0&&i<F.length?`<div class="drop">−${lost} dropped</div>`:''}`}).join('')+`</div>`;
}
function command(){
  const k=S.kpis,B=S.balance,steps=S.stages.map((s,n)=>`<div class="step ${s.state}"><div class="c">${s.state==='done'?'✓':n+1}</div><div class="t">${esc(s.label)}</div><div class="d">${esc(s.detail)}</div></div>`).join('');
  const colors={draft:'amber',telegram:'blue',reminder:'red',confirmed:'green'},icon={draft:'🟡',telegram:'🔵',reminder:'🔴',confirmed:'🟢'};
  const ap=S.approval.map(a=>`<div class="ap c-${colors[a.key]} ${a.state}"><div class="k">${icon[a.key]} ${esc(a.label)}</div><div class="t">${a.ts?esc(short(a.ts)):(a.state==='skipped'?'skipped':'pending')}</div><div class="nt">${esc(a.note)}</div></div>`).join('');
  const picked=sel().filter(i=>i.signal!=null),rest=S.articles.filter(a=>a.signal!=null&&a.status==='new');
  const avg=picked.length?Math.round(picked.reduce((a,b)=>a+b.signal,0)/picked.length):null,avr=rest.length?Math.round(rest.reduce((a,b)=>a+b.signal,0)/rest.length):'—';
  return `<div class="card"><h2>Approval status</h2><p class="sub">The Wednesday evening pipeline, live from the database.</p><div class="appr">${ap}</div></div>
  <div class="card" style="margin-top:16px"><h2>The ${S.funnel[0].n}-to-${S.kpis.selected} signal funnel</h2><p class="sub">Every article the pipeline saw this week, and how it narrowed to the issue. The Articles tab shows the reason each one was dropped.</p>${funnel()}</div>
  <div class="card" style="margin-top:16px"><h2>This week’s pipeline</h2><p class="sub">Monday to Wednesday collection, Wednesday selection, your confirmation, Thursday delivery.</p><div class="steps">${steps}</div></div>
  <div class="grid g6">${kpi(k.articles_week,'articles ingested','')}${kpi(k.duplicates,'duplicates caught',S.memory.dup_in_week+' in-week · '+S.memory.dup_past+' vs past issues')}${kpi(k.sources_ok+'/'+k.sources_total,'sources live','RSS · Google News · 3 APIs')}
   ${kpi(S.scored,'scored by Gemini','signal 0–100')}${kpi(avg==null?'—':avg,'avg signal of picks','vs '+avr+' for the rest')}${kpi(k.subscribers,'active subscribers','target 2,200')}</div>
  <div class="grid g2"><div class="card"><h3>Topic diversity radar</h3><div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">${radar(B.axes)}<div class="list" style="flex:1;min-width:190px">
    <div class="r"><span>Stories picked</span><span>${B.count} ${B.count_ok?'<span class="chip ok">8–10 ✓</span>':'<span class="chip bad">need 8–10</span>'}</span></div>
    <div class="r"><span>Distinct sectors</span><span>${B.topics} ${B.topics_ok?'<span class="chip ok">≥3 ✓</span>':'<span class="chip bad">need ≥3</span>'}</span></div></div></div></div>
   <div class="card"><h3>Next scheduled runs (IST)</h3><div class="list">${S.next_runs.map(r=>`<div class="r"><span>${esc(r.label)}</span><span>${when(r.at)}</span></div>`).join('')}</div>
    <h3 style="margin-top:18px">Run a step manually</h3><div class="acts"><button class="act" data-run="ingest">Fetch articles</button><button class="act pri" data-run="select">Run Gemini selection</button><button class="act" data-run="draft">Re-send draft to Telegram</button></div><div class="note" id="note"></div>
    <div class="guard"><span>🔒</span><span>No send button exists here by design. The newsletter is emailed only after you confirm in Telegram.</span></div></div></div>
  <div class="grid g2"><div class="card"><h3>Where the articles came from</h3>${bars(S.sources.slice(0,8))}</div>
   <div class="card"><h3>Activity log</h3><div class="feed">${S.events.slice(0,9).map(e=>`<div class="r"><span class="mut">${esc(short(e.ts))}</span><span><span class="chip">${esc(e.kind)}</span></span><span class="mut">${esc((e.detail||'').slice(0,110))}</span></div>`).join('')}</div></div></div>`;
}

const ACC={free:['ok','🟢 free access'],soft:['warn','🟡 soft paywall'],hard:['bad','🔴 hard paywall'],dead:['bad','🔴 dead link'],unknown:['','⚪ unverified']};
const accChip=i=>{const a=ACC[i.access];return a?`<span class="chip ${a[0]}">${a[1]}</span>`:''};
const altLine=i=>i.alt_url&&['soft','hard','dead'].includes(i.access)?`<div class="mono" style="font-size:11.5px;margin-top:6px">Free coverage: <a href="${esc(i.alt_url)}" target="_blank" rel="noopener">${esc(i.alt_source)}</a> (added to the email)</div>`:(['soft','hard'].includes(i.access)?`<div class="mono mut" style="font-size:11.5px;margin-top:6px">No free coverage of this story found this week.</div>`:'');
const srcPane=i=>{if(!i.source_text)return `<p>${esc(i.snippet||'(no text from the feed; Gemini reasons from the headline)')}</p>`;
  let h=esc(i.source_text.slice(0,1400));(i.quotes||[]).forEach(q=>{const e=esc(q);if(h.includes(e))h=h.replace(e,'<mark>'+e+'</mark>')});
  return `<div class="mono mut" style="font-size:10.5px;margin-bottom:4px">SOURCE TEXT · extracted · ${(i.quotes||[]).length?'key quotes highlighted by Gemini':'no quotes flagged'}</div><div class="src">${h}</div>`};
const TAGS=['Make it more counterintuitive','Focus on regulatory friction','Sharper closer','Shorter','Focus on unit economics'];
function curation(){
  const s=sel();if(!s.length)return `<div class="card"><div class="empty">No draft yet this week. Selection runs Wednesday 2:00 PM IST.</div></div>`;
  const T=S.tuner,notes=(S.issue&&S.issue.selection_notes||'').split('\nFLAG:');
  const sl=(k,l,a,b)=>`<div class="sl"><div class="lab"><span>${l}</span><b id="tv-${k}">${T[k]}</b></div><input type="range" min="0" max="100" value="${T[k]}" data-tune="${k}"><div class="lab"><span>${a}</span><span>${b}</span></div></div>`;
  const cards=s.map(i=>`<div class="rc"><div class="raw"><h4>Raw article · ${esc(i.source)}</h4><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>${srcPane(i)}<span class="chip t">${esc(i.topic)}</span> ${accChip(i)}${altLine(i)}</div>
   <div><h4>Gemini Flash commentary ${i.edited?'· <span class="chip">edited by you</span>':''}</h4><p class="cm">${esc(i.commentary)}</p>${checks(i.checks)}${counterBox(i)}${backlink(i)}
    <div class="tags">${TAGS.map(t=>`<button class="act sm ghost" data-rv="${i.id}" data-ins="${esc(t)}">↻ ${esc(t)}</button>`).join('')}</div>
    ${rv[i.id]?`<div class="rv">${rv[i.id].loading?'Rewriting…':esc(rv[i.id].commentary)}${rv[i.id].checks?`<small>${rv[i.id].checks.every(c=>c.ok)?'✓ passes all voice checks':'⚠ '+rv[i.id].checks.filter(c=>!c.ok).map(c=>c.rule).join(', ')} · preview only: tap Edit in Telegram to use it ${copyBtn('rvt'+i.id,'Copy')}</small><span id="rvt${i.id}" style="display:none">${esc(rv[i.id].commentary)}</span>`:''}</div>`:''}</div>
   <div><h4>Why it was chosen</h4><div style="display:flex;gap:12px;align-items:center">${sigRing(i.signal)}<div><span class="chip t">${esc((i.selection_filter||'').toLowerCase())}</span><div class="mut mono" style="font-size:11px;margin-top:4px">signal ${i.signal==null?'n/a':i.signal+'/100'}</div></div></div>
    <p class="why" style="margin-top:10px">Matched <b>${esc(i.selection_filter)}</b>: ${esc(i.why)}</p>${i.flags?`<div class="flag">${esc(i.flags)}</div>`:''}</div></div>`).join('');
  const opts=s.map(i=>`<option value="${i.id}" ${ed.item==i.id?'selected':''}>#${i.position} ${esc(i.title.slice(0,50))}</option>`).join('');
  return `<div class="grid g2" style="margin-top:0"><div class="card"><h2>Voice micro-tuner</h2><p class="sub">Steers Gemini’s next editorial pass. Style only: the hard voice rules always apply.</p>
    ${sl('cynicism','Cynicism','Pragmatic operator','Witty insider')}${sl('focus','Focus bias','Macro unit economics','Founder / VC incentives')}${sl('density','Density','Strictly 2 lines','Full 3 lines')}
    <div class="acts"><button class="act pri" data-run="select">Re-run selection with this tuning</button><button class="act" id="opendr">Runner-ups drawer (${bk().length})</button></div><div class="note" id="note"></div></div>
   <div class="card"><h2>Voice guardrail editor</h2><p class="sub">Type or paste commentary. Banned words glow red; the rules re-check live.</p>
    <div class="tools" style="margin-bottom:10px"><select id="edsel"><option value="">Free text</option>${opts}</select></div>
    <div class="edw"><div class="hl" id="hl"></div><textarea id="edt" placeholder="Paste a commentary…" rows="4">${esc(ed.text)}</textarea></div><div id="edck" style="margin-top:8px"></div><div id="edsug" class="tags"></div></div></div>
  ${subjectCard()}${fusionCard()}${voiceCard()}
  <div style="margin-top:20px"><h2>Reasoning cards</h2><p class="sub">${esc(notes[0]||'')} Raw article, Gemini’s draft and the editorial reasoning side by side. ${S.kpis.reviewed}/${s.length} ticked in Telegram.</p>${notes[1]?`<div class="flag">⚠ ${esc(notes[1])}</div>`:''}${cards}</div>`;
}
function drawer(){
  const b=bk().slice(0,5);
  $('#drawer').innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center"><h2 style="margin:0">Runner-ups</h2><button class="act sm" id="closedr">Close</button></div>
   <p class="sub" style="margin-top:6px">The next-best stories from this week’s batch. Preview the commentary Gemini would write; to actually swap, tap <b>Swap</b> on that story in Telegram.</p>
   ${b.map(i=>`<div class="ru"><b>${esc(i.title)}</b><div class="mut mono" style="font-size:11px;margin:6px 0">${esc(i.source)} · ${esc(i.topic)} · signal ${i.signal==null?'n/a':i.signal} ${new Set(sel().map(x=>x.topic)).has(i.topic)?'':'<span class="chip ok">adds a new sector</span>'} ${accChip(i)}</div><div style="font-size:12.5px;color:var(--mut)">${esc(i.why)}</div>
    <div class="acts" style="margin-top:10px"><button class="act sm" data-ru="${i.id}">Preview commentary</button></div>${ru[i.id]?`<div class="rv">${ru[i.id].loading?'Drafting…':esc(ru[i.id].commentary)}${ru[i.id].checks?`<small>${ru[i.id].checks.every(c=>c.ok)?'✓ passes all voice checks':'⚠ check the voice rules'}</small>`:''}</div>`:''}</div>`).join('')||'<div class="empty">No runner-ups.</div>'}`;
}
function editorUpdate(){
  const t=$('#edt');if(!t)return;ed.text=t.value;const bad=Object.keys(S.buzz);
  let html=esc(t.value),found=[];
  bad.forEach(w=>{const re=new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');if(re.test(t.value)){found.push(w);html=html.replace(re,m=>`<mark>${m}</mark>`)}});
  $('#hl').innerHTML=html+'\n';
  $('#edsug').innerHTML=found.map(w=>`<button class="act sm ghost" data-swap="${esc(w)}">${esc(w)} → ${esc(S.buzz[w])}</button>`).join('');
  clearTimeout(editorUpdate.t);editorUpdate.t=setTimeout(async()=>{const it=ed.item?S.items.find(x=>x.id==ed.item):null;
    const r=await post('/api/admin/voice-check',{text:t.value,title:it?it.title:'',snippet:it?it.snippet:''});if($('#edck'))$('#edck').innerHTML=t.value.trim()?checks(r.checks):'<span class="mut mono" style="font-size:12px">Waiting for text…</span>'},350);
}

const TCOL={STARTUP:'#F59E0B',COMPANY:'#FBBF24',FOUNDER:'#60A5FA',INVESTOR:'#A78BFA',REGULATOR:'#10B981',OTHER:'#8B8F98'};
function graphSvg(){
  const g=S.graph;if(!g.nodes.length)return '<div class="empty">Entities appear once a draft has been generated.</div>';
  const order=Object.keys(TCOL),nodes=[...g.nodes].sort((a,b)=>order.indexOf(a.type)-order.indexOf(b.type)),W=760,H=480,cx=W/2,cy=H/2,N=nodes.length,pos={};
  nodes.forEach((n,i)=>{const a=-Math.PI/2+2*Math.PI*i/N,R=i%2?150:200;pos[n.name]={x:cx+Math.cos(a)*R*1.35,y:cy+Math.sin(a)*R*.95,a}});
  const conn=gSel?new Set(g.edges.filter(e=>e[0]===gSel||e[1]===gSel).flatMap(e=>[e[0],e[1]])):null;
  const edges=g.edges.map(([a,b,w])=>{const hot=gSel&&(a===gSel||b===gSel);return `<line x1="${pos[a].x}" y1="${pos[a].y}" x2="${pos[b].x}" y2="${pos[b].y}" stroke="${hot?'var(--acc)':'var(--mut)'}" stroke-opacity="${hot?.9:.25}" stroke-width="${hot?2:1}"/>`}).join('');
  const ns=nodes.map(n=>{const p=pos[n.name],r=6+Math.min(8,n.count*2.5),dim=conn&&!conn.has(n.name)&&n.name!==gSel,right=Math.cos(p.a)>=0;
    return `<g class="nd" data-node="${esc(n.name)}" opacity="${dim?.25:1}"><circle cx="${p.x}" cy="${p.y}" r="${r}" fill="${TCOL[n.type]}" fill-opacity=".85" stroke="${n.repeat?'#EF4444':'transparent'}" stroke-width="3"/>
     <text x="${p.x+(right?r+5:-r-5)}" y="${p.y+3}" text-anchor="${right?'start':'end'}" ${n.name===gSel?'style="fill:var(--ink);font-weight:600"':''}>${esc(n.name)}</text></g>`}).join('');
  return `<svg class="gsvg" viewBox="-90 0 ${W+180} ${H}">${edges}${ns}</svg>`;
}
function intelligence(){
  const g=S.graph,M=S.memory,T=S.trends,node=g.nodes.find(n=>n.name===gSel);
  const legend=Object.entries(TCOL).map(([t,c])=>`<span class="chip" style="color:${c}"><i class="dot" style="background:${c};display:inline-block;margin-right:5px"></i>${t.toLowerCase()}</span>`).join('');
  const panel=node?`<h3>${esc(node.name)} · ${node.type.toLowerCase()}</h3>${node.repeat?collision(node):'<span class="chip ok">first appearance in the 4-week window</span>'}
    <div class="list" style="margin-top:10px">${[...node.stories].sort((a,b)=>b.week.localeCompare(a.week)).map(s=>`<div class="r"><span><a href="${esc(s.url)}" target="_blank" rel="noopener" style="text-decoration:none">${esc(s.title)}</a><br><span class="mut mono" style="font-size:11px">${esc(s.topic)}</span></span><span style="text-align:right">${s.days_ago!=null?s.days_ago+' days ago':'wk '+esc(s.week.slice(5))}${s.edition?'<br>'+(s.status==='sent'?'Edition #'+s.edition:'draft (not sent)'):''}</span></div>`).join('')}</div>`:
    `<h3>Click any node</h3><p class="mut" style="font-size:13px">See when and how that startup, founder, investor or regulator was covered in the last four issues.</p>${g.repeats.length?`<div class="flag">Repeat entities this window: ${g.repeats.map(esc).join(', ')}</div>`:'<span class="chip ok">no entity repeats detected</span>'}`;
  const secs=[...new Set((T?T.clusters:[]).flatMap(c=>c.sectors))].sort();
  const heat=T&&T.clusters.length?`<div class="cl" style="--n:${secs.length}"><span></span>${secs.map(s=>`<span class="mut mono" style="font-size:10px;text-align:center">${esc(s.split(' ')[0].replace('&',''))}</span>`).join('')}<span class="mut mono" style="font-size:10px;text-align:center">size</span></div>`+
    [...T.clusters].sort((a,b)=>b.size-a.size).map(c=>`<div class="cl" style="--n:${secs.length}"><span class="nm">${c.cross?'⚡ ':''}${esc(c.name)}</span>${secs.map(s=>{const on=c.sectors.includes(s);return `<span style="height:26px;border-radius:6px;display:grid;place-items:center;font:11px var(--mono);background:${on?(c.cross?'rgba(245,158,11,'+(.25+c.size/30)+')':'rgba(16,185,129,'+(.2+c.size/30)+')'):'var(--soft)'}">${on?c.size:''}</span>`}).join('')}<span class="mono mut" style="text-align:center">${c.size}</span></div>`).join(''):'<div class="empty">No trend clusters yet.</div>';
  const ins=T?T.clusters.filter(c=>c.cross&&c.insight).slice(0,4).map(c=>`<div class="r"><span><b>${esc(c.sectors.join(' × '))}</b><br>${esc(c.insight)}</span><span class="mono" style="font-size:11px">${esc(c.name)}</span></div>`).join(''):'';
  const wk=M.weeks;
  const mat=wk.length?`<div class="hm" style="grid-template-columns:150px repeat(${wk.length},1fr)"><span></span>${wk.map(w=>`<span class="hd">${esc(w.slice(5))}${w===S.week?' ●':''}</span>`).join('')}${M.topics.map(t=>`<span class="rn">${esc(t)}</span>`+wk.map(w=>{const n=(M.matrix[t]||{})[w]||0;return `<span class="cell" style="${n?`background:rgba(245,158,11,${.18+n*.22});color:var(--ink)`:''}">${n||''}</span>`}).join('')).join('')}</div>`:'<div class="empty">No history yet.</div>';
  return `<div class="grid g21" style="margin-top:0"><div class="card"><h2>4-week entity knowledge graph</h2><p class="sub">Startups, founders, investors and regulators across the last four issues and this one. A red ring means the entity has been covered in more than one issue.</p><div class="kv" style="margin-bottom:10px">${legend}</div>${graphSvg()}</div><div class="card">${panel}</div></div>
  <div class="grid g2"><div class="card"><h2>Trend density heatmap</h2><p class="sub">${T?T.clusters.reduce((a,c)=>a+c.size,0)+' of '+S.kpis.articles_week:'The '+S.kpis.articles_week} articles grouped by Gemini into emerging trend clusters. ⚡ marks clusters that connect different sectors.</p>${heat}${ins?`<h3 style="margin-top:18px">Cross-sector links nobody has stated</h3><div class="list">${ins}</div>`:''}</div>
   <div class="card"><h2>Archive memory matrix</h2><p class="sub">Stories by sector across the issues in the 4-week window. This is what the pipeline checks new picks against.</p>${mat}
    <h3 style="margin-top:18px">Overlap flags for this week’s picks</h3>${M.overlaps.length?`<div class="list">${M.overlaps.map(o=>`<div class="r"><span>${esc(o.title)}</span><span class="chip bad">${o.entities.map(esc).join(', ')} · wk ${o.weeks.map(w=>w.slice(5)).join(', ')}</span></div>`).join('')}</div>`:'<span class="chip ok">No entity overlap with earlier issues</span>'}
    <div class="kv" style="margin-top:14px"><span class="pill info">${M.dup_in_week} duplicate headlines inside this week</span><span class="pill warn">${M.dup_past} matched stories from earlier issues</span></div></div></div>`;
}

function simInit(){sim={kept:{},swapped:{},used:{},menu:null,editing:null,edits:{},tuned:{},voice:null,angles:{},conf:0,loading:{}}}
const TUNE_TXT=['Make it a notch spicier and more opinionated: a sharper claim and a dry edge.','Bring in the unit-economics angle. Use only numbers present in the article text.','Rewrite in exactly 2 sentences, keeping the sharpest claim and the closer.'];
function phone(){
  if(!sim)simInit();const s=sel();let h=`<div class="msg"><b>The Dispatch · draft for week of ${esc(S.week)}</b><br>${s.length} stories · ${S.kpis.subscribers} active subscribers<br><span style="color:#8fa3b8">Review each story: Keep, Swap (3 options), Edit, Voice or Angles. Nothing is sent until you confirm.</span></div>`;
  s.forEach(i=>{const sw=sim.swapped[i.id],title=sw?sw.title:i.title,cm=sim.edits[i.id]||(sw?sw.commentary:i.commentary),src=sw?sw.source:i.source,mark=sim.kept[i.id]?'✅ ':'';
    if(sim.menu===i.id){const opts=bk().filter(b=>!sim.used[b.id]).slice(0,3);
      h+=`<div class="msg"><b>🔄 Swap story ${i.position}</b>: choose a replacement<br><br>${opts.map((b,n)=>`<b>${'ABC'[n]})</b> <a>${esc(b.title.slice(0,90))}</a> (${esc(b.source)}) · ${esc(b.topic)}<br>${esc(b.commentary||'(drafted on demand in the real bot)')}`).join('<br><br>')||'No runner-ups left.'}<div class="kb">${opts.map((b,n)=>`<button data-sim="pick:${i.id}:${b.id}">Select ${'ABC'[n]}</button>`).join('')}</div><div class="kb one"><button data-sim="back:${i.id}">↩️ Keep original</button></div></div>`;return}
    h+=`<div class="msg"><b>${mark}${i.position}/${s.length} · ${esc(sw?sw.topic:i.topic)}</b>${sim.edits[i.id]?' · ✏️ edited':''}<br><a>${esc(title)}</a> (${esc(src)})${i.access==='hard'||i.access==='soft'?`<br>${i.access==='hard'?'🔴 hard paywall':'🟡 soft paywall'}`:''}<br><br>${sim.loading[i.id]?'<i>Gemini is working on it…</i>':esc(cm)}
     <div class="kb"><button data-sim="keep:${i.id}">✅ Keep</button><button data-sim="swap:${i.id}">🔄 Swap</button><button data-sim="edit:${i.id}">✏️ Edit</button></div>
     <div class="kb"><button data-sim="voice:${i.id}">🎙 Voice</button><button data-sim="ang:${i.id}">🧠 Angles</button></div>
     <div class="kb"><button data-sim="tune:${i.id}:0">🔥 Spicier</button><button data-sim="tune:${i.id}:1">📊 Unit econ.</button><button data-sim="tune:${i.id}:2">✂️ Trim</button></div>${sim.tuned[i.id]?`<div class="kb one"><button data-sim="reset:${i.id}">↩️ Back to Gemini's original</button></div>`:''}</div>`;
    if(sim.voice===i.id)h+=`<div class="msg">🎙 <b>Voice comment for story ${i.position}.</b> Reply to this message with a voice note: just say your raw take. I'll turn it into 2 to 3 sharp lines in your voice.<br><span style="color:#8fa3b8">(Works in the real bot: hold the mic and speak. Try it in Telegram.)</span></div>`;
    if(sim.angles[i.id])h+=`<div class="msg">🧠 <b>Angles for story ${i.position}</b>: things to check, not facts<br>${(i.counter||[]).map(c=>'• '+esc(c)).join('<br>')||'No angles were generated for this story.'}</div>`;
    if(sim.editing===i.id)h+=`<div class="msg me"><div style="font-size:11px;color:#a9c4e0;margin-bottom:4px">Reply with your version of story ${i.position}</div><textarea id="simtxt">${esc(cm)}</textarea><div class="kb one"><button data-sim="save:${i.id}">Send</button></div></div>`});
  h+=`<div class="msg">When you are happy with the draft:<div class="kb one"><button data-sim="confirm:0">📬 Confirm final draft</button></div></div>`;
  if(sim.conf>=1)h+=`<div class="msg">Send this issue to <b>${S.kpis.subscribers}</b> subscribers on Thursday morning?<br>${s.filter(i=>!sim.kept[i.id]).length} stories not yet ticked with Keep. This is the final confirmation.<div class="kb"><button data-sim="yes:0">✅ Yes, send Thursday</button><button data-sim="no:0">Cancel</button></div></div>`;
  if(sim.conf===2)h+=`<div class="msg">✅ <b>Confirmed.</b> It will go out Thursday 8:00 AM IST.<br><span style="color:#8fa3b8">(Simulation: nothing was sent and the real draft is unchanged.)</span></div>`;
  return `<div class="phone"><div class="ph"><div class="av">D</div><div><b>THE DISPATCH</b><small>@Dispatch_Mesa_Bot · bot</small></div></div><div class="body" id="simbody">${h}</div><div class="ft">Sandbox · tap the buttons exactly as you would in Telegram</div></div>`;
}
function telegram(){
  const tl=S.approval.map(a=>`<div class="i ${a.state}"><b style="font:600 12px var(--mono)">${esc(a.label)}</b><div class="mut mono" style="font-size:11.5px">${a.ts?esc(short(a.ts)):'pending'} · ${esc(a.note)}</div></div>`).join('');
  return `<div class="grid g12" style="margin-top:0"><div class="card"><h2>Embedded Telegram simulator</h2><p class="sub">The real draft, rendered like your phone. The buttons work, but only in this sandbox. Swap shows the three pre-drafted runner-ups, each with its own commentary.</p>${phone()}<div class="acts" style="justify-content:center;margin-top:14px"><button class="act sm" data-sim="reset:0">Reset simulation</button><a class="act sm" href="${esc(S.bot)}" target="_blank" rel="noopener" style="text-decoration:none">Open the real bot ↗</a></div></div>
   <div class="stack"><div class="card"><h2>Approval pipeline</h2><p class="sub">What has actually happened this week.</p><div class="tl">${tl}</div><div class="acts"><button class="act" data-run="draft">Force re-send draft to Telegram</button><button class="act" data-run="ping">Ping reminder now</button></div><div class="note" id="note"></div></div>
   <div class="card"><h3>Why approval stays in Telegram</h3><div class="list"><div class="r"><span>Two-step confirmation</span><span>Confirm → “Yes, send Thursday”</span></div><div class="r"><span>Only your chat is obeyed</span><span>chat id + webhook secret</span></div><div class="r"><span>Swaps and edits</span><span>saved to the real draft there</span></div><div class="r"><span>This page is open to anyone</span><span>so it can preview, never approve</span></div></div></div></div></div>`;
}

const xlen=t=>t.replace(/https?:\/\/\S+/g,'x'.repeat(23)).length;   // X counts every link as 23 characters
function xthread(){const s=sel();if(!s.length)return[];const out=[`🧵 The Dispatch · this week in Indian startups: ${s.length} stories worth your time, with the part the headline leaves out. ↓`];
  s.forEach((i,n)=>{let t=i.commentary.replace(/\s+/g,' ');const link=' '+i.url,max=280-24-String(n+1).length-String(s.length).length-3;if(t.length>max){const sents=t.match(/[^.?]+[.?]/g)||[t];t='';for(const x of sents){if((t+x).length>max)break;t+=x}t=(t||sents[0]).trim().slice(0,max)}out.push(`${n+1}/${s.length} ${t}${link}`)});
  out.push(`That’s the week. The full issue lands in inboxes every Thursday. Subscribe: ${S.public_url}`);return out}
function linkedin(){const s=sel();if(!s.length)return '';return `The Dispatch, week of ${S.week}: ${s.length} stories on the Indian startup ecosystem, and what each one is really saying.\n\n`+s.map((i,n)=>`${n+1}. ${i.title}\n${i.commentary}`).join('\n\n')+`\n\nI send the full issue every Thursday. Subscribe: ${S.public_url}`}
function delivery(){
  const L=S.launchpad,lc=S.linkcheck,E=S.engagement,it=sel();const th=xthread();
  const lcRows=lc?lc.rows.map(r=>`<tr><td>#${r.position}</td><td class="ti"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></td><td><span class="chip ${r.state==='ok'?'ok':'bad'}">${r.state}</span></td><td class="mono">${r.status||'—'}</td><td class="mono mut">${r.ms} ms</td></tr>`).join(''):'';
  return `<div class="card"><div class="lp"><div class="lamp ${L.armed?'armed':'safe'}">${L.armed?'🟢':'🛡️'}</div><div style="flex:1;min-width:240px"><h2 style="margin-bottom:2px">Fail-safe launchpad</h2><div class="mono" style="font-size:13px;color:${L.armed?'var(--ok)':'var(--acc)'}">${esc(L.headline)}</div>
   <p class="sub" style="margin:6px 0 0">Three independent locks: Telegram’s two-step confirm, a database check in the sender, and the Thursday job. Delivery without your confirmation is blocked at three independent points.</p></div>
   <div style="text-align:right"><div class="mono mut" style="font-size:11px;margin-bottom:6px">is_confirmed</div><span class="sw ${L.confirmed?'on':''}"></span> <b class="mono">${L.confirmed}</b></div></div>
   <div class="list" style="margin-top:14px">${L.checks.map(c=>`<div class="r"><span>${c.ok?'<span class="chip ok">✓</span>':'<span class="chip bad">✗</span>'} ${esc(c.label)}</span><span>${esc(c.detail)}</span></div>`).join('')}</div></div>
  <div class="grid g2"><div class="card"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center"><h2>Email preview</h2><div class="acts"><div class="seg"><button class="${pvDev==='desktop'?'on':''}" data-pv="desktop">Desktop</button><button class="${pvDev==='mobile'?'on':''}" data-pv="mobile">Mobile</button></div><div class="seg"><button class="${!pvDark?'on':''}" data-pvd="0">Light</button><button class="${pvDark?'on':''}" data-pvd="1">Dark</button></div></div></div>
    <p class="sub">The exact HTML subscribers would receive, built from the current draft. Dark mode is simulated.</p><div class="pv ${pvDark?'dk':''}"><div class="pvh"><b>The Dispatch</b> &lt;onboarding@resend.dev&gt;<br><span class="mut">Subject: The Dispatch · ${S.week}</span></div><iframe class="pvf" src="/api/admin/email-preview" style="width:${pvDev==='mobile'?'375px':'100%'}"></iframe></div></div>
   <div class="stack"><div class="card"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><h2>Pre-flight link health</h2><button class="act sm" data-run="linkcheck">Run check now</button></div><p class="sub">Pings every selected URL for dead links, 404s and paywalls. Runs automatically Thursday 8:00 AM, before sending; problems come to you on Telegram.</p>
     ${lc?`<div class="kv" style="margin-bottom:10px"><span class="pill ${lc.problems?'bad':'ok'}">${lc.problems?lc.problems+' need attention':'all '+lc.rows.length+' links healthy'}</span><span class="pill">checked ${esc(short(lc.at))} IST</span></div><div class="tw"><table><tbody>${lcRows}</tbody></table></div>`:'<div class="empty">Not run yet this week.</div>'}<div class="note" id="note"></div></div>
    <div class="card"><h2>Engagement</h2><p class="sub">Open and click events arrive through the Resend webhook once emails go out from a verified domain.</p><div class="grid g2" style="margin:0;align-items:center"><div>${gauge(E.open_rate,S.benchmark_open_rate)}</div><div>
     <div class="list"><div class="r"><span>Delivered</span><span>${E.delivered}</span></div><div class="r"><span>Opened</span><span>${E.opened}</span></div><div class="r"><span>Clicked</span><span>${E.clicked}</span></div></div></div></div>
     <h3 style="margin-top:16px">Clicks by story topic</h3>${E.clicks_by_topic.length?bars(E.clicks_by_topic):'<div class="mut" style="font-size:13px">No tracked clicks yet. Nothing here is estimated.</div>'}</div></div></div>
  ${deliverCard()}${featuredCard()}
  <div class="card" style="margin-top:16px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><h2>Social repurposing</h2><div class="seg"><button class="${socTab==='x'?'on':''}" data-soc="x">X thread</button><button class="${socTab==='li'?'on':''}" data-soc="li">LinkedIn post</button></div></div>
   <p class="sub">Built from the current draft’s commentary. Posts stay inside the platform limits.</p>
   ${!it.length?'<div class="empty">No draft yet.</div>':socTab==='x'?`<div class="acts" style="margin-bottom:10px">${copyBtn('xall','Copy whole thread')}<span class="mut mono" style="font-size:12px">${th.length} posts</span></div><span id="xall" style="display:none">${esc(th.join('\n\n'))}</span>${th.map(t=>`<div class="soc tw1"><span class="mono mut" style="font-size:11px">${xlen(t)}/280</span><br>${esc(t)}</div>`).join('')}`:
   `<div class="acts" style="margin-bottom:10px">${copyBtn('liall','Copy post')}<span class="mut mono" style="font-size:12px">${linkedin().length} characters</span></div><span id="liall" style="display:none">${esc(linkedin())}</span><div class="soc">${esc(linkedin())}</div>`}</div>`;
}

function subscribers(){
  const c=S.sub_counts,G=S.growth,pct=Math.min(100,G.active/G.target*100),prob=S.subscribers.filter(s=>['bounced','complained','unsubscribed'].includes(s.status));
  const total=(c.active||0)+(c.bounced||0)+(c.complained||0),health=total?Math.round(100*(c.active||0)/total):100;
  return `<div class="card"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><h2>Growth toward 2,200</h2><span class="mono mut">${G.active} active · ${(G.target-G.active).toLocaleString()} to go</span></div><div class="br" style="grid-template-columns:1fr;margin-top:10px"><span class="tr" style="height:12px"><i class="fi" style="width:${Math.max(1.5,pct)}%"></i></span></div>
   <p class="sub" style="margin:8px 0 0">Your existing list is imported once; sign-ups after that confirm by email. ${S.subscribers.some(s=>s.note==='sample')?'The list shown here is generated sample data: test addresses, not real people.':''}</p></div>
  <div class="grid g4">${kpi(c.active||0,'active','')}${kpi(c.pending||0,'pending confirmation','')}${kpi(c.unsubscribed||0,'unsubscribed','')}${kpi(health+'%','list health',(c.bounced||0)+' bounced · '+(c.complained||0)+' complaints')}</div>
  <div class="grid g21"><div class="card"><h2>Bounce &amp; health safeguard</h2><p class="sub">Permanent bounces, spam complaints and unsubscribes are logged and removed from the send list automatically. No spreadsheet cleaning.</p>
    <div class="tw"><table><thead><tr><th>Address</th><th>Category</th><th>Detail</th><th>When</th></tr></thead><tbody>${prob.map(s=>`<tr><td class="mono">${esc(s.email)}</td><td>${pill(s.status)}</td><td class="mut">${esc(s.note==='sample'?'sample record':(s.note||''))}</td><td class="mono mut">${esc(short(s.status_changed_at))}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Nothing to clean.</td></tr>'}</tbody></table></div></div>
   <div class="card"><h3>Why people unsubscribe</h3>${S.unsub_reasons.length?bars(S.unsub_reasons.map(r=>[r.r,r.n])):'<div class="mut" style="font-size:13px">No reasons recorded yet. The unsubscribe page asks for an optional reason.</div>'}
    <div class="list" style="margin-top:14px"><div class="r"><span>Unsubscribe link in every email</span><span>one click</span></div><div class="r"><span>Hard bounce / complaint</span><span>auto-removed</span></div><div class="r"><span>New sign-ups</span><span>double opt-in</span></div></div></div></div>
  <div class="grid g2"><div class="card"><h2>Add subscribers</h2><p class="sub">${S.confirm_mode==='instant'?'Addresses are added as active straight away, because the sender is still Resend’s shared test address and cannot deliver confirmation emails to other inboxes.':'Each address gets the normal confirmation email first.'} Up to 10 at a time. Addresses are masked on this page.</p><textarea class="ta" id="em" placeholder="priya@example.com"></textarea><div class="acts" style="margin-top:10px"><button class="act pri" id="addsub">${S.confirm_mode==='instant'?'Add subscribers':'Send confirmation'}</button></div><div class="note" id="note"></div></div>
   <div class="card"><h3>Send log</h3><div class="tw"><table><thead><tr><th>Week</th><th>Status</th><th>Sent</th><th>Failed</th></tr></thead><tbody>${S.sends.map(x=>`<tr><td>${esc(x.week)}</td><td>${pill(x.status)}</td><td>${x.sent||0}</td><td>${x.failed||0}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Nothing sent yet.</td></tr>'}</tbody></table></div></div></div>`;
}

function articles(){
  const srcs=[...new Set(S.articles.map(a=>a.source))].sort();
  let rows=S.articles.filter(a=>(!F.filter||a.signal_filter===F.filter)&&(!F.topic||(a.topic||'').startsWith(F.topic))&&(F.status==='all'||a.status===F.status)&&(F.source==='all'||a.source===F.source)&&(!F.q||(a.title+a.source).toLowerCase().includes(F.q.toLowerCase())));
  if(F.sort==='signal')rows=[...rows].sort((a,b)=>(b.signal??-1)-(a.signal??-1));
  const tot=rows.length;rows=rows.slice(0,F.limit);const c={all:S.articles.length};S.articles.forEach(a=>c[a.status]=(c[a.status]||0)+1);
  return `<div class="card"><h2>Signal-to-noise live feed</h2><p class="sub">${S.articles.length<S.kpis.articles_week?`Showing ${S.articles.length} of ${S.kpis.articles_week} articles stored this week`:'Every article stored this week'}, rated 0–100 by Gemini for editorial signal. ${S.scored} of ${S.articles.length} scored. Duplicates are kept for the audit trail.</p>
  <div class="tools">${F.filter||F.topic?`<button class="act sm" id="clrf">Clear filter: ${esc(F.filter||F.topic)} ✕</button>`:''}<input id="q" placeholder="Search…" value="${esc(F.q)}"><select id="fs"><option value="all">All statuses (${c.all})</option>${['new','selected','dup'].map(s=>`<option value="${s}" ${F.status===s?'selected':''}>${badge(s)[1]} (${c[s]||0})</option>`).join('')}</select>
   <select id="fsrc"><option value="all">All sources</option>${srcs.map(s=>`<option ${F.source===s?'selected':''}>${esc(s)}</option>`).join('')}</select><select id="fsort"><option value="time" ${F.sort==='time'?'selected':''}>Newest first</option><option value="signal" ${F.sort==='signal'?'selected':''}>Highest signal first</option></select></div>
  <div class="tw"><table><thead><tr><th>Headline</th><th>Source</th><th>Signal</th><th>Status</th><th>Published</th></tr></thead><tbody>
  ${rows.map(a=>`<tr><td class="ti"><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a><div class="why-d">${esc(a.reason||'')}</div></td><td>${esc(a.source)}</td>
   <td><div class="sig">${a.signal==null?'<span class="mut">—</span>':`<i class="${a.signal>=70?'hi':''}" style="width:${Math.max(4,a.signal*.55)}px"></i>${a.signal}`}</div>${a.signal_filter&&a.signal_filter!=='NONE'?`<span class="chip">${esc(a.signal_filter.toLowerCase())}</span>`:''}</td>
   <td>${pill(a.status)}${a.topic?` <span class="chip t">${esc(a.topic)}</span>`:''}</td><td class="mono mut">${esc(short(a.published_at))}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Nothing matches.</td></tr>'}</tbody></table></div>
  ${tot>F.limit?`<div class="more"><button class="act" id="more">Show more (${tot-F.limit} left)</button></div>`:''}</div>`;
}

function sources(){
  const g=S.ingest;if(!g)return `<div class="card"><div class="empty">No ingest has run yet.</div></div>`;
  const fail=Object.entries(g.sources_failed||{}),ok=Object.entries(g.per_source||{}).sort((a,b)=>b[1]-a[1]);
  const kinds=[['RSS feeds',ok.filter(x=>x[0].startsWith('rss:'))],['Google News searches',ok.filter(x=>x[0].startsWith('google:'))],['News APIs (NewsAPI, GNews, NewsData.io)',ok.filter(x=>/^(newsapi|gnews|newsdata)/.test(x[0]))],['Other',ok.filter(x=>/^(hackernews|gdelt)/.test(x[0]))]];
  const kn={GEMINI_API_KEY:'Gemini',DATABASE_URL:'Neon',TELEGRAM_BOT_TOKEN:'Telegram',RESEND_API_KEY:'Resend',RESEND_WEBHOOK_SECRET:'Resend webhook',NEWSAPI_KEY:'NewsAPI',GNEWS_API_KEY:'GNews',NEWSDATA_API_KEY:'NewsData.io'};
  const st=S.style;
  return `<div class="card"><h2>Source health</h2><p class="sub">Last ingest ${esc(short(g.at))} IST · ${g.sources_ok} of ${g.sources_total} sources returned articles · ${g.seen||0} seen, ${g.new||0} new, ${g.dup||0} duplicates, ${g.old||0} too old, ${g.exists||0} already stored.</p>
  <div class="kv">${Object.entries(S.keys).map(([k,v])=>`<span class="pill ${v?'ok':'bad'}"><i class="dot"></i>${kn[k]||k}</span>`).join('')}<span class="pill info">model ${esc(S.model)}</span><span class="pill">style guide v${st.version} · ${st.examples} examples · ${st.banned} banned phrases</span></div></div>
  <div class="grid g2">${kinds.filter(k=>k[1].length).map(([t,r])=>`<div class="card"><h3>${t}</h3>${bars(r.map(([n,v])=>[n.replace(/^(rss|google|newsapi|gnews|newsdata):/,''),v]),Math.max(...ok.map(x=>x[1])))}</div>`).join('')}</div>
  ${fail.length?`<div class="card" style="margin-top:16px"><h3>Failed on the last run</h3><div class="list">${fail.map(([n,e])=>`<div class="r"><span>${esc(n)}</span><span>${esc(e)}</span></div>`).join('')}</div></div>`:''}`;
}

const counterBox=i=>(i.counter&&i.counter.length)?`<details class="dv"><summary>🧠 Devil’s advocate: ${i.counter.length} things to check</summary><ul>${i.counter.map(c=>`<li>${esc(c)}</li>`).join('')}</ul><div class="mono mut" style="font-size:10.5px">Prompts to verify, not facts.</div></details>`:'';
const backlink=i=>{const b=((S.memory||{}).backlinks||[]).find(x=>x.title===i.title);return b?`<div class="rv" style="font-size:14px;margin-top:10px">🔗 <b>Backlink idea:</b> ${esc(b.text)} <a href="${esc(b.url)}" target="_blank" rel="noopener">open</a></div>`:''};
const collision=n=>{const st=[...n.stories].sort((a,b)=>b.week.localeCompare(a.week));const l=st.find(x=>x.days_ago!=null);return `<div class="flag" style="background:var(--bad-soft);color:var(--bad)">⚠ Collision: ${l?`covered ${l.days_ago} days ago in ${l.status==='sent'?'Edition #'+l.edition:'an earlier draft issue (not sent)'}`:'covered in an earlier issue'}${n.weeks.length>1?` and in ${n.weeks.length} issues in total`:''}. Avoid repeating the angle.</div>`};
function subjectCard(){const o=(S.issue&&S.issue.subject_options)||[];if(!o.length)return '';return `<div class="card" style="margin-top:16px"><h2>Subject line options</h2><p class="sub">Gemini’s three hooks for this issue. You pick one in Telegram; A is used if you do not. No open-rate prediction is shown: that needs your past performance data.</p><div class="list">${o.map((x,n)=>`<div class="r"><span><b class="serif" style="font-size:17px">${'ABC'[n]}) ${esc(x.subject)}</b><br><span class="mut" style="font-size:12.5px">${esc(x.preheader)}</span></span><span><span class="chip t">${esc(x.style.toLowerCase())}</span>${S.issue.subject===x.subject?' <span class="chip ok">in use</span>':''}</span></div>`).join('')}</div></div>`}
function voiceCard(){const st=S.style;return `<div class="card" style="margin-top:16px"><h2>Voice evolution</h2><p class="sub">Every edit you make (typed or spoken) is logged against Gemini’s draft. On the 1st of each month the best pairs become new few-shot examples in a new style-guide version; older versions are kept.</p>
 <div class="kv"><span class="pill info">style guide v${st.version}</span><span class="pill">${st.examples} examples</span><span class="pill">${st.edits_total} edits captured</span><span class="pill ${st.edits_pending?'warn':''}">${st.edits_pending} waiting to be learned</span></div><div class="acts" style="margin-top:12px"><button class="act sm" data-run="promote">Learn from my edits now</button></div><div class="note" id="note"></div></div>`}
function fusionCard(){const s=sel();if(s.length<2)return '';const fus=(S.issue&&S.issue.fusions)||[],byPos={};s.forEach(i=>byPos[i.position]=i);
  const A=fz&&s.find(i=>i.id===fz.a),B=fz&&s.find(i=>i.id===fz.b);
  return `<div class="card" style="margin-top:16px"><h2>Trend-fusion canvas</h2><p class="sub">Drag a line from one story to another. Gemini connects the two into one trend-connecting commentary block, in your voice. Preview only.</p>
  <div class="fz" id="fz"><svg class="fzsvg"><line id="fzl" stroke="var(--acc)" stroke-width="3" stroke-dasharray="6 5" style="display:none"/><line id="fzf" stroke="var(--acc)" stroke-width="3" style="display:none"/></svg>${s.map(i=>`<div class="fnode ${fz&&(fz.a===i.id||fz.b===i.id)?'on':''}" data-id="${i.id}"><b>${i.position} · ${esc(i.topic)}</b>${esc(i.title.length>78?i.title.slice(0,76)+'…':i.title)}</div>`).join('')}</div>
  ${fus.length?`<div class="tags" style="margin-top:12px"><span class="mono mut" style="font-size:11px;align-self:center">Gemini suggests:</span>${fus.map(f=>byPos[f.a]&&byPos[f.b]?`<button class="act sm ghost" data-fz="${byPos[f.a].id},${byPos[f.b].id}" title="${esc(f.angle)}">${f.a} × ${f.b}</button>`:'').join('')}</div>`:''}
  ${fz?`<div class="rv" style="margin-top:14px">${fz.loading?'Connecting the dots…':fz.res?`<b>${A?A.position:''} × ${B?B.position:''}</b><br>${esc(fz.res.commentary)}<small>${fz.res.checks.every(c=>c.ok)?'✓ passes all voice checks':'⚠ '+fz.res.checks.filter(c=>!c.ok).map(c=>c.rule).join(', ')} · preview only ${copyBtn('fzt','Copy')}</small><span id="fzt" style="display:none">${esc(fz.res.commentary)}</span>`:esc(fz.msg||'')}</div>`:''}</div>`}
function fzDraw(){const f=$('#fzf'),box=$('#fz');if(!f||!box)return;if(!(fz&&fz.a&&fz.b)){f.style.display='none';return}const r=box.getBoundingClientRect(),a=box.querySelector(`.fnode[data-id="${fz.a}"]`),b=box.querySelector(`.fnode[data-id="${fz.b}"]`);if(!a||!b)return;
  const A=a.getBoundingClientRect(),B=b.getBoundingClientRect();f.setAttribute('x1',A.left+A.width/2-r.left);f.setAttribute('y1',A.top+A.height/2-r.top);f.setAttribute('x2',B.left+B.width/2-r.left);f.setAttribute('y2',B.top+B.height/2-r.top);f.style.display='block'}
async function fuseRun(a,b){fz={a,b,loading:true};render();const j=await post('/api/admin/fuse',{a,b});fz={a,b,res:j.ok?j:null,msg:j.ok?'':(j.message||'Try again shortly.')};render()}
function deliverCard(){const d=S.deliverability||[];if(!d.length)return '';const bad=d.filter(x=>!x.ok).length;return `<div class="card" style="margin-top:16px"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px"><h2>Deliverability check</h2><span class="pill ${bad?'warn':'ok'}">${bad?bad+' to fix':'all clear'}</span></div><p class="sub">Heuristic checks on the assembled email for the current draft. They protect the open rate; this is not a full spam-filter simulation.</p><div class="list">${d.map(x=>`<div class="r"><span>${x.ok?'<span class="chip ok">✓</span>':'<span class="chip bad">✗</span>'} ${esc(x.rule)}</span><span>${esc(x.detail)}</span></div>`).join('')}</div></div>`}
function featuredCard(){const seen={},rows=[];sel().forEach(i=>(i.entities||[]).forEach(e=>{if(['STARTUP','COMPANY','FOUNDER','INVESTOR'].includes(e.type)&&!seen[e.name]){seen[e.name]=1;rows.push({...e,story:i})}}));if(!rows.length)return '';
  return `<div class="card" style="margin-top:16px"><h2>Featured this week: outreach list</h2><p class="sub">Startups, founders and investors covered in this edition. Handles are never guessed: each row opens a search for you, and the message is ready to copy. You send them yourself.</p><div class="tw"><table><thead><tr><th>Name</th><th>Type</th><th>Story</th><th></th></tr></thead><tbody>${rows.map((r,n)=>`<tr><td><b>${esc(r.name)}</b></td><td><span class="chip">${r.type.toLowerCase()}</span></td><td class="mut">#${r.story.position}</td><td><div class="acts"><a class="act sm" style="text-decoration:none" target="_blank" rel="noopener" href="https://x.com/search?q=${encodeURIComponent(r.name)}&f=user">Find on X</a><a class="act sm" style="text-decoration:none" target="_blank" rel="noopener" href="https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(r.name)}">LinkedIn</a>${copyBtn('dm'+n,'Copy message')}</div><span id="dm${n}" style="display:none">${esc(`Hi, ${r.name} came up in this week's The Dispatch (story ${r.story.position}: "${r.story.title.slice(0,90)}"). Thought you might want to see it: ${S.public_url}`)}</span></td></tr>`).join('')}</tbody></table></div></div>`}
const V={command,curation,intelligence,telegram,delivery,subscribers,articles,sources};
function render(){head();$('#main').innerHTML=(V[tab]||V.command)();if(tab==='curation')editorUpdate();drawer();$('#drawer').classList.toggle('open',openDrawer);$('#scrim').classList.toggle('open',openDrawer);fzDraw()}
async function load(){const r=await fetch('/api/admin/state');S=await r.json();fetchedAt=Date.now();render()}
async function silent(){const keepNote=$('#note')&&$('#note').textContent,cls=$('#note')&&$('#note').className;const r=await fetch('/api/admin/state?fresh=true');if(!r.ok)return;S=await r.json();fetchedAt=Date.now();
  const x=document.activeElement;if(x&&x.matches('input,textarea,select'))return head();render();const n=$('#note');if(n&&keepNote){n.className=cls;n.textContent=keepNote}}
const flash=(m,id)=>{const n=$(id||'#note');if(n){n.className='note show';n.textContent=m}};
document.addEventListener('click',async e=>{
  const g=s=>e.target.closest(s);let b;
  if(b=g('[data-t]')){tab=b.dataset.t;location.hash=tab;render();return}
  if(g('#theme')){const t=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=t;try{localStorage.setItem('dispatch-theme',t)}catch(x){}return}
  if(e.target.id==='more'){F.limit+=100;render();return}
  if(b=g('[data-run]')){const old=b.textContent;b.disabled=true;b.textContent='Working…';const id=b.closest('#banner')?'#bnote':'#note';flash('Running. Selection can take up to a minute.',id);
    try{const j=await post('/api/admin/run/'+b.dataset.run);flash((j.ok?'✓ ':'✗ ')+(j.message||j.detail||'done'),id)}catch(x){flash('✗ '+x,id)}b.disabled=false;b.textContent=old;await silent();return}
  if(b=g('[data-snooze]')){const j=await post('/api/admin/snooze',{minutes:+b.dataset.snooze});flash((j.ok?'✓ ':'✗ ')+j.message,'#bnote');await silent();return}
  if(b=g('[data-rv]')){const id=+b.dataset.rv;rv[id]={loading:true};render();const j=await post('/api/admin/revoice',{item_id:id,instruction:b.dataset.ins});rv[id]=j.ok?j:{commentary:j.message||'Could not rewrite right now.'};render();return}
  if(b=g('[data-ru]')){const id=+b.dataset.ru;ru[id]={loading:true};drawer();const j=await post('/api/admin/preview-commentary',{item_id:id});ru[id]=j.ok?j:{commentary:j.message||'Try again shortly.'};drawer();return}
  if(g('#opendr')){openDrawer=true;render();return}if(g('#closedr')||e.target.id==='scrim'){openDrawer=false;render();return}
  if(b=g('[data-swap]')){const t=$('#edt'),w=b.dataset.swap,re=new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');t.value=t.value.replace(re,S.buzz[w]);editorUpdate();return}
  if(b=g('[data-node]')){gSel=gSel===b.dataset.node?null:b.dataset.node;render();return}
  if(b=g('[data-pv]')){pvDev=b.dataset.pv;render();return}if(b=g('[data-pvd]')){pvDark=b.dataset.pvd==='1';render();return}if(b=g('[data-soc]')){socTab=b.dataset.soc;render();return}
  if(b=g('[data-copy]')){const el=document.getElementById(b.dataset.copy);try{await navigator.clipboard.writeText(el.textContent);b.textContent='Copied ✓'}catch(x){b.textContent='Select + copy manually'}return}
  if(b=g('[data-fz]')){const[x,y]=b.dataset.fz.split(',').map(Number);await fuseRun(x,y);return}
  if(g('#clrf')){F.filter='';F.topic='';render();return}
  if(g('#kbtn')){palOpen();return}
  if(b=g('.pi')){palRun(+b.dataset.i);return}
  if(e.target.id==='pal'){palClose();return}
  if(b=g('[data-sim]')){await simAct(b.dataset.sim);return}
  if(e.target.id==='addsub'){flash('Sending…');const j=await post('/api/admin/subscribers',{emails:$('#em').value});flash(j.ok?`✓ ${j.added} ${j.mode==='instant'?'added as active':'confirmation email(s) sent'}${j.invalid?`, ${j.invalid} invalid`:''}.`:'✗ '+j.message);await silent()}
});
async function simAct(a){const p=a.split(':'),k=p[0],id=+p[1],bid=+p[2];if(!sim)simInit();
  if(k==='reset'&&p.length===2&&id===0)simInit();else if(k==='reset'){delete sim.edits[id];delete sim.tuned[id]}
  else if(k==='keep')sim.kept[id]=!sim.kept[id];else if(k==='edit')sim.editing=id;else if(k==='voice')sim.voice=sim.voice===id?null:id;else if(k==='ang')sim.angles[id]=!sim.angles[id];
  else if(k==='save'){const v=$('#simtxt').value.trim();if(v){sim.edits[id]=v;sim.kept[id]=true}sim.editing=null}
  else if(k==='confirm')sim.conf=1;else if(k==='no')sim.conf=0;else if(k==='yes')sim.conf=2;
  else if(k==='swap')sim.menu=id;else if(k==='back')sim.menu=null;
  else if(k==='pick'){const b=bk().find(x=>x.id===bid);if(b){sim.swapped[id]={title:b.title,source:b.source,topic:b.topic,commentary:b.commentary||b.why||''};sim.used[bid]=true;delete sim.edits[id];sim.kept[id]=false}sim.menu=null}
  else if(k==='tune'){sim.loading[id]=true;render();const j=await post('/api/admin/revoice',{item_id:id,instruction:TUNE_TXT[bid]});sim.loading[id]=false;if(j.ok){sim.edits[id]=j.commentary;sim.tuned[id]=true}}
  render();const bd=$('#simbody');if(bd&&k!=='reset')bd.scrollTop=k==='confirm'||k==='yes'?bd.scrollHeight:bd.scrollTop}
let tuneT;
document.addEventListener('input',e=>{const t=e.target;
  if(t.id==='q'){F.q=t.value;const p=t.selectionStart;render();const q=$('#q');q.focus();q.setSelectionRange(p,p)}
  if(t.id==='edt')editorUpdate();
  if(t.dataset&&t.dataset.tune){$('#tv-'+t.dataset.tune).textContent=t.value;S.tuner[t.dataset.tune]=+t.value;clearTimeout(tuneT);tuneT=setTimeout(async()=>{const j=await post('/api/admin/tuner',S.tuner);flash(j.ok?'✓ '+j.message:'…')},600)}});
document.addEventListener('change',e=>{const t=e.target;if(t.id==='fs'){F.status=t.value;F.limit=60;render()}if(t.id==='fsrc'){F.source=t.value;F.limit=60;render()}if(t.id==='fsort'){F.sort=t.value;render()}
  if(t.id==='edsel'){ed.item=t.value;const it=S.items.find(x=>x.id==t.value);ed.text=it?it.commentary:'';render()}});
async function runStep(step){flash('Running…','#bnote');try{const j=await post('/api/admin/run/'+step);flash((j.ok?'✓ ':'✗ ')+(j.message||j.detail||'done'),'#bnote')}catch(x){flash('✗ '+x,'#bnote')}await silent()}
const SLUG=t=>t.toLowerCase().replace(/&/g,'and').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
function palBuild(){const q=pal.q.trim().toLowerCase(),out=[];const add=(g,label,run,hint='')=>{if(!q||label.toLowerCase().includes(q.replace(/^[>\/]/,'').trim())||(q[0]!=='>'&&q[0]!=='/'&&label.toLowerCase().includes(q)))out.push({g,label,run,hint})};
  const mode=q[0]==='>'?'a':q[0]==='/'?'f':'';
  if(!mode||mode==='a'){[['> Re-run Editorial Pass',()=>runStep('select'),'Gemini'],['> Fetch articles now',()=>runStep('ingest'),'RSS + APIs'],['> Re-send draft to Telegram',()=>runStep('draft'),'Telegram'],['> Force Telegram Reminder',()=>runStep('ping'),'pinned alert'],['> Snooze reminder 1 hour',async()=>{const j=await post('/api/admin/snooze',{minutes:60});flash((j.ok?'✓ ':'✗ ')+j.message,'#bnote');await silent()},'10 PM'],['> Run link health check',()=>runStep('linkcheck'),'pre-flight'],['> Open runner-ups drawer',()=>{tab='curation';openDrawer=true;render()},'swap'],['> Toggle light / dark',()=>$('#theme').click(),'theme']].forEach(([l,r,h])=>add('Actions',l,r,h))}
  if(!mode||mode==='f'){[['/counterintuitive','COUNTERINTUITIVE'],['/under-reported','UNDER-REPORTED'],['/trend-connecting','TREND-CONNECTING']].forEach(([l,f])=>add('Filters',l,()=>{F.filter=f;F.topic='';F.status='all';tab='articles';location.hash='articles';render()},'editorial filter'));
    ((S.balance&&S.balance.axes)||[]).forEach(x=>add('Filters','/'+SLUG(x.topic).split('-')[0],()=>{F.topic=x.topic;F.filter='';F.status='all';tab='articles';location.hash='articles';render()},x.topic))}
  if(!mode){TABS.forEach(([k,l])=>add('Go to',l,()=>{tab=k;location.hash=k;render()},'view'));
    sel().forEach(i=>add('This week’s stories','#'+i.position+' '+i.title,()=>{tab='curation';location.hash='curation';render()},i.topic));
    if(q.length>=3){S.articles.filter(a=>a.title.toLowerCase().includes(q)).slice(0,6).forEach(a=>out.push({g:'Candidate articles',label:a.title,hint:a.source,run:()=>{F.q=q;F.status='all';F.filter='';F.topic='';tab='articles';location.hash='articles';render()}}))}}
  return out.slice(0,30)}
function palRender(){pal.items=palBuild();let last='',h='';pal.items.forEach((it,n)=>{if(it.g!==last){h+=`<div class="pg">${esc(it.g)}</div>`;last=it.g}h+=`<div class="pi ${n===pal.sel?'on':''}" data-i="${n}"><span>${esc(it.label)}</span><small>${esc(it.hint||'')}</small></div>`});$('#pall').innerHTML=h||'<div class="pg">No matches</div>'}
function palOpen(){pal.open=true;pal.q='';pal.sel=0;$('#pal').classList.add('open');$('#palq').value='';palRender();setTimeout(()=>$('#palq').focus(),20)}
function palClose(){pal.open=false;$('#pal').classList.remove('open')}
async function palRun(n){const it=pal.items[n];if(!it)return;palClose();await it.run()}
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();pal.open?palClose():palOpen();return}
  if(!pal.open)return;if(e.key==='Escape')palClose();else if(e.key==='ArrowDown'){e.preventDefault();pal.sel=Math.min(pal.items.length-1,pal.sel+1);palRender()}else if(e.key==='ArrowUp'){e.preventDefault();pal.sel=Math.max(0,pal.sel-1);palRender()}else if(e.key==='Enter'){e.preventDefault();palRun(pal.sel)}});
document.addEventListener('input',e=>{if(e.target.id==='palq'){pal.q=e.target.value;pal.sel=0;palRender()}});
document.addEventListener('pointerdown',e=>{const n=e.target.closest&&e.target.closest('.fnode');if(!n)return;fzDrag={id:+n.dataset.id};e.preventDefault()});
document.addEventListener('pointermove',e=>{if(!fzDrag)return;const box=$('#fz'),l=$('#fzl');if(!box||!l)return;const r=box.getBoundingClientRect(),n=box.querySelector('.fnode[data-id="'+fzDrag.id+'"]').getBoundingClientRect();
  l.setAttribute('x1',n.left+n.width/2-r.left);l.setAttribute('y1',n.top+n.height/2-r.top);l.setAttribute('x2',e.clientX-r.left);l.setAttribute('y2',e.clientY-r.top);l.style.display='block'});
document.addEventListener('pointerup',async e=>{if(!fzDrag)return;const from=fzDrag.id;fzDrag=null;const l=$('#fzl');if(l)l.style.display='none';const t=document.elementFromPoint(e.clientX,e.clientY),n=t&&t.closest&&t.closest('.fnode');if(n&&+n.dataset.id!==from)await fuseRun(from,+n.dataset.id)});
window.addEventListener('hashchange',()=>{tab=(location.hash||'#command').slice(1);if(S)render()});
load();setInterval(()=>{if(document.visibilityState==='visible'&&['command','articles','subscribers','sources'].includes(tab))silent()},30000);
</script></body></html>"""
