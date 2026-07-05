#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <mutex>

#include "dm_h3510_ros_cpp/dmcan.h"

namespace dm_h3510_ros_cpp
{

struct Feedback
{
  double position_rad = 0.0;
  double velocity_rad_s = 0.0;
  double torque_nm = 0.0;
};

struct CanConfig
{
  uint8_t channel = 0;
  bool canfd = false;
  bool brs = false;
  uint32_t nominal_baud = 1000000;
  uint32_t data_baud = 5000000;
  float nominal_sample_point = 0.875F;
  float data_sample_point = 0.75F;
};

class DmUsb2Canfd
{
public:
  using FeedbackCallback = std::function<void(const Feedback &)>;

  DmUsb2Canfd(CanConfig can_config, uint32_t master_id, FeedbackCallback feedback_callback);
  ~DmUsb2Canfd();

  DmUsb2Canfd(const DmUsb2Canfd &) = delete;
  DmUsb2Canfd & operator=(const DmUsb2Canfd &) = delete;

  void open();
  void close();
  bool send_can(uint32_t can_id, const uint8_t * payload, uint8_t length);
  bool switch_control_mode(uint32_t motor_can_id, uint32_t mode_code);
  void enable_mode(uint32_t control_can_id, int repeats = 5);
  void disable(uint32_t control_can_id, int repeats = 5);
  bool send_position_velocity(
    uint32_t position_velocity_can_id,
    float position_rad,
    float velocity_rad_s);
  bool send_velocity(uint32_t velocity_can_id, float velocity_rad_s);

private:
  static void recv_callback(dmcan_device_handle * handle, usb_rx_frame_t * frame);
  void handle_frame(dmcan_device_handle * handle, usb_rx_frame_t * frame);
  static Feedback decode_feedback(const usb_rx_frame_t & frame);

  CanConfig can_config_;
  uint32_t master_id_;
  FeedbackCallback feedback_callback_;
  dmcan_context * context_ = nullptr;
  dmcan_device_handle * device_ = nullptr;
  bool opened_ = false;
  std::mutex mutex_;

  static std::mutex active_mutex_;
  static DmUsb2Canfd * active_instance_;
};

}  // namespace dm_h3510_ros_cpp
