// 无人机 YOLO C++ ROS 节点实现。
// 节点把 /camera/image_mjpeg 的每帧压缩图像送入 RKNN 推理器，并同步输出：
// 1. HTTP /detections JSON，供浏览器 Canvas 使用；
// 2. ROS /yolo/detections，供其他 ROS2 节点使用。
#include "drone_yolo_web_cpp/yolo_overlay_node.hpp"

#include <algorithm>
#include <cctype>
#include <functional>
#include <iterator>
#include <stdexcept>
#include <sstream>
#include <utility>

namespace drone_yolo_web_cpp
{
namespace
{

std::string trim(std::string value)
{
  auto first = std::find_if_not(
    value.begin(),
    value.end(),
    [](unsigned char ch) { return std::isspace(ch) != 0; });
  auto last = std::find_if_not(
    value.rbegin(),
    value.rend(),
    [](unsigned char ch) { return std::isspace(ch) != 0; }).base();
  if (first >= last) {
    return {};
  }
  return std::string(first, last);
}

std::vector<std::string> parse_labels(const std::string & value)
{
  // drone 工作区默认单类别；如果后续模型扩展为多类别，按逗号分隔解析标签。
  std::vector<std::string> labels;
  std::stringstream stream(value);
  std::string item;
  while (std::getline(stream, item, ',')) {
    item = trim(item);
    if (!item.empty()) {
      labels.push_back(item);
    }
  }
  if (labels.empty()) {
    labels.push_back("drone");
  }
  return labels;
}

}  // namespace

DroneYoloOverlayNode::DroneYoloOverlayNode()
: Node("drone_yolo_web_cpp_node")
{
  input_topic_ = declare_parameter<std::string>("input_topic", "/camera/image_mjpeg");
  model_path_ = declare_parameter<std::string>(
    "model_path",
    "/home/lckfb/workspace/drone_yolo_web_cpp_ws/models/yolo11n.rknn");
  labels_ = parse_labels(declare_parameter<std::string>("labels", "drone"));
  port_ = declare_parameter<int>("port", 8092);
  camera_url_ = declare_parameter<std::string>("camera_url", "http://127.0.0.1:8081/stream.mjpg");
  confidence_threshold_ = declare_parameter<double>("confidence_threshold", 0.60);
  iou_threshold_ = declare_parameter<double>("iou_threshold", 0.45);
  fps_window_seconds_ = declare_parameter<double>("fps_window_seconds", 2.0);
  detections_topic_ = declare_parameter<std::string>("detections_topic", "/yolo/detections");

  detector_ = std::make_unique<Yolo11RknnDetector>(
    model_path_,
    labels_,
    confidence_threshold_,
    iou_threshold_);

  subscription_ = create_subscription<sensor_msgs::msg::CompressedImage>(
    input_topic_,
    rclcpp::SensorDataQoS(),
    std::bind(&DroneYoloOverlayNode::on_image, this, std::placeholders::_1));
  detections_publisher_ =
    create_publisher<vision_msgs::msg::Detection2DArray>(detections_topic_, 10);

  http_server_ = std::make_unique<HttpOverlayServer>(
    port_,
    camera_url_,
    [this]() { return snapshot(); });
  http_server_->start();

  RCLCPP_INFO(
    get_logger(),
    "RKNN model ready: input=%dx%dx%d outputs=%u classes=%d quant=%s",
    detector_->model_width(),
    detector_->model_height(),
    detector_->model_channels(),
    detector_->output_count(),
    detector_->class_count(),
    detector_->is_quantized() ? "true" : "false");
  RCLCPP_INFO(
    get_logger(),
    "Serving Drone YOLO C++ overlay at http://0.0.0.0:%d/ using %s; publishing detections on %s",
    port_,
    model_path_.c_str(),
    detections_topic_.c_str());
}

DroneYoloOverlayNode::~DroneYoloOverlayNode()
{
  if (http_server_) {
    http_server_->stop();
  }
}

void DroneYoloOverlayNode::on_image(const sensor_msgs::msg::CompressedImage::SharedPtr message)
{
  try {
    InferenceResult result = detector_->process_jpeg(message->data);
    update_snapshot_and_publish(*message, std::move(result));
  } catch (const std::exception & ex) {
    RCLCPP_ERROR_THROTTLE(
      get_logger(),
      *get_clock(),
      2000,
      "Drone YOLO C++ callback failed: %s",
      ex.what());
  }
}

void DroneYoloOverlayNode::update_snapshot_and_publish(
  const sensor_msgs::msg::CompressedImage & input,
  InferenceResult result)
{
  const auto now = std::chrono::steady_clock::now();
  {
    std::lock_guard<std::mutex> lock(snapshot_mutex_);

    // HTTP 服务线程读取的是这份快照；更新粒度以“完成一次推理”为准。
    latest_detections_ = result.detections;
    latest_image_width_ = result.image_width;
    latest_image_height_ = result.image_height;
    latest_timings_ = result.timings;
    latest_frame_time_ = now;
    frame_count_++;

    frame_times_.push_back(now);
    const double window = std::max(0.2, fps_window_seconds_);
    while (frame_times_.size() > 2 &&
      std::chrono::duration<double>(now - frame_times_.front()).count() > window)
    {
      frame_times_.erase(frame_times_.begin());
    }

  }

  publish_detections(input, result);
}

void DroneYoloOverlayNode::publish_detections(
  const sensor_msgs::msg::CompressedImage & input,
  const InferenceResult & result)
{
  // vision_msgs 使用检测框中心点和宽高；内部 Detection 使用左上角和宽高。
  vision_msgs::msg::Detection2DArray message;
  message.header = input.header;
  message.detections.reserve(result.detections.size());

  for (const auto & detection : result.detections) {
    vision_msgs::msg::Detection2D output;
    output.header = input.header;
    output.id = detection.label;
    output.bbox.center.position.x = detection.x + detection.width * 0.5;
    output.bbox.center.position.y = detection.y + detection.height * 0.5;
    output.bbox.center.theta = 0.0;
    output.bbox.size_x = detection.width;
    output.bbox.size_y = detection.height;

    vision_msgs::msg::ObjectHypothesisWithPose result_msg;
    result_msg.hypothesis.class_id = std::to_string(detection.class_id);
    result_msg.hypothesis.score = detection.score;
    output.results.push_back(std::move(result_msg));
    message.detections.push_back(std::move(output));
  }

  detections_publisher_->publish(message);
}

DetectionSnapshot DroneYoloOverlayNode::snapshot() const
{
  std::lock_guard<std::mutex> lock(snapshot_mutex_);
  DetectionSnapshot output;
  output.detections = latest_detections_;
  output.frame_count = frame_count_;
  output.image_width = latest_image_width_;
  output.image_height = latest_image_height_;
  output.result_fps = current_result_fps_locked();
  output.last_pipeline_ms = latest_timings_.total_ms;
  output.last_decode_ms = latest_timings_.decode_ms;
  output.last_inference_ms = latest_timings_.inference_ms;
  output.last_postprocess_ms = latest_timings_.postprocess_ms;
  output.age_seconds = frame_count_ > 0
    ? std::chrono::duration<double>(std::chrono::steady_clock::now() - latest_frame_time_).count()
    : -1.0;
  return output;
}

double DroneYoloOverlayNode::current_result_fps_locked() const
{
  // 统计口径是滑动窗口内完成推理的帧，不是摄像头采集 FPS 或 HTTP 轮询频率。
  const double window = std::max(0.2, fps_window_seconds_);
  const auto now = std::chrono::steady_clock::now();
  auto first = frame_times_.begin();
  while (first != frame_times_.end() &&
    std::chrono::duration<double>(now - *first).count() > window)
  {
    ++first;
  }

  const auto count = static_cast<size_t>(std::distance(first, frame_times_.end()));
  if (count < 2) {
    return 0.0;
  }

  const double elapsed =
    std::chrono::duration<double>(frame_times_.back() - *first).count();
  return elapsed > 0.0 ? static_cast<double>(count - 1) / elapsed : 0.0;
}

}  // namespace drone_yolo_web_cpp
