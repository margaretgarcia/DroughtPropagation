"""Local server for the Arizona Drought Propagation Explorer.

Serves this folder and opens it in your browser. Sends no-cache headers so the
browser always loads the current files (never a stale cached version). If the
default port is busy (e.g. an old server is still running), it automatically
picks the next free port. Stop the server by closing this window or Ctrl+C.

Usage (from the batch file):  python serve.py
"""
import http.server
import os
import socket
import socketserver
import sys
import webbrowser

START_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


class Server(socketserver.TCPServer):
    allow_reuse_address = True


def port_in_use(port):
    """True if something is already listening on this port (a stale server).

    On Windows allow_reuse_address lets bind() succeed on a port another server
    already holds, so we detect a live listener by trying to connect instead."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    port = START_PORT
    while port_in_use(port) and port < START_PORT + 20:
        port += 1
    try:
        httpd = Server(("127.0.0.1", port), NoCacheHandler)
    except OSError as e:
        print("Could not start the server on port %d: %s" % (port, e))
        input("Press Enter to close...")
        return

    url = "http://localhost:%d/index.html" % port
    print("=" * 60)
    print(" Arizona Drought Propagation Explorer")
    print(" Serving at: " + url)
    print(" Keep this window open while using the site.")
    print(" Press Ctrl+C or close this window to stop.")
    print("=" * 60)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
