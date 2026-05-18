#pragma once

// 无人机检测 Canvas 前端的轻量 HTTP 服务。
// 视频仍来自 camera_web_cpp 的 8081 原始 MJPEG 流，本服务只提供页面、JSON 和健康检查。

#include <atomic>
#include <cstddef>
#include <functional>
#include <string>
#include <thread>

#include "drone_yolo_web_cpp/detection.hpp"

namespace drone_yolo_web_cpp
{

class HttpOverlayServer
{
public:
  // 通过回调读取最新检测快照，避免 HTTP 线程直接依赖 ROS 节点内部锁。
  using SnapshotProvider = std::function<DetectionSnapshot()>;

  HttpOverlayServer(int port, std::string camera_url, SnapshotProvider snapshot_provider);
  ~HttpOverlayServer();

  void start();
  void stop();

private:
  // 单线程监听，多客户端请求用短生命周期线程处理；接口简单，避免引入 Web 框架。
  void serve();
  void handle_client(int client_fd);
  void send_response(
    int fd,
    const std::string & content_type,
    const std::string & body,
    const std::string & cache_control);
  bool send_all(int fd, const void * data, size_t size);
  std::string index_html() const;

  int port_ {};
  std::string camera_url_;
  SnapshotProvider snapshot_provider_;
  std::atomic<bool> running_ {false};
  int server_fd_ {-1};
  std::thread server_thread_;
};

}  // namespace drone_yolo_web_cpp
