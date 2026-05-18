"""将 Anti-UAV VOC/XML 数据集转换为 YOLO 格式。

脚本会把 DroneTrainDataset 划分为 train/val，把 DroneTestDataset 作为 test；
没有 XML 的测试图片按空标签负样本保留。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
CLASS_NAMES = ["drone"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Convert Anti-UAV VOC/XML folders to YOLO format.")
    parser.add_argument("--train-images", required=True)
    parser.add_argument("--train-xmls", required=True)
    parser.add_argument("--test-images", required=True)
    parser.add_argument("--test-xmls", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", default="rk3576-drone-v1")
    parser.add_argument("--copy", action="store_true", help="Copy images instead of hard-linking them.")
    parser.add_argument("--clean", action="store_true", help="Remove the output directory before conversion.")
    return parser.parse_args()


def natural_key(path: Path) -> tuple[int, int | str]:
    stem = path.stem
    if stem.isdigit():
        return (0, int(stem))
    return (1, stem)


def image_files(directory: Path) -> list[Path]:
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
        key=natural_key,
    )


def split_group(stem: str) -> str:
    """按文件名推断分组，避免同一序列被随机拆到 train/val 两边。"""
    if stem.isdigit():
        return f"numeric_{int(stem) // 1000}"
    match = re.match(r"pos_G(?P<g>\d+)P(?P<p>\d+)(?:_V(?P<v>\d+))?$", stem)
    if match:
        g = match.group("g")
        p = int(match.group("p"))
        v = match.group("v") or "none"
        return f"g{g}_v{v}_p{p // 1000}"
    return stem


def stable_score(value: str, seed: str) -> str:
    return hashlib.sha1(f"{seed}:{value}".encode("utf-8")).hexdigest()


def choose_val_groups(images: list[Path], val_ratio: float, seed: str) -> set[str]:
    """使用稳定 hash 选择验证集分组，保证重复运行划分一致。"""
    groups: dict[str, int] = {}
    for image in images:
        group = split_group(image.stem)
        groups[group] = groups.get(group, 0) + 1

    target = max(1, round(len(images) * val_ratio))
    chosen: set[str] = set()
    count = 0
    for group, group_count in sorted(groups.items(), key=lambda item: stable_score(item[0], seed)):
        if count >= target:
            break
        chosen.add(group)
        count += group_count
    return chosen


def parse_voc_xml(xml_path: Path) -> tuple[tuple[int, int], list[tuple[int, float, float, float, float]], list[str]]:
    """解析单个 VOC XML，并转换为 YOLO 归一化框。"""
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    if size is None:
        raise ValueError("missing size")
    width = int(float(size.findtext("width", "0")))
    height = int(float(size.findtext("height", "0")))
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid image size {width}x{height}")

    labels: list[tuple[int, float, float, float, float]] = []
    warnings: list[str] = []
    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip().lower()
        if name != "drone":
            warnings.append(f"ignored_class:{name}")
            continue
        box = obj.find("bndbox")
        if box is None:
            warnings.append("missing_box")
            continue
        xmin = float(box.findtext("xmin", "0"))
        ymin = float(box.findtext("ymin", "0"))
        xmax = float(box.findtext("xmax", "0"))
        ymax = float(box.findtext("ymax", "0"))

        clipped = (
            max(0.0, min(xmin, width)),
            max(0.0, min(ymin, height)),
            max(0.0, min(xmax, width)),
            max(0.0, min(ymax, height)),
        )
        if clipped != (xmin, ymin, xmax, ymax):
            warnings.append("clipped_box")
        xmin, ymin, xmax, ymax = clipped
        if not (xmin < xmax and ymin < ymax):
            warnings.append("invalid_box")
            continue

        cx = ((xmin + xmax) / 2.0) / width
        cy = ((ymin + ymax) / 2.0) / height
        bw = (xmax - xmin) / width
        bh = (ymax - ymin) / height
        labels.append((0, cx, cy, bw, bh))
    return (width, height), labels, warnings


def link_or_copy(src: Path, dst: Path, copy: bool) -> None:
    """优先硬链接图片以节省空间，跨盘或不支持时回退到复制。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    if copy:
        shutil.copy2(src, dst)
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def write_label(label_path: Path, labels: list[tuple[int, float, float, float, float]]) -> None:
    label_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}" for cls, cx, cy, bw, bh in labels]
    label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def convert_image(
    image: Path,
    xml_dir: Path,
    output: Path,
    split: str,
    copy: bool,
    allow_missing_xml: bool,
) -> dict[str, object]:
    """转换单张图片及其标签，返回清单记录用于后续审计。"""
    xml_path = xml_dir / f"{image.stem}.xml"
    warnings: list[str] = []
    labels: list[tuple[int, float, float, float, float]] = []
    size: tuple[int, int] | None = None

    if xml_path.exists():
        size, labels, warnings = parse_voc_xml(xml_path)
    elif allow_missing_xml:
        warnings.append("missing_xml_as_negative")
    else:
        raise FileNotFoundError(xml_path)

    image_out = output / "images" / split / image.name
    label_out = output / "labels" / split / f"{image.stem}.txt"
    link_or_copy(image, image_out, copy)
    write_label(label_out, labels)
    return {
        "image": str(image),
        "split": split,
        "boxes": len(labels),
        "size": list(size) if size else None,
        "warnings": warnings,
    }


def ensure_clean_output(output: Path) -> None:
    """只允许清理固定输出目录，避免误删任意路径。"""
    if not output.exists():
        return
    resolved = output.resolve()
    if not str(resolved).lower().endswith("dronetraindataset_yolo"):
        raise SystemExit(f"Refusing to clean unexpected output path: {resolved}")
    shutil.rmtree(resolved)


def main() -> None:
    """执行完整 VOC 到 YOLO 转换流程。"""
    args = parse_args()
    train_images = Path(args.train_images).resolve()
    train_xmls = Path(args.train_xmls).resolve()
    test_images = Path(args.test_images).resolve()
    test_xmls = Path(args.test_xmls).resolve()
    output = Path(args.output).resolve()

    if args.clean:
        ensure_clean_output(output)

    train_files = image_files(train_images)
    test_files = image_files(test_images)
    val_groups = choose_val_groups(train_files, args.val_ratio, args.seed)

    records: list[dict[str, object]] = []
    for image in train_files:
        split = "val" if split_group(image.stem) in val_groups else "train"
        records.append(convert_image(image, train_xmls, output, split, args.copy, allow_missing_xml=False))
    for image in test_files:
        records.append(convert_image(image, test_xmls, output, "test", args.copy, allow_missing_xml=True))

    data_yaml = output / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {output.as_posix()}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "",
                "names:",
                "  0: drone",
                "",
            ]
        ),
        encoding="utf-8",
    )

    summary: dict[str, object] = {
        "output": str(output),
        "data_yaml": str(data_yaml),
        "classes": CLASS_NAMES,
        "source": {
            "train_images": str(train_images),
            "train_xmls": str(train_xmls),
            "test_images": str(test_images),
            "test_xmls": str(test_xmls),
        },
        "splits": {},
        "warnings": {},
    }
    for split in ("train", "val", "test"):
        split_records = [record for record in records if record["split"] == split]
        summary["splits"][split] = {
            "images": len(split_records),
            "boxes": sum(int(record["boxes"]) for record in split_records),
            "empty_labels": sum(1 for record in split_records if int(record["boxes"]) == 0),
        }
    warning_counts: dict[str, int] = {}
    warning_examples: dict[str, list[str]] = {}
    for record in records:
        for warning in record["warnings"]:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
            warning_examples.setdefault(warning, [])
            if len(warning_examples[warning]) < 10:
                warning_examples[warning].append(str(record["image"]))
    summary["warnings"] = {"counts": warning_counts, "examples": warning_examples}

    (output / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
