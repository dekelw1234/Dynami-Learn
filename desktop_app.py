import threading
import socket
import time
import uvicorn
import webview

from api.main import app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_server(port: int):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


class Api:
    def __init__(self):
        self.window = None

    def toggle_fullscreen(self):
        if self.window:
            self.window.toggle_fullscreen()


def main():
    port = _free_port()
    server_thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    server_thread.start()

    # give uvicorn a moment to bind before pointing the window at it
    time.sleep(0.75)

    api = Api()
    window = webview.create_window(
        "Dynami-Learn",
        f"http://127.0.0.1:{port}",
        width=1400,
        height=900,
        min_size=(900, 600),
        js_api=api,
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    main()
