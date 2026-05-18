// YOLO11 RKNN C API 推理与后处理实现。
// 输入来自摄像头 MJPEG 压缩帧，因此推理前必须先 JPEG 解码并做 letterbox。
#include "drone_yolo_web_cpp/yolo11_rknn_detector.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iterator>
#include <numeric>
#include <stdexcept>
#include <utility>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

namespace drone_yolo_web_cpp
{
namespace
{

constexpr int kMaxDetections = 128;

std::vector<unsigned char> read_file(const std::string & path)
{
  std::ifstream stream(path, std::ios::binary);
  if (!stream) {
    throw std::runtime_error("failed to open RKNN model: " + path);
  }
  return std::vector<unsigned char>(
    std::istreambuf_iterator<char>(stream),
    std::istreambuf_iterator<char>());
}

double elapsed_ms(
  const std::chrono::steady_clock::time_point & start,
  const std::chrono::steady_clock::time_point & end)
{
  return std::chrono::duration<double, std::milli>(end - start).count();
}

float dequant_i8(int8_t value, int32_t zero_point, float scale)
{
  return (static_cast<float>(value) - static_cast<float>(zero_point)) * scale;
}

float dequant_u8(uint8_t value, int32_t zero_point, float scale)
{
  return (static_cast<float>(value) - static_cast<float>(zero_point)) * scale;
}

int8_t quant_i8(float value, int32_t zero_point, float scale)
{
  const float quantized = value / scale + static_cast<float>(zero_point);
  return static_cast<int8_t>(std::clamp(std::round(quantized), -128.0F, 127.0F));
}

uint8_t quant_u8(float value, int32_t zero_point, float scale)
{
  const float quantized = value / scale + static_cast<float>(zero_point);
  return static_cast<uint8_t>(std::clamp(std::round(quantized), 0.0F, 255.0F));
}

std::array<float, 4> compute_dfl(const std::vector<float> & logits, int dfl_len)
{
  // YOLO11 box 分支使用 DFL 分布回归，这里把每条边的离散分布还原为距离。
  std::array<float, 4> box {};
  for (int side = 0; side < 4; ++side) {
    const int base = side * dfl_len;
    float max_logit = logits[base];
    for (int i = 1; i < dfl_len; ++i) {
      max_logit = std::max(max_logit, logits[base + i]);
    }

    float sum = 0.0F;
    float weighted = 0.0F;
    for (int i = 0; i < dfl_len; ++i) {
      const float value = std::exp(logits[base + i] - max_logit);
      sum += value;
      weighted += value * static_cast<float>(i);
    }
    box[side] = sum > 0.0F ? weighted / sum : 0.0F;
  }
  return box;
}

float intersection_over_union(const Detection & a, const Detection & b)
{
  const float a_right = a.x + a.width;
  const float a_bottom = a.y + a.height;
  const float b_right = b.x + b.width;
  const float b_bottom = b.y + b.height;

  const float inter_left = std::max(a.x, b.x);
  const float inter_top = std::max(a.y, b.y);
  const float inter_right = std::min(a_right, b_right);
  const float inter_bottom = std::min(a_bottom, b_bottom);
  const float inter_width = std::max(0.0F, inter_right - inter_left);
  const float inter_height = std::max(0.0F, inter_bottom - inter_top);
  const float inter_area = inter_width * inter_height;
  const float union_area = a.width * a.height + b.width * b.height - inter_area;
  return union_area > 0.0F ? inter_area / union_area : 0.0F;
}

}  // namespace

Yolo11RknnDetector::Yolo11RknnDetector(
  std::string model_path,
  std::vector<std::string> labels,
  double confidence_threshold,
  double iou_threshold)
: model_path_(std::move(model_path)),
  labels_(std::move(labels)),
  confidence_threshold_(confidence_threshold),
  iou_threshold_(iou_threshold)
{
  init_model();
}

Yolo11RknnDetector::~Yolo11RknnDetector()
{
  release_model();
}

void Yolo11RknnDetector::init_model()
{
  // RKNN runtime 需要模型二进制常驻到 rknn_init 完成；之后运行时使用 ctx_。
  const auto model_data = read_file(model_path_);
  const int ret = rknn_init(&ctx_, const_cast<unsigned char *>(model_data.data()),
    static_cast<uint32_t>(model_data.size()), 0, nullptr);
  if (ret < 0) {
    throw std::runtime_error("rknn_init failed: " + std::to_string(ret));
  }

  const int io_ret = rknn_query(ctx_, RKNN_QUERY_IN_OUT_NUM, &io_num_, sizeof(io_num_));
  if (io_ret != RKNN_SUCC) {
    throw std::runtime_error("RKNN_QUERY_IN_OUT_NUM failed: " + std::to_string(io_ret));
  }
  if (io_num_.n_input < 1 || io_num_.n_output < 2) {
    throw std::runtime_error("unexpected RKNN input/output count");
  }

  query_tensor_attrs();

  const auto & input = input_attrs_.at(0);
  if (input.fmt == RKNN_TENSOR_NCHW) {
    model_channels_ = input.dims[1];
    model_height_ = input.dims[2];
    model_width_ = input.dims[3];
  } else {
    model_height_ = input.dims[1];
    model_width_ = input.dims[2];
    model_channels_ = input.dims[3];
  }

  const auto & output = output_attrs_.at(0);
  is_quantized_ =
    output.qnt_type == RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC &&
    (output.type == RKNN_TENSOR_INT8 || output.type == RKNN_TENSOR_UINT8);

  if (io_num_.n_output >= 2) {
    class_count_ = std::max(1, static_cast<int>(output_attrs_.at(1).dims[1]));
  }
  if (labels_.empty()) {
    labels_.push_back("drone");
  }
  while (static_cast<int>(labels_.size()) < class_count_) {
    labels_.push_back("class_" + std::to_string(labels_.size()));
  }
}

void Yolo11RknnDetector::query_tensor_attrs()
{
  input_attrs_.resize(io_num_.n_input);
  for (uint32_t i = 0; i < io_num_.n_input; ++i) {
    std::memset(&input_attrs_[i], 0, sizeof(rknn_tensor_attr));
    input_attrs_[i].index = i;
    const int ret = rknn_query(ctx_, RKNN_QUERY_INPUT_ATTR, &input_attrs_[i], sizeof(rknn_tensor_attr));
    if (ret != RKNN_SUCC) {
      throw std::runtime_error("RKNN_QUERY_INPUT_ATTR failed: " + std::to_string(ret));
    }
  }

  output_attrs_.resize(io_num_.n_output);
  for (uint32_t i = 0; i < io_num_.n_output; ++i) {
    std::memset(&output_attrs_[i], 0, sizeof(rknn_tensor_attr));
    output_attrs_[i].index = i;
    const int ret = rknn_query(ctx_, RKNN_QUERY_OUTPUT_ATTR, &output_attrs_[i], sizeof(rknn_tensor_attr));
    if (ret != RKNN_SUCC) {
      throw std::runtime_error("RKNN_QUERY_OUTPUT_ATTR failed: " + std::to_string(ret));
    }
  }
}

void Yolo11RknnDetector::release_model()
{
  if (ctx_ != 0) {
    rknn_destroy(ctx_);
    ctx_ = 0;
  }
}

InferenceResult Yolo11RknnDetector::process_jpeg(const std::vector<unsigned char> & jpeg_bytes)
{
  // 摄像头服务不重编码，但 RKNN 输入需要 RGB 像素矩阵，因此这里必须解码 JPEG。
  const auto pipeline_start = std::chrono::steady_clock::now();
  const cv::Mat encoded(1, static_cast<int>(jpeg_bytes.size()), CV_8UC1,
    const_cast<unsigned char *>(jpeg_bytes.data()));
  cv::Mat bgr = cv::imdecode(encoded, cv::IMREAD_COLOR);
  if (bgr.empty()) {
    throw std::runtime_error("failed to decode input JPEG");
  }

  cv::Mat rgb;
  cv::cvtColor(bgr, rgb, cv::COLOR_BGR2RGB);
  LetterboxInfo letterbox;
  cv::Mat input = make_letterbox(rgb, letterbox);
  const auto decode_end = std::chrono::steady_clock::now();

  auto detections = run_inference(input, bgr.cols, bgr.rows, letterbox);
  const auto pipeline_end = std::chrono::steady_clock::now();

  InferenceResult result;
  result.detections = std::move(detections);
  result.image_width = bgr.cols;
  result.image_height = bgr.rows;
  result.timings.decode_ms = elapsed_ms(pipeline_start, decode_end);
  result.timings.inference_ms = last_inference_ms_;
  result.timings.total_ms = elapsed_ms(pipeline_start, pipeline_end);
  result.timings.postprocess_ms =
    std::max(0.0, result.timings.total_ms - result.timings.decode_ms - result.timings.inference_ms);
  return result;
}

cv::Mat Yolo11RknnDetector::make_letterbox(const cv::Mat & rgb, LetterboxInfo & info) const
{
  // 按 YOLO 训练/导出时的 letterbox 方式缩放，保持宽高比并填充 114 灰边。
  const int source_width = rgb.cols;
  const int source_height = rgb.rows;
  const float ratio = std::min(
    static_cast<float>(model_width_) / static_cast<float>(source_width),
    static_cast<float>(model_height_) / static_cast<float>(source_height));

  const int resized_width = static_cast<int>(std::round(static_cast<float>(source_width) * ratio));
  const int resized_height = static_cast<int>(std::round(static_cast<float>(source_height) * ratio));
  const int pad_width = model_width_ - resized_width;
  const int pad_height = model_height_ - resized_height;
  const int left = pad_width / 2;
  const int right = pad_width - left;
  const int top = pad_height / 2;
  const int bottom = pad_height - top;

  cv::Mat resized;
  if (source_width != resized_width || source_height != resized_height) {
    cv::resize(rgb, resized, cv::Size(resized_width, resized_height), 0.0, 0.0, cv::INTER_LINEAR);
  } else {
    resized = rgb;
  }

  cv::Mat output;
  cv::copyMakeBorder(
    resized,
    output,
    top,
    bottom,
    left,
    right,
    cv::BORDER_CONSTANT,
    cv::Scalar(114, 114, 114));

  info.ratio = ratio;
  info.pad_x = static_cast<float>(left);
  info.pad_y = static_cast<float>(top);
  return output.isContinuous() ? output : output.clone();
}

std::vector<Detection> Yolo11RknnDetector::run_inference(
  cv::Mat & input,
  int image_width,
  int image_height,
  const LetterboxInfo & info)
{
  rknn_input input_data {};
  input_data.index = 0;
  input_data.type = RKNN_TENSOR_UINT8;
  input_data.fmt = RKNN_TENSOR_NHWC;
  input_data.size = static_cast<uint32_t>(model_width_ * model_height_ * model_channels_);
  input_data.buf = input.data;

  int ret = rknn_inputs_set(ctx_, io_num_.n_input, &input_data);
  if (ret < 0) {
    throw std::runtime_error("rknn_inputs_set failed: " + std::to_string(ret));
  }

  const auto inference_start = std::chrono::steady_clock::now();
  ret = rknn_run(ctx_, nullptr);
  if (ret < 0) {
    throw std::runtime_error("rknn_run failed: " + std::to_string(ret));
  }

  std::vector<rknn_output> outputs(io_num_.n_output);
  for (uint32_t i = 0; i < io_num_.n_output; ++i) {
    outputs[i].index = i;
    outputs[i].want_float = !is_quantized_;
  }

  ret = rknn_outputs_get(ctx_, io_num_.n_output, outputs.data(), nullptr);
  const auto inference_end = std::chrono::steady_clock::now();
  if (ret < 0) {
    throw std::runtime_error("rknn_outputs_get failed: " + std::to_string(ret));
  }

  std::vector<Detection> detections;
  try {
    detections = postprocess(outputs, image_width, image_height, info);
  } catch (...) {
    rknn_outputs_release(ctx_, io_num_.n_output, outputs.data());
    throw;
  }
  rknn_outputs_release(ctx_, io_num_.n_output, outputs.data());

  last_inference_ms_ = elapsed_ms(inference_start, inference_end);
  return detections;
}

std::vector<Detection> Yolo11RknnDetector::postprocess(
  const std::vector<rknn_output> & outputs,
  int image_width,
  int image_height,
  const LetterboxInfo & info) const
{
  // 当前 YOLO11 RKNN 输出按 3 个尺度分支排列，每个分支包含 box 和 score。
  std::vector<Detection> candidates;
  const int branches = 3;
  const int outputs_per_branch = static_cast<int>(io_num_.n_output) / branches;
  if (outputs_per_branch < 2) {
    throw std::runtime_error("unexpected YOLO11 output count");
  }
  const int dfl_len = output_attrs_[0].dims[1] / 4;

  for (int branch = 0; branch < branches; ++branch) {
    const int box_index = branch * outputs_per_branch;
    const int score_index = box_index + 1;
    const int score_sum_index = outputs_per_branch == 3 ? box_index + 2 : -1;
    const auto & box_attr = output_attrs_.at(box_index);
    const auto & score_attr = output_attrs_.at(score_index);
    const rknn_output & box_output = outputs.at(box_index);
    const rknn_output & score_output = outputs.at(score_index);
    const rknn_output * score_sum_output =
      score_sum_index >= 0 ? &outputs.at(score_sum_index) : nullptr;
    const rknn_tensor_attr * score_sum_attr =
      score_sum_index >= 0 ? &output_attrs_.at(score_sum_index) : nullptr;

    const int grid_h = box_attr.dims[2];
    const int grid_w = box_attr.dims[3];
    const int stride = model_height_ / grid_h;
    process_branch(
      box_output,
      score_output,
      score_sum_output,
      box_attr,
      score_attr,
      score_sum_attr,
      grid_h,
      grid_w,
      stride,
      dfl_len,
      candidates);
  }

  std::sort(
    candidates.begin(),
    candidates.end(),
    [](const Detection & a, const Detection & b) { return a.score > b.score; });

  std::vector<Detection> kept_raw;
  kept_raw.reserve(std::min<int>(kMaxDetections, candidates.size()));
  for (const auto & candidate : candidates) {
    bool suppressed = false;
    for (const auto & existing : kept_raw) {
      if (candidate.class_id == existing.class_id &&
        intersection_over_union(candidate, existing) > static_cast<float>(iou_threshold_))
      {
        suppressed = true;
        break;
      }
    }
    if (!suppressed) {
      kept_raw.push_back(candidate);
      if (static_cast<int>(kept_raw.size()) >= kMaxDetections) {
        break;
      }
    }
  }

  std::vector<Detection> scaled;
  scaled.reserve(kept_raw.size());
  for (const auto & detection : kept_raw) {
    scaled.push_back(scale_detection(detection, image_width, image_height, info));
  }
  return scaled;
}

void Yolo11RknnDetector::process_branch(
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
  std::vector<Detection> & candidates) const
{
  // 每个网格点先用 score_sum 快速过滤，再寻找最高类别分数并计算 DFL box。
  const int grid_len = grid_h * grid_w;
  const float threshold = static_cast<float>(confidence_threshold_);
  std::vector<float> dfl_logits(static_cast<size_t>(dfl_len * 4));

  for (int row = 0; row < grid_h; ++row) {
    for (int col = 0; col < grid_w; ++col) {
      const int grid_offset = row * grid_w + col;
      if (!passes_score_sum(score_sum_output, score_sum_attr, grid_offset, threshold)) {
        continue;
      }

      int class_id = -1;
      float class_score = 0.0F;
      find_best_class(score_output, score_attr, grid_offset, grid_len, threshold, class_id, class_score);
      if (class_id < 0 || class_score < threshold) {
        continue;
      }

      for (int i = 0; i < dfl_len * 4; ++i) {
        const int offset = grid_offset + i * grid_len;
        dfl_logits[static_cast<size_t>(i)] = tensor_value(box_output, box_attr, offset);
      }
      const auto box = compute_dfl(dfl_logits, dfl_len);
      const float x1 = (-box[0] + static_cast<float>(col) + 0.5F) * static_cast<float>(stride);
      const float y1 = (-box[1] + static_cast<float>(row) + 0.5F) * static_cast<float>(stride);
      const float x2 = (box[2] + static_cast<float>(col) + 0.5F) * static_cast<float>(stride);
      const float y2 = (box[3] + static_cast<float>(row) + 0.5F) * static_cast<float>(stride);

      Detection det;
      det.class_id = class_id;
      det.label = class_id >= 0 && class_id < static_cast<int>(labels_.size()) ?
        labels_[static_cast<size_t>(class_id)] :
        "unknown";
      det.score = class_score;
      det.x = x1;
      det.y = y1;
      det.width = std::max(0.0F, x2 - x1);
      det.height = std::max(0.0F, y2 - y1);
      if (det.width > 1.0F && det.height > 1.0F) {
        candidates.push_back(std::move(det));
      }
    }
  }
}

bool Yolo11RknnDetector::passes_score_sum(
  const rknn_output * score_sum_output,
  const rknn_tensor_attr * score_sum_attr,
  int grid_offset,
  float threshold) const
{
  if (score_sum_output == nullptr || score_sum_attr == nullptr || score_sum_output->buf == nullptr) {
    return true;
  }
  return tensor_value(*score_sum_output, *score_sum_attr, grid_offset) >= threshold;
}

void Yolo11RknnDetector::find_best_class(
  const rknn_output & score_output,
  const rknn_tensor_attr & score_attr,
  int grid_offset,
  int grid_len,
  float threshold,
  int & class_id,
  float & class_score) const
{
  // 量化模型直接在量化域比较阈值和类别分数，减少反量化次数。
  class_id = -1;
  class_score = 0.0F;

  if (is_quantized_ && score_attr.type == RKNN_TENSOR_INT8) {
    const auto * values = static_cast<const int8_t *>(score_output.buf);
    const int8_t threshold_i8 = quant_i8(threshold, score_attr.zp, score_attr.scale);
    int8_t best = threshold_i8;
    for (int c = 0; c < class_count_; ++c) {
      const int8_t value = values[grid_offset + c * grid_len];
      if (value > best) {
        best = value;
        class_id = c;
      }
    }
    if (class_id >= 0) {
      class_score = dequant_i8(best, score_attr.zp, score_attr.scale);
    }
    return;
  }

  if (is_quantized_ && score_attr.type == RKNN_TENSOR_UINT8) {
    const auto * values = static_cast<const uint8_t *>(score_output.buf);
    const uint8_t threshold_u8 = quant_u8(threshold, score_attr.zp, score_attr.scale);
    uint8_t best = threshold_u8;
    for (int c = 0; c < class_count_; ++c) {
      const uint8_t value = values[grid_offset + c * grid_len];
      if (value > best) {
        best = value;
        class_id = c;
      }
    }
    if (class_id >= 0) {
      class_score = dequant_u8(best, score_attr.zp, score_attr.scale);
    }
    return;
  }

  const auto * values = static_cast<const float *>(score_output.buf);
  for (int c = 0; c < class_count_; ++c) {
    const float value = values[grid_offset + c * grid_len];
    if (value > threshold && value > class_score) {
      class_score = value;
      class_id = c;
    }
  }
}

float Yolo11RknnDetector::tensor_value(
  const rknn_output & output,
  const rknn_tensor_attr & attr,
  int offset) const
{
  if (is_quantized_ && attr.type == RKNN_TENSOR_INT8) {
    return dequant_i8(static_cast<const int8_t *>(output.buf)[offset], attr.zp, attr.scale);
  }
  if (is_quantized_ && attr.type == RKNN_TENSOR_UINT8) {
    return dequant_u8(static_cast<const uint8_t *>(output.buf)[offset], attr.zp, attr.scale);
  }
  return static_cast<const float *>(output.buf)[offset];
}

Detection Yolo11RknnDetector::scale_detection(
  const Detection & det,
  int image_width,
  int image_height,
  const LetterboxInfo & info) const
{
  // 把模型输入坐标去掉 padding 后缩放回摄像头原图坐标，并裁剪到图像范围内。
  Detection scaled = det;
  const float left = (det.x - info.pad_x) / info.ratio;
  const float top = (det.y - info.pad_y) / info.ratio;
  const float right = (det.x + det.width - info.pad_x) / info.ratio;
  const float bottom = (det.y + det.height - info.pad_y) / info.ratio;

  const float clamped_left = std::clamp(left, 0.0F, static_cast<float>(image_width - 1));
  const float clamped_top = std::clamp(top, 0.0F, static_cast<float>(image_height - 1));
  const float clamped_right = std::clamp(right, 0.0F, static_cast<float>(image_width - 1));
  const float clamped_bottom = std::clamp(bottom, 0.0F, static_cast<float>(image_height - 1));

  scaled.x = clamped_left;
  scaled.y = clamped_top;
  scaled.width = std::max(0.0F, clamped_right - clamped_left);
  scaled.height = std::max(0.0F, clamped_bottom - clamped_top);
  return scaled;
}

}  // namespace drone_yolo_web_cpp
