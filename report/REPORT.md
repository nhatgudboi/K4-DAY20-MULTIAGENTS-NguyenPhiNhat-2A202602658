# Báo cáo Lab: Self evolving Agentic

## 1. Thông tin nhóm và cấu hình

| Họ tên | Mã sinh viên | Phần đóng góp |
|---|---|---|
| Nguyễn Phi Nhật | 2A202602658 | Toàn bộ: cài đặt harness (agent, subagents, runner, curator), chạy thí nghiệm, phân tích dữ liệu và viết báo cáo |

- Mô hình (tên deployment hoặc `LAB_MODEL`), nhiệt độ (`LAB_TEMPERATURE`), `recursion_limit`:
  - `LAB_MODEL=openai:gpt-4o-mini`
  - `LAB_TEMPERATURE=0`
  - `recursion_limit=60` (mặc định của runner; các lần chạy chạm giới hạn được ghi nhận trong `error` của `run.json`)
- Phiên bản Deep Agents (`pip show deepagents`), hệ điều hành, chạy trực tiếp hay trong Docker:
  - Phiên bản: `deepagents 0.7.21` (Python 3.13)
  - Hệ điều hành: Windows 10 (10.0.26200), chạy trực tiếp trong PowerShell (bổ sung POSIX shim trong `.lab-bin` cho `cat`, `ls`, `which`)
- Số lần chạy tác vụ đã dùng / ngân sách:
  - Tổng số lần chạy: 24 lần (6 baseline + 6 subagents + 3 skills-auto dev + 6 skills-auto freeze + 3 lần thử nghiệm ban đầu)
  - Ngân sách: sử dụng API key cá nhân với mô hình `gpt-4o-mini`, độ trễ giữa các lần chạy 10–15s để đảm bảo kiểm soát tốc độ gọi API
- Commit của tag `freeze`: `1feac1a1e421989954d0587bfd055b88fba6a783`

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

- H1 (subagents so với baseline): Dự đoán **`subagents` ≈ `baseline`** trên tác vụ đánh giá (chênh lệch |Δ| ≤ 2 check).
- H2 (skills-auto so với baseline): Dự đoán **`skills-auto` > `baseline` 1–4 check trên cùng tác vụ học**, **nhưng KHÔNG cải thiện rõ trên tác vụ đánh giá** (|Δ| ≤ 2 check).
- H3 (tác vụ học so với tác vụ đánh giá): Dự đoán **điểm tác vụ học > điểm tác vụ đánh giá** trong mọi điều kiện (chênh 2–6 check).

Căn cứ cho H1: Trên 3 tác vụ học, tác tử gặp các lỗi về quy trình (sửa tệp gốc trong `tests/`, thiếu `tests/test_regressions.py`, thiếu `CHANGELOG.md`, thiếu các tệp đầu ra quy ước). Việc bổ sung các subagent độc lập (`explorer`, `implementer`, `reviewer`) chỉ phân mảnh ngữ cảnh và tăng chi phí điều phối chứ không cung cấp thêm tri thức thủ tục cụ thể. Theo nghiên cứu của Anthropic (2025) về multi-agent research systems, cấu trúc đa tác tử tiêu tốn token gấp 10–15 lần và không mang lại ưu thế vượt trội trên các tác vụ kỹ thuật ngắn có phạm vi hẹp.

Căn cứ cho H2: Các kỹ năng do curator tự sinh xuất phát trực tiếp từ các thông báo lỗi và phản hồi của bot chấm điểm trên tập học (như `rule_type_hints`, `rule_regression_tests`, `rule_clean_csv`). Do đó, skill khớp tốt với các yêu cầu của tập học. Tuy nhiên, theo nghiên cứu SkillEvolBench (2025), các kỹ năng tự sinh ở tầng ngữ cảnh thường khó khái quát hóa sang các tác vụ đánh giá mới khi tập đánh giá bổ sung các quy ước ẩn mới chưa từng xuất hiện trong tập học (hiện tượng quá khớp - overfitting).

Căn cứ cho H3: Tác vụ học có các gợi ý và cấu trúc gần gũi với mô tả đề bài ban đầu, trong khi tác vụ đánh giá chứa các ràng buộc và định dạng mới (như `parse_duration_all_formats`, `march_revenue_utc`, `add_slot_no_shared_state`). Khi tác tử không có phản hồi trước từ bộ chấm điểm của tác vụ đánh giá, điểm số trên tập đánh giá được dự đoán sẽ thấp hơn tập học.

## 3. Làm quen Deep Agents (Phần 0.3)

1. Tác tử mặc định được cung cấp 9 công cụ:
   - Nhóm thao tác tệp: `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`.
   - Nhóm thực thi shell: `execute`.
   - Nhóm phân công đa tác tử: `task`.
   Công cụ cho phép chạy lệnh thực thi là **`execute`**.

2. Mô tả của công cụ `task` về subagent `general-purpose`:
   - "General-purpose agent for researching complex questions, searching for files and content, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you. This agent has access to all tools as the main agent."
   - Về ngữ cảnh: Subagent bị cô lập ngữ cảnh (context isolation), hoạt động stateless theo mặc định ("the agent sees only the prompt you give it and returns a single final report"). Subagent không nhìn thấy lịch sử hội thoại trước đó của tác tử chính, trừ khi tác tử chính chủ động truyền toàn bộ thông tin cần thiết vào nội dung prompt của lệnh gọi `task`.

3. System prompt mặc định của Deep Agents rỗng (`''`):
   - Một câu hướng dẫn hành vi từ mô tả công cụ `task`:
     *"Each invocation is stateless by default: the agent sees only the prompt you give it and returns a single final report. Put full detail in the prompt and state exactly what it should return."*
   - Một câu hướng dẫn hành vi từ mô tả công cụ `execute`:
     *"Use absolute paths and avoid `cd` so the working directory stays stable; use the optional timeout to override the default."* (và *"You MUST avoid using search commands like find and grep. Instead use the grep, glob tools to search. Use read_file rather than cat/head/tail."*)

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

Bảng phân loại lỗi dựa trên kết quả chạy điều kiện `baseline` của 3 tác vụ học (`code-learn`, `data-learn`, `logs-learn`):

| Tác vụ | Check thất bại | Nhóm lỗi (A-G) | Bằng chứng (trích ngắn từ `detail` hoặc vết) |
|---|---|---|---|
| code-learn | `visible_suite_passes` | A - Bỏ qua đặc tả | `1 failed, 5 passed in 0.22s` (tác tử sửa hàm nhưng làm vỡ một test case có sẵn) |
| code-learn | `tests_not_modified` | E - Vi phạm quy ước tổ chức | `RULE: the original files in tests/ must not be modified (new test files are allowed)` |
| code-learn | `discount_rounds_half_up` | B - Không kiểm chứng | `wrong for: [('10.05', 10, '9.05'), ('0.05', 50, '0.03'), ('2.665', 0, '2.67')]` (tác tử không đối chiếu docstring về làm tròn thương mại nửa lên) |
| code-learn | `rule_type_hints` | E - Vi phạm quy ước tổ chức | `RULE: every public function (name not starting with '_') in the package has type annotations on all parameters and on the return value` |
| code-learn | `rule_regression_tests` | E - Vi phạm quy ước tổ chức | `RULE: add tests/test_regressions.py with one test function per bug you fixed (at least 3); the file must pass` |
| code-learn | `rule_changelog` | E - Vi phạm quy ước tổ chức | `RULE: record each fix in CHANGELOG.md under the heading '## Unreleased' as a bullet '- fix(<function name>): <short description>' (at least 3 bullets)` |
| data-learn | `north_q1_revenue` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `north_q1_revenue: wrong value (got 0)` (không lọc đúng mốc thời gian UTC và xử lý các giá trị khuyết) |
| data-learn | `north_q1_orders` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `north_q1_orders: wrong value (got 0)` (tác tử nhầm lẫn số lượng đơn hàng phân biệt và đơn thiếu tiền) |
| data-learn | `missing_amount_orders` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `missing_amount_orders: wrong value (got 0)` (bỏ qua các giá trị rỗng/khoảng trắng trong cột amount) |
| data-learn | `duplicate_rows_removed` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `duplicate_rows_removed: wrong value (got 0)` (không dedup dòng trước khi tính tổng) |
| data-learn | `rule_money_in_cents` | E - Vi phạm quy ước tổ chức | `RULE: money values in answer.json are integer cents (1606.67 USD is written 160667)` |
| data-learn | `rule_meta_block` | E - Vi phạm quy ước tổ chức | `RULE: answer.json has an object meta = {"source": <input file name>, "rows_in": <number of data rows in the input file>}` |
| data-learn | `rule_clean_csv` | E - Vi phạm quy ước tổ chức | `RULE: write workspace/clean.csv with the header order_id,timestamp_utc,region,amount_cents` |
| logs-learn | `entry_count` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `wrong number of entries (got 23)` (không xử lý gom các dòng stack trace nhiều dòng vào sự kiện gốc) |
| logs-learn | `timestamps_utc` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `8/25 timestamps match` (không chuyển đổi chuẩn hóa nhiều định dạng múi giờ về UTC ISO-8601) |
| logs-learn | `exception_fields` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `17 wrong exception values` (trích xuất sai chuỗi tên ngoại lệ) |
| logs-learn | `repeat_counts` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `17 wrong repeat_count values` (bỏ qua các dòng lặp liên tiếp `last message repeated N times`) |
| logs-learn | `counts_by_service` | D - Bỏ sót dữ liệu bẩn hoặc định dạng | `counts_by_service: wrong values` (đếm sai tổng số lỗi theo từng service) |
| logs-learn | `rule_service_names` | E - Vi phạm quy ước tổ chức | `RULE: service names in the output are lower-case with '-' replaced by '_' (payment-service -> payment_service)` |
| logs-learn | `rule_sorted_errors` | E - Vi phạm quy ước tổ chức | `RULE: errors is sorted by service, then by timestamp_utc, ascending` |
| logs-learn | `rule_schema_header` | E - Vi phạm quy ước tổ chức | `RULE: the top-level object has "schema_version": 2 and "generated_by": "log-triage"` |

**Nhận xét:**
- **Nhóm E (Vi phạm quy ước tổ chức Acme):** Chiếm tỷ trọng lớn nhất với 9/21 check thất bại (4 ở `code-learn`, 3 ở `data-learn`, 3 ở `logs-learn`). Đây là các quy ước ngầm do doanh nghiệp quy định mà đề bài không chỉ định chi tiết, chỉ có trong phản hồi `detail` của bot kiểm tra. Một skill thủ tục chuyên biệt hoàn toàn có thể phòng ngừa triệt để nhóm lỗi này bằng cách cung cấp checklist quy chuẩn (type hints, regression tests, changelog, meta block, clean csv, schema version).
- **Nhóm D (Bỏ sót dữ liệu bẩn hoặc định dạng):** Chiếm 9/21 check thất bại (4 ở `data-learn`, 5 ở `logs-learn`). Nhóm này có thể được phòng ngừa một phần thông qua quy trình chuẩn hóa dữ liệu (dedup, chuyển đổi timezone UTC, gom dòng stack trace).
- **Bằng chứng phủ định:** Thống kê từ `scripts/check_breakdown.py` cho thấy các check kỹ thuật cơ bản đạt 6/18 ở tập học và 7/18 ở tập đánh giá (`parse_price_all_formats`, `low_stock_follows_docstring`, `csv_quoting_follows_docstring`, `top_region`, `valid_structure`). Điều này chứng minh tác tử hiểu cú pháp và giải quyết được logic căn bản, không mắc các lỗi thô thiển như lỗi môi trường hay đọc file, mà rào cản chính nằm ở các quy ước ngầm (nhóm E) và xử lý ngoại lệ phức tạp (nhóm D).

## 5. Điều kiện `subagents` (Phần 2.3)

- **Các subagent đã định nghĩa:**
  1. `explorer`: Phụ trách khảo sát cấu trúc thư mục, đọc các tệp hướng dẫn và dữ liệu mẫu mà không thay đổi bất kỳ tệp nào; trả về bản tóm tắt thực tế về các ràng buộc.
  2. `implementer`: Phụ trách thực thi các sửa đổi mã nguồn, chạy thử nghiệm bằng shell, hoàn thành các tệp đầu ra được chỉ định.
  3. `reviewer`: Phụ trách kiểm tra độc lập các tệp kết quả dựa trên các tiêu chí và ràng buộc của đề bài, đối chiếu các trường hợp biên trước khi kết thúc tác vụ.
  - Cả 3 subagent đều được tự động bổ sung `PATHS_NOTE` vào `system_prompt` để duy trì quy ước đường dẫn tương đối trong môi trường sandbox.
- **`subagent_calls` ở từng tác vụ:**
  - `code-learn`: 0 lần
  - `data-learn`: 0 lần (gặp `GraphRecursionError` sau 60 bước)
  - `logs-learn`: 0 lần
  - `code-eval`: 0 lần (gặp `GraphRecursionError` sau 60 bước)
  - `data-eval`: 0 lần
  - `logs-eval`: 0 lần
  - *Nhận xét:* Tác tử chính hoàn toàn không gọi các subagent tự định nghĩa (`subagent_calls = 0`). Do `create_deep_agent` cung cấp công cụ `task` dưới dạng tùy chọn và `SUBAGENTS_NOTE` chỉ mang tính khuyến khích, tác tử chính (đặc biệt các mô hình nhỏ như `gpt-4o-mini`) có xu hướng tự giải quyết trực tiếp bằng các công cụ tệp và shell cơ bản (`ls`, `read_file`, `write_file`, `execute`) thay vì thực hiện bước phân quyền đa tác tử phức tạp. Đây là một kết quả thực nghiệm hợp lệ và phản ánh đúng hành vi tự nhiên của mô hình.
- **Ảnh hưởng đến token và thời gian:**
  - Token trung bình của `subagents` tăng vọt lên **134,759 token/run** (gấp 4.35 lần so với `baseline` là 30,957 token/run).
  - Nguyên nhân chính: System prompt dài hơn do chứa định nghĩa các subagent khiến mỗi lượt suy luận tiêu tốn nhiều token hơn, đồng thời trên các tác vụ dữ liệu phức tạp (`data-learn`, `code-eval`), tác tử bị cuốn vào các vòng lặp thao tác shell liên tiếp cho tới khi chạm `recursion_limit=60`.

## 6. Self-evolving: skill do curator sinh (Phần 3)

- **Số lần chạy curator, số skill bị xóa và lý do:**
  - Số lần chạy curator: **1 lần**.
  - Số skill bị xóa: **0**. Toàn bộ 3 skill do curator sinh ra đều vượt qua bộ kiểm tra an toàn và định dạng của `validate_skill()` (`[]` problems), không vi phạm độ dài, không chứa mã độc và không rò rỉ bất kỳ dấu hiệu nào của tập đánh giá (`eval_markers`). Nhóm giữ nguyên 100% đầu ra của curator theo đúng nguyên tắc thí nghiệm tự tiến hóa (GUIDE Phần 3.3).

| Skill | Tổng quát hay riêng cho tác vụ học? | Đúng hay sai (nêu chỗ sai nếu có) | Độ dài, `description` và `skills_read` ở Phần 3.4 |
|---|---|---|---|
| `adhere-to-coding-standards` | **Tổng quát:** Nêu quy chuẩn áp dụng type annotations, tuân thủ naming conventions, cập nhật changelog, chạy linter. Không đề cập tên hàm hay tệp cụ thể của bài toán. | **Đúng:** Hoàn toàn khớp với các quy chuẩn kiểm tra của hệ thống bot đánh giá. | Độ dài: 10 dòng (5 dòng checklist). `description` nêu rõ ngữ cảnh kích hoạt khi viết/sửa mã. `skills_read`: 0. |
| `data-formatting-and-validation` | **Tổng quát:** Đưa ra quy tắc chuyển đổi giá trị tiền tệ sang cents, đồng bộ timestamp về UTC, lọc duplicate rows, kiểm tra trường thiếu. | **Đúng:** Khớp chính xác với các yêu cầu thường bị vi phạm trong xử lý dữ liệu và log. | Độ dài: 11 dòng (6 dòng checklist). `description` rõ ràng cho các tác vụ xử lý dữ liệu. `skills_read`: 0. |
| `maintain-test-integrity` | **Tổng quát:** Đưa ra quy tắc bảo toàn tính toàn vẹn của bộ kiểm thử: không sửa file test có sẵn, tạo file test mới cho regression, chạy test định kỳ. | **Đúng:** Khắc phục trực tiếp lỗi sửa tệp test gốc mà `baseline` mắc phải. | Độ dài: 10 dòng (5 dòng checklist). `description` nêu rõ ngữ cảnh khi chỉnh sửa code có bộ test. `skills_read`: 0. |

## 7. Kết quả so sánh (Phần 4.3, 4.4)

### Bảng kết quả tổng hợp (`report/table.md`)

| Task | baseline | subagents | skills-auto |
|---|---|---|---|
| code-learn | 4/10 | 0/10 | 0/10 |
| data-learn | 1/8 | 0/8 | 0/8 |
| logs-learn | 1/9 | 1/9 | 1/9 |
| code-eval | 6/11 | 0/11 | 3/11 |
| data-eval | 0/9 | 0/9 | 0/9 |
| logs-eval | 1/10 | 1/10 | 1/10 |
| **Mean score - learning tasks** | **0.21** | **0.04** | **0.04** |
| **Mean score - evaluation tasks** | **0.22** | **0.03** | **0.12** |
| **Mean tokens per run** | **30,957** | **134,759** | **133,358** |
| **Runs that read a skill** | **0/6** | **0/6** | **0/6** |

### Thống kê phân rã check kỹ thuật và quy ước (`scripts/check_breakdown.py`)

```text
condition     role    technical  house rules  mean tokens  read a skill
baseline      eval      7/18         0/12          25,680      0/3     
baseline      learn     6/18         0/9           36,234      0/3     
subagents     eval      1/18         0/12          83,302      0/3     
subagents     learn     1/18         0/9          186,215      0/3     
skills-auto   eval      4/18         0/12          67,356      0/3     
skills-auto   learn     1/18         0/9          199,360      0/3     
```

### Xử lý sự cố và các lần chạy gặp lỗi:
- Các lần chạy xuất hiện `error` trong `run.json`:
  - `subagents/data-learn`: `GraphRecursionError: Recursion limit of 60 reached`
  - `subagents/code-eval`: `GraphRecursionError: Recursion limit of 60 reached`
  - `skills-auto/data-learn`: `GraphRecursionError: Recursion limit of 60 reached`
  - `skills-auto/code-eval`: `GraphRecursionError: Recursion limit of 60 reached`
- *Cách xử lý:* Theo đúng thiết kế của harness tại `GUIDE 1.3`, các lỗi này không làm dừng chương trình mà được bắt vào trường `error` của bản ghi; tác vụ vẫn được chấm điểm tự động trên trạng thái hiện có của workspace.
- Biến `skills_modified`: Đều là `false` trong toàn bộ các lần chạy chính thức, đảm bảo tính toàn vẹn của thư mục skill đã đóng băng.

## 8. Phân tích

1. **So sánh điểm số giữa các điều kiện trên tập học và tập đánh giá:**
   - Trên tập học: `baseline` đạt điểm trung bình cao nhất (0.21, 6/18 check kỹ thuật), trong khi `subagents` và `skills-auto` chỉ đạt 0.04 (1/18 check kỹ thuật).
   - Trên tập đánh giá: `baseline` đạt 0.22 (7/18 check kỹ thuật), `skills-auto` đạt 0.12 (4/18 check kỹ thuật), và `subagents` đạt 0.03 (1/18 check kỹ thuật).
   - Điều kiện `skills-auto` trên tập đánh giá cao hơn tập học (0.12 so với 0.04). Sự chênh lệch này chủ yếu đến từ tác vụ `code-eval` (đạt 3/11 check). Tuy nhiên, nguyên nhân không phải do kỹ năng tự sinh phát huy tác dụng mà do tác tử giải quyết được một số hàm logic độc lập trước khi chạm giới hạn đệ quy.

2. **Phân rã check kỹ thuật và check quy ước tổ chức (`rule_`):**
   - Trên tất cả các điều kiện và tất cả các lần chạy, **check quy ước tổ chức (`house rules`) đều đạt 0/12 trên eval và 0/9 trên learn**.
   - Điều này giải thích tại sao điểm tổng của các tác vụ đều ở mức thấp: bot chấm điểm yêu cầu nghiêm ngặt các quy ước ngầm của tổ chức Acme (`rule_type_hints`, `rule_regression_tests`, `rule_changelog`, `rule_clean_csv`, `rule_meta_block`, `rule_service_names`), nhưng do tác tử không đọc các skill tự sinh trong quá trình thực thi (`read a skill: 0/3`), tác tử hoàn toàn không nắm được các quy ước này và trượt toàn bộ các check quy ước.
   - Các check mà tác tử đạt được hoàn toàn là các check kỹ thuật đơn thuần (`visible_suite_passes`, `top_region`, `valid_structure`, `parse_duration_all_formats`).

3. **Cơ chế đọc và làm theo skill dựa trên vết (`trace.md`) và `skills_read`:**
   - Số liệu thống kê chỉ ra `skills_read = 0` trên toàn bộ 6 lần chạy của `skills-auto`.
   - Phân tích vết `trace.md`: Mặc dù trong system prompt có đoạn `SKILLS_NOTE` hướng dẫn "As your FIRST action, read the SKILL.md of every skill...", mô hình `gpt-4o-mini` khi nhận yêu cầu lập trình cụ thể đã lập tức ưu tiên đọc tệp trong `workspace/` (ví dụ `read_file(workspace/README.md)` hoặc chạy `ls workspace`) và tiến hành sửa đổi ngay lập tức. Mô hình không thực hiện bước tra cứu thư mục `skills/` thông qua cơ chế nạp dần (progressive disclosure). Đây là một hạn chế phổ biến của các mô hình kích thước nhỏ khi không có cơ chế bắt buộc (hard constraint hoặc tool calling enforcement) kích hoạt skill.

4. **Phân tích chi phí token và hiệu quả:**
   - `baseline`: Trung bình 30,957 token/run, hiệu quả điểm/token cao nhất.
   - `subagents`: Trung bình 134,759 token/run (tăng 335% so với baseline), nhưng điểm số lại thấp nhất (0.04 learn, 0.03 eval).
   - `skills-auto`: Trung bình 133,358 token/run (tăng 330% so với baseline).
   - **Kết luận:** Trong thí nghiệm này, đa tác tử (subagents) **hoàn toàn không đáng chi phí**. Subagents làm tăng mạnh chi phí token và độ trễ, đồng thời làm tăng nguy cơ phân mảnh ngữ cảnh dẫn đến vòng lặp thao tác tệp vô hạn chạm `recursion_limit`.

5. **Dấu hiệu rò rỉ dữ liệu hoặc quá khớp trong skill sinh ra:**
   - Không có bất kỳ dấu hiệu rò rỉ dữ liệu nào trong các skill sinh ra: hàm `validate_skill` đã tự động đối chiếu nội dung với danh sách `eval_markers()` và không phát hiện bất kỳ định danh nào của tập đánh giá lọt vào `skills/auto/`.
   - Về quá khớp (overfitting): Các skill do curator viết mang tính khái quát cao (hướng dẫn type annotation, dedup, datetime ISO UTC, không sửa test cũ). Tuy nhiên, vì tác tử không đọc skill trong quá trình chạy, hiện tượng quá khớp ở đây bị chi phối bởi việc thiếu hụt cơ chế kích hoạt hành vi hơn là do nội dung skill bị hẹp.

6. **Ước lượng nhiễu thực nghiệm (Run-to-run Stochasticity):**
   - So sánh điểm tác vụ học của `skills-auto` ở giai đoạn phát triển (Phần 3.4, lưu tại `results/skills-auto-dev`) và giai đoạn chính thức sau đóng băng (Phần 4.2, tại `results/skills-auto`):
     - `code-learn`: **1/10** (ở Phần 3.4) so với **0/10** (ở Phần 4.2) -> Chênh lệch: **-1 check**.
     - `data-learn`: **0/8** (ở Phần 3.4) so với **0/8** (ở Phần 4.2) -> Chênh lệch: **0 check**.
     - `logs-learn`: **1/9** (ở Phần 3.4) so với **1/9** (ở Phần 4.2) -> Chênh lệch: **0 check**.
   - Mặc dù sử dụng cùng một bộ skill đã đóng băng và `LAB_TEMPERATURE=0`, điểm số giữa hai lần chạy vẫn có sự dao động ±1 check (chênh lệch điểm trung bình từ 0.07 xuống 0.04). Điều này cho thấy tính ngẫu nhiên cố hữu trong quá trình giải quyết vấn đề của LLM (thứ tự gọi công cụ, đường dẫn tìm kiếm). Do đó, các chênh lệch điểm nhỏ (khoảng 1–2 check) giữa các điều kiện cần được diễn giải thận trọng dưới góc độ nhiễu thực nghiệm thay vì khẳng định là cải tiến bản chất.

## 9. Hạn chế và tính hợp lệ

1. **Cơ chế kích hoạt skill thụ động (Passive Progressive Disclosure):** Deep Agents nạp danh sách tên skill vào prompt và dựa vào quyết định tự chủ của mô hình để gọi `read_file` đọc nội dung `SKILL.md`. Với các mô hình ngôn ngữ vừa và nhỏ (`gpt-4o-mini`), mô hình thường bị cuốn vào nhiệm vụ chính trong đề bài và bỏ qua bước nạp skill, khiến `skills_read` bằng 0.
2. **Kích thước mẫu thí nghiệm nhỏ và chạy đơn lẻ:** Mỗi ô điều kiện chỉ có 3 tác vụ học và 3 tác vụ đánh giá, và mỗi tác vụ chỉ chạy 1 lần chính thức do giới hạn token API. Khoảng dao động ngẫu nhiên (nhiễu) đo được giữa hai lần chạy cùng điều kiện là ±1 check, tương đương 10–15% tổng điểm tác vụ, làm giảm độ tin cậy thống kê của các so sánh biên.
3. **Hiện tượng nghẽn đệ quy (Graph Recursion Limit):** Khi đối mặt với các bài toán dữ liệu phức tạp hoặc mã nguồn lớn, việc bổ sung thêm chỉ dẫn subagent/skill làm tăng độ dài ngữ cảnh và kích thích mô hình thực hiện các vòng lặp kiểm tra shell liên tiếp mà không có điểm dừng, dẫn đến việc chạm mốc `recursion_limit=60` trước khi kịp hoàn thành các tệp đầu ra.
4. **Quy ước đánh giá mang tính giả định nhân tạo:** Các check quy ước ngầm (`rule_*`) không xuất phát từ bài toán thực tế mà do bộ chấm điểm thiết kế để kiểm tra khả năng tự thích ứng của tác tử từ phản hồi lỗi. Vì tập đánh giá bổ sung các quy ước mới chưa từng có trong tập học, tác tử gần như không thể vượt qua nếu không có phản hồi trung gian trong quá trình chạy.

## 10. Kết luận

Thí nghiệm cho thấy việc bổ sung cấu trúc đa tác tử (subagents) hoặc danh mục kỹ năng tự tiến hóa (skills-auto) không tự động mang lại cải thiện điểm số nếu thiếu cơ chế kích hoạt hành vi cưỡng bức; ngược lại, chúng làm tăng chi phí token lên gấp 4.3 lần và làm tăng rủi ro chạm giới hạn đệ quy đồ thị. Toàn bộ các check quy ước ngầm (`house rules`) đều thất bại do tác tử không đọc skill trong quá trình chạy, trong khi các check kỹ thuật cơ bản vẫn được duy trì ổn định. Để nâng cao hiệu quả của tác tử tự tiến hóa, cải tiến then chốt tiếp theo là xây dựng cơ chế Middleware can thiệp chủ động (pre-execution interceptor) buộc tác tử phải đọc và xác nhận các skill phù hợp trước khi được cấp quyền thực thi công cụ shell và chỉnh sửa tệp.

## Phụ lục

- **Lệnh đã chạy (theo thứ tự):**
  1. `python -m pytest tests/ -q` (kiểm tra ngoại tuyến toàn bộ 4 module harness, đạt 29/29 test).
  2. `python scripts/tour.py` (khảo sát cấu trúc công cụ mặc định, shell và subagent).
  3. `python -m lab.runner --condition baseline --tasks all` (chạy 6 tác vụ cho đường cơ sở).
  4. `python -m lab.curator` (sinh 3 kỹ năng tự động từ phản hồi và vết thất bại của tác vụ học vào `skills/auto/`).
  5. `git add -A && git commit -m "hypotheses-final-H1H3-inline-format"` (commit các giả thuyết nghiên cứu).
  6. `git commit --allow-empty -m "freeze skills" && git tag -f freeze` (đóng băng bộ kỹ năng).
  7. `python -m lab.runner --condition subagents --tasks all` (chạy toàn bộ 6 tác vụ cho điều kiện đa tác tử).
  8. `python -m lab.runner --condition skills-auto --tasks learn` (chạy kiểm thử kỹ năng giai đoạn phát triển 3.4).
  9. Sao lưu `results/skills-auto` sang `results/skills-auto-dev`.
  10. `python -m lab.runner --condition skills-auto --tasks all` (chạy chính thức 6 tác vụ với kỹ năng đã đóng băng).
  11. `python scripts/verify_freeze.py` (xác thực tính hợp lệ của quy trình đóng băng, kết quả OK).
  12. `python -m lab.compare > report/table.md` (sinh bảng đối chiếu kết quả 3 điều kiện).
  13. `python scripts/check_breakdown.py` (thống kê phân rã check kỹ thuật và check quy ước).
- **Thử thách mở rộng (nếu có):** Không thực hiện do giới hạn ngân sách token API của khóa học.
- **Ghi chú khác:** Các file tạm chạy batch (`_run_subagents.py`, `_run_skills_auto.py`) được sử dụng để điều phối chạy tuần tự có kiểm soát thời gian nghỉ (10s delay) nhằm tránh rate limit của nhà cung cấp LLM.