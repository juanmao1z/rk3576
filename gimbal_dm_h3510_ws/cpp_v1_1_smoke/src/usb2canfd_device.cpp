#include "dm_h3510/usb2canfd_device.hpp"

#include <cstdio>
#include <iostream>

namespace dm_h3510 {
namespace {

// 达妙反馈帧使用无符号整数压缩，需要按协议映射回物理量。
float uint_to_float(uint16_t value, float min_value, float max_value, int bits) {
  return static_cast<float>(value) / static_cast<float>((1 << bits) - 1) *
             (max_value - min_value) +
         min_value;
}

}  // namespace

Usb2CanfdDevice* Usb2CanfdDevice::active_ = nullptr;

Usb2CanfdDevice::Usb2CanfdDevice(CanConfig can_config, uint32_t master_id)
    : can_config_(can_config), master_id_(master_id) {}

Usb2CanfdDevice::~Usb2CanfdDevice() {
  if (active_ == this) {
    active_ = nullptr;
  }
}

bool Usb2CanfdDevice::open(int device_index) {
  if (active_ && active_ != this) {
    std::cerr << "Only one Usb2CanfdDevice instance can own SDK callbacks." << std::endl;
    return false;
  }

  dmcan_context_create(&context_);
  if (!context_) {
    std::cerr << "dmcan_context_create failed" << std::endl;
    return false;
  }

  const int dev_cnt = dmcan_find_devices(context_);
  std::cout << "device found cnt: " << dev_cnt << std::endl;
  if (dev_cnt <= 0) {
    std::cerr << "No DM USB2CANFD device found by DM_DeviceSDK." << std::endl;
    return false;
  }

  if (!dmcan_device_get(context_, &device_, device_index) || !device_) {
    std::cerr << "dmcan_device_get(" << device_index << ") failed" << std::endl;
    return false;
  }

  if (!dmcan_device_open(device_)) {
    std::cerr << "dmcan_device_open failed" << std::endl;
    return false;
  }

  dmcan_device_enable_channel(device_, can_config_.channel);

  dmcan_channel_can_info_t can_info = {};
  can_info.channel = can_config_.channel;
  can_info.canfd = can_config_.canfd;
  can_info.can_baudrate = can_config_.nominal_baud;
  can_info.canfd_baudrate = can_config_.data_baud;
  can_info.can_sp = 0.875f;
  can_info.canfd_sp = 0.75f;
  if (!dmcan_device_set_channel_baudrate(device_, can_config_.channel, can_info)) {
    std::cerr << "dmcan_device_set_channel_baudrate failed" << std::endl;
    return false;
  }

  active_ = this;
  dmcan_device_hook_recv_callback(device_, on_recv);
  dmcan_device_hook_sent_callback(device_, on_sent);
  return true;
}

void Usb2CanfdDevice::close() {
  if (device_) {
    // 注意：部分 Windows 环境中显式关闭厂商 SDK 可能阻塞。
    // 当前 CLI 默认依赖进程退出释放句柄，close() 保留给后续长期服务场景调试。
    dmcan_device_hook_recv_callback(device_, nullptr);
    dmcan_device_hook_sent_callback(device_, nullptr);
    dmcan_device_disable_channel(device_, can_config_.channel);
    dmcan_device_close(device_);
    device_ = nullptr;
  }
  if (context_) {
    dmcan_context_destroy(context_);
    context_ = nullptr;
  }
  if (active_ == this) {
    active_ = nullptr;
  }
}

bool Usb2CanfdDevice::send(uint32_t can_id, const uint8_t* payload, uint8_t len, const char* label) {
  if (!device_) {
    std::cerr << "send failed: device is not open" << std::endl;
    return false;
  }
  const bool ok = dmcan_device_send_can(
      device_,
      can_config_.channel,
      can_id,
      can_config_.canfd,
      false,
      false,
      can_config_.brs,
      len,
      const_cast<uint8_t*>(payload));
  std::cout << label << " id=0x" << std::hex << can_id << std::dec
            << " len=" << static_cast<int>(len) << " ok=" << ok << std::endl;
  return ok;
}

RuntimeStats Usb2CanfdDevice::stats() const {
  return RuntimeStats{
      rx_count_.load(),
      master_rx_count_.load(),
      tx_echo_count_.load(),
  };
}

std::optional<Feedback> Usb2CanfdDevice::latest_feedback() const {
  std::lock_guard<std::mutex> lock(feedback_mutex_);
  return latest_feedback_;
}

void Usb2CanfdDevice::on_recv(dmcan_device_handle*, usb_rx_frame_t* frame) {
  if (active_) {
    active_->handle_recv(frame);
  }
}

void Usb2CanfdDevice::on_sent(dmcan_device_handle*, usb_rx_frame_t* frame) {
  if (active_) {
    active_->handle_sent(frame);
  }
}

void Usb2CanfdDevice::handle_recv(usb_rx_frame_t* frame) {
  if (!frame) {
    return;
  }
  const int count = ++rx_count_;
  if (frame->head.can_id == master_id_) {
    ++master_rx_count_;
    const auto* d = frame->payload;
    const uint16_t q_uint = (static_cast<uint16_t>(d[1]) << 8) | d[2];
    const uint16_t dq_uint = (static_cast<uint16_t>(d[3]) << 4) | (d[4] >> 4);
    const uint16_t tau_uint = (static_cast<uint16_t>(d[4] & 0x0F) << 8) | d[5];
    Feedback feedback{
        uint_to_float(q_uint, -12.5f, 12.5f, 16),
        uint_to_float(dq_uint, -280.0f, 280.0f, 12),
        uint_to_float(tau_uint, -1.0f, 1.0f, 12),
    };
    {
      std::lock_guard<std::mutex> lock(feedback_mutex_);
      latest_feedback_ = feedback;
    }
    std::printf("feedback pos=% .6f vel=% .6f tau=% .6f\n",
                feedback.position_rad,
                feedback.velocity_rad_s,
                feedback.torque_nm);
    return;
  }
  if (count <= 20) {
    print_frame("rx other", frame);
  }
}

void Usb2CanfdDevice::handle_sent(usb_rx_frame_t* frame) {
  if (!frame) {
    return;
  }
  if (++tx_echo_count_ <= 12) {
    print_frame("tx", frame);
  }
}

void Usb2CanfdDevice::print_frame(const char* prefix, usb_rx_frame_t* frame) const {
  const int dlen = dmcan_utils_get_dlc_from_len(frame->head.dlc);
  std::printf("%s ch:%u id=0x%X fd:%u brs:%u dlc:%u len:%d data=",
              prefix,
              frame->head.channel,
              frame->head.can_id,
              frame->head.canfd,
              frame->head.brs,
              frame->head.dlc,
              dlen);
  for (int i = 0; i < dlen && i < 64; ++i) {
    std::printf("%02X ", frame->payload[i]);
  }
  std::printf("\n");
}

}  // namespace dm_h3510
