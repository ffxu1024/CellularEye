"""Export YOLO box metrics and RD localization diagnostics.

The input results.csv supplies the fixed checkpoints, methods, and five seeds.
This script does not train or alter datasets/runs; it writes a separate report.
"""
import argparse
import csv
import os
from pathlib import Path

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONF = 0.25
IOU = 0.45
CENTRE_THRESHOLDS = (5.0, 10.0)


def relative(path):
    return Path(os.path.relpath(Path(path).resolve(), ROOT)).as_posix()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True, help="Published evaluation results.csv.")
    parser.add_argument("--test-yaml", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--groups", choices=("all", "all-and-each"), default="all-and-each",
                        help="Evaluate only the combined set, or combined plus every listed test trajectory.")
    parser.add_argument("--group", default=None, help="Run one named group when continuing a large multi-trajectory report.")
    parser.add_argument("--method", default=None, help="Run one displayed method when continuing a large report.")
    parser.add_argument("--device", default="0")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def runtime_yaml(path, image_dirs):
    items = [relative(item) for item in image_dirs]
    path.write_text(yaml.safe_dump({"path": ".", "train": items, "val": items, "test": items,
                                    "names": {0: "uav"}}, sort_keys=False), encoding="utf-8")


def write_summary(path, rows):
    """Write a method/group mean, SD and 95% CI table from the five seed rows."""
    metrics = ("mAP50-95", "mAP50", "mAP75", "Precision", "Recall", "F1", "TP_conf0.25_iou0.45",
               "FP_conf0.25_iou0.45", "FN_conf0.25_iou0.45", "NoPrediction_conf0.25",
               "DopplerMAE_bins_detected", "RangeMAE_bins_detected", "CentreMeanError_bins_detected",
               "CentreMedianError_bins_detected", "CentreSuccess_le_5_bins", "CentreSuccess_le_10_bins")
    output = []
    for group, method in sorted({(row["Group"], row["Method"]) for row in rows}):
        selected = [row for row in rows if row["Group"] == group and row["Method"] == method]
        for metric in metrics:
            if metric.startswith("CentreSuccess"):
                values = [100 * float(row[metric]) / float(row["Frames"]) for row in selected]
                metric_name = metric.replace("CentreSuccess", "C") + "_percent"
            else:
                values = [float(row[metric]) for row in selected if row[metric] != ""]
                metric_name = metric
            mean = float(np.mean(values)) if values else ""
            std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0 if values else ""
            output.append({"Group": group, "Method": method, "Metric": metric_name, "N": len(values),
                           "Mean": mean, "Std": std,
                           "CI95": 1.96 * std / np.sqrt(len(values)) if len(values) > 1 else 0.0 if values else ""})
    write_csv(path, output, ("Group", "Method", "Metric", "N", "Mean", "Std", "CI95"))


def main():
    args = parse_args()
    os.chdir(ROOT)
    results_path, test_yaml, output = (ROOT / args.results).resolve(), (ROOT / args.test_yaml).resolve(), (ROOT / args.output_dir).resolve()
    with results_path.open(newline="", encoding="utf-8") as stream:
        runs = list(csv.DictReader(stream))
    required = {"Method", "Seed", "Run", "Weights"}
    if not runs or not required.issubset(runs[0]):
        raise ValueError(f"{relative(results_path)} is not an evaluation results.csv")
    config = yaml.safe_load(test_yaml.read_text(encoding="utf-8")) or {}
    test_items = config.get("test")
    test_items = [test_items] if isinstance(test_items, str) else test_items
    if not isinstance(test_items, list) or not test_items:
        raise ValueError(f"{relative(test_yaml)} requires non-empty test paths")
    dataset_root = Path(config.get("path", "."))
    if dataset_root.is_absolute() or any(Path(item).is_absolute() for item in test_items):
        raise ValueError("Dataset YAML paths must remain repository-relative")
    image_dirs = [ROOT / dataset_root / item for item in test_items]
    groups = {"all": image_dirs}
    if args.groups == "all-and-each" and len(image_dirs) > 1:
        groups.update({directory.parent.parent.name: [directory] for directory in image_dirs})
    for directory in image_dirs:
        if not directory.is_dir() or not list(directory.glob("*.png")):
            raise FileNotFoundError(f"Missing PNG test directory: {relative(directory)}")
    for row in runs:
        checkpoint = ROOT / row["Run"] / "weights" / f"{row['Weights']}.pt"
        if not checkpoint.is_file():
            raise FileNotFoundError(f"Missing checkpoint: {relative(checkpoint)}")
    print(f"Validated {len(runs)} checkpoint rows and {len(image_dirs)} test directories in {relative(test_yaml)}.")
    if args.dry_run:
        return

    if output.exists() and any(output.iterdir()) and not args.resume:
        raise FileExistsError(f"Output exists: {relative(output)}; choose another directory or --resume.")
    output.mkdir(parents=True, exist_ok=True)
    runtime = output / "runtime_yamls"
    runtime.mkdir(exist_ok=args.resume)
    image_columns = ("Group", "Image", "Method", "Seed", "Predictions_conf0.25", "DopplerError_bins",
                     "RangeError_bins", "CentreError_bins", "WidthError_bins", "HeightError_bins")
    metric_columns = ("Group", "Method", "Seed", "Frames", "mAP50-95", "mAP50", "mAP75", "Precision", "Recall", "F1",
                      "TP_conf0.25_iou0.45", "FP_conf0.25_iou0.45", "FN_conf0.25_iou0.45", "NoPrediction_conf0.25",
                      "DopplerMAE_bins_detected", "RangeMAE_bins_detected", "CentreMeanError_bins_detected",
                      "CentreMedianError_bins_detected", "CentreSuccess_le_5_bins", "CentreSuccess_le_10_bins")
    image_path, metric_path = output / "per_image_localisation.csv", output / "per_seed_metrics.csv"
    if args.resume and metric_path.is_file():
        with metric_path.open(newline="", encoding="utf-8") as stream:
            metrics_rows = list(csv.DictReader(stream))
        with image_path.open(newline="", encoding="utf-8") as stream:
            image_rows = list(csv.DictReader(stream))
    else:
        metrics_rows, image_rows = [], []
    completed = {(row["Group"], row["Method"], str(row["Seed"])) for row in metrics_rows}

    from ultralytics import YOLO
    from ultralytics.data import utils as data_utils
    from ultralytics.models.yolo.detect import DetectionValidator
    from ultralytics.utils import ops
    data_utils.DATASETS_DIR = ROOT

    class Collector(DetectionValidator):
        records = None

        def update_metrics(self, preds, batch):
            super().update_metrics(preds, batch)
            for sample_index, pred in enumerate(preds):
                prepared = self._prepare_batch(sample_index, batch)
                # plots=False avoids image creation, so explicitly update the same native confusion matrix.
                self.confusion_matrix.process_batch(pred, prepared, conf=CONF, iou_thres=IOU)
                gt = ops.scale_boxes(prepared["imgsz"], prepared["bboxes"].clone(), prepared["ori_shape"],
                                     ratio_pad=prepared["ratio_pad"]).detach().cpu().numpy()
                boxes = self.scale_preds(pred, prepared)["bboxes"].detach().cpu().numpy()
                confidence = pred["conf"].detach().cpu().numpy()
                self.records.append((str(Path(prepared["im_file"]).resolve()), gt, boxes[confidence >= CONF]))

    methods = list(dict.fromkeys(row["Method"] for row in runs))
    for group, directories in groups.items():
        if args.group and group != args.group:
            continue
        dataset_yaml = runtime / f"{group}.yaml"
        runtime_yaml(dataset_yaml, directories)
        for run in sorted(runs, key=lambda row: (methods.index(row["Method"]), int(row["Seed"]))):
            if args.method and run["Method"] != args.method:
                continue
            key = (group, run["Method"], str(run["Seed"]))
            if key in completed:
                continue
            Collector.records = []
            checkpoint = ROOT / run["Run"] / "weights" / f"{run['Weights']}.pt"
            metric = YOLO(str(checkpoint)).val(validator=Collector, data=str(dataset_yaml), split="test", imgsz=(1024, 512),
                                               batch=16, workers=0, device=args.device, plots=False, project="/tmp",
                                               name="cellulareye_diagnostic_val", exist_ok=True, verbose=False)
            matrix = metric.confusion_matrix.matrix
            records = Collector.records
            errors = []
            for image, gt, predictions in records:
                if len(gt) != 1:
                    raise ValueError(f"Expected exactly one GT box in {relative(image)}")
                target = gt[0]
                tcx, tcy = (target[0] + target[2]) / 2, (target[1] + target[3]) / 2
                if len(predictions):
                    centres = np.column_stack(((predictions[:, 0] + predictions[:, 2]) / 2,
                                                (predictions[:, 1] + predictions[:, 3]) / 2))
                    index = int(np.argmin(np.linalg.norm(centres - (tcx, tcy), axis=1)))
                    box = predictions[index]
                    dx, dy = (box[0] + box[2]) / 2 - tcx, (box[1] + box[3]) / 2 - tcy
                    values = (dx, dy, float(np.hypot(dx, dy)), (box[2] - box[0]) - (target[2] - target[0]),
                              (box[3] - box[1]) - (target[3] - target[1]))
                    errors.append(values)
                else:
                    values = ("", "", "", "", "")
                image_rows.append(dict(zip(image_columns, (group, relative(image), run["Method"], run["Seed"],
                                                            len(predictions), *values))))
            values = np.asarray(errors, dtype=float)
            precision, recall = float(metric.box.mp), float(metric.box.mr)
            metrics_rows.append({"Group": group, "Method": run["Method"], "Seed": run["Seed"], "Frames": len(records),
                                 "mAP50-95": metric.box.map, "mAP50": metric.box.map50, "mAP75": metric.box.map75,
                                 "Precision": precision, "Recall": recall,
                                 "F1": 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall),
                                 "TP_conf0.25_iou0.45": int(matrix[0, 0]), "FP_conf0.25_iou0.45": int(matrix[0, 1]),
                                 "FN_conf0.25_iou0.45": int(matrix[1, 0]), "NoPrediction_conf0.25": len(records) - len(errors),
                                 "DopplerMAE_bins_detected": float(np.mean(np.abs(values[:, 0]))) if len(values) else "",
                                 "RangeMAE_bins_detected": float(np.mean(np.abs(values[:, 1]))) if len(values) else "",
                                 "CentreMeanError_bins_detected": float(np.mean(values[:, 2])) if len(values) else "",
                                 "CentreMedianError_bins_detected": float(np.median(values[:, 2])) if len(values) else "",
                                 "CentreSuccess_le_5_bins": int(np.sum(values[:, 2] <= CENTRE_THRESHOLDS[0])) if len(values) else 0,
                                 "CentreSuccess_le_10_bins": int(np.sum(values[:, 2] <= CENTRE_THRESHOLDS[1])) if len(values) else 0})
            write_csv(image_path, image_rows, image_columns)
            write_csv(metric_path, metrics_rows, metric_columns)
    write_summary(output / "summary.csv", metrics_rows)
    print(f"Saved diagnostics to {relative(output)}")


if __name__ == "__main__":
    main()
