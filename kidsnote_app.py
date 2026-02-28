#!/usr/bin/env python3
"""
키즈노트 백업 프로그램 - 웹 기반 GUI 앱
브라우저에서 열리는 로컬 웹 인터페이스
"""

import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# PyInstaller 번들 내에서 실행 시 경로 보정
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    sys.path.insert(0, bundle_dir)

from kidsnote_backup import KidsnoteBackup

# 라이선스 API URL (Google Apps Script 배포 URL)
LICENSE_API_URL = "https://script.google.com/macros/s/여기에_배포ID_입력/exec"

# 서버 포트
PORT = 18585

# 전역 상태
app_state = {
    'is_running': False,
    'logs': [],
    'progress': 0,
    'progress_label': '대기 중',
    'done': False,
    'success': False,
    'cancelled': False,
}
backup_instance = None
backup_lock = threading.Lock()

HTML_PAGE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>키즈노트 백업</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f5f5;
    color: #333;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 30px 20px;
}
.container {
    background: white;
    border-radius: 16px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.1);
    padding: 36px;
    width: 100%;
    max-width: 500px;
}
h1 {
    text-align: center;
    font-size: 24px;
    color: #2c3e50;
    margin-bottom: 28px;
    font-weight: 700;
}
.section {
    margin-bottom: 20px;
}
.section-title {
    font-size: 13px;
    font-weight: 600;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 10px;
}
label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    color: #555;
    margin-bottom: 6px;
}
input[type="text"], input[type="password"] {
    width: 100%;
    padding: 12px 14px;
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    font-size: 15px;
    transition: border-color 0.2s;
    outline: none;
    margin-bottom: 12px;
}
input:focus {
    border-color: #4a90d9;
}
.folder-row {
    display: flex;
    gap: 8px;
}
.folder-row input {
    flex: 1;
    margin-bottom: 0;
}
.folder-btn {
    padding: 12px 16px;
    background: #eee;
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    font-size: 14px;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.2s;
}
.folder-btn:hover { background: #ddd; }
.btn-row {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}
.btn {
    flex: 1;
    padding: 14px;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s;
}
.btn:active { transform: scale(0.98); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-start {
    background: #4a90d9;
    color: white;
}
.btn-start:hover:not(:disabled) { background: #3a7bc8; }
.btn-stop {
    background: #d94a4a;
    color: white;
    flex: 0.4;
}
.btn-stop:hover:not(:disabled) { background: #c43a3a; }
.progress-wrap {
    background: #e8e8e8;
    border-radius: 10px;
    height: 28px;
    overflow: hidden;
    margin-bottom: 8px;
    position: relative;
}
.progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #4a90d9, #5ba0e9);
    border-radius: 10px;
    transition: width 0.3s;
    width: 0%;
}
.progress-text {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
    color: #555;
}
.progress-label {
    text-align: center;
    font-size: 13px;
    color: #888;
    margin-bottom: 16px;
}
.log-box {
    background: #1e1e1e;
    color: #d4d4d4;
    border-radius: 10px;
    padding: 14px;
    font-family: "SF Mono", "Menlo", "Consolas", monospace;
    font-size: 12px;
    line-height: 1.6;
    height: 240px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}
.btn-open {
    display: none;
    width: 100%;
    padding: 14px;
    background: #4CAF50;
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    margin-top: 12px;
    transition: background 0.2s;
}
.btn-open:hover { background: #45a049; }
.btn-open.show { display: block; }
.license-section {
    background: #f8f9fa;
    border: 2px solid #e0e0e0;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
}
.license-section.verified {
    border-color: #4CAF50;
    background: #f0f9f0;
}
.license-row {
    display: flex;
    gap: 8px;
}
.license-row input {
    flex: 1;
    margin-bottom: 0;
}
.btn-verify {
    padding: 12px 20px;
    background: #4a90d9;
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.2s;
}
.btn-verify:hover:not(:disabled) { background: #3a7bc8; }
.btn-verify:disabled { opacity: 0.5; cursor: not-allowed; }
.license-msg {
    font-size: 13px;
    margin-top: 10px;
    font-weight: 500;
}
.license-msg.success { color: #4CAF50; }
.license-msg.error { color: #d94a4a; }
.disabled-overlay {
    opacity: 0.5;
    pointer-events: none;
}
</style>
</head>
<body>
<div class="container">
    <h1>키즈노트 백업 프로그램</h1>

    <div class="license-section" id="licenseSection">
        <div class="section-title">라이선스 인증</div>
        <label for="licenseKey">라이선스 키</label>
        <div class="license-row">
            <input type="text" id="licenseKey" placeholder="KN-XXXX-XXXX">
            <button class="btn-verify" id="verifyBtn" onclick="verifyLicense()">인증</button>
        </div>
        <div class="license-msg" id="licenseMsg"></div>
    </div>

    <div id="mainContent" class="disabled-overlay">
    <div class="section">
        <div class="section-title">로그인 정보</div>
        <label for="email">아이디</label>
        <input type="text" id="email" placeholder="키즈노트 아이디">
        <label for="password">비밀번호</label>
        <input type="password" id="password" placeholder="비밀번호">
    </div>

    <div class="section">
        <div class="section-title">저장 위치</div>
        <div class="folder-row">
            <input type="text" id="output" placeholder="저장 폴더 경로">
            <button class="folder-btn" onclick="browseFolder()">폴더 선택</button>
        </div>
    </div>

    <div class="btn-row">
        <button class="btn btn-start" id="startBtn" onclick="startBackup()">백업 시작</button>
        <button class="btn btn-stop" id="stopBtn" onclick="stopBackup()" disabled>중지</button>
    </div>
    </div>

    <div class="progress-wrap">
        <div class="progress-bar" id="progressBar"></div>
        <div class="progress-text" id="progressText">0%</div>
    </div>
    <div class="progress-label" id="progressLabel">대기 중</div>

    <div class="section">
        <div class="section-title">진행 상황</div>
        <div class="log-box" id="logBox"></div>
    </div>

    <button class="btn-open" id="openBtn" onclick="openFolder()">저장 폴더 열기</button>
</div>

<script>
let pollTimer = null;
let logIndex = 0;
let licenseKey = '';
let licenseVerified = false;

// 기본 저장 경로 가져오기
fetch('/api/default_path')
    .then(r => r.json())
    .then(d => { document.getElementById('output').value = d.path; });

function verifyLicense() {
    const key = document.getElementById('licenseKey').value.trim();
    if (!key) { alert('라이선스 키를 입력해주세요.'); return; }

    const msg = document.getElementById('licenseMsg');
    const btn = document.getElementById('verifyBtn');
    btn.disabled = true;
    msg.textContent = '인증 중...';
    msg.className = 'license-msg';

    fetch('/api/verify_license', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({key: key})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            licenseKey = key;
            licenseVerified = true;
            msg.textContent = '인증 완료 (남은 횟수: ' + d.remaining + '/' + d.max + ')';
            msg.className = 'license-msg success';
            document.getElementById('licenseSection').classList.add('verified');
            document.getElementById('licenseKey').disabled = true;
            btn.disabled = true;
            btn.textContent = '인증됨';
            document.getElementById('mainContent').classList.remove('disabled-overlay');
        } else {
            btn.disabled = false;
            msg.textContent = d.error;
            msg.className = 'license-msg error';
        }
    })
    .catch(() => {
        btn.disabled = false;
        msg.textContent = '서버 연결 실패. 인터넷 연결을 확인해주세요.';
        msg.className = 'license-msg error';
    });
}

function startBackup() {
    if (!licenseVerified) { alert('라이선스 인증이 필요합니다.'); return; }

    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value.trim();
    const output = document.getElementById('output').value.trim();

    if (!email) { alert('아이디를 입력해주세요.'); return; }
    if (!password) { alert('비밀번호를 입력해주세요.'); return; }
    if (!output) { alert('저장 위치를 입력해주세요.'); return; }

    document.getElementById('startBtn').disabled = true;
    document.getElementById('stopBtn').disabled = false;
    document.getElementById('openBtn').classList.remove('show');
    document.getElementById('logBox').textContent = '';
    logIndex = 0;

    fetch('/api/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password, output, license_key: licenseKey})
    })
    .then(r => r.json())
    .then(d => {
        if (!d.ok) {
            alert(d.error || '라이선스 사용 처리에 실패했습니다.');
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            return;
        }
        pollTimer = setInterval(pollStatus, 500);
    })
    .catch(() => {
        alert('서버 연결 실패');
        document.getElementById('startBtn').disabled = false;
    });
}

function stopBackup() {
    fetch('/api/stop', {method: 'POST'});
    document.getElementById('stopBtn').disabled = true;
}

function pollStatus() {
    fetch('/api/status?log_offset=' + logIndex)
        .then(r => r.json())
        .then(d => {
            // 로그 업데이트
            const logBox = document.getElementById('logBox');
            if (d.new_logs && d.new_logs.length > 0) {
                for (const line of d.new_logs) {
                    logBox.textContent += line + '\\n';
                }
                logBox.scrollTop = logBox.scrollHeight;
                logIndex += d.new_logs.length;
            }

            // 프로그레스 업데이트
            const pct = Math.round(d.progress);
            document.getElementById('progressBar').style.width = pct + '%';
            document.getElementById('progressText').textContent = pct + '%';
            document.getElementById('progressText').style.color = pct > 50 ? 'white' : '#555';
            document.getElementById('progressLabel').textContent = d.progress_label;

            // 완료 체크
            if (d.done) {
                clearInterval(pollTimer);
                document.getElementById('startBtn').disabled = false;
                document.getElementById('stopBtn').disabled = true;
                if (d.success && !d.cancelled) {
                    document.getElementById('openBtn').classList.add('show');
                    document.getElementById('progressBar').style.width = '100%';
                    document.getElementById('progressText').textContent = '100%';
                    document.getElementById('progressText').style.color = 'white';
                }
            }
        })
        .catch(() => {});
}

function openFolder() {
    fetch('/api/open_folder', {method: 'POST'});
}

function browseFolder() {
    fetch('/api/browse', {method: 'POST'})
        .then(r => r.json())
        .then(d => {
            if (d.path) {
                document.getElementById('output').value = d.path;
            }
        });
}
</script>
</body>
</html>"""


class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 서버 로그 무시

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/' or parsed.path == '':
            self._send_html(HTML_PAGE)

        elif parsed.path == '/api/default_path':
            default = os.path.join(os.path.expanduser("~"), "Desktop", "키즈노트백업")
            self._send_json({'path': default})

        elif parsed.path == '/api/status':
            params = parse_qs(parsed.query)
            offset = int(params.get('log_offset', [0])[0])
            with backup_lock:
                new_logs = app_state['logs'][offset:]
                self._send_json({
                    'is_running': app_state['is_running'],
                    'new_logs': new_logs,
                    'progress': app_state['progress'],
                    'progress_label': app_state['progress_label'],
                    'done': app_state['done'],
                    'success': app_state['success'],
                    'cancelled': app_state['cancelled'],
                })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/verify_license':
            content_len = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_len))
            result = verify_license(body['key'])
            self._send_json(result)

        elif parsed.path == '/api/start':
            content_len = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_len))
            # 라이선스 사용횟수 차감
            license_result = use_license(body.get('license_key', ''))
            if not license_result.get('ok'):
                self._send_json({'ok': False, 'error': license_result.get('error', '라이선스 오류')})
                return
            start_backup(body['email'], body['password'], body['output'])
            self._send_json({'ok': True})

        elif parsed.path == '/api/stop':
            stop_backup()
            self._send_json({'ok': True})

        elif parsed.path == '/api/open_folder':
            open_folder()
            self._send_json({'ok': True})

        elif parsed.path == '/api/browse':
            folder = browse_folder()
            self._send_json({'path': folder})

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def on_log(msg):
    with backup_lock:
        app_state['logs'].append(msg)


def on_progress(current, total, label):
    with backup_lock:
        if total > 0:
            app_state['progress'] = (current / total) * 100
            app_state['progress_label'] = f"{label}: {current}/{total} ({app_state['progress']:.0f}%)"


def run_backup_thread(email, password, output):
    global backup_instance
    try:
        backup_instance = KidsnoteBackup(
            email=email,
            password=password,
            output_dir=output,
            on_log=on_log,
            on_progress=on_progress,
        )
        success = backup_instance.run()
        with backup_lock:
            app_state['done'] = True
            app_state['success'] = success
            app_state['cancelled'] = backup_instance.cancelled
            app_state['is_running'] = False
    except Exception as e:
        on_log(f"\n[오류] 예기치 않은 오류: {e}")
        with backup_lock:
            app_state['done'] = True
            app_state['success'] = False
            app_state['is_running'] = False


def start_backup(email, password, output):
    global backup_instance
    with backup_lock:
        if app_state['is_running']:
            return
        app_state['is_running'] = True
        app_state['logs'] = []
        app_state['progress'] = 0
        app_state['progress_label'] = '시작 중...'
        app_state['done'] = False
        app_state['success'] = False
        app_state['cancelled'] = False

    # 저장 경로 기억 (폴더 열기용)
    app_state['output_dir'] = output

    t = threading.Thread(target=run_backup_thread, args=(email, password, output), daemon=True)
    t.start()


def stop_backup():
    global backup_instance
    if backup_instance:
        backup_instance.cancelled = True
        with backup_lock:
            app_state['progress_label'] = '중지 중...'


def browse_folder():
    """네이티브 폴더 선택 다이얼로그"""
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ['osascript', '-e',
                 'set theFolder to choose folder with prompt "백업 저장 위치 선택"'
                 '\nreturn POSIX path of theFolder'],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip().rstrip('/')
        elif system == "Windows":
            ps_cmd = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null;"
                "$dlg = New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$dlg.Description = '백업 저장 위치 선택';"
                "if ($dlg.ShowDialog() -eq 'OK') { $dlg.SelectedPath }"
            )
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        else:
            result = subprocess.run(
                ['zenity', '--file-selection', '--directory', '--title=백업 저장 위치 선택'],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
    except Exception:
        pass
    return ''


def verify_license(key):
    """Google Apps Script API로 라이선스 키 검증"""
    import urllib.request
    import urllib.parse
    try:
        url = LICENSE_API_URL + '?' + urllib.parse.urlencode({'action': 'verify', 'key': key})
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {'ok': False, 'error': f'서버 연결 실패: {e}'}


def use_license(key):
    """Google Apps Script API로 라이선스 사용횟수 차감"""
    import urllib.request
    import urllib.parse
    try:
        url = LICENSE_API_URL + '?' + urllib.parse.urlencode({'action': 'use', 'key': key})
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {'ok': False, 'error': f'라이선스 처리 실패: {e}'}


def open_folder():
    folder = app_state.get('output_dir', '')
    if folder and os.path.isdir(folder):
        if platform.system() == "Darwin":
            subprocess.Popen(["open", folder])
        elif platform.system() == "Windows":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])


def open_as_app(url):
    """Chrome/Edge --app 모드로 열어서 독립 앱처럼 보이게 함"""
    system = platform.system()

    # Chrome/Edge 경로 후보
    if system == "Darwin":
        candidates = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
        ]
    elif system == "Windows":
        local = os.environ.get('LOCALAPPDATA', '')
        pf = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        pf86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
        candidates = [
            os.path.join(local, r'Google\Chrome\Application\chrome.exe'),
            os.path.join(pf, r'Google\Chrome\Application\chrome.exe'),
            os.path.join(pf86, r'Google\Chrome\Application\chrome.exe'),
            os.path.join(pf, r'Microsoft\Edge\Application\msedge.exe'),
            os.path.join(pf86, r'Microsoft\Edge\Application\msedge.exe'),
        ]
    else:
        candidates = ['google-chrome', 'chromium-browser', 'chromium', 'microsoft-edge']

    for browser in candidates:
        try:
            if system in ("Darwin", "Windows") and not os.path.exists(browser):
                continue
            proc = subprocess.Popen(
                [browser, f'--app={url}', '--window-size=540,750'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return proc
        except FileNotFoundError:
            continue

    # Chromium 계열 못 찾으면 일반 브라우저로 폴백
    webbrowser.open(url)
    return None


def wait_for_server(url, timeout=5):
    """서버가 응답할 때까지 대기"""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.1)
    return False


def main():
    server = HTTPServer(('127.0.0.1', PORT), RequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    url = f'http://127.0.0.1:{PORT}'
    print(f"키즈노트 백업 프로그램이 시작되었습니다.")
    print(f"종료하려면 Ctrl+C를 누르세요.")

    # 서버 준비될 때까지 대기 후 브라우저 열기
    wait_for_server(url)
    open_as_app(url)

    # 서버 유지 (Ctrl+C로 종료)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
