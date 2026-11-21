"""Motion and lighting layer for the dashboard (presentation only).

Nothing here changes a number or a record: the counters end on the exact text the page was built with, and every
animation sits behind `prefers-reduced-motion: no-preference`, so people who ask for less motion get the static page.
Glows are shadows and gradients only; text colors, and so contrast, are unchanged.
"""

ICON = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill-rule='evenodd' d='%s'/></svg>"
ICONS = {
    "s1": "M4 20V10h4v10zm6 0V4h4v16zm6 0v-7h4v7z",
    "ats": "M7 7h11l-3-3 1.4-1.4L22 8l-5.6 5.4L15 12l3-3H7zm10 10H6l3 3-1.4 1.4L2 16l5.6-5.4L9 12l-3 3h11z",
    "mix": "M12 3l9 5-9 5-9-5zM4.6 12L12 16l7.4-4L21 13l-9 5-9-5zm0 4L12 20l7.4-4L21 17l-9 5-9-5z",
    "engine": "M13 2L4 14h6l-1 8 9-12h-6z",
    "outliers": "M12 2a10 10 0 100 20 10 10 0 000-20zm0 4a6 6 0 110 12 6 6 0 010-12zm0 4a2 2 0 100 4 2 2 0 000-4z",
    "trends": "M3 18l6-7 4 4 8-10v3l-8 10-4-4-6 7z",
}

CSS = """
/* ---- lighting: spotlight board, neon edge, gradient card tops, stat tiles (static; always on) */
.board{position:relative;overflow:hidden;box-shadow:0 0 0 1px rgba(90,162,240,.35),0 14px 44px -14px rgba(57,135,229,.6);
  background:radial-gradient(900px circle at 85% -20%,rgba(57,135,229,.22),transparent 55%),var(--board)}
.board::before{content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(420px circle at var(--mx,18%) var(--my,0%),rgba(120,180,255,.20),transparent 62%)}
.board>*{position:relative}
.big{text-shadow:0 0 26px rgba(90,162,240,.65),0 0 2px rgba(255,255,255,.5)}
.stats .stat{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:8px;padding:8px 12px;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
.stat .v{text-shadow:0 0 14px rgba(90,162,240,.35)}
.meter .t i{background:linear-gradient(90deg,var(--accent),#7cc4ff);box-shadow:0 0 10px rgba(90,162,240,.7)}
.card,.game{position:relative}
.card::before{content:"";position:absolute;left:0;right:0;top:0;height:2px;border-radius:8px 8px 0 0;opacity:.85;
  background:linear-gradient(90deg,var(--accent),var(--c3) 55%,transparent)}
.sechead h2::after{content:"";display:block;width:44px;height:3px;border-radius:2px;margin-top:5px;
  background:linear-gradient(90deg,var(--accent),var(--c3));box-shadow:0 0 10px color-mix(in srgb,var(--accent) 70%,transparent)}
.chip.win{box-shadow:0 0 10px -3px var(--good)}.chip.loss{box-shadow:0 0 10px -3px var(--bad)}
.wb i.ok,.ub i.pos{box-shadow:0 0 8px color-mix(in srgb,var(--accent) 65%,transparent)}
.ub i.neg{box-shadow:0 0 8px color-mix(in srgb,var(--neg) 60%,transparent)}
.tabs button{display:inline-flex;align-items:center;gap:7px}
.tabs button::before{content:"";width:15px;height:15px;background:currentColor;flex:none;opacity:.85;
  -webkit-mask:var(--ic) center/contain no-repeat;mask:var(--ic) center/contain no-repeat}
.tabs button[aria-selected="true"]{text-shadow:0 0 14px color-mix(in srgb,var(--accent) 60%,transparent)}
.tabs button[aria-selected="true"]::before{opacity:1;filter:drop-shadow(0 0 4px var(--accent))}
.chip.state.open::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:currentColor;margin-right:6px;vertical-align:1px}
.tchart .ln{filter:drop-shadow(0 0 3px color-mix(in srgb,currentColor 50%,transparent))}
%ICONS%

/* ---- motion (only when the viewer has not asked for less) */
@media (prefers-reduced-motion:no-preference){
  .tabpane:not([hidden]){animation:fxrise .38s ease-out}
  .meter .t i,.wb i{animation:fxfill .9s cubic-bezier(.2,.8,.2,1)}
  .ub i{animation:fxgrow .8s cubic-bezier(.2,.8,.2,1)}.ub i.pos{transform-origin:left}.ub i.neg{transform-origin:right}
  .tchart svg{animation:fxreveal 1s ease-out}
  .chip.state.open::before{animation:fxpulse 1.8s ease-out infinite}
  .card,.game,.stats .stat{transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}
  .card:hover,.game:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--accent) 55%,var(--line));
    box-shadow:0 10px 28px -14px color-mix(in srgb,var(--accent) 65%,transparent)}
  .stats .stat:hover{transform:translateY(-2px);box-shadow:0 0 18px -4px rgba(90,162,240,.6)}
  .tchart .mk{transition:r .15s ease}
  @keyframes fxrise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  @keyframes fxfill{from{width:0}}
  @keyframes fxgrow{from{transform:scaleX(0)}}
  @keyframes fxreveal{from{clip-path:inset(-4px 100% -4px -4px)}to{clip-path:inset(-4px -4px -4px -4px)}}
  @keyframes fxpulse{0%{box-shadow:0 0 0 0 color-mix(in srgb,currentColor 60%,transparent)}70%{box-shadow:0 0 0 8px transparent}100%{box-shadow:0 0 0 0 transparent}}
}
"""

JS = r"""
(function(){
  // spotlight follows the pointer on the scoreboard bands
  document.querySelectorAll('.board').forEach(function(b){
    b.addEventListener('pointermove',function(e){var r=b.getBoundingClientRect();
      b.style.setProperty('--mx',(e.clientX-r.left)+'px');b.style.setProperty('--my',(e.clientY-r.top)+'px')});
  });
  if(!window.matchMedia||matchMedia('(prefers-reduced-motion: reduce)').matches||!('IntersectionObserver' in window))return;
  // animated counters: each number counts up from zero and the element ends on its original text, character for character
  var SEL='.board .big,.board .stat .v,.board .side .mid,.meter .k b';
  function run(el){
    var orig=el.textContent,parts=orig.split(/(\d+(?:\.\d+)?)/);
    if(parts.length<2)return;
    var t0=null,dur=900;
    function step(ts){
      if(t0===null)t0=ts;var p=Math.min((ts-t0)/dur,1),k=1-Math.pow(1-p,3),out='';
      parts.forEach(function(s,i){
        if(i%2===0){out+=s;return}
        var dec=(s.split('.')[1]||'').length;out+=(parseFloat(s)*k).toFixed(dec);
      });
      el.textContent=p<1?out:orig;
      if(p<1)requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){io.unobserve(e.target);if(e.target.children.length===0)run(e.target)}})},{threshold:.2});
  document.querySelectorAll(SEL).forEach(function(el){io.observe(el)});
})();
"""


def css() -> str:
    rules = "\n".join(f'.tabs button[data-tab="{k}"]{{--ic:url("{ICON % v}")}}' for k, v in ICONS.items())
    return CSS.replace("%ICONS%", rules)
