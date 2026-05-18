#pragma once

// 无人机 YOLO 叠框 ROS2 节点。
// 节点订阅 /camera/image_mjpeg，调用 RKNN 推理器，缓存最新 drone 检测结果，
// 同时向 HTTP 前端和 /yolo/detections ROS 话题输出。

#include <chrono>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/compressed_image.hpp"
#include "vision_msgs/msg/detection2_d_array.hpp"
#include "drone_yolo_web_cpp/detection.hpp"
#include "drone_yolo_web_cpp/http_overlay_server.hpp"
#include "drone_yolo_web_cpp/yolo11_rknn_detector.hpp"

namespace drone_yolo_web_cpp
{

class DroneYoloOverlayNode : public rclcpp::Node
{
public:
  DroneYoloOverlayNode();
  ~DroneYoloOverlayNode() override;

private:
  // ROS 图像回调中只处理一帧：JPEG 解码、RKNN 推理、更新快照并发布检测话题。
  void on_image(const sensor_msgs::msg::CompressedImage::SharedPtr message);
  void update_snapshot_and_publish(const sensor_msgs::msg::CompressedImage & input, InferenceResult result);
  void publish_detections(
    const sensor_msgs::msg::CompressedImage & input,
    const InferenceResult & result);
  DetectionSnapshot snapshot() const;
  double current_result_fps_locked() const;

  std::string input_topic_;
  std::string model_path_;
  std::string camera_url_;
  std::vector<std::string> labels_;
  int port_ {};
  double confidence_threshold_ {};
  double iou_threshold_ {};
  double fps_window_seconds_ {};
  std::string detections_topic_;

  std::unique_ptr<Yolo11RknnDetector> detector_;
  std::unique_ptr<HttpOverlayServer> http_server_;
  rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr subscription_;
  rclcpp::Publisher<vision_msgs::msg::Detection2DArray>::SharedPtr detections_publisher_;

  mutable std::mutex snapshot_mutex_;
  // 以下字段只在 snapshot_mutex_ 保护下读写，供 HTTP 线程获取一致快照。
  std::vector<Detection> latest_detections_;
  std::vector<std::chrono::steady_clock::time_point> frame_times_;
  std::chrono::steady_clock::time_point latest_frame_time_ {};
  uint64_t frame_count_ {};
  int latest_image_width_ {};
  int latest_image_height_ {};
  PipelineTimings latest_timings_;
};

}  // namespace drone_yolo_web_cpp
