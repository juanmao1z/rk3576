#pragma once

#include <cstdint>

namespace dm_h3510 {

/// CAN 通信参数。当前默认值复现 DMTool 抓包：经典 CAN、1 Mbps。
struct CanConfig {
  uint8_t channel = 0;
  bool canfd = false;
  bool brs = false;
  uint32_t nominal_baud = 1000000;
  uint32_t data_baud = 5000000;
};

/// DM-H3510 电机参数。速度模式命令 ID = can_id + velocity_id_offset。
struct MotorConfig {
  uint32_t can_id = 0x001;
  uint32_t master_id = 0x011;
  uint32_t velocity_id_offset = 0x200;
  bool switch_mode_on_start = false;
};

/// 电机反馈量，单位与达妙协议解码结果保持一致。
struct Feedback {
  float position_rad = 0.0f;
  float velocity_rad_s = 0.0f;
  float torque_nm = 0.0f;
};

/// 运行统计，用于判断通信是否真正闭环。
struct RuntimeStats {
  int rx_count = 0;
  int master_rx_count = 0;
  int tx_echo_count = 0;
};

/// 计算速度模式下的控制帧 ID。DM-H3510 当前为 0x001 + 0x200 = 0x201。
inline uint32_t velocity_can_id(const MotorConfig& config) {
  return config.can_id + config.velocity_id_offset;
}

}  // namespace dm_h3510
