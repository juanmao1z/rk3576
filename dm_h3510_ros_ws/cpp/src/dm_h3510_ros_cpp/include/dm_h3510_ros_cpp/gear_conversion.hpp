#pragma once

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace dm_h3510_ros_cpp
{

struct GearConfig
{
  double ratio = 1.0;
  double direction = 1.0;
};

struct GearPositionVelocity
{
  double position_rad = 0.0;
  double velocity_rad_s = 0.0;
};

struct PositionVelocityControlConfig
{
  double kp = 2.0;
  double max_velocity_rad_s = 0.3;
  double tolerance_rad = 0.02;
};

class MotorPositionUnwrapper
{
public:
  double unwrap(double raw_position_rad)
  {
    if (!initialized_) {
      previous_raw_position_rad_ = raw_position_rad;
      unwrapped_position_rad_ = raw_position_rad;
      initialized_ = true;
      return unwrapped_position_rad_;
    }

    double delta = raw_position_rad - previous_raw_position_rad_;
    if (delta > kHalfFeedbackRangeRad) {
      delta -= kFeedbackRangeRad;
    } else if (delta < -kHalfFeedbackRangeRad) {
      delta += kFeedbackRangeRad;
    }

    previous_raw_position_rad_ = raw_position_rad;
    unwrapped_position_rad_ += delta;
    return unwrapped_position_rad_;
  }

  void reset()
  {
    initialized_ = false;
    previous_raw_position_rad_ = 0.0;
    unwrapped_position_rad_ = 0.0;
  }

private:
  static constexpr double kFeedbackRangeRad = 25.0;
  static constexpr double kHalfFeedbackRangeRad = kFeedbackRangeRad / 2.0;

  bool initialized_ = false;
  double previous_raw_position_rad_ = 0.0;
  double unwrapped_position_rad_ = 0.0;
};

inline double normalized_direction(const GearConfig & config)
{
  return config.direction < 0.0 ? -1.0 : 1.0;
}

inline void validate_gear_config(const GearConfig & config)
{
  if (config.ratio <= 0.0) {
    throw std::invalid_argument("gear ratio must be greater than 0");
  }
}

inline GearPositionVelocity to_motor_command(
  double output_position_rad,
  double output_velocity_rad_s,
  const GearConfig & config)
{
  validate_gear_config(config);
  return {
    output_position_rad * config.ratio * normalized_direction(config),
    std::abs(output_velocity_rad_s) * config.ratio,
  };
}

inline double to_motor_velocity_command(double output_velocity_rad_s, const GearConfig & config)
{
  validate_gear_config(config);
  return output_velocity_rad_s * config.ratio * normalized_direction(config);
}

inline double compute_output_velocity_command(
  double target_position_rad,
  double current_position_rad,
  const PositionVelocityControlConfig & config)
{
  const double error = target_position_rad - current_position_rad;
  if (std::abs(error) <= std::abs(config.tolerance_rad)) {
    return 0.0;
  }

  const double max_velocity = std::abs(config.max_velocity_rad_s);
  return std::clamp(error * config.kp, -max_velocity, max_velocity);
}

inline double compute_initial_output_velocity_command(
  double target_position_rad,
  const PositionVelocityControlConfig & config)
{
  if (std::abs(target_position_rad) <= std::abs(config.tolerance_rad)) {
    return 0.0;
  }

  const double max_velocity = std::abs(config.max_velocity_rad_s);
  return target_position_rad > 0.0 ? max_velocity : -max_velocity;
}

inline GearPositionVelocity to_output_feedback(
  double motor_position_rad,
  double motor_velocity_rad_s,
  const GearConfig & config)
{
  validate_gear_config(config);
  return {
    motor_position_rad / config.ratio * normalized_direction(config),
    motor_velocity_rad_s / config.ratio,
  };
}

}  // namespace dm_h3510_ros_cpp
