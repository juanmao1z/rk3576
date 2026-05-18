#pragma once

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/compressed_image.hpp"

namespace camera_web_cpp
{

/**
 * @brief MJPEG 浏览器转发与运行指标统计组件。
 *
 * 该组件负责：
 * 1. 订阅 `sensor_msgs/msg/CompressedImage`；
 * 2. 将最新 JPEG 帧缓存为共享指针，供多个 HTTP 客户端复用；
 * 3. 提供 `/stream.mjpg`、`/snapshot.jpg`、`/health`、`/metrics` 等接口；
 * 4. 在浏览器页面端显示 FPS 与 CPU 指标覆盖层；
 * 5. 以线程级统计方式分别计算采集线程和 HTTP 服务线程 CPU 占用。
 *
 * 当前版本不把文字直接烧进 JPEG 图像，而是通过前端覆盖层展示，
 * 这样能避免每帧重新解码和重绘，整体更省 CPU。
 */
class CompressedMjpegServer : public rclcpp::Node
{
public:
  /**
   * @brief 创建 Web 转发组件。
   * @param options 由 component container 传入的节点选项。
   */
  explicit CompressedMjpegServer(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

  /**
   * @brief 析构时停止 HTTP 服务线程并关闭监听 socket。
   */
  ~CompressedMjpegServer() override;

private:
  /**
   * @brief 接收同进程传入的压缩图像消息。
   *
   * 这里使用 UniquePtr 回调，以便在 intra-process 模式下尽量减少额外复制。
   * 收到消息后会更新最新帧缓存，并刷新 FPS / CPU 统计信息。
   */
  void on_image(sensor_msgs::msg::CompressedImage::UniquePtr message);

  /**
   * @brief HTTP 服务线程主函数。
   */
  void serve();

  /**
   * @brief 处理单个客户端请求。
   * @param client_fd 客户端 socket 描述符。
   */
  void handle_client(int client_fd);

  /**
   * @brief 保证缓冲区完整写出的辅助函数。
   * @return 写出成功返回 true；客户端断开或 socket 错误时返回 false。
   */
  bool send_all(int fd, const void * data, size_t size);

  /**
   * @brief 返回浏览器主页面。
   */
  void send_index(int fd);

  /**
   * @brief 返回叠加层使用的实时指标 JSON。
   */
  void send_metrics(int fd);

  /**
   * @brief 返回最小健康检查信息。
   */
  void send_health(int fd);

  /**
   * @brief 返回最近一帧 JPEG 静态图。
   */
  void send_snapshot(int fd);

  /**
   * @brief 以 multipart MJPEG 形式持续输出视频流。
   */
  void send_stream(int fd);

  /**
   * @brief 在持锁状态下更新 FPS 与 CPU 指标。
   */
  void update_metrics_locked();

  /**
   * @brief 基于滑动窗口计算当前 ROS FPS。
   */
  double calculate_ros_fps_locked() const;

  /**
   * @brief 读取指定线程的 CPU tick。
   *
   * 当前组件化版本统一通过 `/proc/self/task/<tid>/stat`
   * 读取采集线程和 HTTP 服务线程的 utime + stime。
   */
  static long read_process_cpu_ticks(pid_t pid);

  /**
   * @brief 将两次采样的 tick 差值换算为 CPU 百分比。
   */
  double ticks_to_percent(long previous_ticks, long current_ticks, double wall_delta) const;

  /// 订阅的压缩图像话题名。
  std::string topic_;
  /// HTTP 监听端口。
  int port_ {8081};
  /// 用于显示的目标帧率。
  double target_fps_ {30.0};
  /// Linux 每秒 tick 数。
  long clock_ticks_ {100};
  /// 当前在线 CPU 核数，用于整机归一化。
  long cpu_count_ {1};
  /// HTTP 监听 socket。
  int server_fd_ {-1};
  /// 控制服务线程退出的标志位。
  std::atomic<bool> running_ {true};
  /// HTTP 服务线程。
  std::thread server_thread_;
  /// 保护最新帧和统计数据的互斥锁。
  std::mutex frame_mutex_;
  /// 当有新帧到来时唤醒等待中的流式客户端。
  std::condition_variable frame_cv_;
  /// 指向最近一帧 JPEG 数据的共享指针。
  std::shared_ptr<const std::vector<unsigned char>> latest_frame_;
  /// 从启动至今累计收到的帧数。
  uint64_t frame_count_ {0};
  /// 最近一帧到达的时间戳。
  std::chrono::steady_clock::time_point last_frame_time_ {std::chrono::steady_clock::now()};
  /// 用于计算 ROS FPS 的滑动窗口时间戳队列。
  std::deque<std::chrono::steady_clock::time_point> frame_times_;
  /// 上一次 CPU 采样时间。
  std::chrono::steady_clock::time_point last_cpu_sample_time_ {std::chrono::steady_clock::now()};
  /// 上一次 HTTP 服务线程的 CPU tick。
  long last_server_ticks_ {-1};
  /// 上一次采集线程的 CPU tick。
  long last_capture_thread_ticks_ {-1};
  /// 当前滑动窗口下的 ROS FPS。
  double current_ros_fps_ {0.0};
  /// 采集线程 CPU 百分比。
  double current_publisher_cpu_ {0.0};
  /// Web 转发部分 CPU 百分比。
  double current_server_cpu_ {0.0};
  /// 按整机核数归一化后的整条链路 CPU 百分比。
  double current_pipeline_cpu_ {0.0};
  /// 订阅压缩图像的 ROS2 订阅器。
  rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr subscription_;
};

}  // namespace camera_web_cpp
