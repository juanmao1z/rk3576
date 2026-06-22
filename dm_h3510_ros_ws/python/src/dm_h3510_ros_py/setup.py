from setuptools import setup

package_name = 'dm_h3510_ros_py'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/dm_h3510_ros_py.launch.py']),
        ('share/' + package_name + '/config', ['config/dm_h3510_ros_py.yaml']),
        (
            'share/' + package_name + '/vendor/dm_device_sdk/linux/arm64',
            ['vendor/dm_device_sdk/linux/arm64/libdm_device.so'],
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lckfb',
    maintainer_email='lckfb@example.local',
    description='ROS2 driver for DM-H3510 through DAMIAO USB2CANFD and DM_DeviceSDK.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'dm_h3510_ros_py_node = dm_h3510_ros_py.dm_h3510_ros_py_node:main',
        ],
    },
)
