#include "dm_h3510/dm_h3510_controller.hpp"

#include <cstring>
#include <thread>

namespace dm_h3510 {

DmH3510Controller::DmH3510Controller(Usb2CanfdDevice& device, MotorConfig motor_config)
    : device_(device), motor_config_(motor_config) {}

bool DmH3510Controller::switch_to_velocity_mode() {
  uint8_t payload[8] = {
      static_cast<uint8_t>(motor_config_.can_id & 0xFF),
      static_cast<uint8_t>((motor_config_.can_id >> 8) & 0xFF),
      0x55,
      10,
      3,
      0,
      0,
      0,
  };
  return device_.send(0x7FF, payload, 8, "switch vel mode");
}

bool DmH3510Controller::enable_velocity_mode(int repeats) {
  bool ok = true;
  for (int i = 0; i < repeats; ++i) {
    ok = send_control_cmd(0xFC, "enable") && ok;
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
  }
  return ok;
}

bool DmH3510Controller::disable(int repeats) {
  bool ok = true;
  for (int i = 0; i < repeats; ++i) {
    ok = send_control_cmd(0xFD, "disable") && ok;
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
  }
  return ok;
}

bool DmH3510Controller::send_velocity(float velocity_rad_s) {
  uint8_t payload[4] = {};
  std::memcpy(payload, &velocity_rad_s, sizeof(float));
  return device_.send(velocity_can_id(motor_config_), payload, 4, "velocity");
}

bool DmH3510Controller::stop() {
  return send_velocity(0.0f);
}

RuntimeStats DmH3510Controller::run_velocity(float velocity_rad_s,
                                             std::chrono::milliseconds duration,
                                             std::chrono::milliseconds period) {
  // DMTool 已经把电机设置为速度模式时，不需要每次启动都发 0x7FF 切模式帧。
  if (motor_config_.switch_mode_on_start) {
    switch_to_velocity_mode();
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }

  enable_velocity_mode();
  const auto start = std::chrono::steady_clock::now();
  while (std::chrono::steady_clock::now() - start < duration) {
    send_velocity(velocity_rad_s);
    std::this_thread::sleep_for(period);
  }

  stop();
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
  disable();
  return device_.stats();
}

bool DmH3510Controller::send_control_cmd(uint8_t cmd, const char* label) {
  uint8_t payload[8] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, cmd};
  return device_.send(velocity_can_id(motor_config_), payload, 8, label);
}

}  // namespace dm_h3510
