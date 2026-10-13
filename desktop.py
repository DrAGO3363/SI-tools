"""Native Windows desktop shell for SEO Universal Amir Edition."""
import threading
import tkinter as tk
from tkinter import messagebox
import server


def main():
    try:
        import webview
    except ImportError:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror('SEO Universal', 'Missing pywebview. Please use Build-Windows.bat to build the app.')
        root.destroy()
        return
    try:
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 8765), server.Handler)
    except OSError as exc:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror('SEO Universal', f'Port 8765 is already in use.\nClose other SEO windows and retry.\n\n{exc}')
        root.destroy()
        return
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        webview.create_window('SEO Universal | Amir Edition', 'http://127.0.0.1:8765/', width=1360, height=880, min_size=(960, 640), background_color='#0c1824')
        webview.start(gui='edgechromium')
    finally:
        httpd.shutdown()
        httpd.server_close()

if __name__ == '__main__':
    main()
