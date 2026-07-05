"""DM-H3510 ROS2 驱动节点。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32

from .dm_usb2canfd import DmUsb2Canfd, Feedback


POS_VEL_MODE_CODE = 2


class DmH3510RosNode(Node):
    """通过 USB2CANFD 控制 DM-H3510 的 ROS2 节点。"""

    def __init__(self) -> None:
        super().__init__("dm_h3510_ros_py_node")
        self._declare_parameters()
        self._load_parameters()
        self._last_feedback: Optional[Feedback] = None
        self._target_position = 0.0
        self._target_velocity = self._default_velocity_rad_s
        self._has_target = False
        self._position_velocity_can_id = self._can_id + self._position_velocity_id_offset

        self._state_pub = self.create_publisher(JointState, self._state_topic, 10)
        self._driver = DmUsb2Canfd(
            library_path=self._resolve_library_path(),
            channel=self._channel,
            canfd=self._canfd,
            brs=self._brs,
            nominal_baud=self._nominal_baud,
            data_baud=self._data_baud,
            master_id=self._master_id,
            feedback_callback=self._on_feedback,
        )
        self._driver.open()
        if self._switch_mode_on_start:
            self._driver.switch_control_mode(self._can_id, POS_VEL_MODE_CODE)
        self._driver.enable_mode(self._position_velocity_can_id)

        self._position_sub = self.create_subscription(
            Float32,
            self._position_topic,
            self._on_position_command,
            10,
        )
        self._target_joint_sub = self.create_subscription(
            JointState,
            self._target_joint_topic,
            self._on_target_joint_command,
            10,
        )
        self._send_timer = self.create_timer(self._command_period_s, self._send_current_target)

        self.get_logger().info(
            "DM-H3510 ROS 节点已启动为 position-speed cascade: can_id=0x%X master_id=0x%X control_id=0x%X position_topic=%s joint_topic=%s"
            % (
                self._can_id,
                self._master_id,
                self._position_velocity_can_id,
                self._position_topic,
                self._target_joint_topic,
            )
        )

    def destroy_node(self) -> bool:
        """节点退出时先保持当前位置再失能。"""

        try:
            hold_position = (
                self._last_feedback.position_rad
                if self._last_feedback is not None
                else self._to_motor_position(self._target_position)
            )
            self._driver.send_position_velocity(self._position_velocity_can_id, hold_position, 0.0)
            self._driver.disable(self._position_velocity_can_id)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f"退出停机时发生异常: {exc}")
        return super().destroy_node()

    def _declare_parameters(self) -> None:
        self.declare_parameter("library_path", "")
        self.declare_parameter("position_topic", "/gimbal/position_cmd")
        self.declare_parameter("target_joint_topic", "/gimbal/target_joint_state")
        self.declare_parameter("state_topic", "/gimbal/state")
        self.declare_parameter("joint_name", "dm_h3510_joint")
        self.declare_parameter("default_velocity_rad_s", 0.5)
        self.declare_parameter("command_period_ms", 20)
        self.declare_parameter("switch_mode_on_start", True)
        self.declare_parameter("can.channel", 0)
        self.declare_parameter("can.canfd", False)
        self.declare_parameter("can.brs", False)
        self.declare_parameter("can.nominal_baud", 1000000)
        self.declare_parameter("can.data_baud", 5000000)
        self.declare_parameter("motor.can_id", 1)
        self.declare_parameter("motor.master_id", 17)
        self.declare_parameter("motor.position_velocity_id_offset", 256)
        self.declare_parameter("motor.gear_ratio", 35.0)
        self.declare_parameter("motor.gear_direction", 1.0)

    def _load_parameters(self) -> None:
        self._library_path = self.get_parameter("library_path").value
        self._position_topic = self.get_parameter("position_topic").value
        self._target_joint_topic = self.get_parameter("target_joint_topic").value
        self._state_topic = self.get_parameter("state_topic").value
        self._joint_name = self.get_parameter("joint_name").value
        self._default_velocity_rad_s = float(self.get_parameter("default_velocity_rad_s").value)
        self._command_period_s = self.get_parameter("command_period_ms").value / 1000.0
        self._switch_mode_on_start = bool(self.get_parameter("switch_mode_on_start").value)
        self._channel = int(self.get_parameter("can.channel").value)
        self._canfd = bool(self.get_parameter("can.canfd").value)
        self._brs = bool(self.get_parameter("can.brs").value)
        self._nominal_baud = int(self.get_parameter("can.nominal_baud").value)
        self._data_baud = int(self.get_parameter("can.data_baud").value)
        self._can_id = int(self.get_parameter("motor.can_id").value)
        self._master_id = int(self.get_parameter("motor.master_id").value)
        self._position_velocity_id_offset = int(
            self.get_parameter("motor.position_velocity_id_offset").value
        )
        self._gear_ratio = float(self.get_parameter("motor.gear_ratio").value)
        self._gear_direction = (
            -1.0 if float(self.get_parameter("motor.gear_direction").value) < 0.0 else 1.0
        )
        if self._gear_ratio <= 0.0:
            raise ValueError("motor.gear_ratio must be greater than 0")

    def _resolve_library_path(self) -> str:
        """解析 libdm_device.so 位置，默认使用包内 vendor 目录。"""

        if self._library_path:
            return self._library_path
        package_share = Path(get_package_share_directory("dm_h3510_ros_py"))
        default_path = package_share / "vendor/dm_device_sdk/linux/arm64/libdm_device.so"
        if default_path.exists():
            return str(default_path)
        env_path = os.environ.get("DM_DEVICE_SDK_LIB", "")
        if env_path:
            return env_path
        raise RuntimeError("未找到 libdm_device.so，请设置 library_path 或 DM_DEVICE_SDK_LIB")

    def _on_position_command(self, msg: Float32) -> None:
        self._target_position = float(msg.data)
        self._target_velocity = self._default_velocity_rad_s
        self._has_target = True
        self._send_current_target()

    def _on_target_joint_command(self, msg: JointState) -> None:
        if not msg.position:
            self.get_logger().warning("收到 target_joint_state 但 position 为空，已忽略")
            return
        self._target_position = float(msg.position[0])
        if msg.velocity:
            self._target_velocity = float(msg.velocity[0])
        else:
            self._target_velocity = self._default_velocity_rad_s
        self._has_target = True
        self._send_current_target()

    def _send_current_target(self) -> None:
        if not self._has_target:
            return
        self._driver.send_position_velocity(
            self._position_velocity_can_id,
            self._to_motor_position(self._target_position),
            self._to_motor_velocity(self._target_velocity),
        )

    def _on_feedback(self, feedback: Feedback) -> None:
        self._last_feedback = feedback
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [self._joint_name]
        msg.position = [self._to_output_position(feedback.position_rad)]
        msg.velocity = [self._to_output_velocity(feedback.velocity_rad_s)]
        msg.effort = [feedback.torque_nm]
        self._state_pub.publish(msg)

    def _to_motor_position(self, output_position_rad: float) -> float:
        return output_position_rad * self._gear_ratio * self._gear_direction

    def _to_motor_velocity(self, output_velocity_rad_s: float) -> float:
        return abs(output_velocity_rad_s) * self._gear_ratio

    def _to_output_position(self, motor_position_rad: float) -> float:
        return motor_position_rad / self._gear_ratio * self._gear_direction

    def _to_output_velocity(self, motor_velocity_rad_s: float) -> float:
        return motor_velocity_rad_s / self._gear_ratio


def main() -> None:
    rclpy.init()
    node = DmH3510RosNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
