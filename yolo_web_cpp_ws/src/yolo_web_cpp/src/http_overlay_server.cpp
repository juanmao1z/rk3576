// YOLO C++ Canvas 前端的内置 HTTP 服务。
// 8081 端口负责视频流，本服务只提供 HTML、检测 JSON 和健康检查。
#include "yolo_web_cpp/http_overlay_server.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <sstream>
#include <stdexcept>
#include <utility>

#include "yolo_web_cpp/json_utils.hpp"

namespace yolo_web_cpp
{

HttpOverlayServer::HttpOverlayServer(
  int port,
  std::string camera_url,
  SnapshotProvider snapshot_provider)
: port_(port),
  camera_url_(std::move(camera_url)),
  snapshot_provider_(std::move(snapshot_provider))
{
}

HttpOverlayServer::~HttpOverlayServer()
{
  stop();
}

void HttpOverlayServer::start()
{
  if (running_.exchange(true)) {
    return;
  }
  server_thread_ = std::thread(&HttpOverlayServer::serve, this);
}

void HttpOverlayServer::stop()
{
  running_.store(false);
  if (server_fd_ >= 0) {
    ::shutdown(server_fd_, SHUT_RDWR);
    ::close(server_fd_);
    server_fd_ = -1;
  }
  if (server_thread_.joinable()) {
    server_thread_.join();
  }
}

void HttpOverlayServer::serve()
{
  // 直接使用 POSIX socket，减少板端部署依赖；请求体很小，不需要完整 HTTP 框架。
  server_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
  if (server_fd_ < 0) {
    running_.store(false);
    return;
  }

  int enable = 1;
  setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &enable, sizeof(enable));

  sockaddr_in addr {};
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = INADDR_ANY;
  addr.sin_port = htons(static_cast<uint16_t>(port_));

  if (bind(server_fd_, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) < 0) {
    running_.store(false);
    return;
  }
  if (listen(server_fd_, 16) < 0) {
    running_.store(false);
    return;
  }

  while (running_.load()) {
    const int client = accept(server_fd_, nullptr, nullptr);
    if (client < 0) {
      continue;
    }
    std::thread(&HttpOverlayServer::handle_client, this, client).detach();
  }
}

void HttpOverlayServer::handle_client(int client_fd)
{
  char buffer[2048] {};
  const ssize_t received = recv(client_fd, buffer, sizeof(buffer) - 1, 0);
  if (received <= 0) {
    ::close(client_fd);
    return;
  }

  const std::string request(buffer, static_cast<size_t>(received));
  const DetectionSnapshot snapshot = snapshot_provider_();
  // 只按路径前缀分发 GET 请求；浏览器页面、健康检查和 JSON 调试足够使用。
  if (request.find("GET /detections") == 0) {
    send_response(client_fd, "application/json", detections_to_json(snapshot), "no-cache");
  } else if (request.find("GET /health") == 0) {
    send_response(client_fd, "text/plain; charset=utf-8", health_to_text(snapshot), "no-cache");
  } else {
    send_response(client_fd, "text/html; charset=utf-8", index_html(), "no-cache");
  }
  ::close(client_fd);
}

bool HttpOverlayServer::send_all(int fd, const void * data, size_t size)
{
  const char * ptr = static_cast<const char *>(data);
  size_t sent_total = 0;
  while (sent_total < size) {
    const ssize_t sent = send(fd, ptr + sent_total, size - sent_total, MSG_NOSIGNAL);
    if (sent <= 0) {
      return false;
    }
    sent_total += static_cast<size_t>(sent);
  }
  return true;
}

void HttpOverlayServer::send_response(
  int fd,
  const std::string & content_type,
  const std::string & body,
  const std::string & cache_control)
{
  const std::string header =
    "HTTP/1.1 200 OK\r\nContent-Type: " + content_type +
    "\r\nContent-Length: " + std::to_string(body.size()) +
    "\r\nCache-Control: " + cache_control +
    "\r\nConnection: close\r\n\r\n";
  if (!send_all(fd, header.data(), header.size())) {
    return;
  }
  send_all(fd, body.data(), body.size());
}

std::string HttpOverlayServer::index_html() const
{
  // 页面直接引用 camera_url_ 的 MJPEG <img>，Canvas 按 /detections 坐标叠框。
  std::ostringstream html;
  html << R"(<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YOLO C++ Canvas</title>
  <style>
    body{margin:0;background:#111;color:#eee;font-family:system-ui,sans-serif;}
    main{max-width:1280px;margin:0 auto;padding:20px;}
    .viewer{position:relative;background:#000;line-height:0;}
    img{display:block;width:100%;height:auto;background:#000;}
    canvas{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;}
    .hud{position:absolute;left:12px;top:12px;padding:8px 10px;border-radius:4px;background:rgba(0,0,0,.72);color:#00ff66;font:600 15px/1.45 ui-monospace,monospace;white-space:pre;line-height:1.45;}
    code{color:#8fd;}
  </style>
</head>
<body>
  <main>
    <h1>YOLO C++ Canvas</h1>
    <p>Video: <code>)" << json_escape(camera_url_) << R"(</code> | Detections: <code>/detections</code></p>
    <div class="viewer" id="viewer">
      <img id="stream" src=")" << camera_url_ << R"(" alt="camera stream">
      <canvas id="overlay"></canvas>
      <div class="hud" id="hud">Waiting for detections...</div>
    </div>
  </main>
  <script>
    const img = document.getElementById('stream');
    const canvas = document.getElementById('overlay');
    const ctx = canvas.getContext('2d');
    const hud = document.getElementById('hud');
    function resizeCanvas() {
      const rect = img.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const width = Math.max(1, Math.round(rect.width * dpr));
      const height = Math.max(1, Math.round(rect.height * dpr));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return rect;
    }
    function draw(data) {
      const rect = resizeCanvas();
      ctx.clearRect(0, 0, rect.width, rect.height);
      const scaleX = rect.width / Math.max(1, data.image_width || img.naturalWidth || 1);
      const scaleY = rect.height / Math.max(1, data.image_height || img.naturalHeight || 1);
      ctx.lineWidth = 2;
      ctx.font = '14px ui-monospace, monospace';
      for (const det of data.detections || []) {
        const x = det.x * scaleX;
        const y = det.y * scaleY;
        const w = det.width * scaleX;
        const h = det.height * scaleY;
        const label = `${det.label} ${(det.score * 100).toFixed(0)}%`;
        ctx.strokeStyle = '#00ff66';
        ctx.fillStyle = 'rgba(0,0,0,.74)';
        ctx.strokeRect(x, y, w, h);
        const textWidth = ctx.measureText(label).width + 10;
        ctx.fillRect(x, Math.max(0, y - 22), textWidth, 22);
        ctx.fillStyle = '#00ff66';
        ctx.fillText(label, x + 5, Math.max(14, y - 7));
      }
      hud.textContent =
        `DETECTIONS: ${(data.detections || []).length}\n` +
        `RESULT FPS: ${(data.result_fps || 0).toFixed(1)}\n` +
        `PIPELINE: ${(data.last_pipeline_ms || 0).toFixed(1)} ms\n` +
        `RKNN: ${(data.last_inference_ms || 0).toFixed(1)} ms\n` +
        `AGE: ${(data.age || 0).toFixed(2)} s`;
    }
    async function tick() {
      try {
        const res = await fetch('/detections', {cache: 'no-store'});
        draw(await res.json());
      } catch (error) {
        hud.textContent = 'Detection service unavailable';
      }
      setTimeout(tick, 80);
    }
    window.addEventListener('resize', () => fetch('/detections', {cache:'no-store'}).then(r => r.json()).then(draw).catch(() => {}));
    tick();
  </script>
</body>
</html>)";
  return html.str();
}

}  // namespace yolo_web_cpp
