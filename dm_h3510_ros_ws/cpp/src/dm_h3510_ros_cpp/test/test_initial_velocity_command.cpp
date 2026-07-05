#include "dm_h3510_ros_cpp/gear_conversion.hpp"

#include <gtest/gtest.h>

namespace dm_h3510_ros_cpp
{
namespace
{

TEST(InitialVelocityCommand, SendsPositiveLimitedSpeedBeforeFeedback)
{
  PositionVelocityControlConfig config;
  config.kp = 2.0;
  config.max_velocity_rad_s = 0.3;
  config.tolerance_rad = 0.02;

  EXPECT_DOUBLE_EQ(compute_initial_output_velocity_command(1.0, config), 0.3);
}

TEST(InitialVelocityCommand, SendsNegativeLimitedSpeedBeforeFeedback)
{
  PositionVelocityControlConfig config;
  config.kp = 2.0;
  config.max_velocity_rad_s = 0.3;
  config.tolerance_rad = 0.02;

  EXPECT_DOUBLE_EQ(compute_initial_output_velocity_command(-1.0, config), -0.3);
}

TEST(InitialVelocityCommand, HoldsWhenTargetIsInsideTolerance)
{
  PositionVelocityControlConfig config;
  config.kp = 2.0;
  config.max_velocity_rad_s = 0.3;
  config.tolerance_rad = 0.02;

  EXPECT_DOUBLE_EQ(compute_initial_output_velocity_command(0.01, config), 0.0);
}

}  // namespace
}  // namespace dm_h3510_ros_cpp
