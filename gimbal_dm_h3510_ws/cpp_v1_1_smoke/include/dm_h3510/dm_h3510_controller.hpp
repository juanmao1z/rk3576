#pragma once

#include <chrono>

#include "dm_h3510/protocol.hpp"
#include "dm_h3510/usb2canfd_device.hpp"

namespace dm_h3510 {

/// DM-H3510 速度模式控制器。
///
/// 该类只表达电机控制语义：切速度模式、使能、发送速度、停止、失能。
/// 底层 USB2CANFD/CAN 帧发送由 Usb2CanfdDevice 负责。
class DmH3510Controller {
 public:
  DmH3510Controller(Usb2CanfdDevice& device, MotorConfig motor_config);

  /// 发送 0x7FF 模式切换帧。当前 DMTool 已配置为速度模式时默认不需要。
  bool switch_to_velocity_mode();

  /// 发送速度模式使能帧：FF FF FF FF FF FF FF FC。
  bool enable_velocity_mode(int repeats = 5);

  /// 发送失能帧：FF FF FF FF FF FF FF FD。
  bool disable(int repeats = 5);

  /// 发送速度命令。payload 为小端 float，例如 5 rad/s = 00 00 A0 40。
  bool send_velocity(float velocity_rad_s);

  /// 发送 0 速度命令，但不失能。
  bool stop();

  /// 完整速度测试流程：可选切模式 -> 使能 -> 周期发送速度 -> 0 速度 -> 失能。
  RuntimeStats run_velocity(float velocity_rad_s,
                            std::chrono::milliseconds duration,
                            std::chrono::milliseconds period);

 private:
  bool send_control_cmd(uint8_t cmd, const char* label);

  Usb2CanfdDevice& device_;
  MotorConfig motor_config_;
};

}  // namespace dm_h3510
