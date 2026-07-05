#pragma once

#include <optional>
#include <string>
#include <vector>

namespace gimbal_tracker
{

struct TrackerConfig
{
  std::string target_class = "drone";
  double min_confidence = 0.60;
  double image_width = 640.0;
  double image_height = 480.0;
  double deadband_px = 40.0;
  double kp_x = -0.0008;
  double max_step_rad = 0.03;
  double min_yaw_rad = -6.2832;
  double max_yaw_rad = 6.2832;
  double velocity_rad_s = 0.3;
};

struct DetectionCandidate
{
  std::string class_id;
  std::string label;
  double score = 0.0;
  double center_x = 0.0;
  double center_y = 0.0;
  double size_x = 0.0;
  double size_y = 0.0;
};

struct TrackCommand
{
  DetectionCandidate target;
  double error_x = 0.0;
  double delta_yaw = 0.0;
  double target_yaw = 0.0;
  double velocity_rad_s = 0.0;
  bool in_deadband = false;
};

std::optional<DetectionCandidate> select_target(
  const std::vector<DetectionCandidate> & detections,
  const TrackerConfig & config);

std::optional<TrackCommand> compute_track_command(
  const std::vector<DetectionCandidate> & detections,
  double current_yaw,
  const TrackerConfig & config);

}  // namespace gimbal_tracker
