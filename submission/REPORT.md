# Báo cáo Day 09 - Đào Duy Hiếu - 2A202603235

## 1. Kết luận trước
Pipeline kết luận **Hold**. Từ 224 ảnh đầu vào, bước intake giữ lại
193 ảnh và loại 31 ảnh hỏng, quá nhỏ, trùng hoặc rò rỉ với tập đánh giá.
Sau autofix và vòng duyệt mô phỏng 80 ảnh, dataset không còn lỗi bắt
buộc nhưng vẫn còn 34/193 ảnh có cảnh báo, tương đương 17,62%, vượt
ngưỡng Hold 10%.

Dataset tại `submission/export/clean_v1` là bản nháp phục vụ thí
nghiệm, chưa đủ điều kiện phát hành.

## 2. Lỗi và phân việc
| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Lý do |
|---|---:|---|---|
| `BAD_CLASS_ID` | 6 dòng/6 ảnh | Máy | ID ngoài 0–3, xóa dòng |
| `BAD_CLASS_NAME` | 2 issue/1 file | Máy | Ghi lại names trong YAML |
| `BAD_FORMAT` | 3 dòng/3 ảnh | Máy | Dòng không parse được, xóa |
| `BAD_SIZE` | 3 ảnh | Máy | Ảnh không đạt kích thước |
| `BOX_HUGE` | 3 ảnh | Người | Cần đánh giá box có hợp lý |
| `BOX_OUT_OF_IMAGE` | 8 dòng/8 ảnh | Máy | Clip box vào ảnh |
| `BOX_TINY` | 6 issue/4 ảnh | Người | Cần xem vật nhỏ có cần gán |
| `BOX_ZERO` | 4 dòng/4 ảnh | Máy | Box không có diện tích |
| `CORRUPT_IMAGE` | 2 ảnh | Máy | Ảnh không đọc được |
| `DUP_BOX` | 7 dòng/7 ảnh | Máy | Xóa box trùng |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy | Xóa bản trùng |
| `DUP_IMAGE_NEAR` | 7 ảnh | Máy | Xóa bản gần trùng |
| `EMPTY_LABEL` | 11 ảnh | Người | Xác nhận ảnh nền hay chưa gán |
| `LEAK_TEST` | 11 ảnh | Máy | Loại ảnh trùng tập đánh giá |
| `MISSING_LABEL_FILE` | 6 ảnh | Người | Máy không được tự bịa nhãn |
| `POSSIBLE_FALSE_POS` | 28 issue/26 ảnh | Người | Model chỉ đưa ý kiến |
| `POSSIBLE_LOOSE_BOX` | 27 issue/23 ảnh | Người | Cần đánh giá vị trí box |
| `POSSIBLE_MISSING` | 53 issue/52 ảnh | Người | Cần xác nhận vật bị thiếu |
| `POSSIBLE_WRONG_CLASS` | 17 ảnh | Người | Cần xác nhận class thật |

- `05_review_queue.csv` xếp ảnh theo điểm ưu tiên giảm dần. Mỗi cảnh báo
được nhân với trọng số trong `review.weights`; cảnh báo có confidence
của model còn được nhân thêm với `(1 + confidence)`. Các ảnh đã được
máy sửa dòng cũng được cộng điểm để con người kiểm tra lại. Đặc biệt,
ảnh chưa có file nhãn nhận mã `NEEDS_LABEL` với trọng số 10 vì chỉ
người mới có thể gán nhãn.
- Vì vậy, `img_0020` đứng đầu với điểm 11,524 do đồng thời có
`FIXED_DROP_LINE`, `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS`.
Sáu ảnh `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`
và `img_0219` đứng tiếp theo với điểm 10 vì đều cần người gán nhãn
(`NEEDS_LABEL`).
- Với ngân sách 80 ảnh, người duyệt đã xem 80/121 ảnh trong hàng đợi.
Trong đó, 74 ảnh chứa tổng cộng 94 issue ngữ nghĩa: 52
`POSSIBLE_MISSING`, 17 `POSSIBLE_WRONG_CLASS`, 13
`POSSIBLE_FALSE_POS` và 12 `POSSIBLE_LOOSE_BOX`. Một ảnh có thể chứa
nhiều issue cùng loại hoặc khác loại, nên số issue lớn hơn số ảnh.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall trước => sau | Lý do |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | 2 | 16 | P: 1.00 -> 1.00; R: 0.50 -> 0.83 | Tăng recall ảnh gần trùng mà chưa tạo FP trên calib |
| `second_opinion.conf` | 0.25 | 0.6 | Missing P: 0.50 -> 0.57, R: 1.00 -> 1.00; Wrong-class P: 0.56 -> 0.62, R: 0.83 -> 0.83 | Giảm cảnh báo sai nhưng vẫn ưu tiên không bỏ sót missing |

Tập calibration chỉ có 39 ảnh nên có thể không đại diện cho dữ liệu
raw. `phash_dist=16` có precision 1.00 trên calibration nhưng vẫn có
thể coi hai ảnh khác nhau có bố cục giống nhau là gần trùng. Vì vậy
cần mở xem các cặp ảnh bị loại, không chỉ dựa vào F1.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
Pipeline chính dùng ngân sách duyệt 80 ảnh và kết luận **Hold**: vòng
cuối không còn ERROR nhưng còn 34/193 ảnh cảnh báo.

Trong thí nghiệm `--budget 0`, không ảnh nào được người duyệt xử lý,
nên sáu lỗi bắt buộc còn lại sau autofix không được giải quyết. Gate
kết luận **Rework**, trả mã thoát 20 và không xuất dataset. Điều này
chứng minh lỗi bắt buộc thực sự chặn pipeline.

Hai điểm mù:
1. Model second-opinion có thể mắc cùng lỗi với người gán nên không
phát hiện được nhầm lớp hoặc thiếu nhãn.
2. Perceptual hash có thể bỏ sót ảnh trùng đã crop, xoay hoặc biến đổi
mạnh; ngược lại, hai ảnh khác nhau có bố cục tương tự có thể bị xem là
gần trùng.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Đã train
Result: 
| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 193 | 2 | 0.730 ± 0.001 | 0.501 ± 0.001 | 0.800 ± 0.019 | 0.624 ± 0.012 |

Chênh mAP50 (clean − raw) = **+0.004**.

Clean tăng mAP50 từ 0.7258 lên 0.7301, chênh +0.0043, và tăng
precision từ 0.7635 lên 0.8001. Tuy nhiên, mAP50-95 giảm từ 0.5117
xuống 0.5007 và recall giảm từ 0.6490 xuống 0.6243.

Kết quả cho thấy sự đánh đổi: model clean dự đoán thận trọng hơn và
có precision cao hơn nhưng bỏ sót nhiều vật thể hơn. Với chỉ hai seed,
mức tăng mAP50 nhỏ và các chỉ số thay đổi trái chiều, chưa đủ bằng
chứng để kết luận clean tốt hơn raw một cách ổn định.

Hai giả thuyết: pipeline loại nhãn nhiễu nên precision tăng; nhưng
clean chỉ còn 193 thay vì 224 ảnh nên có thể mất mẫu hữu ích, đặc biệt
ở lớp truck, khiến recall và mAP50-95 giảm. Cần chạy thêm seed và xem
AP theo từng lớp để kiểm chứng.

## 6. Quyết định và ghi chú AI
(a) Tôi giữ quyết định **Hold**. Để chuyển sang Release cần xử lý thêm ít
nhất 15 ảnh, đưa số ảnh chưa duyệt còn cảnh báo từ 34 xuống tối đa
19/193, tức là dưới 10%.

(b)Tôi dùng AI để hỗ trợ triển khai 4 module từ docstring và unit test.
Tôi kiểm tra bằng test riêng từng module, toàn bộ 79 test, pipeline
end-to-end và kết quả calibration. Một lỗi phát hiện trong quá trình
làm là pipeline trên Windows gặp `UnicodeEncodeError` khi chưa bật
UTF-8; sau khi đọc traceback, tôi đặt `PYTHONUTF8=1` và chạy lại. Tiếp theo tôi sử dụng AI để giải thích và review lại src code, tìm lỗi sai trong src code, sau đó yêu cầu AI sửa lại các lỗi đã phát hiện ra.

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
