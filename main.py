import sys
import time
import io
import ctypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import PIL.ImageGrab

# --- Enable DPI Awareness for accurate screen capture ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

PORT = 8000

class StreamHandler(SimpleHTTPRequestHandler):
    """Serves the live MJPEG ScreenX desktop/game stream with theme toggling."""

    def log_error(self, format, *args):
        # Suppress harmless connection abort/broken pipe errors caused by client disconnects
        if args and any(err in str(args[0]) for err in ["10053", "10054", "Broken pipe"]):
            return
        super().log_error(format, *args)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            
            html = """<html><head><meta charset='UTF-8'><title>ScreenX - Live Stream</title>
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
    <img src='/stream'>
  </div>
</div>
</body></html>"""
            self.wfile.write(html.encode('utf-8'))

        elif self.path == "/stream":
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            try:
                while True:
                    img = PIL.ImageGrab.grab()  

                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=75)
                    frame = buf.getvalue()

                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
                    self.wfile.flush()
                    time.sleep(0.04)  # ~25 FPS real-time streaming
            except Exception:
                pass
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silence per-request logging


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests concurrently to support streaming."""
    daemon_threads = True


def start_server(ip):
    try:
        server = ThreadedHTTPServer(("0.0.0.0", PORT), StreamHandler)
        print(f"ScreenX streaming at: http://{ip}>:{PORT}")
        server.serve_forever()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        start_server("localhost")
    except KeyboardInterrupt:
        sys.exit(0)