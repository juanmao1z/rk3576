// RTSP 摄像头输入组件。
//
// 设计目标：
// 1. 接收网络摄像头 H.264/RTSP 输入；
// 2. 对外继续发布 sensor_msgs/msg/CompressedImage；
// 3. 让现有 YOLO 和浏览器转发链路无需感知输入源变化。

#include "camera_web_cpp/rtsp_mjpeg_publisher.hpp"

#include <sys/syscall.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <stdexcept>
#include <thread>
#include <vector>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include "camera_web_cpp/runtime_shared_state.hpp"
#include "rclcpp_components/register_node_macro.hpp"

namespace camera_web_cpp
{

struct RtspMjpegPublisher::CaptureHandle
{
  cv::VideoCapture cap;
};

RtspMjpegPublisher::RtspMjpegPublisher(const rclcpp::NodeOptions & options)
: Node("rtsp_mjpeg_publisher", options)
{
  rtsp_url_ = this->declare_parameter<std::string>("rtsp_url", "");
  topic_ = this->declare_parameter<std::string>("topic", "/camera/image_mjpeg");
  frame_id_ = this->declare_parameter<std::string>("frame_id", "rtsp_camera");
  width_ = this->declare_parameter<int>("width", 1280);
  height_ = this->declare_parameter<int>("height", 960);
  fps_ = this->declare_parameter<int>("fps", 25);
  jpeg_quality_ = this->declare_parameter<int>("jpeg_quality", 85);
  reconnect_delay_ms_ = this->declare_parameter<int>("reconnect_delay_ms", 1000);

  if (rtsp_url_.empty()) {
    throw std::runtime_error("rtsp_url parameter is required");
  }

  jpeg_quality_ = std::max(1, std::min(100, jpeg_quality_));
  publisher_ = this->create_publisher<sensor_msgs::msg::CompressedImage>(topic_, 10);
  capture_ = new CaptureHandle();
  capture_thread_ = std::thread(&RtspMjpegPublisher::capture_loop, this);

  RCLCPP_INFO(
    get_logger(),
    "Publishing RTSP frames from %s to %s at %dx%d@%d",
    rtsp_url_.c_str(),
    topic_.c_str(),
    width_,
    height_,
    fps_);
}

RtspMjpegPublisher::~RtspMjpegPublisher()
{
  running_.store(false);
  if (capture_thread_.joinable()) {
    capture_thread_.join();
  }
  close_capture();
  delete capture_;
  capture_ = nullptr;
}

bool RtspMjpegPublisher::open_capture()
{
  close_capture();
  if (!capture_->cap.open(rtsp_url_, cv::CAP_FFMPEG)) {
    RCLCPP_WARN(get_logger(), "Failed to open RTSP stream");
    return false;
  }
  capture_->cap.set(cv::CAP_PROP_BUFFERSIZE, 1);
  if (fps_ > 0) {
    capture_->cap.set(cv::CAP_PROP_FPS, static_cast<double>(fps_));
  }
  return true;
}

void RtspMjpegPublisher::close_capture()
{
  if (capture_ != nullptr && capture_->cap.isOpened()) {
    capture_->cap.release();
  }
}

void RtspMjpegPublisher::capture_loop()
{
  RuntimeSharedState::instance().capture_tid.store(
    static_cast<pid_t>(::syscall(SYS_gettid)),
    std::memory_order_relaxed);

  while (running_.load()) {
    if (capture_ == nullptr || !capture_->cap.isOpened()) {
      if (!open_capture()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(reconnect_delay_ms_));
        continue;
      }
    }

    if (!read_and_publish_frame()) {
      RCLCPP_WARN(get_logger(), "RTSP frame read failed, reconnecting");
      close_capture();
      std::this_thread::sleep_for(std::chrono::milliseconds(reconnect_delay_ms_));
    }
  }
}

bool RtspMjpegPublisher::read_and_publish_frame()
{
  cv::Mat frame;
  if (!capture_->cap.read(frame) || frame.empty()) {
    return false;
  }

  if (width_ > 0 && height_ > 0 && (frame.cols != width_ || frame.rows != height_)) {
    cv::resize(frame, frame, cv::Size(width_, height_));
  }

  std::vector<unsigned char> encoded;
  const std::vector<int> encode_params = {
    cv::IMWRITE_JPEG_QUALITY,
    jpeg_quality_,
  };
  if (!cv::imencode(".jpg", frame, encoded, encode_params)) {
    RCLCPP_WARN(get_logger(), "JPEG encoding failed");
    return true;
  }

  sensor_msgs::msg::CompressedImage message;
  message.header.stamp = now();
  message.header.frame_id = frame_id_;
  message.format = "jpeg";
  message.data = std::move(encoded);
  publisher_->publish(message);
  return true;
}

}  // namespace camera_web_cpp

RCLCPP_COMPONENTS_REGISTER_NODE(camera_web_cpp::RtspMjpegPublisher)
