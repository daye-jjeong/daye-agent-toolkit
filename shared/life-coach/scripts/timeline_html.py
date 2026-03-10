#!/usr/bin/env python3
"""Work session timeline — interactive HTML (daily / weekly).

Usage (standalone):
    python3 daily_coach.py  --json | python3 timeline_html.py
    python3 weekly_coach.py --json | python3 timeline_html.py --weekly

Embeddable:
    from timeline_html import build, timeline_section_html
    title, days = build(data, weekly=False)
    html_fragment = timeline_section_html(days, title)
"""
import argparse, json, sys
from datetime import datetime
from pathlib import Path

WEEKDAY = "월화수목금토일"

def to_h(t: str) -> float:
    if "T" in t: t = t[11:16]
    h, m = map(int, t.split(":"))
    return h + m / 60

def dedup(sessions):
    seen, out = set(), []
    for s in sessions:
        k = (s.get("start_at"), s.get("repo"), s.get("tag"))
        if k not in seen:
            seen.add(k); out.append(s)
    return out

def prep(sessions):
    return [
        {
            "repo":     (s.get("repo") or "?").split("/")[-1],
            "tag":      s.get("tag") or "기타",
            "start":    (s.get("start_at") or "00:00")[11:16],
            "duration": s.get("duration_min") or 30,
            "summary":  (s.get("summary") or "")[:100],
        }
        for s in dedup(sessions)
    ]

def build(data: dict, weekly: bool) -> tuple[str, list]:
    dates = data.get("dates", [])
    if weekly:
        title = "주간 타임라인"
        if dates:
            mon = datetime.strptime(dates[0], "%Y-%m-%d")
            sun = datetime.strptime(dates[6], "%Y-%m-%d")
            title = f'{mon.month}/{mon.day} ~ {sun.month}/{sun.day} 주간 타임라인'
        days_out = []
        for d in data.get("daily", []):
            if not d.get("activities") and not d.get("work_hours", 0):
                continue
            dt = datetime.strptime(d["date"], "%Y-%m-%d")
            days_out.append({
                "date":       d["date"],
                "label":      f'{dt.month}/{dt.day}({WEEKDAY[dt.weekday()]})',
                "work_hours": d.get("work_hours", 0),
                "sessions":   prep(d.get("activities", [])),
            })
        return title, days_out
    else:
        date_str = data.get("date", "")
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        title = f'{dt.month}/{dt.day}({WEEKDAY[dt.weekday()]}) 작업 타임라인'
        return title, [{
            "date":       date_str,
            "label":      f'{dt.month}/{dt.day}({WEEKDAY[dt.weekday()]})',
            "work_hours": data.get("work_hours", 0),
            "sessions":   prep(data.get("sessions", [])),
        }]

# ── CSS ───────────────────────────────────────────────────────────────────────

TIMELINE_CSS = """
.tl-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
.tl-header h2{font-size:16px;font-weight:700;color:#F0F0F0}
.tl-toggle{display:flex;gap:3px;background:var(--bg3,#2C2C2E);border-radius:8px;padding:3px}
.tl-toggle button{padding:5px 14px;border:none;border-radius:6px;cursor:pointer;background:transparent;color:var(--mu,#888);font-size:12px;font-weight:500;transition:all .15s}
.tl-toggle button.active{background:#484848;color:var(--tx,#E0E0E0)}
.tl-axis-wrap{display:flex;margin-left:var(--lw,170px);border-bottom:1px solid #3A3A3A;margin-bottom:3px}
.tl-axis-tick{flex:1;font-size:10px;color:#555;padding:2px 0 3px}
.tl-day{border-bottom:1px solid #282828}
.tl-day-hdr{display:flex;align-items:center;padding:8px 4px;cursor:pointer;user-select:none;border-radius:6px;transition:background .1s}
.tl-day-hdr:hover{background:var(--bg2,#242426)}
.tl-chevron{width:20px;font-size:10px;color:#555;text-align:center;transition:transform .2s;flex-shrink:0}
.tl-day-hdr.open .tl-chevron{transform:rotate(90deg)}
.tl-day-date{width:94px;font-size:12px;font-weight:600;color:#CCC;flex-shrink:0}
.tl-day-hrs{width:36px;font-size:11px;color:var(--mu,#888);flex-shrink:0}
.tl-mini-track{flex:1;position:relative;height:16px}
.tl-mini-bar{position:absolute;top:2px;height:12px;border-radius:2px;min-width:2px}
.tl-day-detail{display:none;padding:2px 0 10px}
.tl-day-detail.open{display:block}
.tl-row{display:flex;align-items:center;min-height:30px;border-radius:4px}
.tl-row:hover{background:var(--bg2,#242426)}
.tl-label{width:var(--lw,170px);min-width:var(--lw,170px);padding-right:12px;font-size:11px;color:#B0B0B0;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tl-track{flex:1;position:relative;height:28px;background:repeating-linear-gradient(90deg,transparent,transparent calc(100%/12 - 1px),#282828 calc(100%/12 - 1px),#282828 calc(100%/12))}
.tl-bar{position:absolute;top:4px;height:20px;border-radius:4px;display:flex;align-items:center;overflow:hidden;white-space:nowrap;font-size:10px;font-weight:600;color:white;min-width:3px;cursor:default;transition:filter .12s}
.tl-bar:hover{filter:brightness(1.22);z-index:10}
.tl-bar span{padding:0 6px;overflow:hidden;text-overflow:ellipsis}
.tl-tip{display:none;position:fixed;pointer-events:none;z-index:999;background:#111;border:1px solid #444;border-radius:8px;padding:9px 13px;font-size:12px;line-height:1.65;color:#EEE;max-width:320px;box-shadow:0 4px 20px rgba(0,0,0,.7)}
.tl-legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px;padding-top:12px;border-top:1px solid var(--bd,#333)}
.tl-lg-item{display:flex;align-items:center;gap:5px;font-size:11px;color:#999}
.tl-lg-dot{width:10px;height:10px;border-radius:2px;flex-shrink:0}
"""

# ── JS ────────────────────────────────────────────────────────────────────────

TIMELINE_JS = r"""
const TC={"리팩토링":"#4A90D9","디버깅":"#E07B5A","코딩":"#7ABD7E","설계":"#9B7BC8","ops":"#F0C040","문서":"#5AC8D9","리뷰":"#D9A85A","기타":"#707070"};
const PAL=["#4A90D9","#E07B5A","#7ABD7E","#9B7BC8","#F0C040","#5AC8D9","#D9A85A","#D95A90","#80C0A0","#C0A080","#A080C0","#80A0C0"];
let ci=0; const RC={}; function rc(r){if(!RC[r])RC[r]=PAL[ci++%PAL.length];return RC[r];}

let tlMode='repo';
const tlOpen=new Set();

function toH(t){const[h,m]=t.split(':').map(Number);return h+m/60;}
function pct(h){return(h/24*100).toFixed(3)+'%';}

function tlSetMode(m){
  tlMode=m;
  document.getElementById('tl-b-repo').classList.toggle('active',m==='repo');
  document.getElementById('tl-b-tag').classList.toggle('active',m==='tag');
  tlRender();
}
function tlToggle(date){tlOpen.has(date)?tlOpen.delete(date):tlOpen.add(date);tlRender();}

function tlGroupBy(sessions,key){
  const g={};
  for(const s of sessions){const k=s[key]||'기타';(g[k]=g[k]||[]).push(s);}
  return Object.entries(g).sort((a,b)=>
    b[1].reduce((s,x)=>s+x.duration,0)-a[1].reduce((s,x)=>s+x.duration,0));
}

function tlBarH(s){
  const st=toH(s.start),end=st+s.duration/60;
  const c=TC[s.tag]||'#707070';
  const lbl=s.duration>=45?`${s.start} · ${Math.floor(s.duration/60)}h${String(s.duration%60).padStart(2,'0')}`:'';
  const tip=`${s.repo} [${s.tag}]\n${s.start} · ${s.duration}분${s.summary?'\n'+s.summary:''}`;
  return `<div class="tl-bar" style="left:${pct(st)};width:${pct(end-st)};background:${c}"
    onmouseenter="tlShowT(event,${JSON.stringify(tip)})" onmouseleave="tlHideT()">
    <span>${lbl}</span></div>`;
}
function tlRowH(lbl,sessions){
  return `<div class="tl-row"><div class="tl-label" title="${lbl}">${lbl}</div><div class="tl-track">${sessions.map(tlBarH).join('')}</div></div>`;
}
function tlMiniH(sessions){
  return sessions.map(s=>{
    const st=toH(s.start),end=st+s.duration/60;
    return `<div class="tl-mini-bar" style="left:${pct(st)};width:${pct(end-st)};background:${TC[s.tag]||'#707070'};opacity:.7"></div>`;
  }).join('');
}

function tlRender(){
  document.getElementById('tl-chart').innerHTML=TL_DATA.map(day=>{
    const isOpen=tlOpen.has(day.date);
    let detail='';
    if(isOpen){
      const groups=tlGroupBy(day.sessions,tlMode==='repo'?'repo':'tag');
      const rows=groups.map(([key,sess])=>{
        const tot=sess.reduce((s,x)=>s+x.duration,0);
        const ds=tot>=60?`${Math.floor(tot/60)}h${String(tot%60).padStart(2,'0')}m`:`${tot}m`;
        return tlRowH(`${key}  ${ds}`,sess);
      }).join('');
      detail=`<div class="tl-day-detail open">${rows}</div>`;
    }
    return `<div class="tl-day">
      <div class="tl-day-hdr ${isOpen?'open':''}" onclick="tlToggle('${day.date}')">
        <div class="tl-chevron">▶</div>
        <div class="tl-day-date">${day.label}</div>
        <div class="tl-day-hrs">${day.work_hours}h</div>
        <div class="tl-mini-track">${tlMiniH(day.sessions)}</div>
      </div>${detail}</div>`;
  }).join('');
}

// Axis
(function(){
  const ax=document.getElementById('tl-axis');
  for(let h=0;h<=22;h+=2){const d=document.createElement('div');d.className='tl-axis-tick';d.textContent=`${String(h).padStart(2,'0')}:00`;ax.appendChild(d);}
})();

// Legend
document.getElementById('tl-legend').innerHTML=Object.entries(TC).map(([t,c])=>
  `<div class="tl-lg-item"><div class="tl-lg-dot" style="background:${c}"></div>${t}</div>`).join('');

// Tooltip
function tlShowT(e,text){const t=document.getElementById('tl-tip');t.style.display='block';t.innerHTML=text.replace(/\n/g,'<br>');tlMoveT(e);}
function tlMoveT(e){const t=document.getElementById('tl-tip');t.style.left=Math.min(e.clientX+14,window.innerWidth-t.offsetWidth-16)+'px';t.style.top=(e.clientY-10)+'px';}
function tlHideT(){document.getElementById('tl-tip').style.display='none';}
document.addEventListener('mousemove',tlMoveT);

TL_DATA.forEach(d=>d.sessions.forEach(s=>rc(s.repo)));
if(TL_DATA.length)tlOpen.add(TL_DATA[0].date);
tlRender();
"""

# ── HTML structure ────────────────────────────────────────────────────────────

TIMELINE_HTML = """
<div class="tl-header">
  <h2>TMPL_TITLE</h2>
  <div class="tl-toggle">
    <button id="tl-b-repo" class="active" onclick="tlSetMode('repo')">레포별</button>
    <button id="tl-b-tag"               onclick="tlSetMode('tag')">태그별</button>
  </div>
</div>
<div class="tl-axis-wrap" id="tl-axis"></div>
<div id="tl-chart"></div>
<div class="tl-legend" id="tl-legend"></div>
<div class="tl-tip" id="tl-tip"></div>
"""

# ── Public API ────────────────────────────────────────────────────────────────

def timeline_section_html(days: list, title: str) -> str:
    """Return self-contained timeline HTML fragment (style + markup + script).

    Embed this inside any <body> — no outer page wrapper included.
    """
    data_json = json.dumps(days, ensure_ascii=False)
    structure = TIMELINE_HTML.replace("TMPL_TITLE", title)
    return (
        f'<style>{TIMELINE_CSS}</style>\n'
        f'<div id="timeline-section">{structure}</div>\n'
        f'<script>\nconst TL_DATA={data_json};\n{TIMELINE_JS}</script>'
    )


def build_standalone_page(days: list, title: str) -> str:
    """Full standalone HTML page with timeline."""
    section = timeline_section_html(days, title)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"><title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#1C1C1E;--bg2:#242426;--bg3:#2C2C2E;--bd:#333;--tx:#E0E0E0;--mu:#888;--lw:170px}}
body{{background:var(--bg);color:var(--tx);font-family:-apple-system,"Apple SD Gothic Neo",sans-serif;font-size:13px;padding:28px 32px;max-width:1200px}}
</style>
</head>
<body>
{section}
</body></html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly", action="store_true")
    parser.add_argument("--input")
    parser.add_argument("--output", default="/tmp/work_timeline.html")
    args = parser.parse_args()

    raw = json.load(open(args.input) if args.input else sys.stdin)
    title, days = build(raw, args.weekly)

    html = build_standalone_page(days, title)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"[timeline_html] saved: {args.output}", file=sys.stderr)

if __name__ == "__main__":
    main()
