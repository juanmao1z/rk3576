#include <chrono>
#include <cstdint>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "std_msgs/msg/float32.hpp"

#include "dm_h3510_ros_cpp/dm_usb2canfd.hpp"

namespace dm_h3510_ros_cpp
{

constexpr uint32_t kPosVelModeCode = 2;

class DmH3510RosCppNode : public rclcpp::Node
{
public:
  DmH3510RosCppNode()
  : Node("dm_h3510_ros_cpp_node")
  {
    declare_parameters();
    load_parameters();

    position_velocity_can_id_ = can_id_ + position_velocity_id_offset_;
    target_velocity_ = default_velocity_rad_s_;

    state_pub_ = create_publisher<sensor_msgs::msg::JointState>(state_topic_, 10);
    position_sub_ = create_subscription<std_msgs::msg::Float32>(
      position_topic_,
      10,
      [this](const std_msgs::msg::Float32::SharedPtr msg) {
        on_position_command(*msg);
      });
    target_joint_sub_ = create_subscription<sensor_msgs::msg::JointState>(
      target_joint_topic_,
      10,
      [this](const sensor_msgs::msg::JointState::SharedPtr msg) {
        on_target_joint_command(*msg);
      });

    driver_ = std::make_unique<DmUsb2Canfd>(
      can_config_,
      master_id_,
      [this](const Feedback & feedback) {
        publish_feedback(feedback);
      });

    driver_->open();
    if (switch_mode_on_start_) {
      driver_->switch_control_mode(can_id_, kPosVelModeCode);
    }
    driver_->enable_mode(position_velocity_can_id_);

    send_timer_ = create_wall_timer(
      std::chrono::milliseconds(command_period_ms_),
      [this]() {
        send_current_target();
      });

    RCLCPP_INFO(
      get_logger(),
      "DM-H3510 C++ ROS 节点已启动为 position-speed cascade: can_id=0x%X master_id=0x%X control_id=0x%X position_topic=%s joint_topic=%s",
      can_id_,
      master_id_,
      position_velocity_can_id_,
      position_topic_.c_str(),
      target_joint_topic_.c_str());
  }

  ~DmH3510RosCppNode() override
  {
    try {
      if (driver_) {
        const float hold_position = has_feedback_ ? last_feedback_.position_rad : target_position_;
        driver_->send_position_velocity(position_velocity_can_id_, hold_position, 0.0F);
        driver_->disable(position_velocity_can_id_);
        driver_->close();
      }
    } catch (const std::exception & exc) {
      RCLCPP_WARN(get_logger(), "退出停机时发生异常: %s", exc.what());
    }
  }

private:
  void declare_parameters()
  {
    declare_parameter<std::string>("position_topic", "/gimbal/position_cmd");
    declare_parameter<std::string>("target_joint_topic", "/gimbal/target_joint_state");
    declare_parameter<std::string>("state_topic", "/gimbal/state");
    declare_parameter<std::string>("joint_name", "dm_h3510_joint");
    declare_parameter<double>("default_velocity_rad_s", 1.0);
    declare_parameter<int>("command_period_ms", 20);
    declare_parameter<bool>("switch_mode_on_start", true);
    declare_parameter<int>("can.channel", 0);
    declare_parameter<bool>("can.canfd", false);
    declare_parameter<bool>("can.brs", false);
    declare_parameter<int>("can.nominal_baud", 1000000);
    declare_parameter<int>("can.data_baud", 5000000);
    declare_parameter<int>("motor.can_id", 1);
    declare_parameter<int>("motor.master_id", 17);
    declare_parameter<int>("motor.position_velocity_id_offset", 256);
  }

  void load_parameters()
  {
    position_topic_ = get_parameter("position_topic").as_string();
    target_joint_topic_ = get_parameter("target_joint_topic").as_string();
    state_topic_ = get_parameter("state_topic").as_string();
    joint_name_ = get_parameter("joint_name").as_string();
    default_velocity_rad_s_ = static_cast<float>(get_parameter("default_velocity_rad_s").as_double());
    command_period_ms_ = get_parameter("command_period_ms").as_int();
    switch_mode_on_start_ = get_parameter("switch_mode_on_start").as_bool();

    can_config_.channel = static_cast<uint8_t>(get_parameter("can.channel").as_int());
    can_config_.canfd = get_parameter("can.canfd").as_bool();
    can_config_.brs = get_parameter("can.brs").as_bool();
    can_config_.nominal_baud = static_cast<uint32_t>(get_parameter("can.nominal_baud").as_int());
    can_config_.data_baud = static_cast<uint32_t>(get_parameter("can.data_baud").as_int());

    can_id_ = static_cast<uint32_t>(get_parameter("motor.can_id").as_int());
    master_id_ = static_cast<uint32_t>(get_parameter("motor.master_id").as_int());
    position_velocity_id_offset_ =
      static_cast<uint32_t>(get_parameter("motor.position_velocity_id_offset").as_int());
  }

  void on_position_command(const std_msgs::msg::Float32 & msg)
  {
    target_position_ = msg.data;
    target_velocity_ = default_velocity_rad_s_;
    has_target_ = true;
    send_current_target();
  }

  void on_target_joint_command(const sensor_msgs::msg::JointState & msg)
  {
    if (msg.position.empty()) {
      RCLCPP_WARN(get_logger(), "收到 target_joint_state 但 position 为空，已忽略");
      return;
    }
    target_position_ = static_cast<float>(msg.position[0]);
    target_velocity_ = msg.velocity.empty() ?
      default_velocity_rad_s_ : static_cast<float>(msg.velocity[0]);
    has_target_ = true;
    send_current_target();
  }

  void send_current_target()
  {
    if (!has_target_) {
      return;
    }
    driver_->send_position_velocity(
      position_velocity_can_id_,
      target_position_,
      target_velocity_);
  }

  void publish_feedback(const Feedback & feedback)
  {
    last_feedback_ = feedback;
    has_feedback_ = true;

    sensor_msgs::msg::JointState msg;
    msg.header.stamp = now();
    msg.name.push_back(joint_name_);
    msg.position.push_back(feedback.position_rad);
    msg.velocity.push_back(feedback.velocity_rad_s);
    msg.effort.push_back(feedback.torque_nm);
    state_pub_->publish(msg);
  }

  CanConfig can_config_;
  std::unique_ptr<DmUsb2Canfd> driver_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr state_pub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr position_sub_;
  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr target_joint_sub_;
  rclcpp::TimerBase::SharedPtr send_timer_;

  std::string position_topic_;
  std::string target_joint_topic_;
  std::string state_topic_;
  std::string joint_name_;
  float default_velocity_rad_s_ = 1.0F;
  int command_period_ms_ = 20;
  bool switch_mode_on_start_ = true;
  uint32_t can_id_ = 1;
  uint32_t master_id_ = 17;
  uint32_t position_velocity_id_offset_ = 256;
  uint32_t position_velocity_can_id_ = 0x101;
  float target_position_ = 0.0F;
  float target_velocity_ = 1.0F;
  bool has_target_ = false;
  Feedback last_feedback_;
  bool has_feedback_ = false;
};

}  // namespace dm_h3510_ros_cpp

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<dm_h3510_ros_cpp::DmH3510RosCppNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
