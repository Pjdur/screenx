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
    """Serves the live MJPEG desktop/game stream."""

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
            
            html = """<html><head><meta charset='UTF-8'><title>Live Screen Stream</title>
<style>
:root { --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; }
html, body { height: 100vh; margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; overflow: hidden; display: flex; flex-direction: column; box-sizing: border-box; }
header { display: flex; justify-content: space-between; align-items: center; padding: 12px 24px; border-bottom: 1px solid var(--border); background: var(--card-bg); flex-shrink: 0; }
h2 { margin: 0; font-size: 1.25rem; font-weight: 600; }
.stream-wrapper { flex: 1; display: flex; justify-content: center; align-items: center; padding: 16px; overflow: hidden; background: #020617; }
.stream-container { position: relative; max-width: 100%; max-height: 100%; display: flex; justify-content: center; align-items: center; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: #000; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); }
.stream-container img { display: block; max-width: 100%; max-height: calc(100vh - 100px); width: auto; height: auto; object-fit: contain; }
</style>
</head><body>
<header>
  <h2>🖥️ Live Screen Stream</h2>
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
        print(f"Streaming at: http://{ip}:{PORT}")
        server.serve_forever()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        start_server("192.168.1.145")
    except KeyboardInterrupt:
        sys.exit(0)