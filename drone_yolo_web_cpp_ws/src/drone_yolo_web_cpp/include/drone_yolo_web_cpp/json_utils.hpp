#pragma once

// HTTP 接口使用的字符串序列化工具。
// 当前返回体很小，手写 JSON 能避免在板端引入额外依赖。

#include <string>

#include "drone_yolo_web_cpp/detection.hpp"

namespace drone_yolo_web_cpp
{

std::string json_escape(const std::string & input);
std::string detections_to_json(const DetectionSnapshot & snapshot);
std::string health_to_text(const DetectionSnapshot & snapshot);

}  // namespace drone_yolo_web_cpp
