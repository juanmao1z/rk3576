#!/usr/bin/env python3
import argparse
import os
import sys
import time
from typing import List, Tuple, Optional

import cv2
import numpy as np
from rknnlite.api import RKNNLite

OBJ_THRESH = 0.25
NMS_THRESH = 0.45
IMG_SIZE = (640, 640)  # (width, height)

DEFAULT_CLASSES = (
    "person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
    "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich",
    "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa",
    "pottedplant", "bed", "diningtable", "toilet", "tvmonitor", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
)


def load_labels(path: Optional[str]) -> List[str]:
    if not path:
        return list(DEFAULT_CLASSES)
    with open(path, 'r', encoding='utf-8') as f:
        labels = [line.strip() for line in f if line.strip()]
    if not labels:
        raise ValueError(f'labels file is empty: {path}')
    return labels


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def softmax(x: np.ndarray, axis: int) -> np.ndarray:
    x = x - np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x)
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)


def filter_boxes(boxes: np.ndarray, box_confidences: np.ndarray, box_class_probs: np.ndarray):
    box_confidences = box_confidences.reshape(-1)
    class_max_score = np.max(box_class_probs, axis=-1)
    classes = np.argmax(box_class_probs, axis=-1)
    keep = np.where(class_max_score * box_confidences >= OBJ_THRESH)
    scores = (class_max_score * box_confidences)[keep]
    boxes = boxes[keep]
    classes = classes[keep]
    return boxes, classes, scores


def nms_boxes(boxes: np.ndarray, scores: np.ndarray) -> np.ndarray:
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1e-5)
        h = np.maximum(0.0, yy2 - yy1 + 1e-5)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)

        inds = np.where(ovr <= NMS_THRESH)[0]
        order = order[inds + 1]

    return np.array(keep, dtype=np.int32)


def dfl(position: np.ndarray) -> np.ndarray:
    # position: [N, C, H, W], C = 4 * reg_max
    n, c, h, w = position.shape
    p_num = 4
    mc = c // p_num
    y = position.reshape(n, p_num, mc, h, w)
    y = softmax(y, axis=2)
    acc = np.arange(mc, dtype=np.float32).reshape(1, 1, mc, 1, 1)
    y = (y * acc).sum(axis=2)
    return y


def box_process(position: np.ndarray) -> np.ndarray:
    grid_h, grid_w = position.shape[2:4]
    col, row = np.meshgrid(np.arange(0, grid_w), np.arange(0, grid_h))
    col = col.reshape(1, 1, grid_h, grid_w)
    row = row.reshape(1, 1, grid_h, grid_w)
    grid = np.concatenate((col, row), axis=1)
    stride = np.array([IMG_SIZE[1] // grid_h, IMG_SIZE[0] // grid_w], dtype=np.float32).reshape(1, 2, 1, 1)

    position = dfl(position)
    box_xy1 = grid + 0.5 - position[:, 0:2, :, :]
    box_xy2 = grid + 0.5 + position[:, 2:4, :, :]
    xyxy = np.concatenate((box_xy1 * stride, box_xy2 * stride), axis=1)
    return xyxy


def sp_flatten(x: np.ndarray) -> np.ndarray:
    ch = x.shape[1]
    x = x.transpose(0, 2, 3, 1)
    return x.reshape(-1, ch)


def post_process(outputs: List[np.ndarray]):
    boxes, scores, classes_conf = [], [], []
    default_branch = 3
    pair_per_branch = len(outputs) // default_branch
    if pair_per_branch < 2:
        raise ValueError(f'unexpected output count: {len(outputs)}')

    # Match Rockchip official yolo11 optimized output format.
    # Each branch typically contains:
    #   bbox_reg, cls_conf, score_sum(optional)
    # Python demo ignores score_sum and uses cls_conf only.
    for i in range(default_branch):
        boxes.append(box_process(outputs[pair_per_branch * i]))
        classes_conf.append(outputs[pair_per_branch * i + 1])
        scores.append(np.ones_like(outputs[pair_per_branch * i + 1][:, :1, :, :], dtype=np.float32))

    boxes = np.concatenate([sp_flatten(v) for v in boxes], axis=0)
    classes_conf = np.concatenate([sp_flatten(v) for v in classes_conf], axis=0)
    scores = np.concatenate([sp_flatten(v) for v in scores], axis=0)

    boxes, classes, scores = filter_boxes(boxes, scores, classes_conf)
    if boxes is None or len(boxes) == 0:
        return None, None, None

    nboxes, nclasses, nscores = [], [], []
    for c in set(classes.tolist()):
        inds = np.where(classes == c)
        b = boxes[inds]
        c_arr = classes[inds]
        s = scores[inds]
        keep = nms_boxes(b, s)
        if len(keep) != 0:
            nboxes.append(b[keep])
            nclasses.append(c_arr[keep])
            nscores.append(s[keep])

    if not nboxes:
        return None, None, None

    boxes = np.concatenate(nboxes, axis=0)
    classes = np.concatenate(nclasses, axis=0)
    scores = np.concatenate(nscores, axis=0)
    return boxes, classes, scores


def letterbox(
    image: np.ndarray,
    new_shape: Tuple[int, int] = IMG_SIZE,
    pad_color: Tuple[int, int, int] = (0, 0, 0),
):
    shape = image.shape[:2]  # h, w
    new_w, new_h = new_shape
    r = min(new_w / shape[1], new_h / shape[0])
    resized_w = int(round(shape[1] * r))
    resized_h = int(round(shape[0] * r))

    dw = new_w - resized_w
    dh = new_h - resized_h
    dw /= 2
    dh /= 2

    if (shape[1], shape[0]) != (resized_w, resized_h):
        image = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)

    top = int(round(dh - 0.1))
    bottom = int(round(dh + 0.1))
    left = int(round(dw - 0.1))
    right = int(round(dw + 0.1))
    image = cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=pad_color)
    return image, r, left, top


def scale_boxes(boxes: np.ndarray, ratio: float, pad_x: int, pad_y: int, orig_w: int, orig_h: int) -> np.ndarray:
    boxes = boxes.copy().astype(np.float32)
    boxes[:, [0, 2]] -= pad_x
    boxes[:, [1, 3]] -= pad_y
    boxes[:, [0, 2]] /= ratio
    boxes[:, [1, 3]] /= ratio
    boxes[:, 0] = np.clip(boxes[:, 0], 0, orig_w - 1)
    boxes[:, 1] = np.clip(boxes[:, 1], 0, orig_h - 1)
    boxes[:, 2] = np.clip(boxes[:, 2], 0, orig_w - 1)
    boxes[:, 3] = np.clip(boxes[:, 3], 0, orig_h - 1)
    return boxes


def draw(image: np.ndarray, boxes: np.ndarray, scores: np.ndarray, classes: np.ndarray, labels: List[str]):
    for box, score, cl in zip(boxes, scores, classes):
        x1, y1, x2, y2 = [int(v) for v in box]
        name = labels[int(cl)] if 0 <= int(cl) < len(labels) else str(int(cl))
        cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(
            image,
            f'{name} {score:.2f}',
            (x1, max(20, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    return image


class RKNNModel:
    def __init__(self, model_path: str):
        self.rknn = RKNNLite()
        ret = self.rknn.load_rknn(model_path)
        if ret != 0:
            raise RuntimeError(f'load_rknn failed: {ret}')
        ret = self.rknn.init_runtime()
        if ret != 0:
            raise RuntimeError(f'init_runtime failed: {ret}')

    def run(self, image_rgb: np.ndarray) -> List[np.ndarray]:
        if image_rgb.ndim == 3:
            image_rgb = np.expand_dims(image_rgb, axis=0)
        image_rgb = np.ascontiguousarray(image_rgb)
        outputs = self.rknn.inference(inputs=[image_rgb])
        if outputs is None:
            raise RuntimeError('RKNN inference returned None')
        return outputs

    def release(self):
        self.rknn.release()


def make_capture(args) -> cv2.VideoCapture:
    if args.backend == 'gst':
        cap = cv2.VideoCapture(args.source, cv2.CAP_GSTREAMER)
    else:
        src = int(args.source) if str(args.source).isdigit() else args.source
        cap = cv2.VideoCapture(src, cv2.CAP_V4L2)
        if args.camera_width > 0:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.camera_width)
        if args.camera_height > 0:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.camera_height)
        if args.camera_fps > 0:
            cap.set(cv2.CAP_PROP_FPS, args.camera_fps)
    return cap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, help='path to yolo11.rknn')
    parser.add_argument('--labels', default=None, help='labels txt path, one class per line')
    parser.add_argument('--source', default='/dev/video0', help='camera source or gst pipeline')
    parser.add_argument('--backend', choices=['v4l2', 'gst'], default='v4l2')
    parser.add_argument('--width', type=int, default=640, help='model input width')
    parser.add_argument('--height', type=int, default=640, help='model input height')
    parser.add_argument('--camera-width', type=int, default=1280)
    parser.add_argument('--camera-height', type=int, default=720)
    parser.add_argument('--camera-fps', type=int, default=30)
    parser.add_argument('--conf', type=float, default=0.25)
    parser.add_argument('--iou', type=float, default=0.45)
    parser.add_argument('--window', default='RK3576 YOLO11 Camera')
    parser.add_argument('--save', default=None, help='optional output mp4 path')
    parser.add_argument('--no-show', action='store_true', help='disable cv2.imshow')
    args = parser.parse_args()

    global OBJ_THRESH, NMS_THRESH, IMG_SIZE
    OBJ_THRESH = args.conf
    NMS_THRESH = args.iou
    IMG_SIZE = (args.width, args.height)

    labels = load_labels(args.labels)
    model = RKNNModel(args.model)
    cap = make_capture(args)

    if not cap.isOpened():
        raise RuntimeError('failed to open camera/video source')

    writer = None
    fps = 0.0
    t_prev = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print('camera read failed')
                break

            orig_h, orig_w = frame.shape[:2]
            img, ratio, pad_x, pad_y = letterbox(frame, new_shape=IMG_SIZE, pad_color=(0, 0, 0))
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            outputs = model.run(img_rgb)
            if len(outputs) == 0:
                raise RuntimeError('RKNN inference returned empty outputs')
            boxes, classes, scores = post_process(outputs)

            vis = frame.copy()
            if boxes is not None:
                real_boxes = scale_boxes(boxes, ratio, pad_x, pad_y, orig_w, orig_h)
                vis = draw(vis, real_boxes, scores, classes, labels)

            now = time.time()
            dt = now - t_prev
            t_prev = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps > 0 else (1.0 / dt)
            cv2.putText(vis, f'FPS: {fps:.2f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

            if args.save:
                if writer is None:
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    writer = cv2.VideoWriter(args.save, fourcc, max(1, args.camera_fps), (vis.shape[1], vis.shape[0]))
                writer.write(vis)

            if not args.no_show:
                cv2.imshow(args.window, vis)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord('q')):
                    break
    finally:
        if writer is not None:
            writer.release()
        cap.release()
        cv2.destroyAllWindows()
        model.release()


if __name__ == '__main__':
    main()
