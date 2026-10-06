"""GUIDE Phần 1 - Dựng tác tử (agent) bằng Deep Agents.   >>> SINH VIÊN CÀI ĐẶT make_backend VÀ build_agent <<<

Pseudo-code: guides/pseudocode/01_agent.md
Kiểm tra:    pytest tests/test_02_agent.py
"""
import sys as _sys
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend

from .model import make_model
from .subagents import get_subagents

# ---- CÓ SẴN, KHÔNG SỬA: system prompt dùng chung cho mọi sinh viên (để đường cơ sở so sánh được) ----
PATHS_NOTE = (
    "PATHS: every path is relative to the sandbox root and never starts with '/'. "
    "The task files are in the folder workspace/ (for example workspace/app.log). "
    "Use exactly this relative form both in the file tools and in the shell (execute); "
    "the shell starts in the sandbox root. "
)
BASE_PROMPT = (
    "You are an engineering assistant working in a sandbox. "
    + PATHS_NOTE
    + "Use the shell to run Python and tests. "
    "When you are done, reply with a short summary that mentions only files you really created or changed."
)
SKILLS_NOTE = (
    " Skills are in the folder skills/ (one sub-folder per skill with a SKILL.md). "
    "As your FIRST action, read the SKILL.md of every skill whose description could apply to the task, "
    "then follow them. Never modify skills/."
)
SUBAGENTS_NOTE = (
    " You have specialised subagents (see the description of the task tool). "
    "For anything beyond a trivial step, delegate to a suitable subagent and put ALL the task rules and file paths "
    "in the delegation message, because a subagent sees only what you send. "
    "Check what a subagent returns before you rely on it."
)
# --------------------------------------------------------------------------------------------------


def make_backend(sandbox: Path):
    """Tạo backend (môi trường thực thi) cho tác tử."""
    import os
    py_dir = str(Path(_sys.executable).parent)
    # Thư mục chứa wrapper cat/which cho môi trường Windows (POSIX utilities).
    extras: list[str] = []
    lab_bin = Path(__file__).resolve().parent.parent.parent / ".lab-bin"
    if lab_bin.exists():
        extras.append(str(lab_bin))
    # Windows: thêm system32 + một số đường dẫn phổ biến.
    if os.name == "nt":
        win_dirs = [
            os.environ.get("SystemRoot", r"C:\Windows") + r"\System32",
            os.environ.get("SystemRoot", r"C:\Windows"),
        ]
    else:
        win_dirs = []
    # PATH separator: Windows dùng ';', POSIX dùng ':'.
    sep = ";" if os.name == "nt" else ":"
    extra_parts = extras + win_dirs
    extra_path = sep.join(extra_parts) if extra_parts else ""
    posix_tail = sep.join(["/usr/local/bin", "/usr/bin", "/bin"])
    path_value = py_dir + (sep + extra_path if extra_path else "") + sep + posix_tail
    env = {
        "PATH": path_value,
        "HOME": str(sandbox),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return LocalShellBackend(
        root_dir=sandbox,
        virtual_mode=True,
        inherit_env=False,
        env=env,
        timeout=120,
    )


def build_agent(sandbox: Path, mode: str = "single", use_skills: bool = False, model=None):
    """Tạo tác tử Deep Agents."""
    if mode not in {"single", "subagents"}:
        raise ValueError(f"unknown mode: {mode}")

    # Một số model (đặc biệt trên cấu hình terminal PowerShell/CWD khác) đôi khi tự suy ra
    # đường dẫn kiểu `/sandbox/workspace/...` rồi báo "not found". Nhấn mạnh: KHÔNG có
    # prefix `/sandbox`; dùng đường dẫn TƯƠNG ĐỐI (`workspace/...`).
    paths_warning = (
        " IMPORTANT: there is NO '/sandbox' prefix in the filesystem. "
        "Use plain RELATIVE paths like 'workspace/sales.csv' or 'skills/<name>/SKILL.md'. "
        "If a file tool returns 'not found', retry with the relative form (no leading slash, no /sandbox)."
    )
    kwargs = {}
    prompt = BASE_PROMPT + paths_warning
    if mode == "subagents":
        kwargs["subagents"] = [
            {**sub, "system_prompt": sub["system_prompt"] + " " + PATHS_NOTE + paths_warning}
            for sub in get_subagents()
        ]
        prompt = prompt + SUBAGENTS_NOTE
    if use_skills:
        kwargs["skills"] = ["/skills/"]
        prompt = prompt + SKILLS_NOTE

    return create_deep_agent(
        model=model or make_model(),
        system_prompt=prompt,
        backend=make_backend(sandbox),
        **kwargs,
    )
