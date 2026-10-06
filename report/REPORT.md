# Báo cáo Lab: Self evolving Agentic

## 1. Thông tin nhóm và cấu hình

| Họ tên | Mã sinh viên | Phần đóng góp |
|---|---|---|
| Nguyễn Phi Nhật | (2A202602658) | Toàn bộ lab (cá nhân) |

- Mô hình: `openai:gpt-4o-mini` (`LAB_MODEL=openai:gpt-4o-mini`), `LAB_TEMPERATURE=0`, `recursion_limit=50` (giảm từ 60 để tiết kiệm token).
- Phiên bản Deep Agents: `deepagents==0.7.21`; Python 3.13.14; **Windows 10**, chạy trực tiếp (không qua Docker). Backend shell đã được vá (`make_backend` thêm `C:\Program Files\Git\usr\bin` + thư mục `.lab-bin` chứa wrapper `cat.bat`, `which.bat`) để có sẵn các lệnh POSIX cơ bản (`cat`, `which`, `ls`, `head`, `tail`).
- Số lần chạy tác vụ: 6 lần (1 baseline × 3 học + 1 subagents × 3 học; phần eval sẽ chạy sau khi đóng băng). Ngân sách OpenAI gặp nhiều lần rate-limit 429 và 1 lần lỗi Cloudflare 520 (xem phụ lục).
- Commit của tag `freeze`: *(sẽ điền sau khi freeze)*.

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

- H1 (subagents so với baseline): Trên **tác vụ đánh giá**, `subagents` sẽ đạt điểm **ngang hoặc thấp hơn** `baseline` nhưng tốn **nhiều token hơn đáng kể** (ước tính gấp 1.5×–2×). Lý do: các tác vụ đánh giá thuộc cùng họ với tác vụ học, nên phân rã công việc (explorer/implementer/reviewer) không tăng chất lượng phân tích thêm nhiều; trong khi đó mỗi subagent sinh thêm system prompt và vòng lặp trao đổi làm phình chi phí. Căn cứ: kết quả `subagents` trên tập học ở Phần 5 cho thấy token tăng nhưng điểm tăng không tương xứng.
- H2 (skills-auto so với baseline): `skills-auto` sẽ **cải thiện đáng kể** điểm `rule_*` (check quy ước Acme) trên cả tập học lẫn tập đánh giá, nhưng **không cải thiện** (hoặc thậm chí giảm nhẹ) điểm check kỹ thuật — vì rule_* là quy ước thủ tục dễ mô tả bằng skill, còn check kỹ thuật phụ thuộc khả năng sinh mã của model. Căn cứ: phân loại lỗi ở mục 4 cho thấy phần lớn check thất bại thuộc nhóm E (rule) và nhóm A (bỏ sót spec); skill có thể khắc phục cả hai.
- H3 (tác vụ học so với tác vụ đánh giá): Tác vụ **học** sẽ đạt điểm cao hơn tác vụ **đánh giá** ở cùng điều kiện (đặc biệt `skills-auto`) do khả năng overfit của skill được sinh từ chính tập học, cộng thêm việc tác vụ đánh giá có thêm quy ước mới (chỉ có thể bắt được nếu skill tổng quát đủ). Chênh lệch này là ước lượng nhiễu thật của thí nghiệm.

## 3. Làm quen Deep Agents (Phần 0.3)

1. **Công cụ của tác tử mặc định**: 9 công cụ — nhóm tệp: `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`; nhóm shell: `execute`; điều phối subagent: `task`. Công cụ chạy lệnh shell là `execute`.
2. **Mô tả công cụ `task` (trích ngắn)**: *"Launch an ephemeral subagent to handle a complex, multi-step task. ... Each invocation is stateless by default: the agent sees only the prompt you give it and returns a single final report. Put full detail in the prompt and state exactly what it should return ... The agent's report is not shown to the user; relay a summary yourself."* Subagent `general-purpose` (mặc định) có **toàn bộ công cụ** như tác tử chính, nhưng **không thấy lịch sử hội thoại** của tác tử chính; nó chỉ thấy đúng prompt mà tác tử chính truyền vào.
3. **Hướng dẫn hành vi**:
   - Từ mô tả `task`: *"Launch multiple agents concurrently when their tasks are independent, using a single message with multiple tool calls."* → khuyến khích song song hóa các tác vụ con độc lập.
   - Từ mô tả `execute`: *"You MUST avoid using search commands like find and grep. Instead use the grep, glob tools to search. Use read_file rather than cat/head/tail."* → tác tử được khuyên dùng công cụ chuyên dụng thay vì shell cho thao tác đọc.

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

> Chỉ dùng tác vụ học. Mỗi dòng là một check thất bại.

| Tác vụ | Check thất bại | Nhóm lỗi (A-G) | Bằng chứng (trích ngắn từ `detail` hoặc vết) |
|---|---|---|---|
| code-learn | visible_suite_passes | B | `detail: "1 error in 0.27s"` — pytest fail, agent báo đã sửa nhưng không chạy lại để xác nhận |
| code-learn | tests_not_modified | F | `detail: "the original files in tests/ must not be modified (new test files are allowed)"` — agent không tạo test mới, hoặc tạo nhầm vị trí |
| code-learn | parse_price_all_formats | D / B | `detail: "SyntaxError: invalid syntax (pricing.py, line 25)"` — sửa lỗi giá nhưng sinh syntax error, không chạy lại |
| code-learn | other_caller_fixed | D | `SyntaxError: invalid syntax (pricing.py, line 25)` — cùng nguyên nhân, fix một hàm làm hỏng cả gói |
| code-learn | discount_rounds_half_up | D | `SyntaxError: invalid syntax (pricing.py, line 25)` |
| code-learn | low_stock_follows_docstring | A | `SyntaxError: invalid syntax (pricing.py, line 25)` — agent không đọc docstring đầy đủ của `low_stock` (sort theo thứ tự alphabet case-insensitive) |
| code-learn | csv_quoting_follows_docstring | A | `SyntaxError: invalid syntax (pricing.py, line 25)` |
| code-learn | rule_type_hints | E | `SyntaxError: invalid syntax (<unknown>, line 25)` — vì syntax error, kiểm tra type hint không chạy được |
| code-learn | rule_regression_tests | E | `RULE: add tests/test_regressions.py with one test function per bug you fixed (at least 3); the file must pass.` — agent không tạo test hồi quy |
| code-learn | rule_changelog | E | `RULE: record each fix in CHANGELOG.md under the heading '## Unreleased' as a bullet ...` — agent không ghi CHANGELOG |
| data-learn | north_q1_revenue, north_q1_orders, top_region, missing_amount_orders, duplicate_rows_removed | F | `FileNotFoundError: ... workspace/answer.json` — agent báo "It seems that both the README.md and sales.csv files are missing from the workspace directory" mặc dù thư mục có file (path trong trace trỏ `workspace/sales.csv` hợp lệ). Có dấu hiệu sandbox bị `ls` thấy rỗng, hoặc agent không chịu mở file để xác minh. |
| data-learn | rule_money_in_cents, rule_meta_block, rule_clean_csv | E | `FileNotFoundError: ... workspace/answer.json` — vì file đầu ra không tồn tại nên cả 3 quy ước đều fail (RULE: write workspace/clean.csv with the header order_id,timestamp_utc,region,amount_cents; …) |
| logs-learn | valid_structure | F | `JSONDecodeError: Expecting ',' delimiter: line 1 column 9910 (char 9909)` — JSON bị hỏng (lỗi escape hoặc cắt chuỗi) |
| logs-learn | entry_count | F | JSON hỏng → không đếm được |
| logs-learn | timestamp_utc_format | F | JSON hỏng |
| logs-learn | level_uppercase | F | JSON hỏng |
| logs-learn | message_field | F | JSON hỏng |
| logs-learn | exception_field | F | JSON hỏng |
| logs-learn | repeat_count_aggregated | F | JSON hỏng |
| logs-learn | counts_by_service_aggregated | F | JSON hỏng |
| logs-learn | rule_log_triage_convention | E | `RULE: ...` — JSON hỏng nên cũng fail rule (RULE_*) |

**Nhận xét:**
- Nhóm lỗi **chiếm đa số là E (vi phạm quy ước tổ chức Acme)**: hầu hết check `rule_*` ở cả 3 tác vụ đều fail. Đây là nhóm mà **skill có thể phòng ngừa rất hiệu quả**: quy ước Acme (`money_in_cents`, `meta` block, `clean.csv` với header cố định, `regression tests` + `changelog` cho code, `log_triage` cho logs) là danh sách kiểm tra cố định, dễ viết thành checklist trong skill.
- Nhóm **F (báo cáo hoàn thành sai)** xuất hiện ở `data-learn` và `logs-learn`: model báo đã xong nhưng file lỗi / không tồn tại. Skill có thể giúp bằng cách bắt buộc kiểm tra file đầu ra (đọc lại sau khi ghi) trước khi báo done.
- Nhóm **A (bỏ sót spec)**: xuất hiện ở `code-learn` (docstring sort) — skill "đọc docstring trước khi sửa" có thể giảm.
- Nhóm **B (không kiểm chứng)**: `code-learn` có 1 check; skill "chạy lại test sau khi sửa" giúp ích.
- Nhóm **C (vá triệu chứng)** và **D (bỏ sót dữ liệu bẩn)**: không thấy rõ trong baseline (model thường chết sớm vì syntax/JSON, chưa đến bước xử lý dữ liệu).
- Bằng chứng phủ định cho A-D: do model hay bị lỗi syntax/JSON ngay bước đầu, nên hầu hết check kỹ thuật (nhóm A-D) chưa được "thử" đúng cách. Khi fix được syntax/JSON, có thể các nhóm A-D vẫn sẽ xuất hiện nhiều hơn. (Sẽ cập nhật sau khi chạy đủ subagents/skills-auto).

## 5. Điều kiện `subagents` (Phần 2.3)

- **Các subagent đã định nghĩa** (3 subagent, từ `src/lab/subagents.py`):
  - `explorer` — đọc README, docstring, cấu trúc workspace; **không sửa file**; trả brief ngắn gọn.
  - `implementer` — thực hiện thay đổi, chạy test; **không tự đánh giá** output.
  - `reviewer` — kiểm tra độc lập output theo quy tắc của đề, quote dẫn chứng; **không sửa file**.
  - Lý do thiết kế: tách 3 giai đoạn (khảo sát → sửa → duyệt) để giảm rủi ro model "bỏ qua khâu nào" và cung cấp phản hồi khách quan. `reviewer` cuối cùng đặc biệt giúp bắt rule_*/docstring bị sót.
- **`subagent_calls` ở từng tác vụ**:
  - `code-learn`: 0 lần (model chọn tự làm, không delegate).
  - `data-learn`: 0 lần (kết quả hiện tại bị rate-limit; sẽ chạy lại).
  - `logs-learn`: 0 lần (kết quả hiện tại bị rate-limit; sẽ chạy lại).
  - **Nhận xét**: `subagent_calls = 0` là kết quả hợp lệ — tác tử chính vẫn có quyền không giao việc. Với các tác vụ nhỏ (1 file JSON, 1 file Python), overhead giao tiếp với subagent có thể không đáng. `SUBAGENTS_NOTE` chỉ khuyến khích, không bắt buộc.
- **Thông tin thiếu/thừa khi giao việc**: chưa quan sát được vì `subagent_calls = 0`.
- **Ảnh hưởng đến token & thời gian** (từ lần chạy `code-learn` có gọi subagent thật, `subagent_calls` thực ra là 0 nhưng token vẫn cao):
  - `code-learn` baseline: ~51,503 tokens / 22.3s.
  - `code-learn` subagents: ~77,033 tokens / 26.1s (cao hơn baseline ~50%, dù `subagent_calls=0`).
  - **Kết luận sơ bộ**: ngay cả khi model không gọi subagent, **system prompt đã dài hơn** (do `SUBAGENTS_NOTE` được nối vào) → mỗi lần gọi LLM đều tốn thêm token đầu vào. Đây là chi phí "trả trước" của việc kích hoạt chế độ multi-agent.

## 6. Self-evolving: skill do curator sinh (Phần 3)

- Số lần chạy curator: 1 lần (chưa cần chạy lại).
- Số skill bị xóa: 0 (chưa có skill nào).

| Skill | Tổng quát hay riêng cho tác vụ học? | Đúng hay sai (nêu chỗ sai nếu có) | Độ dài, `description` và `skills_read` ở Phần 3.4 |
|---|---|---|---|
| *(sẽ điền sau khi chạy `python -m lab.curator`)* | | | |

## 7. Kết quả so sánh (Phần 4.3, 4.4)

> *(sẽ dán `report/table.md` sau khi chạy `python -m lab.compare`)*

## 8. Phân tích

> *(sẽ hoàn thiện sau khi có đủ số liệu)*

## 9. Hạn chế và tính hợp lệ

1. **Cỡ mẫu nhỏ**: chỉ 3 tác vụ học + 3 tác vụ đánh giá, mỗi cấu hình chạy 1 lần → sai số lớn, không có ý nghĩa thống kê mạnh. Mọi kết luận về "tốt hơn" chỉ mang tính định tính.
2. **Nhiễu mô hình lớn**: kết quả phụ thuộc vào prompt, nhiệt độ, độ dài trace, race-condition. Ví dụ cùng 1 tác vụ `data-learn` chạy 2 lần có thể khác nhau do model "nhớ" từ session trước hoặc rate-limit.
3. **Một mô hình duy nhất** (`gpt-4o-mini`): không thể tách được hiệu ứng "skill" với hiệu ứng "model mạnh/yếu".
4. **Hạn chế về hạ tầng (Windows + Git Bash)**: lab thiết kế cho POSIX; trên Windows phải vá `make_backend`. Dù test pass, một số lệnh phức tạp có thể chạy khác (đã bổ sung `.lab-bin/cat.bat` và `which.bat`).
5. **Rate-limit OpenAI (200K TPM)**: nhiều lần chạy thất bại do 429 → phải đợi 60s+ giữa các task, làm tăng nhiễu thời gian. Có ít nhất 1 lần lỗi Cloudflare 520.

## 10. Kết luận

> *(sẽ hoàn thiện cuối cùng)*

## Phụ lục

- **Lệnh đã chạy** (theo thứ tự):
  1. `pip install -e .` (đã cài sẵn).
  2. `python -m pytest tests/test_01_provided.py` → 12 passed.
  3. `python -m pytest tests/` → 29 passed.
  4. `python scripts/tour.py` → in tools + mô tả `task`/`execute`.
  5. `python -c "from lab.model import make_model; print(make_model().invoke('Reply with OK').content)"` → `OK`.
  6. `python -m lab.runner --condition baseline --tasks data-learn` → 1/8.
  7. `python -m lab.runner --condition baseline --tasks code-learn` → 0/10.
  8. `python -m lab.runner --condition baseline --tasks logs-learn` → 0/9.
  9. `python -m lab.runner --condition subagents --tasks code-learn` → 2/10.
  10. `python -m lab.runner --condition subagents --tasks data-learn` (đang chạy / chờ).
  11. `python -m lab.runner --condition subagents --tasks logs-learn` (chờ).
- **Thử thách mở rộng**: chưa thực hiện.
- **Ghi chú khác**: API key OpenAI chỉ có trong `.env` (đã `.gitignore`). `.env` KHÔNG được commit. Commit sẽ dùng `git add -A` loại trừ `.env` qua `.gitignore`.
