#include "dm_h3510_ros_cpp/gear_conversion.hpp"

#include <gtest/gtest.h>

TEST(GearConversion, ConvertsOutputCommandToMotorCommand)
{
  const dm_h3510_ros_cpp::GearConfig config{35.0, 1.0};

  const auto motor = dm_h3510_ros_cpp::to_motor_command(1.2, 0.5, config);

  EXPECT_DOUBLE_EQ(motor.position_rad, 42.0);
  EXPECT_DOUBLE_EQ(motor.velocity_rad_s, 17.5);
}

TEST(GearConversion, ConvertsMotorFeedbackToOutputFeedback)
{
  const dm_h3510_ros_cpp::GearConfig config{35.0, 1.0};

  const auto output = dm_h3510_ros_cpp::to_output_feedback(70.0, 17.5, config);

  EXPECT_DOUBLE_EQ(output.position_rad, 2.0);
  EXPECT_DOUBLE_EQ(output.velocity_rad_s, 0.5);
}

TEST(GearConversion, AppliesDirectionToPositionOnly)
{
  const dm_h3510_ros_cpp::GearConfig config{35.0, -1.0};

  const auto motor = dm_h3510_ros_cpp::to_motor_command(1.0, 0.2, config);
  const auto output = dm_h3510_ros_cpp::to_output_feedback(-35.0, 7.0, config);

  EXPECT_DOUBLE_EQ(motor.position_rad, -35.0);
  EXPECT_DOUBLE_EQ(motor.velocity_rad_s, 7.0);
  EXPECT_DOUBLE_EQ(output.position_rad, 1.0);
  EXPECT_DOUBLE_EQ(output.velocity_rad_s, 0.2);
}

TEST(GearConversion, UnwrapsMotorFeedbackAcrossPositiveBoundary)
{
  dm_h3510_ros_cpp::MotorPositionUnwrapper unwrapper;

  EXPECT_NEAR(unwrapper.unwrap(12.30), 12.30, 1.0e-9);
  EXPECT_NEAR(unwrapper.unwrap(-12.40), 12.60, 1.0e-9);
  EXPECT_NEAR(unwrapper.unwrap(-12.10), 12.90, 1.0e-9);
}

TEST(GearConversion, UnwrapsMotorFeedbackAcrossNegativeBoundary)
{
  dm_h3510_ros_cpp::MotorPositionUnwrapper unwrapper;

  EXPECT_NEAR(unwrapper.unwrap(-12.20), -12.20, 1.0e-9);
  EXPECT_NEAR(unwrapper.unwrap(12.30), -12.70, 1.0e-9);
  EXPECT_NEAR(unwrapper.unwrap(12.00), -13.00, 1.0e-9);
}

TEST(GearConversion, ConvertsSignedOutputVelocityToMotorVelocity)
{
  const dm_h3510_ros_cpp::GearConfig config{35.0, 1.0};

  EXPECT_DOUBLE_EQ(dm_h3510_ros_cpp::to_motor_velocity_command(0.3, config), 10.5);
  EXPECT_DOUBLE_EQ(dm_h3510_ros_cpp::to_motor_velocity_command(-0.3, config), -10.5);
}

TEST(GearConversion, ComputesLimitedOutputVelocityTowardTarget)
{
  const dm_h3510_ros_cpp::PositionVelocityControlConfig config{2.0, 0.3, 0.02};

  EXPECT_DOUBLE_EQ(dm_h3510_ros_cpp::compute_output_velocity_command(1.0, 0.0, config), 0.3);
  EXPECT_DOUBLE_EQ(dm_h3510_ros_cpp::compute_output_velocity_command(-1.0, 0.0, config), -0.3);
  EXPECT_DOUBLE_EQ(dm_h3510_ros_cpp::compute_output_velocity_command(0.01, 0.0, config), 0.0);
}
