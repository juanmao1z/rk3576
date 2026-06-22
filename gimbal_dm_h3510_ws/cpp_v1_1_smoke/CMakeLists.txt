cmake_minimum_required(VERSION 3.20)
project(dm_h3510_control LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(DM_SDK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/vendor/dm_device_sdk")

if(MSVC)
  add_compile_options(/utf-8)
endif()

add_library(dm_h3510_driver
  src/dm_h3510_controller.cpp
  src/usb2canfd_device.cpp
)

target_include_directories(dm_h3510_driver PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
  "${DM_SDK_ROOT}"
)

target_link_libraries(dm_h3510_driver PUBLIC
  "${DM_SDK_ROOT}/dm_device.lib"
)

add_executable(dm_h3510_control
  src/main.cpp
)

target_link_libraries(dm_h3510_control PRIVATE
  dm_h3510_driver
)

add_custom_command(TARGET dm_h3510_control POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${DM_SDK_ROOT}/dm_device.dll"
    "$<TARGET_FILE_DIR:dm_h3510_control>/dm_device.dll"
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${DM_SDK_ROOT}/libusb-1.0.dll"
    "$<TARGET_FILE_DIR:dm_h3510_control>/libusb-1.0.dll"
)
