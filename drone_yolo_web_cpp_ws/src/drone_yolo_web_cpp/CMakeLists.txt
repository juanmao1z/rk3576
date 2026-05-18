cmake_minimum_required(VERSION 3.16)
project(drone_yolo_web_cpp)

# 无人机专用 YOLO C++ 节点构建配置。
# 依赖 OpenCV 做 JPEG 解码/预处理，依赖 RKNN runtime 做 NPU 推理。
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(OpenCV REQUIRED COMPONENTS core imgcodecs imgproc)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(vision_msgs REQUIRED)

add_executable(drone_yolo_web_cpp_node
  src/http_overlay_server.cpp
  src/json_utils.cpp
  src/yolo11_rknn_detector.cpp
  src/yolo_overlay_node.cpp
  src/drone_yolo_web_cpp_node.cpp
)

target_include_directories(drone_yolo_web_cpp_node PRIVATE
  include
  # rknn_api.h 随工作区 vendor，板端链接系统中的 rknnrt。
  third_party/rknpu2/include
)

ament_target_dependencies(drone_yolo_web_cpp_node
  rclcpp
  sensor_msgs
  vision_msgs
)

target_link_libraries(drone_yolo_web_cpp_node
  ${OpenCV_LIBS}
  rknnrt
)

install(TARGETS drone_yolo_web_cpp_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY third_party
  DESTINATION share/${PROJECT_NAME}
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
