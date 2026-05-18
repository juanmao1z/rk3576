cmake_minimum_required(VERSION 3.16)
project(vision_msgs)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/BoundingBox2D.msg"
  "msg/Detection2D.msg"
  "msg/Detection2DArray.msg"
  "msg/ObjectHypothesis.msg"
  "msg/ObjectHypothesisWithPose.msg"
  "msg/Point2D.msg"
  "msg/Pose2D.msg"
  DEPENDENCIES geometry_msgs std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
