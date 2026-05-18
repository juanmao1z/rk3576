// 无人机 YOLO C++ 节点进程入口。
// 具体订阅、推理、HTTP 服务和 ROS 检测发布逻辑都封装在 DroneYoloOverlayNode 中。
#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "drone_yolo_web_cpp/yolo_overlay_node.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<drone_yolo_web_cpp::DroneYoloOverlayNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
