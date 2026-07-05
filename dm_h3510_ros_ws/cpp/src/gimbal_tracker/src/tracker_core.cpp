#include "gimbal_tracker/tracker_core.hpp"

#include <algorithm>
#include <cmath>

namespace gimbal_tracker
{

namespace
{

bool class_matches(const DetectionCandidate & detection, const std::string & target_class)
{
  return detection.class_id == target_class || detection.label == target_class;
}

double area(const DetectionCandidate & detection)
{
  return detection.size_x * detection.size_y;
}

double clamp(double value, double lower, double upper)
{
  return std::max(lower, std::min(value, upper));
}

}  // namespace

std::optional<DetectionCandidate> select_target(
  const std::vector<DetectionCandidate> & detections,
  const TrackerConfig & config)
{
  std::optional<DetectionCandidate> best;

  for (const auto & detection : detections) {
    // 只跟踪目标类别，避免把其他检测框送入云台控制。
    if (!class_matches(detection, config.target_class)) {
      continue;
    }
    // 低置信度目标容易引起抖动，先在视觉侧过滤掉。
    if (detection.score < config.min_confidence) {
      continue;
    }
    if (!best.has_value()) {
      best = detection;
      continue;
    }
    if (detection.score > best->score) {
      best = detection;
      continue;
    }
    // 置信度相同时选择面积更大的目标，通常更接近画面主体。
    if (detection.score == best->score && area(detection) > area(*best)) {
      best = detection;
    }
  }

  return best;
}

std::optional<TrackCommand> compute_track_command(
  const std::vector<DetectionCandidate> & detections,
  double current_yaw,
  const TrackerConfig & config)
{
  const auto target = select_target(detections, config);
  if (!target.has_value()) {
    return std::nullopt;
  }

  TrackCommand command;
  command.target = *target;
  command.error_x = target->center_x - (config.image_width / 2.0);
  // 死区内不修正，防止目标在中心附近时来回小幅摆动。
  command.in_deadband = std::abs(command.error_x) < config.deadband_px;
  if (command.in_deadband) {
    command.delta_yaw = 0.0;
  } else {
    // 单次步进限幅保护云台，不让单帧检测误差直接变成大角度跳变。
    command.delta_yaw = clamp(-config.kp_x * command.error_x, -config.max_step_rad, config.max_step_rad);
  }
  // 总角度限幅保护机械范围，当前配置为从零点向左右各转一圈。
  command.target_yaw = clamp(current_yaw + command.delta_yaw, config.min_yaw_rad, config.max_yaw_rad);
  command.velocity_rad_s = config.velocity_rad_s;
  return command;
}

}  // namespace gimbal_tracker
