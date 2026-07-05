cmake_minimum_required(VERSION 3.8)
project(gimbal_tracker)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(vision_msgs REQUIRED)

add_library(gimbal_tracker_core
  src/tracker_core.cpp)

target_include_directories(gimbal_tracker_core PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include>")

target_compile_features(gimbal_tracker_core PUBLIC cxx_std_17)

add_executable(gimbal_tracker_node
  src/gimbal_tracker_node.cpp)

target_link_libraries(gimbal_tracker_node
  gimbal_tracker_core)

ament_target_dependencies(gimbal_tracker_node
  rclcpp
  sensor_msgs
  vision_msgs)

install(TARGETS gimbal_tracker_core gimbal_tracker_node
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY include/
  DESTINATION include)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_tracker_core test/test_tracker_core.cpp)
  target_link_libraries(test_tracker_core gimbal_tracker_core)
endif()

ament_export_include_directories(include)
ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_package()
