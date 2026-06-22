cmake_minimum_required(VERSION 3.16)
project(camera_web_cpp)

# camera_web_cpp 以组件库方式构建，两个节点会在同一个 component container
# 中运行，从而让 MJPEG 压缩帧走 intra-process 路径，减少跨进程复制。
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(ament_cmake REQUIRED)
find_package(OpenCV REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(sensor_msgs REQUIRED)

add_library(camera_web_cpp_components SHARED
  src/runtime_shared_state.cpp
  src/camera_mjpeg_publisher.cpp
  src/rtsp_mjpeg_publisher.cpp
  src/compressed_mjpeg_server.cpp
)
target_include_directories(camera_web_cpp_components PUBLIC include)
ament_target_dependencies(camera_web_cpp_components rclcpp rclcpp_components sensor_msgs)
target_link_libraries(camera_web_cpp_components ${OpenCV_LIBS})
# 向 rclcpp_components 注册两个可组合节点，launch 文件按插件名加载它们。
rclcpp_components_register_nodes(camera_web_cpp_components
  "camera_web_cpp::CameraMjpegPublisher"
  "camera_web_cpp::RtspMjpegPublisher"
  "camera_web_cpp::CompressedMjpegServer"
)

install(TARGETS
  camera_web_cpp_components
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}
)

ament_export_include_directories(include)
ament_export_libraries(camera_web_cpp_components)
ament_package()
