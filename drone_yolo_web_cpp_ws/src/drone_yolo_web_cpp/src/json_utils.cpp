// 将无人机检测快照序列化为浏览器和调试命令使用的 HTTP 响应。
// 为了减少板端依赖，这里只实现当前字段所需的最小 JSON 转义和格式化。
#include "drone_yolo_web_cpp/json_utils.hpp"

#include <iomanip>
#include <sstream>

namespace drone_yolo_web_cpp
{

std::string json_escape(const std::string & input)
{
  std::ostringstream escaped;
  for (const char ch : input) {
    switch (ch) {
      case '\\':
        escaped << "\\\\";
        break;
      case '"':
        escaped << "\\\"";
        break;
      case '\n':
        escaped << "\\n";
        break;
      case '\r':
        escaped << "\\r";
        break;
      case '\t':
        escaped << "\\t";
        break;
      default:
        if (static_cast<unsigned char>(ch) < 0x20) {
          escaped << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                  << static_cast<int>(static_cast<unsigned char>(ch)) << std::dec;
        } else {
          escaped << ch;
        }
        break;
    }
  }
  return escaped.str();
}

std::string detections_to_json(const DetectionSnapshot & snapshot)
{
  // result_fps 表示最近滑动窗口内“已完成推理并更新结果”的帧率。
  std::ostringstream json;
  json << std::fixed << std::setprecision(3);
  json << "{"
       << "\"frame\":" << snapshot.frame_count << ","
       << "\"image_width\":" << snapshot.image_width << ","
       << "\"image_height\":" << snapshot.image_height << ","
       << "\"result_fps\":" << snapshot.result_fps << ","
       << "\"fps_window\":\"completed inference frames over recent sliding window\","
       << "\"last_pipeline_ms\":" << snapshot.last_pipeline_ms << ","
       << "\"last_decode_ms\":" << snapshot.last_decode_ms << ","
       << "\"last_inference_ms\":" << snapshot.last_inference_ms << ","
       << "\"last_postprocess_ms\":" << snapshot.last_postprocess_ms << ","
       << "\"age\":" << snapshot.age_seconds << ","
       << "\"detections\":[";

  for (size_t i = 0; i < snapshot.detections.size(); ++i) {
    const auto & det = snapshot.detections[i];
    if (i != 0) {
      json << ",";
    }
    json << "{"
         << "\"class_id\":" << det.class_id << ","
         << "\"label\":\"" << json_escape(det.label) << "\","
         << "\"score\":" << det.score << ","
         << "\"x\":" << det.x << ","
         << "\"y\":" << det.y << ","
         << "\"width\":" << det.width << ","
         << "\"height\":" << det.height
         << "}";
  }
  json << "]}";
  return json.str();
}

std::string health_to_text(const DetectionSnapshot & snapshot)
{
  std::ostringstream body;
  body << std::fixed << std::setprecision(3)
       << "frames=" << snapshot.frame_count
       << " age=" << snapshot.age_seconds
       << " result_fps=" << snapshot.result_fps
       << " last_pipeline_ms=" << snapshot.last_pipeline_ms
       << " last_decode_ms=" << snapshot.last_decode_ms
       << " last_inference_ms=" << snapshot.last_inference_ms
       << " last_postprocess_ms=" << snapshot.last_postprocess_ms
       << "\n";
  return body.str();
}

}  // namespace drone_yolo_web_cpp
