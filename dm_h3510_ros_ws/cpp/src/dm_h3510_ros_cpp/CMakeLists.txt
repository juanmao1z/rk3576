cmake_minimum_required(VERSION 3.8)
project(dm_h3510_ros_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)

set(DM_DEVICE_LIB
  "${CMAKE_CURRENT_SOURCE_DIR}/vendor/dm_device_sdk/linux/arm64/libdm_device.so")

add_library(dm_device SHARED IMPORTED)
set_target_properties(dm_device PROPERTIES
  IMPORTED_LOCATION "${DM_DEVICE_LIB}")

add_executable(dm_h3510_ros_cpp_node
  src/dm_usb2canfd.cpp
  src/dm_h3510_ros_cpp_node.cpp)

target_include_directories(dm_h3510_ros_cpp_node PRIVATE
  include)

target_compile_features(dm_h3510_ros_cpp_node PRIVATE cxx_std_17)

ament_target_dependencies(dm_h3510_ros_cpp_node
  rclcpp
  sensor_msgs
  std_msgs)

target_link_libraries(dm_h3510_ros_cpp_node
  dm_device)

set_target_properties(dm_h3510_ros_cpp_node PROPERTIES
  BUILD_RPATH "${CMAKE_CURRENT_SOURCE_DIR}/vendor/dm_device_sdk/linux/arm64"
  INSTALL_RPATH "$ORIGIN")

install(TARGETS dm_h3510_ros_cpp_node
  DESTINATION lib/${PROJECT_NAME})

install(FILES "${DM_DEVICE_LIB}"
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_gear_conversion test/test_gear_conversion.cpp)
  target_include_directories(test_gear_conversion PRIVATE include)
  ament_add_gtest(test_initial_velocity_command test/test_initial_velocity_command.cpp)
  target_include_directories(test_initial_velocity_command PRIVATE include)
endif()

ament_package()
