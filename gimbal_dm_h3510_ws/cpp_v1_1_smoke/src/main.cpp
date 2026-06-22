#include <chrono>
#include <cstdlib>
#include <iostream>
#include <string>

#include "dm_h3510/dm_h3510_controller.hpp"

namespace {

struct CliOptions {
  float velocity = 0.0f;
  int duration_ms = 2000;
  int period_ms = 20;
  int device_index = 0;
  dm_h3510::CanConfig can;
  dm_h3510::MotorConfig motor;
};

void print_usage(const char* exe) {
  std::cout
      << "Usage: " << exe << " [options]\n"
      << "  --velocity <rad/s>       Velocity command. Default: 0\n"
      << "  --duration-ms <ms>       Command duration. Default: 2000\n"
      << "  --period-ms <ms>         Velocity command period. Default: 20\n"
      << "  --can-id <id>            Motor CAN ID. Default: 1\n"
      << "  --master-id <id>         Feedback CAN ID. Default: 17 / 0x11\n"
      << "  --nominal-baud <baud>    Classic CAN baud. Default: 1000000\n"
      << "  --data-baud <baud>       CANFD data baud. Default: 5000000\n"
      << "  --classic-can            Use classic CAN. Default\n"
      << "  --canfd                  Use CANFD with BRS\n"
      << "  --switch-mode            Send 0x7FF velocity-mode switch frame first\n";
}

bool parse_args(int argc, char** argv, CliOptions* options) {
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--help" || arg == "-h") {
      print_usage(argv[0]);
      return false;
    }
    if (arg == "--velocity" && i + 1 < argc) {
      options->velocity = std::strtof(argv[++i], nullptr);
    } else if (arg == "--duration-ms" && i + 1 < argc) {
      options->duration_ms = std::atoi(argv[++i]);
    } else if (arg == "--period-ms" && i + 1 < argc) {
      options->period_ms = std::atoi(argv[++i]);
    } else if (arg == "--device-index" && i + 1 < argc) {
      options->device_index = std::atoi(argv[++i]);
    } else if (arg == "--can-id" && i + 1 < argc) {
      options->motor.can_id = static_cast<uint32_t>(std::strtoul(argv[++i], nullptr, 0));
    } else if (arg == "--master-id" && i + 1 < argc) {
      options->motor.master_id = static_cast<uint32_t>(std::strtoul(argv[++i], nullptr, 0));
    } else if (arg == "--nominal-baud" && i + 1 < argc) {
      options->can.nominal_baud = static_cast<uint32_t>(std::strtoul(argv[++i], nullptr, 0));
    } else if (arg == "--data-baud" && i + 1 < argc) {
      options->can.data_baud = static_cast<uint32_t>(std::strtoul(argv[++i], nullptr, 0));
    } else if (arg == "--classic-can") {
      options->can.canfd = false;
      options->can.brs = false;
    } else if (arg == "--canfd") {
      options->can.canfd = true;
      options->can.brs = true;
    } else if (arg == "--switch-mode") {
      options->motor.switch_mode_on_start = true;
    } else {
      std::cerr << "Unknown or incomplete argument: " << arg << std::endl;
      print_usage(argv[0]);
      return false;
    }
  }
  return true;
}

}  // namespace

int main(int argc, char** argv) {
  CliOptions options;
  if (!parse_args(argc, argv, &options)) {
    return 1;
  }

  dm_h3510::Usb2CanfdDevice device(options.can, options.motor.master_id);
  if (!device.open(options.device_index)) {
    return 2;
  }

  // 打印实际运行参数，便于和 DMTool 抓包或现场故障日志对照。
  std::cout << "DM-H3510 control: can_id=0x" << std::hex << options.motor.can_id
            << " master_id=0x" << options.motor.master_id
            << " velocity_can_id=0x" << dm_h3510::velocity_can_id(options.motor)
            << std::dec
            << " baud=" << options.can.nominal_baud << "/" << options.can.data_baud
            << " canfd=" << options.can.canfd
            << " brs=" << options.can.brs
            << " switch_mode=" << options.motor.switch_mode_on_start
            << " velocity_cmd=" << options.velocity
            << " duration_ms=" << options.duration_ms
            << " period_ms=" << options.period_ms << std::endl;

  dm_h3510::DmH3510Controller motor(device, options.motor);
  // 运行结束后会先发 0 速度再失能，避免测试结束时电机继续转动。
  const auto stats = motor.run_velocity(
      options.velocity,
      std::chrono::milliseconds(options.duration_ms),
      std::chrono::milliseconds(options.period_ms));

  if (const auto feedback = device.latest_feedback()) {
    std::cout << "latest_feedback pos=" << feedback->position_rad
              << " vel=" << feedback->velocity_rad_s
              << " tau=" << feedback->torque_nm << std::endl;
  }
  std::cout << "rx_count=" << stats.rx_count
            << " master_rx_count=" << stats.master_rx_count
            << " tx_echo_count=" << stats.tx_echo_count << std::endl;
  std::cout << "done; process exit will release SDK handles" << std::endl;
  return stats.master_rx_count > 0 ? 0 : 3;
}
