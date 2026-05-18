"""camera_web_bridge 的 ROS2 Python 包安装配置。

这里声明 launch 文件安装路径和两个 console_scripts 入口：
camera_publisher 负责采集，mjpeg_server 负责 Web 转发。
"""

from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'camera_web_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
         glob(os.path.join('launch', '*.launch.py'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lckfb',
    maintainer_email='lckfb@example.local',
    description='ROS2 camera topic publisher and MJPEG browser bridge.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'camera_publisher = camera_web_bridge.camera_publisher:main',
            'mjpeg_server = camera_web_bridge.mjpeg_server:main',
        ],
    },
)
