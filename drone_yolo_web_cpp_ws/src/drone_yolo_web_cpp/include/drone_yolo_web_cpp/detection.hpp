#pragma once

// Drone YOLO Web 前后端共用的检测结果结构。
// 坐标全部使用原始输入图像像素坐标，便于 HTTP JSON、Canvas 和 ROS 消息共用。

#include <cstdint>
#include <string>
#include <vector>

namespace drone_yolo_web_cpp
{

struct Detection
{
  // class_id 对应模型输出类别索引，label 默认是 drone，也可扩展为多类别标签。
  int class_id {};
  std::string label;
  float score {};
  // 左上角坐标和宽高，单位为原始图像像素。
  float x {};
  float y {};
  float width {};
  float height {};
};

struct DetectionSnapshot
{
  // HTTP 线程按需读取的不可变快照，避免直接持有推理线程内部状态。
  std::vector<Detection> detections;
  uint64_t frame_count {};
  int image_width {};
  int image_height {};
  double result_fps {};
  double last_pipeline_ms {};
  double last_decode_ms {};
  double last_inference_ms {};
  double last_postprocess_ms {};
  double age_seconds {-1.0};
};

}  // namespace drone_yolo_web_cpp
