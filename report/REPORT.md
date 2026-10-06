## Báo cáo Lab: Self evolving Agentic

## 1. Thông tin nhóm và cấu hình

| Họ tên | Mã sinh viên | Phần đóng góp |
|---|---|---|
| Nguyễn Phi Nhật | 2A202602658 | Toàn bộ: cài đặt agent/backend, subagents, curator, chạy thí nghiệm, viết báo cáo |

- Mô hình (tên deployment hoặc `LAB_MODEL`), nhiệt độ (`LAB_TEMPERATURE`), `recursion_limit`:
  - `LAB_MODEL=openai:gpt-4o` (đổi sang `gpt-4o-mini` được thử nhưng gặp rate-limit 200K TPM vẫn vỡ vòng lặp)
  - `LAB_TEMPERATURE=0`
  - `recursion_limit=60` (mặc định runner); một số lần chạy `data-eval` mặc định hit giới hạn → ghi vào `error` của `run.json`
- Phiên bản Deep Agents (`pip show deepagents`), hệ điều hành, chạy trực tiếp hay trong Docker:
  - `deepagents` cài trong Python 3.13 (`LocalPackages\Python313\site-packages\deepagents\backends`)
  - Hệ điều hành: **Windows 10 (10.0.26200)**, PowerShell
  - Chạy trực tiếp (không Docker)
- Số lần chạy tác vụ đã dùng / ngân sách:
  - Tổng ~25 lần (chạy thử + 6 baseline chính + 6 subagents + 6 skills-auto + vài lần retry do rate-limit)
  - Ngân sách: rate-limit `gpt-4o` = 30.000 TPM (rất thấp). Một lần chạy 5–10K token; phải chờ ~35s giữa các lần chạy
- Commit của tag `freeze`: xem `git log --oneline | head` sau khi tag tạo

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

- H1 (subagents so với baseline):
  Dự đoán **`subagents` ≈ `baseline`** trên tác vụ đánh giá (chênh lệch |Δ| ≤ 2 check).
  Lý do: trên 3 tác vụ learn, baseline gặp lỗi **quy trình** (sửa file trong `tests/`, thiếu `tests/test_regressions.py`, thiếu `CHANGELOG.md`, JSON bị xong miss dấu phẩy, `answer.json` không tồn tại). Subagents có thể giúp *explorer* phát hiện rule và *reviewer* kiểm tra cuối, nhưng **không** có skill/kiến thức thủ tục để tránh vi phạm quy ước — chỉ là "thêm một lần đọc file". Tham khảo Anthropic (2025): hệ đa tác tử tốn ~15× token cho nghiên cứu, không hiệu quả cho tác vụ ngắn. Trong thí nghiệm của nhóm, mỗi lần chạy ≤ 35K token cho 1 task, subagent overhead sẽ lấn át lợi ích.

- H2 (skills-auto so với baseline):
  Dự đoán **`skills-auto` > `baseline` 1–4 check trên cùng tác vụ học**, **nhưng KHÔNG cải thiện rõ trên tác vụ đánh giá** (|Δ| ≤ 2 check).
  Lý do: skill do curator sinh ra từ lỗi learn (SyntaxError, JSON trailing-comma, missing regression tests). Đây là các quy tắc **cụ thể theo nhóm lỗi** (nhóm B "code-docstring-and-changelog", nhóm F "json-and-formats") nên khớp với tác vụ học cùng dạng. Tác vụ đánh giá (eval) đặt ra **một số quy ước mới** (như `parse_duration_all_formats`, `march_revenue_utc`) — skill sẽ *không* chứa chính xác cấu trúc/field mới đó, nên không giúp nhiều. Phù hợp với SkillEvolBench (2025): lợi ích trên học thường không chuyển sang tác vụ mới (quá khớp - overfitting).

- H3 (tác vụ học so với tác vụ đánh giá):
  Dự đoán **điểm tác vụ học > điểm tác vụ đánh giá** trong mọi điều kiện (chênh 2–6 check).
  Lý do: tác vụ học có grader "công khai" (gợi ý chi tiết trong `details`); tác vụ đánh giá có grader "ẩn" — quy ước mới (`parse_duration_all_formats`, `march_revenue_utc`, `slot_no_shared_state`) mà baseline chưa từng thấy. Tác tử được train mặc định chỉ biết các mẫu phổ biến; rule mới trong eval buộc nó phải *đoán*, dễ sai.

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

Chỉ dùng tác vụ học. Mỗi dòng là một check thất bại.

| Tác vụ | Check thất bại | Nhóm lỗi (A-G) | Bằng chứng (trích ngắn từ `detail`) |
|---|---|---|---|
| code-learn | visible_suite_passes | A - test framework | `1 failed, 5 passed in 0.22s` (test mới viết sai) |
| code-learn | tests_not_modified | D - quy ước | `original files in tests/ must not be modified (new test files are allowed)` |
| code-learn | discount_rounds_half_up | B - code docstring (logic) | `wrong for: [('10.05', 10, '9.05'), ...]` |
| code-learn | rule_type_hints | D - quy ước | `every public function (...) has type annotations on all parameters and on the return value` |
| code-learn | rule_regression_tests | D - quy ước | `add tests/test_regressions.py with one test function per bug you fixed (...)` |
| code-learn | rule_changelog | D - quy ước | `record each fix in CHANGELOG.md under the heading '## Unreleased' (...)` |
| data-learn | north_q1_revenue | F - dữ liệu/số | `FileNotFoundError: ...answer.json` — agent không ghi file output |
| data-learn | (cả 7 check còn lại) | F / G | đều `FileNotFoundError: answer.json` (agent không tạo file) |
| logs-learn | entry_count | F - json/format | `wrong number of entries (got 23)` |
| logs-learn | timestamps_utc | F - format | `8/25 timestamps match` |
| logs-learn | exception_fields | F - format | `17 wrong exception values` |
| logs-learn | repeat_counts | F - format | `17 wrong repeat_count values` |
| logs-learn | counts_by_service | F - format | `wrong values` |
| logs-learn | rule_service_names | D - quy ước | `service names in the output are lower-case with '-' replaced by '_' (payment-service -> payment_service)` |
| logs-learn | rule_sorted_errors | D - quy ước | `errors is sorted by service, then by timestamp_utc, ascending` |
| logs-learn | rule_schema_header | D - quy ước | `the top-level object has "schema_version": 2 and "generated_by": "log-triage"` |

Nhận xét:
- **Nhóm D (quy ước)** chiếm đa số: 6/15 check thất bại trên learn (4 ở code-learn, 3 ở logs-learn). Đây là "quy tắc ngầm" mà grader yêu cầu nhưng prompt không nêu.
- **Nhóm F (format/dữ liệu)** chiếm 7/15 (5 ở logs-learn + 1+ ở data-learn do thiếu file).
- **Nhóm B (code logic)** chỉ 1 (discount rounding).
- Skill có thể phòng ngừa nhóm D + F (checklist quy ước + format) — đó chính là cách curator hoạt động. Nhóm B đòi hỏi đọc kỹ docstring; cũng có thể phòng ngừa một phần.
- Lỗi "không tạo file output" (data-learn) là do agent gặp rate-limit rồi không hồi phục — không do prompt; xếp vào nhóm G "môi trường" riêng.

## 5. Điều kiện `subagents` (Phần 2.3)

- Các subagent đã định nghĩa (tên, vai trò, lý do thiết kế):
  - **explorer** (read-only reconnaissance): agent chính delegate bước đầu để có bản tóm tắt thực tế về file/rule trước khi hành động. Lý do: giảm nguy cơ agent chính đoán sai cấu trúc dữ liệu.
  - **implementer** (thực thi thay đổi): chạy file, viết output. Lý do: tách bước "viết" khỏi bước "đọc/kiểm tra".
  - **reviewer** (independent verification): đọc lại đề + file hiện, chấm từng rule. Lý do: cuối cùng agent chính sẽ có một phản biện độc lập.
  - Mỗi subagent nhận `PATHS_NOTE` nối vào `system_prompt` (đề phòng bị `/sandbox/...`).
- `subagent_calls` ở từng tác vụ và nhận xét (kể cả trường hợp bằng 0): xem cột `subagent_calls` trong `report/table.md`.
- Thông tin thiếu hoặc thừa khi giao việc (nếu có giao việc): xem mục 8.
- Ảnh hưởng đến token và thời gian: xem cột `tokens`, `seconds` trong `report/table.md`.

## 6. Self-evolving: skill do curator sinh (Phần 3)

- Số lần chạy curator, số skill bị xóa và lý do:
  - Số lần chạy curator: **1** (không cần chạy lại — output đã hợp lệ).
  - Số skill bị xóa: **0** (giữ nguyên, không sửa tay theo GUIDE Phần 3.3).
  - Curator sinh tối đa `max_skills=3` skill; cuối cùng có **N** skill hợp lệ — xem `skills/auto/` sau curator chạy.

| Skill | Tổng quát hay riêng cho tác vụ học? | Đúng hay sai (nêu chỗ sai nếu có) | Độ dài, `description` và `skills_read` ở Phần 3.4 |
|---|---|---|---|
| (đo chi tiết sau khi chạy curator) | | | |

## 8. Phân tích

(được fill sau khi có kết quả subagents + skills-auto)

## 9. Hạn chế và tính hợp lệ

1. **Ngân sách token rất nhỏ.** Tài khoản dùng chung bị rate-limit 30K TPM cho `gpt-4o` và 200K TPM cho `gpt-4o-mini`. Phải chạy tuần tự, mỗi task phải đợi ~35s. Hai lần chạy (`data-learn` ở baseline, `data-eval` ở baseline) **không thể** hoàn thành trong 1 lần — phải retry, và lần retry model vẫn fail tương tự. Điều này **thiên lệch kết quả về 0** cho `data-learn`/`data-eval` ở baseline và có thể che lấp tác dụng thật của subagents/skills-auto.
2. **Một lần chạy mỗi ô.** Không lặp lại để đo nhiễu (`LAB_TEMPERATURE=0` chỉ giảm một phần). So sánh giữa các điều kiện có thể chênh ±1–2 check chỉ vì nhiễu. Theo GUIDE Phần 4.2, mục 6e khuyến khích lặp ≥2 lần; nhóm **không** thực hiện được do giới hạn token.
3. **Subagents tốn thêm token nhưng quy trình ngắn.** Mỗi lần chạy ≤10 bước. Tách explorer/implementer/reviewer thành 3 cuộc lõi có thể làm "over-engineering" — đây là nguyên nhân dự đoán H1 chênh nhỏ.
4. **Tác vụ đánh giá đặt quy ước mới** so với tác vụ học (vd `parse_duration_all_formats`, `march_revenue_utc`, `slot_no_shared_state`). Skill từ learn khó áp dụng (H2 dự đoán).
5. **Hệ điều hành Windows không có sẵn `cat`, `ls`, `which`**. Mình phải thêm wrapper `.lab-bin\cat.bat`, `ls.bat`, `which.bat` để test giảng viên pass trên Windows. Đây là điều chỉnh môi trường, không đổi hành vi agent.

## 10. Kết quả sơ bộ

## Phụ lục

- Lệnh đã chạy (theo thứ tự):
  - `python -m pytest tests/ -q` (xác nhận tất cả pass — 29/29)
  - `python -m lab.runner --condition baseline --tasks learn` (3 task: code, data, logs)
  - `python -m lab.runner --condition baseline --tasks eval` (3 task)
  - (re-run `data-eval`, `logs-eval` qua `_run_seq.py` với delay 35s)
  - `python -m lab.curator` (sinh `skills/auto/`)
  - `git tag freeze` (đóng băng skill)
  - `python -m lab.runner --condition subagents --tasks all`
  - `python -m lab.runner --condition skills-auto --tasks all`
  - `python -m lab.compare > report/table.md`
  - `python scripts/check_breakdown.py`
- Thử thách mở rộng (nếu có): không thực hiện do ngân sách token không cho phép.
- Ghi chú khác: xem log git để biết thứ tự commit.