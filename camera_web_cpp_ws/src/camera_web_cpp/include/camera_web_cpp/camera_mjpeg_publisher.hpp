#pragma once

#include <atomic>
#include <string>
#include <thread>
#include <vector>

#include <linux/videodev2.h>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/compressed_image.hpp"

namespace camera_web_cpp
{

/**
 * @brief V4L2 MMAP 缓冲区在用户态的映射描述。
 *
 * 每个缓冲区都对应一块由驱动分配、再通过 mmap 映射到用户空间的内存区域。
 * 采集线程通过 `VIDIOC_DQBUF` 取出缓冲区，再直接从这块内存中读取一帧 MJPEG
 * 压缩数据，随后重新 `VIDIOC_QBUF` 归还给驱动继续使用。
 */
struct Buffer
{
  /// 用户态可访问的缓冲区起始地址。
  void * start {nullptr};
  /// 缓冲区长度，单位字节。
  size_t length {0};
};

/**
 * @brief 摄像头 MJPEG 采集与 ROS2 压缩消息发布组件。
 *
 * 该组件负责：
 * 1. 使用 V4L2 MMAP 模式从 `/dev/video73` 等设备直接获取 MJPEG 压缩帧；
 * 2. 将压缩帧打包为 `sensor_msgs/msg/CompressedImage`；
 * 3. 在同进程容器中发布给 Web 转发组件，配合 intra-process 减少数据搬运。
 *
 * 性能重点：
 * - 不在采集节点内做图像解码；
 * - 不在采集节点内做 JPEG 重编码；
 * - 用阻塞式采集线程替代高频空转轮询。
 */
class CameraMjpegPublisher : public rclcpp::Node
{
public:
  /**
   * @brief 创建摄像头采集组件。
   * @param options 由 component container 传入的节点选项。
   */
  explicit CameraMjpegPublisher(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

  /**
   * @brief 析构时停止采集线程并释放底层设备资源。
   */
  ~CameraMjpegPublisher() override;

private:
  /**
   * @brief 打开并配置摄像头设备。
   *
   * 主要步骤：
   * 1. 打开设备文件；
   * 2. 检查 V4L2 能力；
   * 3. 设置 MJPEG 分辨率与帧率；
   * 4. 申请并映射 MMAP 缓冲区；
   * 5. 启动采集流。
   */
  void open_camera();

  /**
   * @brief 关闭摄像头并释放所有 MMAP 缓冲区。
   */
  void close_camera();

  /**
   * @brief 采集线程主循环。
   *
   * 线程内部通过 poll 阻塞等待新帧到来，然后使用 `VIDIOC_DQBUF`
   * 取出一帧 MJPEG 数据，发布后再立即 `VIDIOC_QBUF` 归还缓冲区。
   */
  void capture_loop();

  /// V4L2 设备路径，例如 `/dev/video73`。
  std::string device_;
  /// ROS2 发布话题名，默认 `/camera/image_mjpeg`。
  std::string topic_;
  /// 输出消息的 frame_id。
  std::string frame_id_;
  /// 目标采集宽度。
  int width_ {640};
  /// 目标采集高度。
  int height_ {480};
  /// 目标采集帧率。
  int fps_ {25};
  /// 摄像头文件描述符。
  int fd_ {-1};
  /// 当前是否已经调用 `VIDIOC_STREAMON`。
  bool streaming_ {false};
  /// 控制采集线程退出的标志位。
  std::atomic<bool> running_ {true};
  /// 负责阻塞等帧并发布消息的采集线程。
  std::thread capture_thread_;
  /// 所有 MMAP 缓冲区的用户态映射信息。
  std::vector<Buffer> buffers_;
  /// 发布 MJPEG 压缩帧的 ROS2 发布器。
  rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr publisher_;
};

}  // namespace camera_web_cpp
