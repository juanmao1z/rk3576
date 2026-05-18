# Packages

外部安装包归档目录，用于集中保存板端或工作区依赖包，避免安装包散落在 workspace 根目录。

## 目录结构

```text
packages/
  ros/       ROS2 相关 .deb 安装包
```

## 使用约定

- 只放安装包和归档文件，不放源码修改。
- RK3576 板端 RKNN Python wheel 仍保留在 `rknn_wheels`。
- 具体包用途见子目录 README。
