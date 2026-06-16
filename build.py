#!/usr/bin/env python3
"""
Rebuilds the Command Center (index.html) with the latest Asana tasks.

Reads command-center.base.html, pulls the current user's incomplete Asana tasks,
derives Start/Due/Est Hrs/% Done from the "Start Date:" / "Due Date:" / "Est. Hrs"
/ "% Done" custom fields, resolves each task's project (walking up the subtask ->
parent chain) and the portfolio (client) that project belongs to, and writes
index.html.

Environment variables:
  ASANA_TOKEN          (required) Asana Personal Access Token
  ASANA_WORKSPACE_GID  (optional) workspace to read; defaults to your first workspace
  DASHBOARD_TZ         (optional) timezone for "today"; default America/New_York
"""
import os, re, json, datetime, urllib.request, urllib.parse
from zoneinfo import ZoneInfo

API = "https://app.asana.com/api/1.0"
BASE = "command-center.base.html"
OUT = "index.html"
OPT = ("name,permalink_url,due_on,start_on,projects.name,memberships.project.name,"
       "parent.name,parent.projects.name,parent.memberships.project.name,"
       "parent.parent.projects.name,custom_fields.name,custom_fields.display_value,"
       "custom_fields.number_value")

def api_get(token, path, params):
    url = API + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def get_workspace(token):
    ws = os.environ.get("ASANA_WORKSPACE_GID", "").strip()
    if ws:
        return ws
    me = api_get(token, "/users/me", {"opt_fields": "workspaces.name"})
    return me["data"]["workspaces"][0]["gid"]

def fetch_tasks(token, workspace):
    tasks, offset = [], None
    while True:
        params = {"assignee": "me", "workspace": workspace,
                  "completed_since": "now", "opt_fields": OPT, "limit": 100}
        if offset:
            params["offset"] = offset
        resp = api_get(token, "/tasks", params)
        tasks.extend(resp.get("data", []))
        nxt = resp.get("next_page")
        if nxt and nxt.get("offset"):
            offset = nxt["offset"]
        else:
            break
    return tasks

def fetch_portfolio_map(token, workspace):
    pmap = {}
    try:
        ports = api_get(token, "/portfolios",
                        {"workspace": workspace, "owner": "me", "opt_fields": "name"})
        for p in ports.get("data", []):
            items = api_get(token, "/portfolios/%s/items" % p["gid"],
                            {"opt_fields": "name"})
            for it in items.get("data", []):
                pmap[it.get("name")] = p.get("name")
    except Exception as e:
        print("portfolio map unavailable:", e)
    return pmap

def datekey(v):
    return str(v)[:10] if v else None

def cf(task, pred):
    for f in task.get("custom_fields") or []:
        if pred((f.get("name") or "").strip()):
            return f
    return None

def proj_of(node):
    if not node:
        return None
    pr = node.get("projects") or []
    if pr and pr[0].get("name"):
        return pr[0]["name"]
    mem = node.get("memberships") or []
    if mem and (mem[0].get("project") or {}).get("name"):
        return mem[0]["project"]["name"]
    return proj_of(node.get("parent"))

def derive(task, portmap):
    duecf = cf(task, lambda n: n.lower().startswith("due date"))
    startcf = cf(task, lambda n: n.lower().startswith("start date"))
    estcf = cf(task, lambda n: re.match(r"est\.?\s*hrs", n, re.I))
    pctcf = cf(task, lambda n: re.match(r"%\s*done", n, re.I))
    project = proj_of(task) or "No Project"
    parent = (task.get("parent") or {}).get("name")
    return {
        "name": (task.get("name") or "").strip(),
        "url": task.get("permalink_url"),
        "start": datekey(startcf.get("display_value") if startcf else None),
        "due": datekey(duecf.get("display_value") if duecf else None),
        "est": (estcf.get("number_value") if estcf else None),
        "pct": (pctcf.get("number_value") if pctcf else None),
        "project": project,
        "portfolio": portmap.get(project),
        "parent": (parent or None),
    }

def build_data(tasks, today, portmap):
    rows = [derive(t, portmap) for t in tasks if (t.get("name") or "").strip()]
    # Each task lands in exactly one bucket, by priority:
    #   Past Due (due < today) > Due Today (due == today) > In Progress (started, not yet due).
    pastDue, dueToday, inProgress = [], [], []
    for r in rows:
        if r["due"] and r["due"] < today:
            pastDue.append(r)
        elif r["due"] == today:
            dueToday.append(r)
        elif r["start"] and r["start"] <= today:
            inProgress.append(r)
        # else: not yet started / no qualifying date -> shown in no list
    return {"pastDue": pastDue, "dueToday": dueToday, "inProgress": inProgress}

CSS = """
  /* ---------- My Tasks (Asana dashboard) ---------- */
  #mytasks .mt-section{margin-top:20px;}
  #mytasks .mt-section:first-child{margin-top:2px;}
  #mytasks .mt-head{display:flex;align-items:center;gap:8px;margin-bottom:10px;}
  #mytasks .mt-head h3{margin:0;font-size:11px;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:var(--ink);}
  #mytasks .mt-dot{width:9px;height:9px;border-radius:50%;flex:none;}
  #mytasks .mt-badge{font-size:11px;font-weight:600;padding:1px 8px;border-radius:999px;background:var(--tint);color:var(--muted);}
  #mytasks .mt-past .mt-dot{background:#E23B2E;}
  #mytasks .mt-due .mt-dot{background:#0171BF;}
  #mytasks .mt-prog .mt-dot{background:#00B050;}
  #mytasks .mt-cards{display:flex;flex-direction:column;gap:12px;}
  #mytasks .mt-card{background:#fff;border:1px solid var(--line);border-radius:11px;overflow:hidden;box-shadow:var(--shadow);}
  #mytasks .mt-card-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 13px;font-weight:600;font-size:12.5px;letter-spacing:.01em;background:#fafbfc;color:var(--ink);border-bottom:1px solid var(--line);}
  #mytasks .mt-proj{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  #mytasks .mt-tag{flex:none;font-size:9.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;padding:2px 8px;border-radius:999px;border:1px solid rgba(255,255,255,.55);white-space:nowrap;}
  #mytasks table{width:100%;border-collapse:collapse;font-size:12.5px;}
  #mytasks thead th{text-align:left;font-weight:500;color:var(--muted);font-size:9.5px;text-transform:uppercase;letter-spacing:.05em;padding:8px 13px;border-bottom:1px solid var(--line);}
  #mytasks tbody td{padding:9px 13px;border-bottom:1px solid var(--line);vertical-align:top;}
  #mytasks tbody tr:last-child td{border-bottom:none;}
  #mytasks th.mt-num,#mytasks td.mt-num{text-align:center;}
  #mytasks thead th:nth-child(2),#mytasks thead th:nth-child(3){text-align:center;}
  #mytasks tr.mt-sub td.mt-dt,#mytasks tr.mt-sub td.mt-num{padding-top:26px;}
  #mytasks td.mt-num{vertical-align:top;font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:500;color:var(--muted);}
  #mytasks .mt-parent{font-size:11px;font-weight:400;color:var(--muted);line-height:1.3;margin-bottom:3px;}
  #mytasks .mt-name a{color:var(--ink);font-weight:500;}
  #mytasks .mt-name a:hover{color:var(--teal);text-decoration:underline;}
  #mytasks .mt-dt{white-space:nowrap;color:var(--muted);font-weight:500;text-align:center;}
  #mytasks .mt-dt.start-today{color:#1f8a4c;}
  #mytasks .mt-dt.due-today{color:#E23B2E;}
  #mytasks .mt-muted{color:#b9c0c1;font-weight:500;}
  #mytasks .mt-empty{color:var(--muted);font-size:12.5px;border:1px dashed var(--line);border-radius:10px;padding:14px;text-align:center;}
  #mytasks .mt-refresh{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:500;color:var(--teal);border:1px solid var(--line);border-radius:8px;padding:5px 10px;transition:.15s;white-space:nowrap;align-self:flex-start;}
  #mytasks .mt-refresh:hover{background:var(--tint);border-color:var(--teal);text-decoration:none;}
  #mytasks .mt-refresh svg{width:13px;height:13px;fill:var(--teal);}
"""

SECTION = """      <!-- MY TASKS (Asana) -->
      <section class="block" id="mytasks">
        <div class="block-head">
          <div class="block-icon"><svg viewBox="0 0 24 24"><path d="M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm-2 14l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg></div>
          <div><h2>My Tasks</h2><p class="sub">From Asana &middot; grouped by project &middot; click a task to open it<span id="mt-stamp"></span></p></div>
          <a class="mt-refresh" href="https://github.com/__REPO__/actions/workflows/refresh.yml" target="_blank" rel="noopener" title="Open GitHub Actions, then click Run workflow to refresh now"><svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.96 7.96 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>Refresh</a>
        </div>
        <div id="mytasksBody"></div>
      </section>
"""

SCRIPT = """
<script>
/* ---- My Tasks (Asana) ---- */
(function(){
  var MY_TASKS_DATE = "__DATE__";
  var MY_TASKS_DATA = __DATA__;
  var PC = {"TSR84801 NPD Reduction":"#FA783C","FTTxx00 Static IP":"#0171BF","BSF Install Health Certificate":"#00B050"};
  var PORTCOL = {"Brightspeed":"#E8731E","Cyclotron":"#5B53C9"};
  var FB = ["#FCC800","#FA4628","#E6E7E8"]; var asg = {}; var fi = 0;
  function colorFor(n){ if(PC[n]) return PC[n]; if(!asg[n]){ asg[n]=FB[fi%FB.length]; fi++; } return asg[n]; }
  function textOn(hex){ var h=hex.replace('#',''); function c(i){return parseInt(h.substr(i,2),16)/255;} function L(x){return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4);} var l=0.2126*L(c(0))+0.7152*L(c(2))+0.0722*L(c(4)); return l>0.45?'#0d1719':'#ffffff'; }
  function fmt(k){ if(!k) return null; var p=k.split('-'); return new Date(+p[0],+p[1]-1,+p[2]).toLocaleDateString('en-US',{month:'short',day:'numeric'}); }
  function esc(s){ return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  function tag(p){ if(!p) return ''; var c=PORTCOL[p]||'#5c6c6f'; return '<span class="mt-tag" style="background:'+c+';color:#fff">'+esc(p)+'</span>'; }
  function dt(k,type){ if(!k) return '<td class="mt-dt mt-muted">\\u2014</td>'; var cls='mt-dt'; if(k===MY_TASKS_DATE) cls = type==='start' ? 'mt-dt start-today' : 'mt-dt due-today'; return '<td class="'+cls+'">'+fmt(k)+'</td>'; }
  function group(arr){ var g={}; arr.forEach(function(t){ (g[t.project]=g[t.project]||[]).push(t); }); return Object.keys(g).sort(function(a,b){return a.localeCompare(b);}).map(function(p){ return {project:p, portfolio:g[p][0].portfolio, tasks:g[p].sort(function(a,b){return a.name.localeCompare(b.name);})}; }); }
  function cards(arr){
    if(!arr.length) return '<div class="mt-empty">No tasks here right now.</div>';
    return '<div class="mt-cards">'+group(arr).map(function(gp){
      var rows=gp.tasks.map(function(t){
        var nameCell = (t.parent ? '<div class="mt-parent">\\u21b3 '+esc(t.parent)+'</div>' : '')
          + '<a href="'+esc(t.url)+'" target="_blank" rel="noopener">'+esc(t.name)+'</a>';
        return '<tr'+(t.parent?' class="mt-sub"':'')+'><td class="mt-name">'+nameCell+'</td>'
          + dt(t.start,'start') + dt(t.due,'due')
          + '<td class="mt-num">'+(t.est!=null?t.est:'<span class="mt-muted">\\u2014</span>')+'</td>'
          + '<td class="mt-num">'+(t.pct!=null?Math.round(t.pct*100)+'%':'<span class="mt-muted">\\u2014</span>')+'</td></tr>';
      }).join('');
      return '<div class="mt-card"><div class="mt-card-head"><span class="mt-proj">'+esc(gp.project)+'</span>'+tag(gp.portfolio)+'</div>'
        + '<table><thead><tr><th>Task</th><th>Start</th><th>Due</th><th class="mt-num">Est Hrs</th><th class="mt-num">% Done</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
    }).join('')+'</div>';
  }
  function sec(cls,label,arr){ return '<div class="mt-section '+cls+'"><div class="mt-head"><span class="mt-dot"></span><h3>'+label+'</h3><span class="mt-badge">'+arr.length+'</span></div>'+cards(arr)+'</div>'; }
  var el=document.getElementById('mytasksBody');
  if(el){ el.innerHTML = sec('mt-past','Past Due',MY_TASKS_DATA.pastDue) + sec('mt-due','Due Today',MY_TASKS_DATA.dueToday) + sec('mt-prog','In Progress',MY_TASKS_DATA.inProgress); }
  var st=document.getElementById('mt-stamp');
  if(st){ var p=MY_TASKS_DATE.split('-'); st.textContent=' \\u00b7 updated '+new Date(+p[0],+p[1]-1,+p[2]).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); }
})();
</script>
"""

def render(base_html, data, today, repo_slug="YOUR-USERNAME/YOUR-REPO"):
    t = base_html
    t = t.replace("</style>", CSS + "</style>", 1)
    section = SECTION.replace("__REPO__", repo_slug)
    close = '    </div><!-- /right col -->'
    if close not in t:
        raise SystemExit("right-column close marker not found in template")
    t = t.replace(close, '\n' + section + close, 1)
    script = SCRIPT.replace("__DATE__", today).replace("__DATA__", json.dumps(data))
    t = t.replace("</body>", script + "\n</body>", 1)
    return t

def main():
    token = os.environ["ASANA_TOKEN"]
    tz = os.environ.get("DASHBOARD_TZ", "America/New_York")
    today = datetime.datetime.now(ZoneInfo(tz)).date().isoformat()
    repo_slug = (os.environ.get("GITHUB_REPOSITORY") or os.environ.get("REPO_SLUG", "")).strip() or "YOUR-USERNAME/YOUR-REPO"
    workspace = get_workspace(token)
    portmap = fetch_portfolio_map(token, workspace)
    tasks = fetch_tasks(token, workspace)
    data = build_data(tasks, today, portmap)
    with open(BASE, "r", encoding="utf-8") as f:
        base_html = f.read()
    html = render(base_html, data, today, repo_slug)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    counts = "past " + str(len(data["pastDue"])) + " due " + str(len(data["dueToday"])) + " inprog " + str(len(data["inProgress"]))
    print("Wrote " + OUT + " for " + today + " | " + counts + " | portfolios " + str(len(portmap)))

if __name__ == "__main__":
    main()
