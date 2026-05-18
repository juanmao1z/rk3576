"""无人机 PT 模型验证、下载、训练和导出命令行入口。

该脚本服务于 Windows PC 端实验流程：先验证预训练 `.pt`，再准备数据集、
训练或导出模型，最后把合适模型转换并部署到 RK3576。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
RUNS_DIR = ROOT / "runs"
DATASETS_DIR = ROOT / "data" / "open_datasets"

MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    # 适合地面摄像头识别空中目标的默认模型。
    "flying_objects_yolov8m": {
        "repo_id": "Javvanny/yolov8m_flying_objects_detection",
        "filename": "yolov8m/weights/best.pt",
        "local_path": MODELS_DIR / "flying_objects_yolov8m.pt",
        "classes": [
            "0: UAV copter / multicopter drone",
            "1: airplane",
            "2: helicopter",
            "3: bird",
            "4: UAV airplane / fixed-wing drone",
        ],
        "drone_class_ids": [0, 4],
        "task": "Detect flying objects from ground cameras.",
    },
    "visdrone_yolov8n": {
        "repo_id": "mshamrai/yolov8n-visdrone",
        "filename": "best.pt",
        "local_path": MODELS_DIR / "visdrone_yolov8n.pt",
        "classes": [
            "pedestrian",
            "people",
            "bicycle",
            "car",
            "van",
            "truck",
            "tricycle",
            "awning-tricycle",
            "bus",
            "motor",
        ],
        "drone_class_ids": [],
        "task": "Detect ground objects in drone-view images. This does not detect the drone body itself.",
    },
}

DATASET_REGISTRY: dict[str, dict[str, Any]] = {
    # 轻量公开测试集，用于快速验证模型能否跑通。
    "kc34251_drone_detection": {
        "repo_id": "kc34251/Drone-Detection",
        "prefix": "drone_dataset_yolo/dataset_txt",
        "local_dir": DATASETS_DIR / "kc34251_drone_detection",
        "task": "Small public YOLO-format drone detection dataset for quick local testing.",
        "source_url": "https://huggingface.co/datasets/kc34251/Drone-Detection",
        "license_note": "Public Hugging Face dataset; license metadata was not declared by the dataset card/API.",
    }
}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _lazy_yolo():
    """延迟导入 Ultralytics，避免 models/datasets 等轻量命令也强制依赖它。"""
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Ultralytics is not installed. Run scripts/setup_env.ps1 first, "
            "then retry the command."
        ) from exc
    return YOLO


def _hf_url(repo_id: str, filename: str) -> str:
    quoted = "/".join(urllib.parse.quote(part) for part in filename.split("/"))
    return f"https://huggingface.co/{repo_id}/resolve/main/{quoted}?download=true"


def _hf_dataset_url(repo_id: str, filename: str) -> str:
    quoted = "/".join(urllib.parse.quote(part) for part in filename.split("/"))
    return f"https://huggingface.co/datasets/{repo_id}/resolve/main/{quoted}?download=true"


def _hf_tree_api_url(repo_id: str, prefix: str) -> str:
    quoted = "/".join(urllib.parse.quote(part) for part in prefix.split("/"))
    return f"https://huggingface.co/api/datasets/{repo_id}/tree/main/{quoted}?recursive=true"


def _download_with_huggingface_hub(repo_id: str, filename: str, destination: Path) -> bool:
    """优先使用 huggingface_hub 下载模型，失败时再回退到 urllib。"""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return False

    downloaded = Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=MODELS_DIR / "_hf_cache",
            local_dir_use_symlinks=False,
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(downloaded.read_bytes())
    return True


def _download_with_urllib(repo_id: str, filename: str, destination: Path) -> None:
    url = _hf_url(repo_id, filename)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")

    with urllib.request.urlopen(url, timeout=60) as response:
        total = int(response.headers.get("content-length", "0") or 0)
        received = 0
        last_print = 0.0
        with tmp.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                now = time.monotonic()
                if now - last_print > 1.0:
                    if total:
                        pct = received * 100 / total
                        print(f"Downloading {destination.name}: {pct:.1f}%")
                    else:
                        print(f"Downloading {destination.name}: {received / 1024 / 1024:.1f} MB")
                    last_print = now

    tmp.replace(destination)


def _download_file(url: str, destination: Path, force: bool = False) -> str:
    """下载普通 URL 文件，使用 .part 临时文件避免留下半成品。"""
    if destination.exists() and not force:
        return "skipped"

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as response:
        with tmp.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    tmp.replace(destination)
    return "downloaded"


def _write_model_metadata(name: str, path: Path) -> None:
    info = MODEL_REGISTRY[name]
    meta_path = path.with_suffix(".json")
    meta_path.write_text(
        json.dumps(
            {
                "name": name,
                "repo_id": info["repo_id"],
                "filename": info["filename"],
                "classes": info["classes"],
                "task": info["task"],
                "downloaded_to": str(path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _download_model(name: str, force: bool = False) -> Path:
    if name not in MODEL_REGISTRY:
        raise SystemExit(f"Unknown model '{name}'. Run 'models' to list available model names.")

    info = MODEL_REGISTRY[name]
    destination = Path(info["local_path"])
    if destination.exists() and not force:
        print(f"Model already exists: {destination}")
        _write_model_metadata(name, destination)
        return destination

    print(f"Downloading model '{name}' from {info['repo_id']} / {info['filename']}")
    try:
        used_hub = _download_with_huggingface_hub(info["repo_id"], info["filename"], destination)
        if not used_hub:
            _download_with_urllib(info["repo_id"], info["filename"], destination)
    except Exception as exc:
        raise SystemExit(f"Failed to download model '{name}': {exc}") from exc

    _write_model_metadata(name, destination)
    print(f"Saved model: {destination}")
    return destination


def _resolve_model(value: str, auto_download: bool = True) -> Path:
    """把模型名称或路径解析为本地 PT 文件路径。"""
    if value in MODEL_REGISTRY:
        path = Path(MODEL_REGISTRY[value]["local_path"])
        if auto_download and not path.exists():
            return _download_model(value)
        if not path.exists():
            raise SystemExit(f"Model is not downloaded yet: {path}")
        return path

    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists():
        raise SystemExit(f"Model path does not exist: {path}")
    return path


def _parse_source(value: str) -> str | int:
    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    return value


def _parse_classes(value: str | None) -> list[int] | None:
    """解析逗号分隔类别 ID，用于 Ultralytics predict/val 的 classes 参数。"""
    if not value:
        return None
    classes: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            classes.append(int(item))
        except ValueError as exc:
            raise SystemExit("--classes must be a comma-separated list of class indexes, for example: 0,3") from exc
    return classes or None


def command_models(_: argparse.Namespace) -> None:
    payload: dict[str, Any] = {}
    for name, info in MODEL_REGISTRY.items():
        local_path = Path(info["local_path"])
        payload[name] = {
            "repo_id": info["repo_id"],
            "filename": info["filename"],
            "local_path": str(local_path),
            "downloaded": local_path.exists(),
            "classes": info["classes"],
            "task": info["task"],
        }
    _print_json(payload)


def command_datasets(_: argparse.Namespace) -> None:
    payload: dict[str, Any] = {}
    for name, info in DATASET_REGISTRY.items():
        local_dir = Path(info["local_dir"])
        yaml_path = local_dir / "data.yaml"
        payload[name] = {
            "repo_id": info["repo_id"],
            "source_url": info["source_url"],
            "local_dir": str(local_dir),
            "data_yaml": str(yaml_path),
            "downloaded": yaml_path.exists(),
            "license_note": info["license_note"],
            "task": info["task"],
        }
    _print_json(payload)


def _dataset_destination(local_dir: Path, source_path: str) -> Path | None:
    name = Path(source_path).name
    suffix = Path(name).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        return local_dir / "images" / "test" / name
    if suffix == ".txt":
        return local_dir / "labels" / "test" / name
    return None


def command_download_dataset(args: argparse.Namespace) -> None:
    """下载注册表中的公开 YOLO 格式测试数据集。"""
    if args.dataset_name not in DATASET_REGISTRY:
        raise SystemExit(f"Unknown dataset '{args.dataset_name}'. Run 'datasets' to list available datasets.")

    info = DATASET_REGISTRY[args.dataset_name]
    local_dir = Path(info["local_dir"])
    api_url = _hf_tree_api_url(info["repo_id"], info["prefix"])
    print(f"Reading file list: {api_url}")
    with urllib.request.urlopen(api_url, timeout=60) as response:
        items = json.loads(response.read().decode("utf-8"))

    files = [item for item in items if item.get("type") == "file"]
    wanted: list[tuple[str, Path]] = []
    image_count = 0
    for item in files:
        path = item["path"]
        destination = _dataset_destination(local_dir, path)
        if destination is None:
            continue
        if destination.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            image_count += 1
            if args.limit and image_count > args.limit:
                continue
        elif args.limit:
            stem = destination.stem
            indexed_images = {
                Path(p).stem
                for p, d in wanted
                if d.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
            }
            if stem not in indexed_images:
                continue
        wanted.append((path, destination))

    if not wanted:
        raise SystemExit("No downloadable dataset files were found.")

    downloaded = 0
    skipped = 0
    failed: list[str] = []
    print(f"Downloading {len(wanted)} files into {local_dir}")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_download_file, _hf_dataset_url(info["repo_id"], path), destination, args.force): path
            for path, destination in wanted
        }
        for index, future in enumerate(as_completed(futures), start=1):
            path = futures[future]
            try:
                status = future.result()
                if status == "downloaded":
                    downloaded += 1
                else:
                    skipped += 1
            except Exception as exc:
                failed.append(f"{path}: {exc}")
            if index == len(futures) or index % 25 == 0:
                print(f"Progress: {index}/{len(futures)} files")

    yaml_path = local_dir / "data.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                f"path: {local_dir.as_posix()}",
                "train: images/test",
                "val: images/test",
                "test: images/test",
                "",
                "names:",
                "  0: drone",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (local_dir / "README.md").write_text(
        "\n".join(
            [
                "# kc34251 Drone Detection",
                "",
                f"Source: {info['source_url']}",
                "",
                f"License note: {info['license_note']}",
                "",
                "Downloaded by `drone_pt_detector.py download-dataset`.",
                "The files are arranged in YOLO format for quick local testing.",
                "",
                "Use:",
                "",
                "```powershell",
                f"powershell -ExecutionPolicy Bypass -File .\\scripts\\detect.ps1 -Source {local_dir}\\images\\test -DroneOnly",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    metadata = {
        "dataset_name": args.dataset_name,
        "repo_id": info["repo_id"],
        "source_url": info["source_url"],
        "local_dir": str(local_dir),
        "data_yaml": str(yaml_path),
        "requested_limit": args.limit or "all",
        "downloaded_files": downloaded,
        "skipped_files": skipped,
        "failed_files": failed,
    }
    (local_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    image_files = list((local_dir / "images" / "test").glob("*"))
    label_files = list((local_dir / "labels" / "test").glob("*.txt"))
    print(f"Dataset ready: {local_dir}")
    print(f"Images: {len(image_files)}")
    print(f"Labels: {len(label_files)}")
    print(f"Data yaml: {yaml_path}")
    if failed:
        print(f"Failed files: {len(failed)}")


def command_download(args: argparse.Namespace) -> None:
    path = _download_model(args.model_name, force=args.force)
    print(path)


def command_detect(args: argparse.Namespace) -> None:
    """运行图片、视频、目录、URL 或摄像头检测。"""
    YOLO = _lazy_yolo()
    model_path = _resolve_model(args.model)
    source = _parse_source(args.source)

    yolo = YOLO(str(model_path))
    classes = _parse_classes(args.classes)
    if args.drone_only:
        if str(args.model) in MODEL_REGISTRY:
            classes = list(MODEL_REGISTRY[str(args.model)]["drone_class_ids"])
        else:
            classes = [0]
        if not classes:
            raise SystemExit(f"Model '{args.model}' does not define drone class ids.")

    results = yolo.predict(
        source=source,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        device=args.device or None,
        classes=classes,
        show=args.show,
        save=True,
        save_txt=args.save_txt,
        save_conf=args.save_conf,
        project=str(RUNS_DIR / "detect"),
        name=args.name,
        exist_ok=args.exist_ok,
        verbose=True,
    )

    save_dir = None
    if results:
        save_dir = getattr(results[0], "save_dir", None)
    print(f"Detection finished. Output: {save_dir or RUNS_DIR / 'detect' / args.name}")


def command_train(args: argparse.Namespace) -> None:
    """基于指定 YOLO 数据集继续训练模型。"""
    YOLO = _lazy_yolo()
    model_path = _resolve_model(args.model)
    data = Path(args.data).expanduser()
    if not data.is_absolute():
        data = (Path.cwd() / data).resolve()
    if not data.exists():
        raise SystemExit(f"Dataset yaml does not exist: {data}")

    yolo = YOLO(str(model_path))
    yolo.train(
        data=str(data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device or None,
        project=str(RUNS_DIR / "train"),
        name=args.name,
        exist_ok=args.exist_ok,
    )


def command_val(args: argparse.Namespace) -> None:
    """在指定 YOLO 数据集上评估模型指标。"""
    YOLO = _lazy_yolo()
    model_path = _resolve_model(args.model)
    data = Path(args.data).expanduser()
    if not data.is_absolute():
        data = (Path.cwd() / data).resolve()
    if not data.exists():
        raise SystemExit(f"Dataset yaml does not exist: {data}")

    classes = _parse_classes(args.classes)
    if args.drone_only:
        if str(args.model) in MODEL_REGISTRY:
            classes = list(MODEL_REGISTRY[str(args.model)]["drone_class_ids"])
        else:
            classes = [0]

    yolo = YOLO(str(model_path))
    metrics = yolo.val(
        data=str(data),
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device or None,
        classes=classes,
        project=str(RUNS_DIR / "val"),
        name=args.name,
        exist_ok=args.exist_ok,
    )
    print(f"Validation finished. Output: {RUNS_DIR / 'val' / args.name}")
    results = getattr(metrics, "results_dict", None)
    if results:
        _print_json({key: float(value) for key, value in results.items()})


def command_export(args: argparse.Namespace) -> None:
    """调用 Ultralytics 导出模型，ONNX/RKNN 等格式由参数控制。"""
    YOLO = _lazy_yolo()
    model_path = _resolve_model(args.model)
    yolo = YOLO(str(model_path))

    export_kwargs: dict[str, Any] = {
        "format": args.format,
        "imgsz": args.imgsz,
        "device": args.device or None,
    }
    if args.format == "rknn":
        export_kwargs["name"] = args.rknn_target

    exported = yolo.export(**export_kwargs)
    print(f"Export finished: {exported}")


def build_parser() -> argparse.ArgumentParser:
    """构建所有子命令的 argparse 入口。"""
    parser = argparse.ArgumentParser(
        description="Download, run, train, and export YOLO .pt models for drone detection."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    models_parser = subparsers.add_parser("models", help="List built-in model presets.")
    models_parser.set_defaults(func=command_models)

    datasets_parser = subparsers.add_parser("datasets", help="List built-in dataset presets.")
    datasets_parser.set_defaults(func=command_datasets)

    dataset_parser = subparsers.add_parser("download-dataset", help="Download a built-in open dataset for testing.")
    dataset_parser.add_argument("--dataset-name", default="kc34251_drone_detection", choices=sorted(DATASET_REGISTRY))
    dataset_parser.add_argument("--limit", type=int, default=0, help="Limit image count. 0 means download all available files.")
    dataset_parser.add_argument("--workers", type=int, default=8)
    dataset_parser.add_argument("--force", action="store_true", help="Redownload existing files.")
    dataset_parser.set_defaults(func=command_download_dataset)

    download_parser = subparsers.add_parser("download", help="Download a built-in pretrained .pt model.")
    download_parser.add_argument("--model-name", default="flying_objects_yolov8m", choices=sorted(MODEL_REGISTRY))
    download_parser.add_argument("--force", action="store_true", help="Redownload even when the file exists.")
    download_parser.set_defaults(func=command_download)

    detect_parser = subparsers.add_parser("detect", help="Run detection on an image, video, folder, URL, or camera.")
    detect_parser.add_argument("--model", default="flying_objects_yolov8m", help="Model preset name or .pt path.")
    detect_parser.add_argument("--source", default="0", help="Image/video/folder/URL/camera index. Use 0 for webcam.")
    detect_parser.add_argument("--conf", type=float, default=0.25)
    detect_parser.add_argument("--iou", type=float, default=0.7)
    detect_parser.add_argument("--imgsz", type=int, default=960)
    detect_parser.add_argument("--device", default="", help="Examples: cpu, 0, 0,1. Empty lets Ultralytics choose.")
    detect_parser.add_argument("--classes", default=None, help="Comma-separated class indexes, e.g. 0 for drone only.")
    detect_parser.add_argument("--drone-only", action="store_true", help="Use the preset drone class ids.")
    detect_parser.add_argument("--show", action="store_true", help="Open an OpenCV preview window.")
    detect_parser.add_argument("--save-txt", action="store_true", help="Save YOLO-format prediction labels.")
    detect_parser.add_argument("--save-conf", action="store_true", help="Save confidence values with labels.")
    detect_parser.add_argument("--name", default="drone_predict")
    detect_parser.add_argument("--exist-ok", action="store_true", help="Reuse the output folder name.")
    detect_parser.set_defaults(func=command_detect)

    train_parser = subparsers.add_parser("train", help="Fine-tune a .pt model on a YOLO dataset.")
    train_parser.add_argument("--model", default="flying_objects_yolov8m", help="Model preset name or .pt path.")
    train_parser.add_argument("--data", required=True, help="YOLO dataset yaml.")
    train_parser.add_argument("--epochs", type=int, default=100)
    train_parser.add_argument("--imgsz", type=int, default=960)
    train_parser.add_argument("--batch", type=int, default=8)
    train_parser.add_argument("--device", default="")
    train_parser.add_argument("--name", default="drone_train")
    train_parser.add_argument("--exist-ok", action="store_true")
    train_parser.set_defaults(func=command_train)

    val_parser = subparsers.add_parser("val", help="Evaluate a .pt model on a YOLO dataset.")
    val_parser.add_argument("--model", default="flying_objects_yolov8m", help="Model preset name or .pt path.")
    val_parser.add_argument("--data", required=True, help="YOLO dataset yaml.")
    val_parser.add_argument("--imgsz", type=int, default=640)
    val_parser.add_argument("--batch", type=int, default=8)
    val_parser.add_argument("--device", default="")
    val_parser.add_argument("--classes", default=None, help="Comma-separated class indexes.")
    val_parser.add_argument("--drone-only", action="store_true", help="Use the preset drone class ids.")
    val_parser.add_argument("--name", default="drone_val")
    val_parser.add_argument("--exist-ok", action="store_true")
    val_parser.set_defaults(func=command_val)

    export_parser = subparsers.add_parser("export", help="Export a .pt model to ONNX or RKNN.")
    export_parser.add_argument("--model", default="flying_objects_yolov8m", help="Model preset name or .pt path.")
    export_parser.add_argument("--format", default="onnx", choices=["onnx", "rknn", "engine", "openvino"])
    export_parser.add_argument("--imgsz", type=int, default=960)
    export_parser.add_argument("--device", default="")
    export_parser.add_argument("--rknn-target", default="rk3576", help="Used only with --format rknn.")
    export_parser.set_defaults(func=command_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
