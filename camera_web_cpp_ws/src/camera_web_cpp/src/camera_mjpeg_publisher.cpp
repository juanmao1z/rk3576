// 基于 V4L2 MMAP 的 MJPEG 采集组件。
//
// 设计目标：
// 1. 直接从摄像头读取 MJPEG 压缩帧，避免在节点内再次做图像编码；
// 2. 发布 CompressedImage，并兼顾同进程组件和外部 ROS 订阅者；
// 3. 采集线程使用 poll 阻塞等帧，避免空转轮询带来的额外 CPU 占用。

#include "camera_web_cpp/camera_mjpeg_publisher.hpp"

#include <fcntl.h>
#include <poll.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <thread>
#include <utility>

#include "camera_web_cpp/runtime_shared_state.hpp"
#include "rclcpp_components/register_node_macro.hpp"

namespace
{

// 对 ioctl 做 EINTR 重试，避免系统调用被信号打断后直接失败。
int xioctl(int fd, unsigned long request, void * arg)
{
  int result;
  do {
    result = ioctl(fd, request, arg);
  } while (result == -1 && errno == EINTR);
  return result;
}

}  // namespace

namespace camera_web_cpp
{

CameraMjpegPublisher::CameraMjpegPublisher(const rclcpp::NodeOptions & options)
: Node("camera_mjpeg_publisher", options)
{
  // 这些参数既决定 V4L2 采集配置，也影响下游 Web 服务展示出来的默认模式。
  device_ = this->declare_parameter<std::string>("device", "/dev/video73");
  topic_ = this->declare_parameter<std::string>("topic", "/camera/image_mjpeg");
  frame_id_ = this->declare_parameter<std::string>("frame_id", "usb_camera");
  width_ = this->declare_parameter<int>("width", 640);
  height_ = this->declare_parameter<int>("height", 480);
  fps_ = this->declare_parameter<int>("fps", 25);

  publisher_ = this->create_publisher<sensor_msgs::msg::CompressedImage>(topic_, 10);
  try {
    open_camera();
  } catch (const std::exception & ex) {
    RCLCPP_WARN(
      get_logger(),
      "Initial camera open failed for %s: %s; capture thread will retry",
      device_.c_str(),
      ex.what());
  }
  capture_thread_ = std::thread(&CameraMjpegPublisher::capture_loop, this);

  RCLCPP_INFO(
    get_logger(),
    "Publishing MJPEG frames from %s to %s at %dx%d@%d using V4L2 MMAP",
    device_.c_str(),
    topic_.c_str(),
    width_,
    height_,
    fps_);
}

CameraMjpegPublisher::~CameraMjpegPublisher()
{
  running_.store(false);
  if (capture_thread_.joinable()) {
    capture_thread_.join();
  }
  close_camera();
}

void CameraMjpegPublisher::open_camera()
{
  close_camera();

  // 以非阻塞方式打开设备，后续配合 poll 等待新帧到来。
  fd_ = ::open(device_.c_str(), O_RDWR | O_NONBLOCK);
  if (fd_ < 0) {
    throw std::runtime_error(
      std::string("failed to open camera device: ") + device_ + ": " + std::strerror(errno));
  }

  v4l2_capability capability {};
  if (xioctl(fd_, VIDIOC_QUERYCAP, &capability) < 0) {
    throw std::runtime_error("VIDIOC_QUERYCAP failed");
  }
  if (!(capability.capabilities & V4L2_CAP_VIDEO_CAPTURE)) {
    throw std::runtime_error("device does not support video capture");
  }
  if (!(capability.capabilities & V4L2_CAP_STREAMING)) {
    throw std::runtime_error("device does not support streaming I/O");
  }

  v4l2_format format {};
  format.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  format.fmt.pix.width = static_cast<uint32_t>(width_);
  format.fmt.pix.height = static_cast<uint32_t>(height_);
  format.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
  format.fmt.pix.field = V4L2_FIELD_ANY;
  if (xioctl(fd_, VIDIOC_S_FMT, &format) < 0) {
    throw std::runtime_error("VIDIOC_S_FMT failed");
  }

  v4l2_streamparm streamparm {};
  streamparm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  streamparm.parm.capture.timeperframe.numerator = 1;
  streamparm.parm.capture.timeperframe.denominator = static_cast<uint32_t>(fps_);
  // 某些 UVC 设备可能不会完全接受请求值，因此这里只尽力设置，不强行失败。
  xioctl(fd_, VIDIOC_S_PARM, &streamparm);

  width_ = static_cast<int>(format.fmt.pix.width);
  height_ = static_cast<int>(format.fmt.pix.height);

  // 申请多缓冲区，减少采集与用户态处理之间的阻塞。
  v4l2_requestbuffers request {};
  request.count = 4;
  request.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  request.memory = V4L2_MEMORY_MMAP;
  if (xioctl(fd_, VIDIOC_REQBUFS, &request) < 0 || request.count < 2) {
    throw std::runtime_error("VIDIOC_REQBUFS failed");
  }

  // 将内核缓冲区映射到用户态，然后统一入队并启动流。
  buffers_.resize(request.count);
  for (uint32_t i = 0; i < request.count; ++i) {
    v4l2_buffer buffer {};
    buffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buffer.memory = V4L2_MEMORY_MMAP;
    buffer.index = i;
    if (xioctl(fd_, VIDIOC_QUERYBUF, &buffer) < 0) {
      throw std::runtime_error("VIDIOC_QUERYBUF failed");
    }
    buffers_[i].length = buffer.length;
    buffers_[i].start = mmap(
      nullptr,
      buffer.length,
      PROT_READ | PROT_WRITE,
      MAP_SHARED,
      fd_,
      static_cast<off_t>(buffer.m.offset));
    if (buffers_[i].start == MAP_FAILED) {
      buffers_[i].start = nullptr;
      throw std::runtime_error("mmap failed");
    }
    if (xioctl(fd_, VIDIOC_QBUF, &buffer) < 0) {
      throw std::runtime_error("VIDIOC_QBUF failed");
    }
  }

  v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  if (xioctl(fd_, VIDIOC_STREAMON, &type) < 0) {
    throw std::runtime_error("VIDIOC_STREAMON failed");
  }
  streaming_ = true;
}

void CameraMjpegPublisher::close_camera()
{
  // 采集线程和错误恢复都可能调用这里，因此实现必须可重复进入。
  if (fd_ >= 0 && streaming_) {
    v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    xioctl(fd_, VIDIOC_STREAMOFF, &type);
  }
  streaming_ = false;

  for (auto & buffer : buffers_) {
    if (buffer.start != nullptr) {
      munmap(buffer.start, buffer.length);
      buffer.start = nullptr;
      buffer.length = 0;
    }
  }
  buffers_.clear();

  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
}

void CameraMjpegPublisher::capture_loop()
{
  // 记录真实采集线程 TID，供同进程 Web 组件单独统计该线程 CPU。
  RuntimeSharedState::instance().capture_tid.store(
    static_cast<pid_t>(::syscall(SYS_gettid)),
    std::memory_order_relaxed);

  while (running_.load()) {
    if (fd_ < 0) {
      try {
        open_camera();
      } catch (const std::exception & ex) {
        RCLCPP_WARN(get_logger(), "Reopen camera failed: %s", ex.what());
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        continue;
      }
    }

    pollfd descriptor {};
    descriptor.fd = fd_;
    descriptor.events = POLLIN;
    const int poll_result = ::poll(&descriptor, 1, 500);
    if (poll_result == 0) {
      continue;
    }
    if (poll_result < 0) {
      if (errno == EINTR) {
        // 被信号打断时直接继续等待，不视为真正错误。
        continue;
      }
      RCLCPP_WARN(get_logger(), "poll failed, reopening device");
      close_camera();
      continue;
    }
    if (descriptor.revents & (POLLERR | POLLHUP | POLLNVAL)) {
      RCLCPP_WARN(get_logger(), "poll reported device error, reopening device");
      close_camera();
      continue;
    }

    v4l2_buffer buffer {};
    buffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buffer.memory = V4L2_MEMORY_MMAP;
    if (xioctl(fd_, VIDIOC_DQBUF, &buffer) < 0) {
      if (errno == EAGAIN) {
        continue;
      }
      RCLCPP_WARN(get_logger(), "VIDIOC_DQBUF failed, reopening device");
      close_camera();
      continue;
    }

    sensor_msgs::msg::CompressedImage message;
    message.header.stamp = now();
    message.header.frame_id = frame_id_;
    message.format = "jpeg";
    auto * begin = static_cast<const uint8_t *>(buffers_[buffer.index].start);
    // 当前仍需把 MMAP 缓冲区内容拷贝进 ROS 消息内存中。
    // 这里优先保证外部 ROS2 订阅者也能稳定收到数据。
    message.data.assign(begin, begin + buffer.bytesused);
    publisher_->publish(message);

    if (xioctl(fd_, VIDIOC_QBUF, &buffer) < 0) {
      RCLCPP_WARN(get_logger(), "VIDIOC_QBUF failed, reopening device");
      close_camera();
    }
  }
}

}  // namespace camera_web_cpp

RCLCPP_COMPONENTS_REGISTER_NODE(camera_web_cpp::CameraMjpegPublisher)
