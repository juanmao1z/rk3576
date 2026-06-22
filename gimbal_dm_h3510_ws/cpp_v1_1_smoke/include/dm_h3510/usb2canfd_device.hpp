#pragma once

#include <array>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <optional>
#include <string>

#include "dm_h3510/protocol.hpp"
#include "dmcan.h"

namespace dm_h3510 {

/// 达妙 USB2CANFD 适配器封装。
///
/// 该类只负责打开设备、配置 CAN 参数、发送 CAN 帧、接收反馈帧。
/// 上层电机协议由 DmH3510Controller 负责，避免把 SDK 细节散落到业务逻辑中。
class Usb2CanfdDevice {
 public:
  Usb2CanfdDevice(CanConfig can_config, uint32_t master_id);
  ~Usb2CanfdDevice();

  Usb2CanfdDevice(const Usb2CanfdDevice&) = delete;
  Usb2CanfdDevice& operator=(const Usb2CanfdDevice&) = delete;

  bool open(int device_index = 0);
  void close();

  /// 发送一帧 CAN/CANFD 数据。
  bool send(uint32_t can_id, const uint8_t* payload, uint8_t len, const char* label);

  /// 返回当前进程内收到的收发统计。
  RuntimeStats stats() const;

  /// 返回最近一帧来自 master_id 的电机反馈。
  std::optional<Feedback> latest_feedback() const;

 private:
  /// 厂商 SDK 回调是 C 风格函数指针，这里用单例指针转发到对象实例。
  static Usb2CanfdDevice* active_;
  static void on_recv(dmcan_device_handle* handle, usb_rx_frame_t* frame);
  static void on_sent(dmcan_device_handle* handle, usb_rx_frame_t* frame);

  /// 接收回调：解析 master_id 反馈帧，并缓存最新反馈。
  void handle_recv(usb_rx_frame_t* frame);

  /// 发送回显回调：只打印前若干帧，避免长时间运行时刷屏。
  void handle_sent(usb_rx_frame_t* frame);
  void print_frame(const char* prefix, usb_rx_frame_t* frame) const;

  CanConfig can_config_;
  uint32_t master_id_ = 0x011;
  dmcan_context* context_ = nullptr;
  dmcan_device_handle* device_ = nullptr;
  std::atomic<int> rx_count_{0};
  std::atomic<int> master_rx_count_{0};
  std::atomic<int> tx_echo_count_{0};
  mutable std::mutex feedback_mutex_;
  std::optional<Feedback> latest_feedback_;
};

}  // namespace dm_h3510
