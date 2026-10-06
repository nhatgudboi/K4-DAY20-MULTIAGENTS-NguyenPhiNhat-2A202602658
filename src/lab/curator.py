"""GUIDE Phần 3 - Người tuyển chọn skill (skill curator): tự viết skill từ các lần chạy thất bại.   >>> SINH VIÊN CÀI ĐẶT curate_skills <<<

Pseudo-code: guides/pseudocode/04_curator.md
Kiểm tra:    pytest tests/test_04_curator.py
Chạy thật:   python -m lab.curator
"""
import json
import re
from pathlib import Path

from .tasks import eval_markers   # có sẵn: định danh của tác vụ đánh giá, tính lúc chạy

# ---- CÓ SẴN, KHÔNG SỬA: kiểm tra và tách khối skill (phần dễ sai và liên quan bảo mật) ----------------
SAFE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_skill(text: str, expected_name: str | None = None) -> list[str]:
    """Kiểm tra nội dung một SKILL.md. Trả về danh sách vấn đề (rỗng = hợp lệ).

    Quy tắc: có khối YAML frontmatter; `name` chữ thường/số/gạch ngang (tối đa 64 ký tự) và bằng `expected_name`
    nếu được truyền; có `description` (tối đa 1024 ký tự); phần thân tối đa 80 dòng; không chứa chuỗi nào của
    `eval_markers()`. Quy tắc về `name` cũng là biện pháp bảo mật: tên khối do LLM sinh ra được dùng để tạo
    đường dẫn, nên `../evil` không được lọt qua.
    """
    problems = []
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text.strip() + "\n", re.S)
    if not m:
        return ["missing YAML frontmatter"]
    front, body = m.groups()
    name = re.search(r"^name:\s*(.+)$", front, re.M)
    desc = re.search(r"^description:\s*(.+)$", front, re.M)
    n = name.group(1).strip() if name else ""
    if not SAFE_NAME.fullmatch(n) or len(n) > 64:
        problems.append("invalid name")
    elif expected_name is not None and n != expected_name:
        problems.append("name differs from the block name")
    if not desc or len(desc.group(1).strip()) > 1024:
        problems.append("missing or too long description")
    if len(body.strip().splitlines()) > 80:
        problems.append("body longer than 80 lines")
    low = text.lower()
    for marker in eval_markers():
        if marker in low:
            problems.append(f"mentions evaluation material: {marker}")
    return problems


def parse_skill_blocks(reply: str) -> list[tuple[str, str]]:
    """Tách câu trả lời của LLM thành danh sách (name, nội dung SKILL.md).

    Khuôn dạng: `=== SKILL: <name> ===` ... `=== END ===`. Một khối kết thúc ở điểm nào đến trước trong ba điểm:
    `=== END ===`, tiêu đề `=== SKILL:` kế tiếp, hoặc cuối văn bản (LLM đôi khi quên dòng END).
    """
    pattern = re.compile(r"^=== SKILL: (\S+) ===[ \t]*\n(.*?)(?=^=== END ===|^=== SKILL: |\Z)", re.S | re.M)
    return [(name, text.strip()) for name, text in pattern.findall(str(reply))]
# --------------------------------------------------------------------------------------------------


def curate_skills(results_dir="results", source_condition="baseline", out_dir=None, model=None, max_skills: int = 3) -> list[Path]:
    """Đọc các lần chạy của TÁC VỤ HỌC, nhờ LLM viết skill, ghi file."""
    from .tasks import ROOT
    from .model import make_model

    if out_dir is None:
        out_dir = ROOT / "skills" / "auto"
    out_dir = Path(out_dir)

    runs = []
    src = Path(results_dir) / source_condition
    if src.exists():
        for run_json in sorted(src.glob("*/run.json")):
            try:
                r = json.loads(run_json.read_text(encoding="utf-8"))
            except Exception:
                continue
            if r.get("role") != "learn":
                continue
            failed = []
            for c in (r.get("checks") or []):
                if not c.get("passed"):
                    failed.append((c.get("name", ""), c.get("detail", "")))
            if not failed:
                continue
            trace = ""
            trace_path = run_json.parent / "trace.md"
            if trace_path.exists():
                txt = trace_path.read_text(encoding="utf-8", errors="replace")
                trace = txt[-6000:]
            runs.append({"task": r.get("task", run_json.parent.name), "failed": failed, "trace": trace})

    if not runs:
        print("[curator] không có check thất bại ở tác vụ học; không gọi mô hình.")
        return []

    parts = []
    for run in runs:
        parts.append(f"### TASK: {run['task']}")
        for name, detail in run["failed"]:
            parts.append(f"- FAIL: {name}\n  detail: {detail}")
        if run["trace"]:
            parts.append("\n-- TRACE (tail) --\n" + run["trace"])
    runs_text = "\n\n".join(parts)

    prompt = (
        "You write SKILLs for an engineering/data-analysis agent. Below are the failed checks "
        "(name + grading-bot comment) and the tails of the traces of learning-task runs.\n"
        "Find GENERAL procedural mistakes (not specific answers) and write up to "
        f"{max_skills} short skills that help avoid those mistakes on NEW tasks of the same kind.\n\n"
        "Rules:\n"
        "- Skill must be GENERAL: do not mention task ids, do not mention a specific task filename, "
        "do not reveal the answer or numbers.\n"
        "- Each skill has `name` (lowercase, dash-separated) and `description` (one sentence: WHEN TO USE), "
        "then at most 40 lines of imperative guidance (a checklist works well).\n"
        "- Exact output format, one character per character:\n"
        "=== SKILL: <name> ===\n"
        "---\n"
        "name: <name>\n"
        "description: <when to use>\n"
        "---\n"
        "<body>\n"
        "=== END ===\n\n"
        "RUNS:\n"
        + runs_text
    )

    if model is None:
        model = make_model()
    reply = model.invoke(prompt).content
    blocks = parse_skill_blocks(reply)

    written: list[Path] = []
    for name, text in blocks:
        if len(written) >= max_skills:
            break
        problems = validate_skill(text, expected_name=name)
        if problems:
            print(f"[curator] skip {name}: {problems}")
            continue
        d = out_dir / name
        d.mkdir(parents=True, exist_ok=True)
        path = d / "SKILL.md"
        path.write_text(text.strip() + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in curate_skills():
        print("wrote", p)
