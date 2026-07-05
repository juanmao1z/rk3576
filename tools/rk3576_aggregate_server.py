#!/usr/bin/env python3
"""RK3576 three-camera aggregate page with YOLO overlay proxy."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import urlopen


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>RK3576 三路摄像头聚合</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #0f1115; color: #e8eaed; font-family: Arial, "Microsoft YaHei", sans-serif; }
    header { height: 48px; display: flex; align-items: center; justify-content: space-between; padding: 0 14px; background: #191c22; border-bottom: 1px solid #2c313a; }
    h1 { margin: 0; font-size: 18px; font-weight: 600; }
    .status { font-size: 13px; color: #aab2c0; }
    main { padding: 10px; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .panel { background: #171a20; border: 1px solid #303640; border-radius: 6px; overflow: hidden; min-width: 0; }
    .title { height: 38px; display: flex; align-items: center; justify-content: space-between; padding: 0 10px; background: #20242c; font-size: 14px; }
    .title span:last-child { color: #9ba5b5; font-size: 12px; }
    .videoBox { position: relative; width: 100%; background: #050608; aspect-ratio: 4 / 3; }
    .wide .videoBox { aspect-ratio: 16 / 9; }
    img { width: 100%; height: 100%; object-fit: contain; display: block; }
    .box { position: absolute; border: 3px solid #00e676; pointer-events: none; }
    .label { position: absolute; left: -3px; top: -24px; height: 22px; padding: 2px 6px; color: #06130a; background: #00e676; font-size: 13px; font-weight: 700; white-space: nowrap; }
    .footer { margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    pre { margin: 0; padding: 10px; min-height: 88px; max-height: 180px; overflow: auto; color: #cfd7e6; background: #11141a; border: 1px solid #303640; border-radius: 6px; font-size: 12px; white-space: pre-wrap; }
    @media (max-width: 1000px) { .grid, .footer { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>RK3576 三路摄像头聚合</h1>
    <div class="status" id="status">初始化中</div>
  </header>
  <main>
    <section class="grid">
      <div class="panel">
        <div class="title"><span>网络摄像头 111 + YOLO 框</span><span id="u1"></span></div>
        <div class="videoBox" id="net1Box"><img id="cam1" alt="net camera 111"></div>
      </div>
      <div class="panel wide">
        <div class="title"><span>网络摄像头 112 + YOLO 框</span><span id="u2"></span></div>
        <div class="videoBox" id="net2Box"><img id="cam2" alt="net camera 112"></div>
      </div>
      <div class="panel">
        <div class="title"><span>云台 USB + YOLO 框</span><span id="u3"></span></div>
        <div class="videoBox" id="usbBox"><img id="cam3" alt="gimbal usb camera"></div>
      </div>
    </section>
    <section class="footer">
      <pre id="health">health 加载中...</pre>
      <pre id="detections">YOLO 加载中...</pre>
    </section>
  </main>
  <script>
    const host = location.hostname || '192.168.1.101';
    const urls = {
      cam1: `http://${host}:8081/stream.mjpg`,
      cam2: `http://${host}:8082/stream.mjpg`,
      cam3: `http://${host}:8083/stream.mjpg`,
      h1: `/proxy?url=${encodeURIComponent('http://127.0.0.1:8081/health')}`,
      h2: `/proxy?url=${encodeURIComponent('http://127.0.0.1:8082/health')}`,
      h3: `/proxy?url=${encodeURIComponent('http://127.0.0.1:8083/health')}`,
      yolo1: `/proxy?url=${encodeURIComponent('http://127.0.0.1:8090/detections')}`,
      yolo2: `/proxy?url=${encodeURIComponent('http://127.0.0.1:8091/detections')}`,
      yolo3: `/proxy?url=${encodeURIComponent('http://127.0.0.1:8092/detections')}`
    };
    cam1.src = urls.cam1;
    cam2.src = urls.cam2;
    cam3.src = urls.cam3;
    u1.textContent = `http://${host}:8081`;
    u2.textContent = `http://${host}:8082`;
    u3.textContent = `http://${host}:8083`;

    function drawBoxes(boxId, data) {
      const videoBox = document.getElementById(boxId);
      videoBox.querySelectorAll('.box').forEach(n => n.remove());
      const iw = data.image_width || 640;
      const ih = data.image_height || 480;
      const rect = videoBox.getBoundingClientRect();
      const scale = Math.min(rect.width / iw, rect.height / ih);
      const drawW = iw * scale;
      const drawH = ih * scale;
      const padX = (rect.width - drawW) / 2;
      const padY = (rect.height - drawH) / 2;
      for (const det of data.detections || []) {
        const box = document.createElement('div');
        box.className = 'box';
        box.style.left = `${padX + det.x * scale}px`;
        box.style.top = `${padY + det.y * scale}px`;
        box.style.width = `${det.width * scale}px`;
        box.style.height = `${det.height * scale}px`;
        const label = document.createElement('div');
        label.className = 'label';
        label.textContent = `${det.label || det.class_id} ${(det.score || 0).toFixed(2)}`;
        box.appendChild(label);
        videoBox.appendChild(box);
      }
    }

    async function refresh() {
      const stamp = new Date().toLocaleTimeString();
      try {
        const hs = await Promise.all([fetch(urls.h1), fetch(urls.h2), fetch(urls.h3)]);
        const txt = await Promise.all(hs.map(r => r.text()));
        health.textContent = `[${stamp}]\n8081 ${txt[0].trim()}\n8082 ${txt[1].trim()}\n8083 ${txt[2].trim()}`;
      } catch (e) {
        health.textContent = `[${stamp}] health 请求失败: ${e.message}`;
      }
      try {
        const rs = await Promise.all([fetch(urls.yolo1), fetch(urls.yolo2), fetch(urls.yolo3)]);
        const data = await Promise.all(rs.map(r => r.json()));
        drawBoxes('net1Box', data[0]);
        drawBoxes('net2Box', data[1]);
        drawBoxes('usbBox', data[2]);
        detections.textContent = `[${stamp}] YOLO\n` +
          `8090/net111 detections=${(data[0].detections || []).length} fps=${data[0].result_fps || 'n/a'}\n` +
          `8091/net112 detections=${(data[1].detections || []).length} fps=${data[1].result_fps || 'n/a'}\n` +
          `8092/usb   detections=${(data[2].detections || []).length} fps=${data[2].result_fps || 'n/a'}\n\n` +
          JSON.stringify({net111: data[0], net112: data[1], usb: data[2]}, null, 2);
      } catch (e) {
        detections.textContent = `[${stamp}] YOLO 请求失败: ${e.message}`;
      }
      status.textContent = `host=${host}  刷新=${stamp}`;
    }
    refresh();
    setInterval(refresh, 300);
    window.addEventListener('resize', refresh);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/index.html"):
            self._send(200, "text/html; charset=utf-8", HTML.encode("utf-8"))
            return
        if self.path.startswith("/proxy?url="):
            self._proxy()
            return
        self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def _proxy(self) -> None:
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(self.path).query)
        url = query.get("url", [""])[0]
        if not url.startswith("http://127.0.0.1:"):
            self._send(400, "text/plain; charset=utf-8", b"bad proxy url\n")
            return
        try:
            with urlopen(url, timeout=2.0) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "text/plain")
        except (OSError, URLError) as exc:
            data = json.dumps({"error": str(exc)}).encode("utf-8")
            content_type = "application/json"
        self._send(200, content_type, data)

    def _send(self, code: int, content_type: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()


if __name__ == "__main__":
    main()
