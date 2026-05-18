"""yolo_web_py 的 ROS2 Python 包安装配置。

该包提供服务端画框版 YOLO 节点：输出带框 MJPEG、检测 JSON 和 ROS 检测话题。
"""

from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'yolo_web_py'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*.launch.py'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lckfb',
    maintainer_email='lckfb@example.local',
    description='Python RKNN YOLO11 MJPEG result stream.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'yolo_web_py_node = yolo_web_py.yolo_web_py_node:main',
        ],
    },
)
