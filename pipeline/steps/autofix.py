"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    fixes = []
    errors = [issue for issue in issues if issue.severity == ERROR]

    drop_line_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    remove_image_codes = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}

    # Xoá ảnh trước để các issue dòng của chính ảnh đó không còn được xử lý.
    removed_stems = []
    for issue in errors:
        should_remove = (
            issue.code in remove_image_codes
            or issue.code.startswith("DUP_IMAGE_")
        )
        if should_remove and issue.image not in removed_stems:
            removed_stems.append(issue.image)

    removed_set = set(removed_stems)
    for stem in removed_stems:
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)
        before = []

        if image_path is not None and image_path.exists():
            before.append(image_path.name)
            image_path.unlink()
        if label_path.exists():
            before.append(label_path.name)
            label_path.unlink()

        if before:
            fixes.append({
                "image": stem,
                "line": None,
                "action": "remove_image",
                "before": ", ".join(before),
                "after": "đã xoá khỏi dataset",
            })

    # Ảnh thiếu nhãn phải chuyển cho người; tuyệt đối không tạo file rỗng.
    for issue in errors:
        if issue.code == "MISSING_LABEL_FILE" and issue.image not in removed_set:
            fixes.append({
                "image": issue.image,
                "line": issue.line,
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    # Gom issue theo file và số dòng gốc, sau đó mỗi file chỉ được ghi lại một lần.
    line_issues = defaultdict(lambda: defaultdict(set))
    for issue in errors:
        if issue.image in removed_set or issue.line is None:
            continue
        if issue.code in drop_line_codes or issue.code == "BOX_OUT_OF_IMAGE":
            line_issues[issue.image][issue.line].add(issue.code)

    for stem, issues_by_line in line_issues.items():
        label_path = ds.label_path(stem)
        if not label_path.exists():
            continue

        original_lines = label_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        new_lines = []

        for line_number, original_line in enumerate(original_lines, 1):
            codes = issues_by_line.get(line_number, set())

            # Xoá dòng ưu tiên hơn clip nếu một dòng có nhiều lỗi.
            if codes & drop_line_codes:
                fixes.append({
                    "image": stem,
                    "line": line_number,
                    "action": "drop_line",
                    "before": original_line,
                    "after": "",
                })
                continue

            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    class_id, cx, cy, width, height = parse_yolo_line(original_line)
                except ValueError:
                    fixes.append({
                        "image": stem,
                        "line": line_number,
                        "action": "drop_line",
                        "before": original_line,
                        "after": "",
                    })
                    continue

                left = max(0.0, cx - width / 2)
                top = max(0.0, cy - height / 2)
                right = min(1.0, cx + width / 2)
                bottom = min(1.0, cy + height / 2)
                new_width = right - left
                new_height = bottom - top

                if new_width <= 0 or new_height <= 0:
                    fixes.append({
                        "image": stem,
                        "line": line_number,
                        "action": "drop_line",
                        "before": original_line,
                        "after": "",
                    })
                    continue

                new_cx = (left + right) / 2
                new_cy = (top + bottom) / 2
                new_line = (
                    f"{class_id} {new_cx:.6f} {new_cy:.6f} "
                    f"{new_width:.6f} {new_height:.6f}"
                )
                new_lines.append(new_line)
                fixes.append({
                    "image": stem,
                    "line": line_number,
                    "action": "clip_box",
                    "before": original_line,
                    "after": new_line,
                })
                continue

            new_lines.append(original_line)

        content = "\n".join(new_lines)
        if new_lines:
            content += "\n"
        label_path.write_text(content, encoding="utf-8")

    # Sửa danh sách tên lớp đúng theo cấu hình dự án.
    if any(issue.code == "BAD_CLASS_NAME" for issue in errors):
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        old_names = data.get("names")
        new_names = list(cfg["classes"])
        if old_names != new_names:
            data["names"] = new_names
            ds.yaml_path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            fixes.append({
                "image": "data.yaml",
                "line": None,
                "action": "rename_classes",
                "before": str(old_names),
                "after": str(new_names),
            })

    return fixes
