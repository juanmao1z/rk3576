#pragma once

// YOLO11 RKNN C API 推理器。
// 职责包含 JPEG 解码、letterbox 预处理、RKNN 输入输出、YOLO11 DFL 后处理、
// NMS 和坐标还原；外层 ROS 节点只负责订阅、发布和 Web 快照。

#include <array>
#include <chrono>
#include <cstdint>
#include <string>
#include <vector>

#include <opencv2/core.hpp>

#include "rknn_api.h"
#include "yolo_web_cpp/detection.hpp"

namespace yolo_web_cpp
{

struct PipelineTimings
{
  // 这些耗时会暴露给 /detections 与 /health，用于区分解码、NPU 推理和后处理成本。
  double decode_ms {};
  double inference_ms {};
  double postprocess_ms {};
  double total_ms {};
};

struct InferenceResult
{
  std::vector<Detection> detections;
  int image_width {};
  int image_height {};
  PipelineTimings timings;
};

class Yolo11RknnDetector
{
public:
  Yolo11RknnDetector(
    std::string model_path,
    std::vector<std::string> labels,
    double confidence_threshold,
    double iou_threshold);
  ~Yolo11RknnDetector();

  Yolo11RknnDetector(const Yolo11RknnDetector &) = delete;
  Yolo11RknnDetector & operator=(const Yolo11RknnDetector &) = delete;

  InferenceResult process_jpeg(const std::vector<unsigned char> & jpeg_bytes);

  int model_width() const { return model_width_; }
  int model_height() const { return model_height_; }
  int model_channels() const { return model_channels_; }
  bool is_quantized() const { return is_quantized_; }
  uint32_t output_count() const { return io_num_.n_output; }
  int class_count() const { return class_count_; }

private:
  struct LetterboxInfo
  {
    // 保存 letterbox 缩放比例和 padding，用于把模型坐标还原到原图坐标。
    float ratio {1.0F};
    float pad_x {0.0F};
    float pad_y {0.0F};
  };

  void init_model();
  void query_tensor_attrs();
  void release_model();

  cv::Mat make_letterbox(const cv::Mat & rgb, LetterboxInfo & info) const;
  std::vector<Detection> run_inference(cv::Mat & input, int image_width, int image_height, const LetterboxInfo & info);
  std::vector<Detection> postprocess(
    const std::vector<rknn_output> & outputs,
    int image_width,
    int image_height,
    const LetterboxInfo & info) const;

  void process_branch(
    const rknn_output & box_output,
    const rknn_output & score_output,
    const rknn_output * score_sum_output,
    const rknn_tensor_attr & box_attr,
    const rknn_tensor_attr & score_attr,
    const rknn_tensor_attr * score_sum_attr,
    int grid_h,
    int grid_w,
    int stride,
    int dfl_len,
    std::vector<Detection> & candidates) const;

  bool passes_score_sum(
    const rknn_output * score_sum_output,
    const rknn_tensor_attr * score_sum_attr,
    int grid_offset,
    float threshold) const;

  void find_best_class(
    const rknn_output & score_output,
    const rknn_tensor_attr & score_attr,
    int grid_offset,
    int grid_len,
    float threshold,
    int & class_id,
    float & class_score) const;

  float tensor_value(const rknn_output & output, const rknn_tensor_attr & attr, int offset) const;
  Detection scale_detection(const Detection & det, int image_width, int image_height, const LetterboxInfo & info) const;

  std::string model_path_;
  std::vector<std::string> labels_;
  double confidence_threshold_ {};
  double iou_threshold_ {};
  rknn_context ctx_ {};
  rknn_input_output_num io_num_ {};
  std::vector<rknn_tensor_attr> input_attrs_;
  std::vector<rknn_tensor_attr> output_attrs_;
  int model_width_ {640};
  int model_height_ {640};
  int model_channels_ {3};
  int class_count_ {1};
  bool is_quantized_ {false};
  double last_inference_ms_ {};
};

}  // namespace yolo_web_cpp
