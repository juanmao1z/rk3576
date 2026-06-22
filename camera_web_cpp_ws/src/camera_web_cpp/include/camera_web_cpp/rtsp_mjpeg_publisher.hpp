#pragma once

#include <atomic>
#include <string>
#include <thread>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/compressed_image.hpp"

namespace camera_web_cpp
{

/**
 * @brief RTSP 视频流到 ROS2 压缩 JPEG 图像的发布组件。
 *
 * 该组件负责从网络摄像头读取 H.264/RTSP 视频帧，编码为 JPEG，
 * 再发布到和 USB 摄像头相同的 `/camera/image_mjpeg` 话题。
 */
class RtspMjpegPublisher : public rclcpp::Node
{
public:
  explicit RtspMjpegPublisher(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~RtspMjpegPublisher() override;

private:
  void capture_loop();
  bool open_capture();
  void close_capture();
  bool read_and_publish_frame();

  std::string rtsp_url_;
  std::string topic_;
  std::string frame_id_;
  int width_ {1280};
  int height_ {960};
  int fps_ {25};
  int jpeg_quality_ {85};
  int reconnect_delay_ms_ {1000};
  std::atomic<bool> running_ {true};
  std::thread capture_thread_;
  rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr publisher_;

  struct CaptureHandle;
  CaptureHandle * capture_ {nullptr};
};

}  // namespace camera_web_cpp
