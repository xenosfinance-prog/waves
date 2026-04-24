/**
 * XenosFinance — xf-hand.js
 * Hand writing animation for all AI-generated content.
 * Include once per page: <script src="/xf-hand.js"></script>
 * Then call: XF.typeInto(element, html, speed, onDone)
 *        or: XF.panRead(element)
 *        or: XF.start(element)   ← generic hover/pan while AI loads
 *        or: XF.stop()
 */
(function(g){
'use strict';

var SVG_ID = 'xf-hand-svg';
var _el = null, _timers = [], _active = false;

var SVG_HTML = '<svg id="'+SVG_ID+'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 140" width="120" height="140" style="position:fixed;pointer-events:none;z-index:99999;opacity:0;transition:opacity 0.25s;filter:drop-shadow(0 2px 8px rgba(0,0,0,0.25));transform-origin:22% 88%;">'
 +'<defs>'
 +'<linearGradient id="xfSkin" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#f9d8bb"/><stop offset="100%" stop-color="#ecb890"/></linearGradient>'
 +'<linearGradient id="xfSkinD" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#e0a06e"/><stop offset="100%" stop-color="#cc8850"/></linearGradient>'
 +'<linearGradient id="xfSlv" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#2a4080"/><stop offset="100%" stop-color="#182858"/></linearGradient>'
 +'<linearGradient id="xfPen" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#1a3a78"/><stop offset="45%" stop-color="#3a6ab0"/><stop offset="100%" stop-color="#1a3a78"/></linearGradient>'
 +'</defs>'
 +'<g transform="rotate(-28,60,125)">'
 +'<rect x="18" y="100" width="54" height="36" rx="8" fill="url(#xfSlv)" stroke="#0f1f50" stroke-width="1.1"/>'
 +'<rect x="20" y="100" width="50" height="6" rx="3" fill="#3a5aaa" opacity="0.4"/>'
 +'<path d="M26 103 Q24 82 28 65 Q30 54 35 50 Q40 46 43 51 Q46 56 44 68 L43 86" fill="url(#xfSkin)" stroke="#c8906a" stroke-width="0.9"/>'
 +'<path d="M36 103 Q34 78 36 62 Q37 53 42 51 Q47 50 49 58 Q51 66 49 78 L48 92" fill="url(#xfSkin)" stroke="#c8906a" stroke-width="0.9"/>'
 +'<path d="M46 103 Q45 80 47 64 Q48 55 53 53 Q58 52 59 60 Q61 68 59 80 L58 96" fill="url(#xfSkin)" stroke="#c8906a" stroke-width="0.9"/>'
 +'<path d="M56 105 Q56 84 58 70 Q59 62 63 60 Q67 59 68 66 Q69 74 67 86 L66 102" fill="url(#xfSkin)" stroke="#c8906a" stroke-width="0.9"/>'
 +'<path d="M18 103 Q16 91 14 80 Q11 67 15 57 Q19 47 24 50 Q29 53 28 65 L26 103" fill="url(#xfSkin)" stroke="#c8906a" stroke-width="0.9"/>'
 +'<path d="M18 103 Q36 114 66 106 Q70 112 68 124 Q66 134 44 137 Q22 135 17 122 Q15 111 18 103Z" fill="url(#xfSkin)" stroke="#c8906a" stroke-width="0.95"/>'
 +'<path d="M28 110 Q43 116 63 110" fill="none" stroke="#c8906a" stroke-width="0.45" opacity="0.5"/>'
 +'<path d="M27 117 Q43 123 62 117" fill="none" stroke="#c8906a" stroke-width="0.35" opacity="0.4"/>'
 +'<ellipse cx="27" cy="50" rx="4" ry="2.8" fill="url(#xfSkinD)" stroke="#b87050" stroke-width="0.5"/>'
 +'<ellipse cx="40" cy="50" rx="4" ry="2.8" fill="url(#xfSkinD)" stroke="#b87050" stroke-width="0.5"/>'
 +'<ellipse cx="51" cy="54" rx="4" ry="2.8" fill="url(#xfSkinD)" stroke="#b87050" stroke-width="0.5"/>'
 +'<ellipse cx="60" cy="61" rx="4" ry="2.8" fill="url(#xfSkinD)" stroke="#b87050" stroke-width="0.5"/>'
 +'<g transform="rotate(15,42,52)">'
 +'<rect x="39" y="5" width="7" height="50" rx="3.5" fill="url(#xfPen)" stroke="#0f205a" stroke-width="0.6"/>'
 +'<rect x="39.5" y="5" width="1.8" height="50" fill="#6090cc" opacity="0.28" rx="0.8"/>'
 +'<rect x="39" y="5" width="7" height="7" rx="3" fill="#999" stroke="#777" stroke-width="0.5"/>'
 +'<polygon points="42.5,55 39,62 46,62" fill="#1a1a1a" stroke="#111" stroke-width="0.4"/>'
 +'<line x1="42.5" y1="62" x2="42.5" y2="68" stroke="#444" stroke-width="1.3" stroke-linecap="round"/>'
 +'<line x1="42.5" y1="68" x2="44.5" y2="74" stroke="#333" stroke-width="0.8" stroke-linecap="round"/>'
 +'</g>'
 +'</g>'
 +'</svg>';

function _inject(){
  if(document.getElementById(SVG_ID)) return;
  var d=document.createElement('div');
  d.innerHTML=SVG_HTML;
  document.body.appendChild(d.firstChild);
  _el=document.getElementById(SVG_ID);
}

function _clearTimers(){ _timers.forEach(clearTimeout); _timers.length=0; }

// Pen tip offset: ~26px from left, ~123px from top of 120×140 SVG
function _moveTo(x,y){
  if(!_el)return;
  _el.style.left=(x-26)+'px';
  _el.style.top=(y-123)+'px';
}
function _show(x,y){ if(!_el)return; _moveTo(x,y); _el.style.opacity='1'; }
function _hide(){ if(!_el)return; _el.style.opacity='0'; _active=false; }

/**
 * typeInto(el, html, speed, onDone)
 * Writes plain text char-by-char into el, hand tip follows cursor.
 * When done, sets full innerHTML and hides hand.
 */
function typeInto(el, html, speed, onDone){
  _inject();
  _clearTimers(); _active=true;
  var tmp=document.createElement('div'); tmp.innerHTML=html;
  var plain=(tmp.textContent||tmp.innerText||'').replace(/\n\n+/g,'\n');
  el.innerHTML='';
  var chars=plain.split(''), i=0, spd=speed||15;

  function tick(){
    if(!_active){ _hide(); return; }
    if(i>=chars.length){
      el.innerHTML=html;
      var t=setTimeout(function(){ _hide(); if(onDone)onDone(); },350);
      _timers.push(t); return;
    }
    el.textContent=plain.substring(0,i+1);
    var r=el.getBoundingClientRect();
    if(r.width>0){
      var lineW=Math.max(Math.floor((r.width-8)/8.2),1);
      var lineN=Math.floor(i/lineW), colN=i%lineW;
      var cx=r.left+8+colN*8.2, cy=r.top+16+lineN*26;
      if(i===0) _show(cx,cy); else _moveTo(cx,cy);
    }
    i++;
    var ch=chars[i-1];
    var d=spd+Math.random()*spd*0.4;
    if(ch==='.') d=spd*3.5;
    else if(ch===',') d=spd*2;
    else if(ch==='\n') d=spd*7;
    else if(ch===' ') d=spd*0.65;
    _timers.push(setTimeout(tick,d));
  }
  tick();
}

/**
 * start(el)
 * Generic: hand pans slowly over el while AI is loading/generating.
 * Call stop() when done.
 */
function start(el){
  _inject();
  _clearTimers(); _active=true;
  var LINE_H=28, line=0;
  function tick(){
    if(!_active){ _hide(); return; }
    var r=el.getBoundingClientRect();
    if(!r.width){ var t=setTimeout(tick,300); _timers.push(t); return; }
    line++;
    var lineY=r.top+line*LINE_H+10;
    if(lineY>r.bottom+10){ line=0; lineY=r.top+10; }
    var STEPS=10, stepW=Math.max((r.width-60)/STEPS,18);
    for(var i=0;i<STEPS;i++){
      (function(idx){
        var t=setTimeout(function(){
          if(!_active) return;
          _moveTo(r.left+36+idx*stepW+(Math.random()*6-3), lineY+(Math.random()*3-1.5));
        }, idx*95+Math.random()*20);
        _timers.push(t);
      })(i);
    }
    if(line===1){ var r2=el.getBoundingClientRect(); _show(r2.left+36, r2.top+10); }
    var t=setTimeout(tick, STEPS*95+130+Math.random()*50);
    _timers.push(t);
  }
  tick();
}

/**
 * panRead(el)
 * Slow pan while user reads an article.
 */
function panRead(el){
  _inject();
  _clearTimers(); _active=true;
  var steps=80, step=0;
  var stepTime=Math.max((el.scrollHeight||600)*4.5,6000)/steps;
  function pan(){
    if(!_active){ _hide(); return; }
    var pct=step/steps;
    var r=el.getBoundingClientRect();
    var x=r.left+44+Math.sin(pct*Math.PI*5)*(r.width*0.34);
    var y=r.top+pct*r.height;
    if(step===0) _show(x,y); else _moveTo(x,y);
    step++;
    if(step<=steps) _timers.push(setTimeout(pan,stepTime));
    else _hide();
  }
  pan();
}

function stop(){ _clearTimers(); _hide(); }

document.addEventListener('DOMContentLoaded', _inject);

g.XF={ typeInto:typeInto, start:start, stop:stop, panRead:panRead };
})(window);
