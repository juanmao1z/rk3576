// 摄像头组件和 Web 组件之间的进程内轻量共享状态。
// 当前只保存线程 TID，用于 /metrics 里区分采集线程和 HTTP 服务线程 CPU。
#include "camera_web_cpp/runtime_shared_state.hpp"

namespace camera_web_cpp
{

RuntimeSharedState & RuntimeSharedState::instance()
{
  // 函数内静态对象避免跨翻译单元的静态初始化顺序问题。
  static RuntimeSharedState shared_state;
  return shared_state;
}

}  // namespace camera_web_cpp
