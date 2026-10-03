"""Frozen desktop sidecar entry point; no system Python is required at runtime."""
from __future__ import annotations

# PyInstaller must divert multiprocessing workers before heavy/API imports.
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

import argparse
import ctypes
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time


def _parent_alive(process_id: int) -> bool:
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x100000, False, process_id)
        if not handle:
            return False
        try:
            kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
            kernel.WaitForSingleObject.restype = ctypes.c_uint32
            return kernel.WaitForSingleObject(handle, 0) == 0x102
        finally:
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel.CloseHandle(handle)
    try:
        os.kill(process_id, 0)
        return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Blackjack Vision Lab desktop backend")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--parent-pid", type=int, default=0)
    parser.add_argument("--self-test", action="store_true")
    options = parser.parse_args()
    if not 0 <= options.port <= 65535:
        parser.error("Port must be in 0..65535")
    bundled_font = Path(__file__).resolve().parent / "assets" / "fonts" / "DejaVuSans-Bold.ttf"
    if bundled_font.exists():
        os.environ["BJLAB_FONT_PATH"] = str(bundled_font)
    import uvicorn
    from bjlab.api import app

    if options.self_test:
        from bjlab.engine import Rules
        from bjlab.simulator import BlackjackSession
        from bjlab.datasets import render_table
        from bjlab.vision import TemplateCardDetector
        import cv2
        cv2.setNumThreads(1)
        import numpy as np
        frame = render_table([{"rank": "A", "suit": "S", "x": 100, "y": 300}])
        detected = TemplateCardDetector().detect(frame)
        if len(detected) != 1 or detected[0].rank != "A":
            raise RuntimeError("Frozen pixel detector self-test failed")
        from PIL import Image, ImageDraw
        from bjlab.datasets import card_font
        from bjlab.ocr import read_text, MODEL_SHA256
        import onnxruntime as ort
        text_image=Image.new('RGB',(70,40),'white')
        ImageDraw.Draw(text_image).text((6,6),'10',font=card_font(22),fill='black',anchor='lt')
        text,score=read_text(np.asarray(text_image))
        if text != '10' or score < .94:
            raise RuntimeError('Frozen offline card OCR self-test failed')
        session = BlackjackSession(Rules(), seed=7)
        session.deal()
        notice_root = Path(__file__).resolve().parent / "assets" / "licenses"
        if getattr(sys, "frozen", False) and not (notice_root / "NOTICE.md").is_file():
            raise RuntimeError("Frozen third-party notice bundle is missing")
        provenance_path = Path(__file__).resolve().parent / "assets" / "build-provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8-sig")) if provenance_path.is_file() else None
        print(json.dumps({"event": "self_test", "status": "ok", "frozen": bool(getattr(sys, "frozen", False)),
                          "numpy": np.__version__, "opencv": cv2.__version__,
                          "onnxruntime": ort.__version__, "ocr_model_sha256": MODEL_SHA256,
                          "offline_card_ocr_self_test": "10",
                          "third_party_notices_bundled": (notice_root / "NOTICE.md").is_file(),
                          "build_provenance": provenance,
                          "ui_bundled": (Path(__file__).resolve().parent / "ui" / "dist" / "index.html").exists()}), flush=True)
        return 0

    # Bind the exact port before announcing readiness, avoiding a port-selection
    # race between the native shell and Uvicorn.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", options.port))
    listener.listen(128)
    port = listener.getsockname()[1]
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False,
                            timeout_graceful_shutdown=5)
    server = uvicorn.Server(config)
    stop = threading.Event()

    def monitor() -> None:
        announced = False
        while not stop.wait(.1):
            if options.parent_pid and not _parent_alive(options.parent_pid):
                server.should_exit = True
                return
            if server.started and not announced:
                message = {"event": "backend_ready", "url": f"http://127.0.0.1:{port}",
                           "pid": os.getpid(), "frozen": bool(getattr(sys, "frozen", False))}
                print(json.dumps(message), flush=True)
                ready_path = os.environ.get("BJLAB_READY_FILE")
                if ready_path:
                    path = Path(ready_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(message), encoding="utf-8")
                announced = True

    threading.Thread(target=monitor, daemon=True, name="desktop-lifecycle").start()
    def shutdown_input() -> None:
        # A blocking read on the inherited Windows pipe stalls CRT stdin
        # initialization in spawned frozen workers. Read only available bytes,
        # so the control channel remains idle while workers initialize Python.
        descriptor = sys.stdin.fileno()
        pending = b""
        if sys.platform == "win32":
            import msvcrt
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.PeekNamedPipe.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                           ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p)
            kernel.PeekNamedPipe.restype = ctypes.c_int
            handle = msvcrt.get_osfhandle(descriptor)
        while not stop.wait(.1):
            if sys.platform == "win32":
                available = ctypes.c_uint32()
                if not kernel.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
                    return
                size = min(available.value, 4096)
                if not size:
                    continue
            else:
                import select
                if not select.select([descriptor], [], [], 0)[0]:
                    continue
                size = 4096
            chunk = os.read(descriptor, size)
            if not chunk:
                return
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                if line.strip() == b"shutdown":
                    server.should_exit = True
                    return
            if len(pending) > 4096:
                pending = b""
    if options.parent_pid and sys.stdin is not None:
        threading.Thread(target=shutdown_input, daemon=True, name="desktop-control").start()
    try:
        server.run(sockets=[listener])
    finally:
        stop.set()
        listener.close()
        import multiprocessing
        for child in multiprocessing.active_children():
            child.terminate()
            child.join(timeout=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
