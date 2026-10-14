"""Web 可视化控制台：浏览器里查看状态、一键开关脚本。

用法：
    python tools/web_panel.py
启动后浏览器打开 http://127.0.0.1:8899
按 F1（或 F12）切换 启动/暂停；也可点网页按钮。
"""

import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml

from src.core.status import EngineStatus
from src.learn.rule_engine import RuleEngine
from src.utils.hotkey import HotkeyWatcher
from src.utils.logger import setup_logger, get_logger
from src.utils import agent_bridge

log = get_logger("quiz.web")

PORT = 8899
STATUS = EngineStatus()
LOCK = threading.Lock()
COORD = None
# 热键监听心跳，供前端展示监听是否存活
HK_BEAT = {"count": 0, "alive": False, "last": ""}


class Coordinator:
    def __init__(self, settings):
        self.settings = settings
        self.engine = None
        self.thread = None

    def _new_engine(self):
        return RuleEngine(self.settings, STATUS, ROOT / "config" / "rules.yaml")

    def _alive(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def start(self):
        with LOCK:
            if self._alive():
                if self.engine.paused:
                    self.engine.resume()
                    return "resumed"
                return "already_running"
            STATUS.set(state="running", message="启动中…")
            self.engine = self._new_engine()
            self.thread = threading.Thread(target=self.engine.run, daemon=True)
            self.thread.start()
            return "started"

    def pause(self):
        with LOCK:
            if self._alive() and not self.engine.paused:
                self.engine.pause()
                return "paused"
            return "not_running"

    def stop(self):
        with LOCK:
            if self.engine:
                self.engine.stop()
            STATUS.set(state="stopped", message="已停止")
            return "stopped"

    def toggle(self):
        """一个键切换：未运行→启动；运行→暂停；暂停→继续。"""
        with LOCK:
            if self._alive():
                if self.engine.paused:
                    self.engine.resume()
                    return "resumed"
                self.engine.pause()
                return "paused"
        return self.start()

    def state(self) -> str:
        if not self._alive():
            return "stopped"
        return "paused" if self.engine.paused else "running"


PAGE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>AI 丝绸之路助手 - 控制台</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Microsoft YaHei', sans-serif; background:#14161a; color:#e0e0e0;
         display:flex; justify-content:center; padding:32px 16px; }
  .card { width:580px; background:#1e1e1e; border-radius:14px; padding:24px;
          box-shadow:0 8px 32px rgba(0,0,0,.5); }
  h1 { font-size:20px; margin-bottom:4px; }
  .sub { color:#757575; font-size:13px; margin-bottom:20px; }
  .state { font-size:34px; font-weight:bold; margin:8px 0; }
  .msg { color:#bdbdbd; font-size:14px; min-height:20px; margin-bottom:12px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:6px 16px; font-size:13px;
          color:#80cbc4; margin-bottom:18px; font-family:Consolas,monospace; }
  .btns { display:flex; gap:10px; margin-bottom:16px; }
  button { flex:1; padding:14px; border:none; border-radius:8px; font-size:16px;
           font-weight:bold; cursor:pointer; color:#fff; transition:opacity .15s; }
  button:hover { opacity:.85; }
  #toggle { background:#00c853; }
  #stop { background:#e53935; flex:0 0 130px; }
  .hint { background:#263238; border-left:4px solid #00e5ff; padding:12px 14px;
          border-radius:6px; font-size:13px; color:#b0bec5; line-height:1.8; }
  kbd { background:#37474f; padding:2px 8px; border-radius:4px; font-family:monospace; color:#00e5ff; }
  .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; vertical-align:middle; }
  .hk { font-size:12px; color:#607d8b; }
</style>
</head>
<body>
<div class="card">
  <h1>🐫 AI 丝绸之路助手</h1>
  <div class="sub">网页控制台 · 实时状态</div>

  <div class="state"><span class="dot" id="dot"></span><span id="state">加载中…</span></div>
  <div class="msg" id="msg"></div>

  <div class="grid">
    <div>当前规则: <span id="rule">-</span></div>
    <div>代理: <span id="agent">-</span></div>
    <div>可见元素: <span id="visible">-</span></div>
    <div>执行次数: <span id="exec">0</span></div>
    <div>未知次数: <span id="unknown">0</span></div>
    <div>最新截图: <span id="last">-</span></div>
  </div>

  <div class="btns">
    <button id="toggle" onclick="act('toggle')">▶ 启动 / 暂停</button>
    <button id="stop" onclick="act('stop')">⏹ 停止</button>
  </div>
  <div class="hk" id="hk">热键监听: 检测中…</div>

  <div class="hint" style="margin-top:14px">
    💡 <b>操作提示</b><br>
    · 点 <b>启动/暂停</b> 切换状态（或按 <kbd>F1</kbd>/<kbd>F12</kbd>）<br>
    · 遇到没见过的界面会自动<b>暂停并截图</b><br>
    · 未知截图列表见下方，点缩略图可放大
  </div>

  <div style="margin-top:16px">
    <div style="font-size:14px;color:#9e9e9e;margin-bottom:8px">
      🆕 未知情况截图（点开可查看，把路径喂给 AI 加规则）
    </div>
    <div id="unknowns" style="display:flex;flex-wrap:wrap;gap:8px"></div>
  </div>
</div>

<div id="lightbox" onclick="this.style.display='none'"
     style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);
            z-index:99;justify-content:center;align-items:center;cursor:zoom-out">
  <img id="lightbox-img" style="max-width:90%;max-height:90%;border-radius:8px">
</div>

<script>
const COLORS={running:'#00c853',paused:'#ff9800',unknown:'#e53935',stopped:'#607d8b',idle:'#888888'};
async function refresh(){
  try{
    const r=await fetch('/status'); const s=await r.json();
    document.getElementById('state').textContent=s.state_label;
    document.getElementById('dot').style.background=COLORS[s.state]||'#888';
    document.getElementById('msg').textContent=s.message;
    document.getElementById('rule').textContent=s.current_rule||'-';
    document.getElementById('agent').textContent=s.agent?'在线 ✅':'离线 ❌';
    document.getElementById('visible').textContent=(s.visible||[]).join(', ')||'-';
    document.getElementById('exec').textContent=s.count_exec;
    document.getElementById('unknown').textContent=s.count_unknown;
    document.getElementById('last').textContent=s.last_unknown?s.last_unknown.split(/[\\/]/).pop():'-';
    const t=document.getElementById('toggle');
    if(s.state==='running'){ t.textContent='⏸ 暂停'; t.style.background='#ff9800'; }
    else { t.textContent='▶ 启动'; t.style.background='#00c853'; }
    document.getElementById('hk').textContent = s.hotkey_alive
      ? '热键监听: 活跃 ✅ (按 F1 / F12 切换)' : '热键监听: 未运行 ❌';
  }catch(e){ document.getElementById('state').textContent='连接断开'; }
}
async function loadUnknowns(){
  try{
    const r=await fetch('/unknowns'); const list=await r.json();
    const box=document.getElementById('unknowns');
    if(!list.length){ box.innerHTML='<span style="color:#546e7a;font-size:13px">暂无</span>'; return; }
    box.innerHTML=list.map(u=>
      '<div style="text-align:center">'+
      '<img src="/shot/'+encodeURIComponent(u.name)+'" '+
      'onclick="showBig(this.src)" '+
      'style="width:120px;height:80px;object-fit:cover;border-radius:6px;border:2px solid #37474f;cursor:pointer">'+
      '<div style="font-size:11px;color:#607d8b;margin-top:3px">'+u.time+'</div></div>').join('');
  }catch(e){}
}
function showBig(src){
  document.getElementById('lightbox-img').src=src;
  document.getElementById('lightbox').style.display='flex';
}
async function act(cmd){ await fetch('/'+cmd,{method:'POST'}); refresh(); }
setInterval(refresh,700); refresh();
setInterval(loadUnknowns,1500); loadUnknowns();
</script>
</body>
</html>'''


def _list_unknowns():
    """列出 data/unknown 下的截图（最新在前）。"""
    d = ROOT / "data" / "unknown"
    if not d.exists():
        return []
    files = sorted(d.glob("unknown_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for f in files[:50]:
        out.append({"name": f.name, "path": str(f),
                    "time": time.strftime("%H:%M:%S", time.localtime(f.stat().st_mtime))})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _serve_shot(self, fname):
        """提供未知截图图片。"""
        from urllib.parse import unquote
        fname = unquote(fname)
        f = (ROOT / "data" / "unknown" / fname).resolve()
        if not str(f).startswith(str((ROOT / "data" / "unknown").resolve())) or not f.exists():
            self._send(404, "not found", "text/plain")
            return
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8") if isinstance(body, str) else body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._send(200, PAGE, "text/html")
        elif self.path == "/unknowns":
            self._send(200, json.dumps(_list_unknowns(), ensure_ascii=False))
        elif self.path.startswith("/shot/"):
            self._serve_shot(self.path[6:])
        elif self.path == "/status":
            s = STATUS.snapshot()
            state = COORD.state() if COORD else "stopped"
            if state == "stopped" and s["state"] in ("unknown",):
                state = "unknown"
            label = {"idle": "未启动", "running": "运行中", "paused": "已暂停",
                     "unknown": "未知情况", "stopped": "已停止"}.get(state, state)
            payload = {
                "state": state, "state_label": label, "message": s["message"],
                "current_rule": s["current_rule"], "visible": s["visible"],
                "count_exec": s["count_exec"], "count_unknown": s["count_unknown"],
                "last_unknown": s["last_unknown"],
                "agent": agent_bridge.agent_alive(),
                "hotkey_alive": HK_BEAT["alive"],
            }
            self._send(200, json.dumps(payload, ensure_ascii=False))
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path == "/toggle":
            r = COORD.toggle()
        elif self.path == "/start":
            r = COORD.start()
        elif self.path == "/pause":
            r = COORD.pause()
        elif self.path == "/stop":
            r = COORD.stop()
        else:
            self._send(404, "not found", "text/plain")
            return
        log.info("网页操作: %s -> %s", self.path, r)
        self._send(200, json.dumps({"result": r}))


def hotkey_watch():
    """监听 F1 与 F12，触发启动/暂停切换。"""
    hk_f1 = HotkeyWatcher("f1")
    hk_f12 = HotkeyWatcher("f12")
    HK_BEAT["alive"] = True
    log.info("热键监听启动（F1 / F12 切换 启动/暂停）")
    while True:
        HK_BEAT["count"] += 1
        try:
            if hk_f1.pressed() or hk_f12.pressed():
                log.info("检测到热键，切换状态。")
                HK_BEAT["last"] = time.strftime("%H:%M:%S")
                COORD.toggle()
        except Exception as e:  # noqa
            log.error("热键监听异常: %s", e)
            HK_BEAT["alive"] = False
        time.sleep(0.05)


def main():
    global COORD
    settings = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    setup_logger(settings["app"]["log_level"])
    COORD = Coordinator(settings)

    log.info("管理员代理: %s", "在线" if agent_bridge.agent_alive() else "离线（请先启动代理）")
    threading.Thread(target=hotkey_watch, daemon=True).start()

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    log.info("控制台已启动: http://127.0.0.1:%d", PORT)
    threading.Timer(0.8, lambda: webbrowser.open("http://127.0.0.1:%d" % PORT)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        COORD.stop()
        log.info("控制台关闭。")


if __name__ == "__main__":
    main()
