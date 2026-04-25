/**
 * XenosFinance — xf-hand.js
 * Hand writing animation — blue engraving style
 * API: XF.typeInto(el, html, speed, onDone)
 *      XF.start(el)
 *      XF.stop()
 *      XF.panRead(el)
 */
(function(g){
'use strict';

var SVG_ID = 'xf-hand-svg';
var _el = null, _timers = [], _active = false;

var SVG_HTML = '<svg id="xf-hand-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 160" width="140" height="160" style="position:fixed;pointer-events:none;z-index:99999;opacity:0;transition:opacity 0.28s;filter:drop-shadow(0 2px 10px rgba(0,0,0,0.18));"><g transform="rotate(-25,70,140)"><rect x="22" y="118" width="64" height="38" rx="6" fill="#1e3a6e" stroke="#0f1f4a" stroke-width="1.2"/><line x1="26" y1="122" x2="82" y2="122" stroke="#3b5aaa" stroke-width="0.5" opacity="0.5"/><line x1="26" y1="128" x2="82" y2="128" stroke="#3b5aaa" stroke-width="0.5" opacity="0.5"/><line x1="26" y1="134" x2="82" y2="134" stroke="#3b5aaa" stroke-width="0.5" opacity="0.5"/><line x1="26" y1="140" x2="82" y2="140" stroke="#3b5aaa" stroke-width="0.5" opacity="0.5"/><line x1="32" y1="118" x2="32" y2="156" stroke="#3b5aaa" stroke-width="0.5" opacity="0.3"/><line x1="44" y1="118" x2="44" y2="156" stroke="#3b5aaa" stroke-width="0.5" opacity="0.3"/><line x1="56" y1="118" x2="56" y2="156" stroke="#3b5aaa" stroke-width="0.5" opacity="0.3"/><line x1="68" y1="118" x2="68" y2="156" stroke="#3b5aaa" stroke-width="0.5" opacity="0.3"/><path d="M30 122 Q27 96 30 78 Q32 65 38 60 Q44 55 48 60 Q52 65 50 80 L48 104" fill="none" stroke="#1a3a6e" stroke-width="1.4"/><path d="M31 122 Q28 97 31 79 Q33 67 38 62 Q43 58 47 62 Q50 67 49 81 L47 105" fill="none" stroke="#1a3a6e" stroke-width="0.6" opacity="0.5"/><path d="M42 122 Q39 94 41 76 Q42 64 48 61 Q54 59 56 66 Q58 74 56 88 L54 108" fill="none" stroke="#1a3a6e" stroke-width="1.4"/><path d="M43 122 Q40 95 42 77 Q43 65 49 62 Q55 60 57 67 Q59 75 57 89 L55 109" fill="none" stroke="#1a3a6e" stroke-width="0.6" opacity="0.5"/><path d="M54 122 Q52 96 53 80 Q54 68 59 65 Q64 63 66 70 Q68 78 66 92 L64 112" fill="none" stroke="#1a3a6e" stroke-width="1.4"/><path d="M55 123 Q53 97 54 81 Q55 69 60 66 Q65 64 67 71 Q69 79 67 93 L65 113" fill="none" stroke="#1a3a6e" stroke-width="0.6" opacity="0.5"/><path d="M64 124 Q63 104 64 90 Q65 80 69 78 Q73 77 74 83 Q75 90 73 102 L72 118" fill="none" stroke="#1a3a6e" stroke-width="1.3"/><path d="M22 122 Q19 108 17 94 Q14 78 18 68 Q22 58 28 61 Q34 64 32 78 L30 122" fill="none" stroke="#1a3a6e" stroke-width="1.4"/><path d="M23 122 Q20 109 18 95 Q15 79 19 69 Q23 60 29 62 Q34 65 33 79 L31 123" fill="none" stroke="#1a3a6e" stroke-width="0.6" opacity="0.5"/><path d="M22 122 Q37 132 72 124 Q76 130 74 142 Q72 152 52 155 Q28 153 22 142 Q19 132 22 122Z" fill="none" stroke="#1a3a6e" stroke-width="1.4"/><path d="M24 122 Q38 131 70 123 Q74 129 72 140 Q70 150 52 153 Q30 151 24 141 Q21 132 24 122Z" fill="none" stroke="#1a3a6e" stroke-width="0.7" opacity="0.5"/><path d="M26 122 Q39 130 68 123 Q72 128 70 138 Q68 148 52 151 Q32 149 26 140 Q23 132 26 122Z" fill="none" stroke="#1a3a6e" stroke-width="0.5" opacity="0.35"/><path d="M30 130 Q45 136 66 130" fill="none" stroke="#1a3a6e" stroke-width="0.5" opacity="0.45"/><path d="M28 137 Q44 143 65 137" fill="none" stroke="#1a3a6e" stroke-width="0.4" opacity="0.38"/><path d="M36 62 Q40 58 44 60" fill="none" stroke="#1a3a6e" stroke-width="0.9"/><path d="M47 62 Q51 58 55 61" fill="none" stroke="#1a3a6e" stroke-width="0.9"/><path d="M57 66 Q61 62 65 65" fill="none" stroke="#1a3a6e" stroke-width="0.9"/><path d="M32 96 Q30 90 31 85" fill="none" stroke="#1a3a6e" stroke-width="0.5" opacity="0.4"/><path d="M44 90 Q42 84 43 79" fill="none" stroke="#1a3a6e" stroke-width="0.5" opacity="0.4"/><path d="M56 92 Q54 86 55 81" fill="none" stroke="#1a3a6e" stroke-width="0.5" opacity="0.4"/><g transform="rotate(18,40,58)"><rect x="36.5" y="6" width="7" height="52" rx="3.5" fill="#1a3a6e" stroke="#0f1f50" stroke-width="0.7"/><rect x="37" y="7" width="1.5" height="50" fill="#4a7ab8" opacity="0.35" rx="0.7"/><rect x="43" y="10" width="2" height="30" rx="1" fill="#0f2050" stroke="#0a1840" stroke-width="0.4"/><rect x="36.5" y="6" width="7" height="9" rx="3" fill="#2a5aaa" stroke="#1a3a6e" stroke-width="0.5"/><rect x="36.5" y="44" width="7" height="14" rx="2" fill="#0f2050"/><line x1="37" y1="47" x2="43" y2="47" stroke="#2a5aaa" stroke-width="0.4" opacity="0.5"/><line x1="37" y1="50" x2="43" y2="50" stroke="#2a5aaa" stroke-width="0.4" opacity="0.5"/><line x1="37" y1="53" x2="43" y2="53" stroke="#2a5aaa" stroke-width="0.4" opacity="0.5"/><polygon points="40,58 37,66 43,66" fill="#222" stroke="#111" stroke-width="0.5"/><line x1="40" y1="66" x2="40" y2="72" stroke="#555" stroke-width="1.4" stroke-linecap="round"/><line x1="40" y1="72" x2="42" y2="79" stroke="#333" stroke-width="0.9" stroke-linecap="round"/></g></g></svg>';

function _inject(){
  if(document.getElementById(SVG_ID)) return;
  var d=document.createElement('div');
  d.innerHTML=SVG_HTML;
  document.body.appendChild(d.firstChild);
  _el=document.getElementById(SVG_ID);
}

function _clearTimers(){ _timers.forEach(clearTimeout); _timers.length=0; }

// Pen tip: ~40px from left, ~79px from top of 140x160 SVG
function _moveTo(x,y){
  if(!_el)return;
  _el.style.left=(x-40)+'px';
  _el.style.top=(y-79)+'px';
}
function _show(x,y){ if(!_el)return; _moveTo(x,y); _el.style.opacity='1'; }
function _hide(){ if(!_el)return; _el.style.opacity='0'; _active=false; }

function typeInto(el,html,speed,onDone){
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
