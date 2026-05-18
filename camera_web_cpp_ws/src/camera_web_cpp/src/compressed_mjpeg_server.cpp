// C++ 版本的浏览器 MJPEG 转发组件。
//
// 设计重点：
// 1. 原样转发摄像头输出的 JPEG 字节，不做二次编码；
// 2. 叠加层放在浏览器端，通过 /metrics 拉取指标，降低服务端 CPU；
// 3. 在同进程模式下使用 intra-process，并通过共享状态估算采集线程 CPU。

#include "camera_web_cpp/compressed_mjpeg_server.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <sstream>
#include <utility>

#include "camera_web_cpp/runtime_shared_state.hpp"
#include "rclcpp_components/register_node_macro.hpp"

namespace camera_web_cpp
{

CompressedMjpegServer::CompressedMjpegServer(const rclcpp::NodeOptions & options)
: Node("compressed_mjpeg_server", options)
{
  // image_topic 与发布组件保持一致；target_fps 只用于前端展示，不参与限流。
  topic_ = this->declare_parameter<std::string>("image_topic", "/camera/image_mjpeg");
  port_ = this->declare_parameter<int>("port", 8081);
  target_fps_ = this->declare_parameter<double>("target_fps", 30.0);
  clock_ticks_ = sysconf(_SC_CLK_TCK);
  cpu_count_ = std::max(1L, sysconf(_SC_NPROCESSORS_ONLN));
  last_cpu_sample_time_ = std::chrono::steady_clock::now();

  subscription_ = this->create_subscription<sensor_msgs::msg::CompressedImage>(
    topic_,
    rclcpp::QoS(10),
    std::bind(&CompressedMjpegServer::on_image, this, std::placeholders::_1));
  // 这里使用 UniquePtr 订阅回调，配合同进程 intra-process 可减少额外拷贝。

  server_thread_ = std::thread(&CompressedMjpegServer::serve, this);
  RCLCPP_INFO(get_logger(), "Serving %s at http://0.0.0.0:%d/", topic_.c_str(), port_);
}

CompressedMjpegServer::~CompressedMjpegServer()
{
  running_.store(false);
  frame_cv_.notify_all();
  if (server_fd_ >= 0) {
    ::shutdown(server_fd_, SHUT_RDWR);
    ::close(server_fd_);
  }
  if (server_thread_.joinable()) {
    server_thread_.join();
  }
}

void CompressedMjpegServer::on_image(sensor_msgs::msg::CompressedImage::UniquePtr message)
{
  std::lock_guard<std::mutex> lock(frame_mutex_);
  // 最新帧改用共享指针缓存，避免每个 HTTP 客户端各自再复制一份大 JPEG 缓冲区。
  latest_frame_ = std::make_shared<std::vector<unsigned char>>(std::move(message->data));
  frame_count_++;
  last_frame_time_ = std::chrono::steady_clock::now();
  frame_times_.push_back(last_frame_time_);
  while (frame_times_.size() > 30) {
    frame_times_.pop_front();
  }
  update_metrics_locked();
  frame_cv_.notify_all();
}

void CompressedMjpegServer::serve()
{
  RuntimeSharedState::instance().server_tid.store(
    static_cast<pid_t>(::syscall(SYS_gettid)),
    std::memory_order_relaxed);
  last_server_ticks_ = read_process_cpu_ticks(
    RuntimeSharedState::instance().server_tid.load(std::memory_order_relaxed));

  server_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
  if (server_fd_ < 0) {
    return;
  }

  int enable = 1;
  setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &enable, sizeof(enable));

  sockaddr_in addr {};
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = INADDR_ANY;
  addr.sin_port = htons(static_cast<uint16_t>(port_));

  if (bind(server_fd_, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) < 0) {
    return;
  }
  if (listen(server_fd_, 8) < 0) {
    return;
  }

  while (running_.load()) {
    int client = accept(server_fd_, nullptr, nullptr);
    if (client < 0) {
      // 服务退出时 accept 可能因为 socket 被关闭而失败，这里直接继续外层判断。
      continue;
    }
    std::thread(&CompressedMjpegServer::handle_client, this, client).detach();
  }
}

void CompressedMjpegServer::handle_client(int client_fd)
{
  char request_buffer[1024] {};
  const ssize_t received = recv(client_fd, request_buffer, sizeof(request_buffer) - 1, 0);
  if (received <= 0) {
    ::close(client_fd);
    return;
  }

  const std::string request(request_buffer, static_cast<size_t>(received));
  if (request.find("GET /health") == 0) {
    send_health(client_fd);
    ::close(client_fd);
    return;
  }
  if (request.find("GET /metrics") == 0) {
    send_metrics(client_fd);
    ::close(client_fd);
    return;
  }
  if (request.find("GET /snapshot.jpg") == 0) {
    send_snapshot(client_fd);
    ::close(client_fd);
    return;
  }
  if (request.find("GET /stream.mjpg") == 0) {
    send_stream(client_fd);
    ::close(client_fd);
    return;
  }
  send_index(client_fd);
  ::close(client_fd);
}

bool CompressedMjpegServer::send_all(int fd, const void * data, size_t size)
{
  const char * ptr = static_cast<const char *>(data);
  size_t sent_total = 0;
  while (sent_total < size) {
    // MSG_NOSIGNAL 可以避免客户端断开后触发 SIGPIPE 导致整个组件进程退出。
    const ssize_t sent = send(fd, ptr + sent_total, size - sent_total, MSG_NOSIGNAL);
    if (sent <= 0) {
      return false;
    }
    sent_total += static_cast<size_t>(sent);
  }
  return true;
}

void CompressedMjpegServer::send_index(int fd)
{
  // 覆盖层放在浏览器侧实现，而不是把文字绘制进 JPEG：
  // 1. 保留原始图像质量；
  // 2. 避免逐帧解码/渲染/编码；
  // 3. 后续新增指标时只需改前端文本，不影响视频链路。
  const std::string body =
    "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>ROS2 C++ Camera Stream</title>"
    "<style>body{margin:0;font-family:system-ui,sans-serif;background:#111;color:#eee;}"
    "main{max-width:1280px;margin:0 auto;padding:20px;}"
    ".viewer{position:relative;display:block;line-height:0;background:#000;}"
    "img{width:100%;height:auto;background:#000;display:block;}"
    ".overlay{position:absolute;left:14px;top:14px;padding:10px 12px;"
    "background:rgba(0,0,0,.72);color:#00ff66;font:600 18px/1.45 monospace;"
    "white-space:pre;border-radius:4px;pointer-events:none;}code{color:#8fd;}</style>"
    "</head><body><main><h1>ROS2 C++ Camera Stream</h1>"
    "<p>Topic: <code>/camera/image_mjpeg</code> | Stream: <code>/stream.mjpg</code></p>"
    "<div class=\"viewer\"><img src=\"/stream.mjpg\" alt=\"ROS2 C++ camera stream\">"
    "<div class=\"overlay\" id=\"overlay\">Loading metrics...</div></div>"
    "<script>"
    "async function updateMetrics(){"
    "try{"
    "const res=await fetch('/metrics',{cache:'no-store'});"
    "const data=await res.json();"
    "document.getElementById('overlay').textContent="
    "`ROS FPS: ${data.ros_fps.toFixed(1)}\\n`+"
    "`Target FPS: ${data.target_fps.toFixed(1)}\\n`+"
    "`Publisher CPU: ${data.publisher_cpu.toFixed(1)}%\\n`+"
    "`MJPEG CPU: ${data.mjpeg_cpu.toFixed(1)}%\\n`+"
    "`Pipeline CPU: ${data.pipeline_cpu.toFixed(1)}% sys`;"
    "}catch(_e){}"
    "}"
    "updateMetrics();setInterval(updateMetrics,500);"
    "</script></main></body></html>";
  const std::string header =
    "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: " +
    std::to_string(body.size()) + "\r\nConnection: close\r\n\r\n";
  if (!send_all(fd, header.data(), header.size())) {
    return;
  }
  send_all(fd, body.data(), body.size());
}

void CompressedMjpegServer::send_metrics(int fd)
{
  std::ostringstream body_stream;
  {
    std::lock_guard<std::mutex> lock(frame_mutex_);
    body_stream << std::fixed << std::setprecision(2)
                << "{"
                << "\"ros_fps\":" << current_ros_fps_ << ","
                << "\"target_fps\":" << target_fps_ << ","
                << "\"publisher_cpu\":" << current_publisher_cpu_ << ","
                << "\"mjpeg_cpu\":" << current_server_cpu_ << ","
                << "\"pipeline_cpu\":" << current_pipeline_cpu_
                << "}";
  }
  const std::string body = body_stream.str();
  const std::string header =
    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " +
    std::to_string(body.size()) + "\r\nCache-Control: no-cache\r\nConnection: close\r\n\r\n";
  if (!send_all(fd, header.data(), header.size())) {
    return;
  }
  send_all(fd, body.data(), body.size());
}

void CompressedMjpegServer::send_health(int fd)
{
  uint64_t frame_count = 0;
  double age = -1.0;
  {
    std::lock_guard<std::mutex> lock(frame_mutex_);
    frame_count = frame_count_;
    if (frame_count_ > 0) {
      age = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - last_frame_time_).count();
    }
  }
  const std::string body =
    "frames=" + std::to_string(frame_count) + " age=" + std::to_string(age) + "\n";
  const std::string header =
    "HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: " +
    std::to_string(body.size()) + "\r\nConnection: close\r\n\r\n";
  if (!send_all(fd, header.data(), header.size())) {
    return;
  }
  send_all(fd, body.data(), body.size());
}

void CompressedMjpegServer::send_snapshot(int fd)
{
  std::shared_ptr<const std::vector<unsigned char>> frame;
  {
    std::lock_guard<std::mutex> lock(frame_mutex_);
    frame = latest_frame_;
  }
  if (!frame || frame->empty()) {
    const std::string response =
      "HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n";
    send_all(fd, response.data(), response.size());
    return;
  }
  const std::string header =
    "HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: " +
    std::to_string(frame->size()) + "\r\nConnection: close\r\n\r\n";
  if (!send_all(fd, header.data(), header.size())) {
    return;
  }
  send_all(fd, frame->data(), frame->size());
}

void CompressedMjpegServer::send_stream(int fd)
{
  const std::string header =
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
    "Cache-Control: no-cache\r\nPragma: no-cache\r\nConnection: close\r\n\r\n";
  if (!send_all(fd, header.data(), header.size())) {
    return;
  }

  uint64_t last_sent = 0;
  while (running_.load()) {
    std::shared_ptr<const std::vector<unsigned char>> frame;
    uint64_t current_count = 0;
    {
      std::unique_lock<std::mutex> lock(frame_mutex_);
      frame_cv_.wait_for(
        lock,
        std::chrono::milliseconds(500),
        [&]() { return !running_.load() || frame_count_ != last_sent; });
      // 使用条件变量等待“有新帧”，替代固定周期空转轮询。
      if (!running_.load()) {
        break;
      }
      current_count = frame_count_;
      if (current_count != last_sent) {
        frame = latest_frame_;
      }
    }
    if (!frame || frame->empty() || current_count == last_sent) {
      continue;
    }
    last_sent = current_count;

    const std::string part_header =
      "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
      std::to_string(frame->size()) + "\r\n\r\n";
    if (!send_all(fd, part_header.data(), part_header.size())) {
      break;
    }
    if (!send_all(fd, frame->data(), frame->size())) {
      break;
    }
    if (!send_all(fd, "\r\n", 2)) {
      break;
    }
  }
}

void CompressedMjpegServer::update_metrics_locked()
{
  current_ros_fps_ = calculate_ros_fps_locked();
  const auto now = std::chrono::steady_clock::now();
  if (now - last_cpu_sample_time_ < std::chrono::milliseconds(500)) {
    return;
  }

  const double wall_delta =
    std::chrono::duration<double>(now - last_cpu_sample_time_).count();
  const pid_t capture_tid = RuntimeSharedState::instance().capture_tid.load(std::memory_order_relaxed);
  const pid_t server_tid = RuntimeSharedState::instance().server_tid.load(std::memory_order_relaxed);
  const long current_capture_thread_ticks = read_process_cpu_ticks(capture_tid);
  const long current_server_ticks = read_process_cpu_ticks(server_tid);

  current_publisher_cpu_ = ticks_to_percent(
    last_capture_thread_ticks_,
    current_capture_thread_ticks,
    wall_delta);
  current_server_cpu_ = ticks_to_percent(
    last_server_ticks_,
    current_server_ticks,
    wall_delta);
  current_pipeline_cpu_ =
    (current_server_cpu_ + current_publisher_cpu_) / static_cast<double>(cpu_count_);

  last_cpu_sample_time_ = now;
  last_server_ticks_ = current_server_ticks;
  last_capture_thread_ticks_ = current_capture_thread_ticks;
}

double CompressedMjpegServer::calculate_ros_fps_locked() const
{
  if (frame_times_.size() < 2) {
    return 0.0;
  }
  const double elapsed =
    std::chrono::duration<double>(frame_times_.back() - frame_times_.front()).count();
  if (elapsed <= 0.0) {
    return 0.0;
  }
  return static_cast<double>(frame_times_.size() - 1) / elapsed;
}

long CompressedMjpegServer::read_process_cpu_ticks(pid_t pid)
{
  if (pid <= 0) {
    return -1;
  }
  // 组件化后，我们统一按线程口径统计关键 CPU 开销。
  const std::string stat_path =
    "/proc/self/task/" + std::to_string(pid) + "/stat";
  std::ifstream stat_file(stat_path);
  if (!stat_file) {
    return -1;
  }
  std::string line;
  std::getline(stat_file, line);
  std::istringstream stream(line);
  std::vector<std::string> fields;
  for (std::string field; stream >> field;) {
    fields.push_back(field);
  }
  if (fields.size() <= 14) {
    return -1;
  }
  return std::stol(fields[13]) + std::stol(fields[14]);
}

double CompressedMjpegServer::ticks_to_percent(
  long previous_ticks,
  long current_ticks,
  double wall_delta) const
{
  if (previous_ticks < 0 || current_ticks < 0 || wall_delta <= 0.0) {
    return 0.0;
  }
  const double cpu_seconds =
    static_cast<double>(current_ticks - previous_ticks) / static_cast<double>(clock_ticks_);
  return std::max(0.0, cpu_seconds / wall_delta * 100.0);
}

}  // namespace camera_web_cpp

RCLCPP_COMPONENTS_REGISTER_NODE(camera_web_cpp::CompressedMjpegServer)
