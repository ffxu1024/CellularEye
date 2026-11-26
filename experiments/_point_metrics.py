"""Box-size-independent RD point labels and confidence-ranked point metrics.

Coordinates are continuous original-image bin indices: d=x*W-.5,
r=(1-y)*H-.5. No image resizing or physical-unit assumption is made here.
"""
import math


def label_points(text, width, height):
    points = []
    for line in text.splitlines():
        if not line.strip():
            continue
        values = list(map(float, line.split()))
        if len(values) != 5 or not all(math.isfinite(v) for v in values):
            raise ValueError("Expected finite class,x,y,w,h labels")
        cls, x, y, w, h = values
        if cls != 0 or not 0 <= x <= 1 or not 0 <= y <= 1 or not 0 < w <= 1 or not 0 < h <= 1:
            raise ValueError("Expected class 0 and normalized valid coordinates")
        points.append([x * width - .5, (1 - y) * height - .5])
    return points


def evaluate_points(truth, predictions, gate=5., threshold=.25):
    """Euclidean-bin gate, confidence-greedy 1:1 matching, all-points AP.

    truth: {image_id: [[d,r], ...]}; predictions: same keys, [[d,r,score],...].
    Every frame must be explicitly present, including empty predictions.
    Equal scores are accumulated as one PR operating point (no tie AP gain).
    """
    if not math.isfinite(gate) or gate <= 0 or not 0 <= threshold <= 1:
        raise ValueError("Invalid gate/threshold")
    if not truth or set(truth) != set(predictions):
        raise ValueError("Predictions must cover every manifest frame exactly")
    ranked = []
    for image, points in predictions.items():
        for point in points:
            if len(point) != 3 or not all(math.isfinite(v) for v in point) or not 0 <= point[2] <= 1:
                raise ValueError("Expected finite d,r,score with score in [0,1]")
            ranked.append((point[2], image, point[0], point[1]))
    ranked.sort(key=lambda p: (-p[0], p[1], p[2], p[3]))
    used = {image: set() for image in truth}
    total = sum(len(points) for points in truth.values())
    tp = fp = selected_tp = selected_fp = 0
    errors, curve = [], []
    for index, (score, image, d, r) in enumerate(ranked):
        candidates = [(math.hypot(d - g[0], r - g[1]), j)
                      for j, g in enumerate(truth[image]) if j not in used[image]]
        error, match = min(candidates, default=(math.inf, -1))
        if error <= gate:
            used[image].add(match)
            tp += 1
            if score >= threshold:
                selected_tp += 1
                errors.append((abs(d - truth[image][match][0]), abs(r - truth[image][match][1]), error))
        else:
            fp += 1
            if score >= threshold:
                selected_fp += 1
        if index + 1 == len(ranked) or ranked[index + 1][0] != score:
            curve.append((tp / total if total else 0., tp / (tp + fp)))
    envelope, ap = 0., 0.
    for index in range(len(curve) - 1, -1, -1):
        recall, precision = curve[index]
        envelope = max(envelope, precision)
        ap += (recall - (curve[index - 1][0] if index else 0.)) * envelope
    precision = selected_tp / (selected_tp + selected_fp) if selected_tp + selected_fp else 0.
    recall = selected_tp / total if total else None
    return {
        "gate_bins": gate, "confidence": threshold, "frames": len(truth),
        "targets": total, "empty_frames": sum(not p for p in truth.values()),
        "TP": selected_tp, "FP": selected_fp, "FN": total - selected_tp,
        "precision": precision, "recall": recall,
        "F1": 2 * precision * recall / (precision + recall) if recall and precision else 0.,
        "point_AP": ap if total else None, "FP_per_frame": selected_fp / len(truth),
        "doppler_MAE_bins_TP": sum(e[0] for e in errors) / len(errors) if errors else None,
        "range_MAE_bins_TP": sum(e[1] for e in errors) / len(errors) if errors else None,
        "center_MAE_bins_TP": sum(e[2] for e in errors) / len(errors) if errors else None,
        "doppler_RMSE_bins_TP": math.sqrt(sum(e[0] ** 2 for e in errors) / len(errors)) if errors else None,
        "range_RMSE_bins_TP": math.sqrt(sum(e[1] ** 2 for e in errors) / len(errors)) if errors else None,
        "center_RMSE_bins_TP": math.sqrt(sum(e[2] ** 2 for e in errors) / len(errors)) if errors else None,
    }
