#include "dm_h3510_ros_cpp/dm_usb2canfd.hpp"

#include <chrono>
#include <cstring>
#include <stdexcept>
#include <thread>

namespace dm_h3510_ros_cpp
{

std::mutex DmUsb2Canfd::active_mutex_;
DmUsb2Canfd * DmUsb2Canfd::active_instance_ = nullptr;

DmUsb2Canfd::DmUsb2Canfd(
  CanConfig can_config,
  uint32_t master_id,
  FeedbackCallback feedback_callback)
: can_config_(can_config),
  master_id_(master_id),
  feedback_callback_(std::move(feedback_callback))
{
}

DmUsb2Canfd::~DmUsb2Canfd()
{
  close();
}

void DmUsb2Canfd::open()
{
  std::lock_guard<std::mutex> lock(mutex_);
  if (opened_) {
    return;
  }

  dmcan_context_create(&context_);
  if (context_ == nullptr) {
    throw std::runtime_error("dmcan_context_create 失败");
  }

  const int device_count = dmcan_find_devices(context_);
  if (device_count <= 0) {
    throw std::runtime_error("未找到 DM USB2CANFD 设备");
  }

  if (!dmcan_device_get(context_, &device_, 0) || device_ == nullptr) {
    throw std::runtime_error("dmcan_device_get(0) 失败");
  }

  if (!dmcan_device_open(device_)) {
    throw std::runtime_error("dmcan_device_open 失败");
  }

  if (!dmcan_device_enable_channel(device_, can_config_.channel)) {
    throw std::runtime_error("使能 CAN 通道失败");
  }

  dmcan_channel_can_info_t can_info {};
  can_info.channel = can_config_.channel;
  can_info.canfd = can_config_.canfd;
  can_info.can_baudrate = can_config_.nominal_baud;
  can_info.canfd_baudrate = can_config_.data_baud;
  can_info.can_sp = can_config_.nominal_sample_point;
  can_info.canfd_sp = can_config_.data_sample_point;

  if (!dmcan_device_set_channel_baudrate(device_, can_config_.channel, can_info)) {
    throw std::runtime_error("设置 CAN 波特率失败");
  }

  {
    std::lock_guard<std::mutex> active_lock(active_mutex_);
    active_instance_ = this;
  }
  dmcan_device_hook_recv_callback(device_, &DmUsb2Canfd::recv_callback);

  opened_ = true;
}

void DmUsb2Canfd::close()
{
  std::lock_guard<std::mutex> lock(mutex_);
  if (!opened_) {
    if (context_ != nullptr) {
      dmcan_context_destroy(context_);
      context_ = nullptr;
    }
    return;
  }

  {
    std::lock_guard<std::mutex> active_lock(active_mutex_);
    if (active_instance_ == this) {
      active_instance_ = nullptr;
    }
  }

  if (device_ != nullptr) {
    dmcan_device_close(device_);
    device_ = nullptr;
  }
  if (context_ != nullptr) {
    dmcan_context_destroy(context_);
    context_ = nullptr;
  }
  opened_ = false;
}

bool DmUsb2Canfd::send_can(uint32_t can_id, const uint8_t * payload, uint8_t length)
{
  std::lock_guard<std::mutex> lock(mutex_);
  if (!opened_ || device_ == nullptr) {
    return false;
  }

  std::array<uint8_t, 64> buffer {};
  if (payload != nullptr && length > 0) {
    std::memcpy(buffer.data(), payload, length);
  }

  return dmcan_device_send_can(
    device_,
    can_config_.channel,
    can_id,
    can_config_.canfd,
    false,
    false,
    can_config_.brs,
    length,
    buffer.data());
}

bool DmUsb2Canfd::switch_control_mode(uint32_t motor_can_id, uint32_t mode_code)
{
  std::array<uint8_t, 8> payload {
    static_cast<uint8_t>(motor_can_id & 0xFFU),
    static_cast<uint8_t>((motor_can_id >> 8U) & 0xFFU),
    0x55,
    10,
    static_cast<uint8_t>(mode_code & 0xFFU),
    static_cast<uint8_t>((mode_code >> 8U) & 0xFFU),
    static_cast<uint8_t>((mode_code >> 16U) & 0xFFU),
    static_cast<uint8_t>((mode_code >> 24U) & 0xFFU)};
  const bool ok = send_can(0x7FF, payload.data(), static_cast<uint8_t>(payload.size()));
  std::this_thread::sleep_for(std::chrono::milliseconds(20));
  return ok;
}

void DmUsb2Canfd::enable_mode(uint32_t control_can_id, int repeats)
{
  const std::array<uint8_t, 8> payload {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFC};
  for (int i = 0; i < repeats; ++i) {
    send_can(control_can_id, payload.data(), static_cast<uint8_t>(payload.size()));
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
}

void DmUsb2Canfd::disable(uint32_t control_can_id, int repeats)
{
  const std::array<uint8_t, 8> payload {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFD};
  for (int i = 0; i < repeats; ++i) {
    send_can(control_can_id, payload.data(), static_cast<uint8_t>(payload.size()));
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
}

bool DmUsb2Canfd::send_position_velocity(
  uint32_t position_velocity_can_id,
  float position_rad,
  float velocity_rad_s)
{
  std::array<uint8_t, 8> payload {};
  static_assert(sizeof(float) == 4, "position-speed 命令需要 4 字节 float");
  std::memcpy(payload.data(), &position_rad, sizeof(float));
  std::memcpy(payload.data() + sizeof(float), &velocity_rad_s, sizeof(float));
  return send_can(position_velocity_can_id, payload.data(), static_cast<uint8_t>(payload.size()));
}

bool DmUsb2Canfd::send_velocity(uint32_t velocity_can_id, float velocity_rad_s)
{
  std::array<uint8_t, 4> payload {};
  static_assert(sizeof(float) == 4, "速度命令需要 4 字节 float");
  std::memcpy(payload.data(), &velocity_rad_s, sizeof(float));
  return send_can(velocity_can_id, payload.data(), static_cast<uint8_t>(payload.size()));
}

void DmUsb2Canfd::recv_callback(dmcan_device_handle * handle, usb_rx_frame_t * frame)
{
  std::lock_guard<std::mutex> lock(active_mutex_);
  if (active_instance_ != nullptr) {
    active_instance_->handle_frame(handle, frame);
  }
}

void DmUsb2Canfd::handle_frame(dmcan_device_handle * handle, usb_rx_frame_t * frame)
{
  if (frame == nullptr || handle != device_) {
    return;
  }
  if (frame->head.can_id != master_id_ || frame->head.dlc < 8) {
    return;
  }
  if (feedback_callback_) {
    feedback_callback_(decode_feedback(*frame));
  }
}

Feedback DmUsb2Canfd::decode_feedback(const usb_rx_frame_t & frame)
{
  const auto * data = frame.payload;
  const uint16_t q_uint = static_cast<uint16_t>((data[1] << 8U) | data[2]);
  const uint16_t dq_uint = static_cast<uint16_t>((data[3] << 4U) | (data[4] >> 4U));
  const uint16_t tau_uint = static_cast<uint16_t>(((data[4] & 0x0FU) << 8U) | data[5]);

  Feedback feedback;
  feedback.position_rad = static_cast<double>(q_uint) / 65535.0 * 25.0 - 12.5;
  feedback.velocity_rad_s = static_cast<double>(dq_uint) / 4095.0 * 560.0 - 280.0;
  feedback.torque_nm = static_cast<double>(tau_uint) / 4095.0 * 2.0 - 1.0;
  return feedback;
}

}  // namespace dm_h3510_ros_cpp
