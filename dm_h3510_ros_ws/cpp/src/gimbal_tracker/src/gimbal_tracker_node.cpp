#include "gimbal_tracker/tracker_core.hpp"

#include <chrono>
#include <memory>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "vision_msgs/msg/detection2_d_array.hpp"

namespace gimbal_tracker
{

class GimbalTrackerNode : public rclcpp::Node
{
public:
  GimbalTrackerNode()
  : Node("gimbal_tracker_node")
  {
    load_parameters();

    target_pub_ = create_publisher<sensor_msgs::msg::JointState>(target_joint_topic_, 10);
    detections_sub_ = create_subscription<vision_msgs::msg::Detection2DArray>(
      detections_topic_,
      10,
      [this](const vision_msgs::msg::Detection2DArray::SharedPtr msg) {
        on_detections(*msg);
      });
    state_sub_ = create_subscription<sensor_msgs::msg::JointState>(
      gimbal_state_topic_,
      10,
      [this](const sensor_msgs::msg::JointState::SharedPtr msg) {
        on_gimbal_state(*msg);
      });

    control_timer_ = create_wall_timer(
      std::chrono::milliseconds(control_period_ms_),
      [this]() {
        tick();
      });

    RCLCPP_INFO(
      get_logger(),
      "gimbal_tracker started: detections=%s state=%s target=%s dry_run=%s rate=%dHz",
      detections_topic_.c_str(),
      gimbal_state_topic_.c_str(),
      target_joint_topic_.c_str(),
      dry_run_ ? "true" : "false",
      control_rate_hz_);
  }

private:
  void load_parameters()
  {
    declare_parameter<std::string>("detections_topic", "/yolo/detections");
    declare_parameter<std::string>("gimbal_state_topic", "/gimbal/state");
    declare_parameter<std::string>("target_joint_topic", "/gimbal/target_joint_state");
    declare_parameter<std::string>("joint_name", "dm_h3510_joint");
    declare_parameter<std::string>("target_class", "drone");
    declare_parameter<double>("min_confidence", 0.60);
    declare_parameter<double>("image_width", 640.0);
    declare_parameter<double>("image_height", 480.0);
    declare_parameter<double>("deadband_px", 40.0);
    declare_parameter<double>("kp_x", -0.0008);
    declare_parameter<double>("max_step_rad", 0.03);
    declare_parameter<double>("min_yaw_rad", -6.2832);
    declare_parameter<double>("max_yaw_rad", 6.2832);
    declare_parameter<double>("velocity_rad_s", 0.3);
    declare_parameter<int>("control_rate_hz", 10);
    declare_parameter<double>("lost_timeout_s", 0.5);
    declare_parameter<bool>("dry_run", true);

    detections_topic_ = get_parameter("detections_topic").as_string();
    gimbal_state_topic_ = get_parameter("gimbal_state_topic").as_string();
    target_joint_topic_ = get_parameter("target_joint_topic").as_string();
    joint_name_ = get_parameter("joint_name").as_string();
    config_.target_class = get_parameter("target_class").as_string();
    config_.min_confidence = get_parameter("min_confidence").as_double();
    config_.image_width = get_parameter("image_width").as_double();
    config_.image_height = get_parameter("image_height").as_double();
    config_.deadband_px = get_parameter("deadband_px").as_double();
    config_.kp_x = get_parameter("kp_x").as_double();
    config_.max_step_rad = get_parameter("max_step_rad").as_double();
    config_.min_yaw_rad = get_parameter("min_yaw_rad").as_double();
    config_.max_yaw_rad = get_parameter("max_yaw_rad").as_double();
    config_.velocity_rad_s = get_parameter("velocity_rad_s").as_double();
    control_rate_hz_ = std::max(1, static_cast<int>(get_parameter("control_rate_hz").as_int()));
    control_period_ms_ = 1000 / control_rate_hz_;
    lost_timeout_s_ = get_parameter("lost_timeout_s").as_double();
    dry_run_ = get_parameter("dry_run").as_bool();
  }

  void on_detections(const vision_msgs::msg::Detection2DArray & msg)
  {
    last_detections_.clear();
    last_detection_time_ = now();

    for (const auto & detection_msg : msg.detections) {
      DetectionCandidate candidate;
      candidate.label = detection_msg.id;
      candidate.center_x = detection_msg.bbox.center.position.x;
      candidate.center_y = detection_msg.bbox.center.position.y;
      candidate.size_x = detection_msg.bbox.size_x;
      candidate.size_y = detection_msg.bbox.size_y;
      if (!detection_msg.results.empty()) {
        candidate.class_id = detection_msg.results.front().hypothesis.class_id;
        candidate.score = detection_msg.results.front().hypothesis.score;
      } else {
        candidate.class_id = detection_msg.id;
        candidate.score = 0.0;
      }
      last_detections_.push_back(candidate);
    }
  }

  void on_gimbal_state(const sensor_msgs::msg::JointState & msg)
  {
    if (msg.position.empty()) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000, "收到 /gimbal/state 但 position 为空");
      return;
    }
    current_yaw_ = msg.position.front();
    has_gimbal_state_ = true;
    last_state_time_ = now();
  }

  void tick()
  {
    // 没有云台反馈时不输出目标，避免在未知当前位置上叠加控制量。
    if (!has_gimbal_state_) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000, "等待 /gimbal/state 后再计算跟踪命令");
      return;
    }

    const auto now_time = now();
    // 检测或云台状态超时都保持静默，防止旧数据继续驱动云台。
    if ((now_time - last_detection_time_).seconds() > lost_timeout_s_) {
      RCLCPP_INFO_THROTTLE(get_logger(), *get_clock(), 2000, "未收到新检测，保持当前角度");
      return;
    }
    if ((now_time - last_state_time_).seconds() > lost_timeout_s_) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000, "/gimbal/state 超时，停止输出目标");
      return;
    }

    const auto command = compute_track_command(last_detections_, current_yaw_, config_);
    if (!command.has_value()) {
      RCLCPP_INFO_THROTTLE(get_logger(), *get_clock(), 1000, "未找到满足条件的目标，保持当前角度");
      return;
    }

    RCLCPP_INFO_THROTTLE(
      get_logger(),
      *get_clock(),
      300,
      "target=%s score=%.3f center=(%.1f, %.1f) error_x=%.1f delta=%.4f current=%.4f target=%.4f dry_run=%s",
      command->target.label.empty() ? command->target.class_id.c_str() : command->target.label.c_str(),
      command->target.score,
      command->target.center_x,
      command->target.center_y,
      command->error_x,
      command->delta_yaw,
      current_yaw_,
      command->target_yaw,
      dry_run_ ? "true" : "false");

    if (dry_run_) {
      return;
    }

    // 驱动层接收 JointState：position 是目标角度，velocity 是速度限制。
    sensor_msgs::msg::JointState target;
    target.header.stamp = now_time;
    target.name.push_back(joint_name_);
    target.position.push_back(command->target_yaw);
    target.velocity.push_back(command->velocity_rad_s);
    target_pub_->publish(target);
  }

  TrackerConfig config_;
  std::string detections_topic_;
  std::string gimbal_state_topic_;
  std::string target_joint_topic_;
  std::string joint_name_;
  bool dry_run_ = true;
  int control_rate_hz_ = 10;
  int control_period_ms_ = 100;
  double lost_timeout_s_ = 0.5;
  double current_yaw_ = 0.0;
  bool has_gimbal_state_ = false;
  rclcpp::Time last_detection_time_{0, 0, RCL_ROS_TIME};
  rclcpp::Time last_state_time_{0, 0, RCL_ROS_TIME};
  std::vector<DetectionCandidate> last_detections_;

  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr target_pub_;
  rclcpp::Subscription<vision_msgs::msg::Detection2DArray>::SharedPtr detections_sub_;
  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr state_sub_;
  rclcpp::TimerBase::SharedPtr control_timer_;
};

}  // namespace gimbal_tracker

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<gimbal_tracker::GimbalTrackerNode>());
  rclcpp::shutdown();
  return 0;
}
