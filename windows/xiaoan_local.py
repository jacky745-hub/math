"""小安 Xiao-An — Windows 本機助手.

Serves the web app from ../app on http://127.0.0.1 and adds local abilities the browser
cannot do on its own:
  - PowerPoint: open a file, start the slide show, next / previous / go to slide, end.
  - Word files: read a .docx from a local path, save the result next to the original.
  - Open things with their Windows app: Spotify (app), local files, web pages.
  - Run R (Rscript) and return the chart.

Only standard-library Python. Run:  python xiaoan_local.py   (or double-click 啟動小安.bat)

Safety
  - Listens on 127.0.0.1 only. Every API call needs a random token that is written into the
    page this server serves, so other websites cannot call it.
  - Files: only under Desktop, Documents, Downloads and OneDrive (plus folders listed in the
    XA_ROOTS environment variable). Saving never overwrites: it writes a new file.
  - The page asks the teacher before every action (open, save, slide show).
"""

import base64
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
APP_DIR = (HERE.parent / "app").resolve()
TOKEN = secrets.token_urlsafe(24)
IS_WINDOWS = platform.system() == "Windows"
MAX_FILE = 25 * 1024 * 1024
READ_EXT = {".docx", ".txt", ".md"}
OPEN_EXT = {".pptx", ".ppt", ".ppsx", ".docx", ".doc", ".pdf", ".xlsx", ".png", ".jpg", ".mp4", ".ggb"}
LIST_EXT = {".pptx", ".ppt", ".ppsx", ".docx"}


# ---------------------------------------------------------------- allowed folders
def allowed_roots():
    home = Path.home()
    roots = [home / "Desktop", home / "Documents", home / "Downloads"]
    for env in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        if os.environ.get(env):
            od = Path(os.environ[env])
            roots += [od, od / "Desktop", od / "Documents"]
    for extra in os.environ.get("XA_ROOTS", "").split(os.pathsep):
        if extra.strip():
            roots.append(Path(extra.strip()))
    out = []
    for r in roots:
        try:
            rr = r.resolve()
        except OSError:
            continue
        if rr.is_dir() and rr not in out:
            out.append(rr)
    return out


class ApiError(Exception):
    pass


def safe_path(raw, exts, must_exist=True):
    if not raw or not isinstance(raw, str):
        raise ApiError("沒有提供檔案路徑。")
    p = Path(raw.strip().strip('"')).expanduser()
    try:
        p = p.resolve(strict=must_exist)
    except (OSError, RuntimeError):
        raise ApiError("找不到這個檔案：" + raw)
    if p.suffix.lower() not in exts:
        raise ApiError("不支援這種檔案：" + p.suffix)
    for root in allowed_roots():
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ApiError("小安只能存取桌面、文件、下載與 OneDrive 資料夾裡的檔案。")


def free_name(folder, name):
    name = Path(name).name  # no folders in a name
    if Path(name).suffix.lower() != ".docx":
        name += ".docx"
    target = folder / name
    stem, n = target.stem, 2
    while target.exists():
        target = folder / f"{stem} ({n}).docx"
        n += 1
    return target


# ---------------------------------------------------------------- PowerPoint via COM
PS_PPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
try {
$cmd = $env:XA_CMD
try { $app = [Runtime.InteropServices.Marshal]::GetActiveObject('PowerPoint.Application') }
catch { if ($cmd -eq 'open') { $app = New-Object -ComObject PowerPoint.Application } else { throw 'PowerPoint 沒有開啟。請先開啟簡報。' } }
if ($cmd -eq 'open') {
  $app.Visible = -1
  $null = $app.Presentations.Open($env:XA_PATH)
} elseif ($cmd -eq 'start') {
  if ($app.Presentations.Count -lt 1) { throw '沒有開啟的簡報。' }
  $null = $app.ActivePresentation.SlideShowSettings.Run()
} elseif ($cmd -ne '') {
  if ($app.SlideShowWindows.Count -lt 1) { throw '簡報沒有在放映。請先按「開始放映」。' }
  $view = $app.SlideShowWindows.Item(1).View
  switch ($cmd) {
    'next' { $view.Next() }
    'prev' { $view.Previous() }
    'goto' { $view.GotoSlide([int]$env:XA_N) }
    'end'  { $view.Exit() }
  }
}
$info = @{ ok = $true; presentations = $app.Presentations.Count; showing = ($app.SlideShowWindows.Count -gt 0) }
if ($info.showing) {
  $v = $app.SlideShowWindows.Item(1).View
  try { $info.slide = $v.Slide.SlideIndex } catch { $info.slide = $null }
  $info.total = $app.SlideShowWindows.Item(1).Presentation.Slides.Count
} elseif ($app.Presentations.Count -gt 0) {
  $info.name = $app.ActivePresentation.Name
  $info.total = $app.ActivePresentation.Slides.Count
}
$info | ConvertTo-Json -Compress
} catch {
  @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
}
"""


def run_powershell(script, env_extra):
    if not IS_WINDOWS:
        raise ApiError("PowerPoint 控制只能在 Windows 上使用。")
    exe = shutil.which("powershell.exe") or shutil.which("powershell")
    if not exe:
        raise ApiError("找不到 Windows PowerShell。")
    env = dict(os.environ, **env_extra)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise ApiError("PowerPoint 沒有回應（超過 60 秒）。")
    lines = [x for x in (r.stdout or "").strip().splitlines() if x.strip().startswith("{")]
    if not lines:
        raise ApiError("PowerPoint 沒有回應。" + (r.stderr or "").strip()[:200])
    info = json.loads(lines[-1])
    if not info.get("ok"):
        raise ApiError(str(info.get("error") or "PowerPoint 指令失敗。").replace('Exception calling', '').strip())
    return info


def api_ppt(body):
    cmd = body.get("cmd")
    if cmd not in {"open", "start", "next", "prev", "goto", "end", "status"}:
        raise ApiError("不認得的簡報指令。")
    env = {"XA_CMD": "" if cmd == "status" else cmd}
    if cmd == "open":
        env["XA_PATH"] = str(safe_path(body.get("path"), {".pptx", ".ppt", ".ppsx"}))
    if cmd == "goto":
        env["XA_N"] = str(max(1, int(body.get("n", 1))))
    return run_powershell(PS_PPT, env)


# ---------------------------------------------------------------- files
def api_list(body):
    items = []
    for root in allowed_roots():
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).relative_to(root).parts)
            dirnames[:] = [d for d in dirnames if not d.startswith((".", "~", "$")) and depth < 2]
            for f in filenames:
                p = Path(dirpath) / f
                if p.suffix.lower() in LIST_EXT and not f.startswith("~$"):
                    try:
                        items.append((p.stat().st_mtime, p))
                    except OSError:
                        pass
    kind = body.get("kind")
    exts = {"word": {".docx"}, "ppt": {".pptx", ".ppt", ".ppsx"}}.get(kind, LIST_EXT)
    items = sorted((x for x in items if x[1].suffix.lower() in exts), reverse=True)[:40]
    return {"files": [{"path": str(p), "name": p.name, "folder": p.parent.name} for _, p in items]}


def api_file_read(body):
    p = safe_path(body.get("path"), READ_EXT)
    if p.stat().st_size > MAX_FILE:
        raise ApiError("檔案太大（超過 25 MB）。")
    return {"name": p.name, "path": str(p), "data": base64.b64encode(p.read_bytes()).decode("ascii")}


def api_file_write(body):
    original = safe_path(body.get("path"), {".docx", ".txt", ".md"})
    data = base64.b64decode(body.get("data") or "", validate=True)
    if not data or len(data) > MAX_FILE:
        raise ApiError("沒有內容或內容太大。")
    if data[:2] != b"PK":
        raise ApiError("寫入的內容不是 Word 檔。")
    target = free_name(original.parent, body.get("name") or original.stem + "_小安解題.docx")
    target.write_bytes(data)
    return {"path": str(target)}


# ---------------------------------------------------------------- open apps
def api_open(body):
    kind, value = body.get("kind"), (body.get("value") or "").strip()
    if kind == "url":
        u = urlparse(value)
        if u.scheme not in ("http", "https") or not u.netloc:
            raise ApiError("網址需要以 http:// 或 https:// 開頭。")
        webbrowser.open(value)
        return {"opened": value}
    if kind == "spotify":
        if not value:
            raise ApiError("請說想聽什麼。")
        uri = "spotify:search:" + value.replace(":", " ")
        if IS_WINDOWS:
            try:
                os.startfile(uri)  # Spotify app, if installed
                return {"opened": "Spotify App"}
            except OSError:
                pass
        webbrowser.open("https://open.spotify.com/search/" + value)
        return {"opened": "Spotify 網頁版"}
    if kind == "file":
        p = safe_path(value, OPEN_EXT)
        if IS_WINDOWS:
            os.startfile(str(p))
        else:
            webbrowser.open(p.as_uri())
        return {"opened": str(p)}
    raise ApiError("不認得要開啟的東西。")


# ---------------------------------------------------------------- R
def find_rscript():
    exe = shutil.which("Rscript")
    if exe or not IS_WINDOWS:
        return exe
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")):
        rdir = Path(base) / "R" if base else None
        if rdir and rdir.is_dir():
            found = sorted(rdir.glob("R-*/bin/Rscript.exe"), reverse=True)
            if found:
                return str(found[0])
    return None


def api_r(body):
    exe = find_rscript()
    if not exe:
        raise ApiError("這台電腦沒有安裝 R。可到 https://cran.r-project.org 下載。")
    code = body.get("code") or ""
    if len(code) > 20000:
        raise ApiError("R 程式碼太長。")
    with tempfile.TemporaryDirectory(prefix="xiaoan-r-") as tmp:
        png = Path(tmp) / "out.png"
        script = Path(tmp) / "run.R"
        script.write_text('out_png <- "' + png.as_posix() + '"\n' + code + "\n", encoding="utf-8")
        try:
            r = subprocess.run([exe, "--vanilla", str(script)], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=180, cwd=tmp, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise ApiError("R 執行超過 3 分鐘，已停止。")
        result = {"ok": r.returncode == 0, "stdout": r.stdout[-4000:], "stderr": r.stderr[-4000:]}
        if png.exists():
            result["png"] = base64.b64encode(png.read_bytes()).decode("ascii")
        return result


def api_ping(body):
    return {"os": platform.system(), "windows": IS_WINDOWS, "r": bool(find_rscript()),
            "roots": [str(r) for r in allowed_roots()], "version": 1}


API = {"ping": api_ping, "ppt": api_ppt, "list": api_list, "file_read": api_file_read,
       "file_write": api_file_write, "open": api_open, "r": api_r}


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(APP_DIR), **kw)

    def log_message(self, fmt, *args):  # quiet console
        if "/api/" in (self.path or ""):
            sys.stderr.write("[小安] " + (fmt % args) + "\n")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._host_ok():
            self.send_error(403)
            return
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = (APP_DIR / "index.html").read_text(encoding="utf-8")
            html = html.replace("<!--XA_LOCAL-->", '<meta name="xa-local-token" content="' + TOKEN + '">')
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/api/"):
            self.send_error(405)
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        origin = self.headers.get("Origin")
        port = self.server.server_address[1]
        if (not self._host_ok() or not path.startswith("/api/")
                or self.headers.get("X-XA-Token") != TOKEN
                or (origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"))):
            self._json(403, {"error": "拒絕存取。"})
            return
        fn = API.get(path[5:])
        if not fn:
            self._json(404, {"error": "沒有這個功能。"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_FILE * 2:
                raise ApiError("資料太大。")
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
            self._json(200, fn(body))
        except ApiError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:  # report, never crash the server
            self._json(500, {"error": "發生錯誤：" + type(e).__name__ + " " + str(e)[:200]})

    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    port = int(os.environ.get("XA_PORT", "8765"))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print("小安本機版已啟動：" + url)
    print("可存取的資料夾：" + "、".join(str(r) for r in allowed_roots()))
    print("關閉這個視窗即可結束小安。")
    if os.environ.get("XA_NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
