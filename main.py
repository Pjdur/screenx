"""ScreenX - stream this computer's screen to any browser on the network as MJPEG."""

import argparse
import ctypes
import io
import socket
import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

import mss
from PIL import Image

# --- Enable DPI Awareness for accurate screen capture ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


class StreamHandler(SimpleHTTPRequestHandler):
    """Serves the live MJPEG ScreenX desktop/game stream using mss for high-speed capture."""

    def log_error(self, format, *args):
        # Suppress harmless connection abort/broken pipe errors caused by client disconnects
        if args and any(err in str(args[0]) for err in ["10053", "10054", "Broken pipe"]):
            return
        super().log_error(format, *args)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            html = """<html><head><meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>ScreenX - Live Stream</title>
<style>
:root { 
    --bg: #0f172a; 
    --card-bg: #1e293b; 
    --border: #334155; 
    --text: #f8fafc; 
    --btn-hover: #475569;
}
[data-theme="light"] { 
    --bg: #f1f5f9; 
    --card-bg: #ffffff; 
    --border: #cbd5e1; 
    --text: #0f172a; 
    --btn-hover: #e2e8f0;
}
html, body { height: 100vh; margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; overflow: hidden; display: flex; flex-direction: column; box-sizing: border-box; transition: background 0.2s, color 0.2s; }
header { display: flex; justify-content: space-between; align-items: center; padding: 12px 24px; border-bottom: 1px solid var(--border); background: var(--card-bg); flex-shrink: 0; transition: background 0.2s, border-color 0.2s; }
h2 { margin: 0; font-size: 1.25rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.theme-btn { background: var(--card-bg); border: 1px solid var(--border); color: var(--text); padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 0.875rem; cursor: pointer; transition: background 0.2s; }
.theme-btn:hover { background: var(--btn-hover); }
.stream-wrapper { flex: 1; display: flex; justify-content: center; align-items: center; padding: 16px; overflow: hidden; background: var(--bg); }
.stream-container { position: relative; max-width: 100%; max-height: 100%; display: flex; justify-content: center; align-items: center; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: #000; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.15); }
.stream-container img { display: block; max-width: 100%; max-height: calc(100vh - 100px); width: auto; height: auto; object-fit: contain; }
</style>
<script>
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('screenx_theme', theme);
    document.getElementById('themeToggle').innerText = theme === 'light' ? '🌙 Dark Mode' : '☀️ Light Mode';
}
function toggleTheme() {
    const current = localStorage.getItem('screenx_theme') || 'dark';
    setTheme(current === 'dark' ? 'light' : 'dark');
}
window.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('screenx_theme') || 'dark';
    setTheme(saved);
});
</script>
</head><body>
<header>
  <h2>⚡ ScreenX</h2>
  <button id='themeToggle' class='theme-btn' onclick='toggleTheme()'>☀️ Light Mode</button>
</header>
<div class='stream-wrapper'>
  <div class='stream-container'>
    <img src='/stream' alt='Live desktop stream'>
  </div>
</div>
</body></html>"""
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)

        elif path == "/stream":
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            try:
                # mss sessions are not thread-safe, so each viewer gets its own capture session.
                with mss.MSS() as sct:
                    monitor = sct.monitors[1]  # First physical display; monitors[0] spans all displays
                    while True:
                        sct_img = sct.grab(monitor)
                        # Efficiently convert mss raw BGRA bytes into a PIL Image
                        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                        buf = io.BytesIO()
                        img.save(buf, format='JPEG', quality=75)
                        frame = buf.getvalue()

                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n')
                        self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                        self.wfile.flush()
                        time.sleep(0.015)  # Faster frame pacing enabled by mss speed
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass  # viewer closed the tab or the network dropped
            except Exception as exc:
                print(f"ScreenX: stream error: {exc!r}", file=sys.stderr)

        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()

        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silence per-request logging


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests concurrently to support streaming."""
    daemon_threads = True
    # On Windows, SO_REUSEADDR lets a second process bind an already-used port, silently
    # splitting traffic between two servers. Fail loudly there; keep the POSIX default.
    allow_reuse_address = sys.platform != "win32"


def _lan_addresses():
    """Best-effort list of non-loopback IPv4 addresses for this machine."""
    addresses = set()

    # Connecting a UDP socket picks the default route's interface without sending traffic.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 1))  # TEST-NET-1, reserved and unroutable
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass

    return sorted(addr for addr in addresses if not addr.startswith("127."))


def print_urls(host, port):
    if host in ("", "0.0.0.0", "::"):
        print(f"ScreenX streaming at: http://localhost:{port}", flush=True)
        for addr in _lan_addresses():
            print(f"                  or: http://{addr}:{port}", flush=True)
        print("Viewers on your network need the second URL. The stream has no authentication.", flush=True)
    else:
        print(f"ScreenX streaming at: http://{host}:{port}", flush=True)


def start_server(host, port):
    try:
        server = ThreadedHTTPServer((host, port), StreamHandler)
    except OSError as exc:
        print(f"ScreenX: cannot listen on {host}:{port} ({exc}).", file=sys.stderr, flush=True)
        print("Is ScreenX already running? Try a different port, e.g. --port 8001.", file=sys.stderr, flush=True)
        return 1

    print_urls(host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nScreenX stopped.")
    finally:
        server.server_close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="screenx",
        description="Stream this computer's screen to any browser on the network.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"interface to bind (default: {DEFAULT_HOST}, all interfaces)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"port to listen on (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args(argv)
    return start_server(args.host, args.port)


if __name__ == "__main__":
    sys.exit(main())