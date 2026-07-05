#include "gimbal_tracker/tracker_core.hpp"

#include <gtest/gtest.h>

namespace
{

gimbal_tracker::DetectionCandidate make_detection(
  double center_x,
  double score = 0.8,
  const std::string & label = "drone")
{
  gimbal_tracker::DetectionCandidate detection;
  detection.class_id = label;
  detection.label = label;
  detection.score = score;
  detection.center_x = center_x;
  detection.center_y = 240.0;
  detection.size_x = 80.0;
  detection.size_y = 60.0;
  return detection;
}

TEST(TrackerCore, ReturnsNoCommandWithoutTarget)
{
  gimbal_tracker::TrackerConfig config;
  const auto command = gimbal_tracker::compute_track_command({}, 0.2, config);
  EXPECT_FALSE(command.has_value());
}

TEST(TrackerCore, KeepsYawWhenTargetIsInsideDeadband)
{
  gimbal_tracker::TrackerConfig config;
  config.deadband_px = 40.0;

  const auto command = gimbal_tracker::compute_track_command({make_detection(340.0)}, 0.2, config);

  ASSERT_TRUE(command.has_value());
  EXPECT_TRUE(command->in_deadband);
  EXPECT_DOUBLE_EQ(command->delta_yaw, 0.0);
  EXPECT_DOUBLE_EQ(command->target_yaw, 0.2);
}

TEST(TrackerCore, LimitsYawStepForRightSideTargetWithReversedCameraMount)
{
  gimbal_tracker::TrackerConfig config;
  config.deadband_px = 40.0;
  config.kp_x = -0.0008;
  config.max_step_rad = 0.03;

  const auto command = gimbal_tracker::compute_track_command({make_detection(520.0)}, 0.2, config);

  ASSERT_TRUE(command.has_value());
  EXPECT_FALSE(command->in_deadband);
  EXPECT_DOUBLE_EQ(command->error_x, 200.0);
  EXPECT_DOUBLE_EQ(command->delta_yaw, 0.03);
  EXPECT_DOUBLE_EQ(command->target_yaw, 0.23);
}

TEST(TrackerCore, AllowsClockwiseOneOutputTurnFromZeroByDefault)
{
  gimbal_tracker::TrackerConfig config;

  const auto command = gimbal_tracker::compute_track_command({make_detection(520.0)}, 6.27, config);

  ASSERT_TRUE(command.has_value());
  EXPECT_NEAR(command->target_yaw, 6.2832, 1.0e-4);
}

TEST(TrackerCore, UsesSlowDefaultTrackingVelocity)
{
  gimbal_tracker::TrackerConfig config;

  const auto command = gimbal_tracker::compute_track_command({make_detection(520.0)}, 0.0, config);

  ASSERT_TRUE(command.has_value());
  EXPECT_DOUBLE_EQ(command->velocity_rad_s, 0.3);
}

}  // namespace
