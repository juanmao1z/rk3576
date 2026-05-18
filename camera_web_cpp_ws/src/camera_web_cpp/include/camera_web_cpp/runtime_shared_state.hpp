#pragma once

#include <atomic>
#include <sys/types.h>

namespace camera_web_cpp
{

/**
 * @brief 同进程组件之间共享的轻量状态。
 *
 * 这套 C++ 版在同一个 component container 中同时加载：
 * 1. 摄像头采集组件 CameraMjpegPublisher
 * 2. Web 转发组件 CompressedMjpegServer
 *
 * 两者虽然位于同一进程，但仍然是两个独立的 ROS2 节点对象。为了避免引入
 * 更重的全局管理对象，这里只保留一份极小的共享状态，专门用于暴露关键线程
 * 的 TID，方便 Web 组件在 /proc/self/task 下单独统计采集线程和 HTTP 服务
 * 线程的 CPU 占用。
 */
struct RuntimeSharedState
{
  /// 采集线程在 Linux 下的真实线程 ID。未就绪时为 -1。
  std::atomic<pid_t> capture_tid {-1};
  /// HTTP 服务线程在 Linux 下的真实线程 ID。未就绪时为 -1。
  std::atomic<pid_t> server_tid {-1};

  /**
   * @brief 获取进程内唯一的共享状态实例。
   *
   * 这里使用函数内静态对象，避免静态初始化顺序问题，同时无需额外生命周期管理。
   */
  static RuntimeSharedState & instance();
};

}  // namespace camera_web_cpp
