# camera_web_bridge

ROS2 Jazzy test package for forwarding a USB camera as a ROS topic and exposing
the topic as an MJPEG browser stream.

Default behavior:

- Reads `/dev/video73`
- Publishes `sensor_msgs/msg/Image` to `/camera/image_raw`
- Serves a browser page on `http://<board-ip>:8080/`
- Serves MJPEG directly on `http://<board-ip>:8080/stream.mjpg`
- Default video mode is `1280x720@30 FPS`

Build:

```bash
cd /home/lckfb/workspace/ros/camera_web_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
```

Run:

```bash
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/ros/camera_web_ws/install/setup.bash
ros2 launch camera_web_bridge camera_web.launch.py
```

Run with custom values:

```bash
ros2 launch camera_web_bridge camera_web.launch.py device:=/dev/video73 width:=1280 height:=720 fps:=15 port:=8080
```
