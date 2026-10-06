"""GUIDE Phần 1 - Chạy một tác vụ (task) và ghi kết quả.   >>> SINH VIÊN CÀI ĐẶT run_task <<<

Pseudo-code: guides/pseudocode/03_runner.md
Kiểm tra:    pytest tests/test_03_runner.py
Chạy thật:   python -m lab.runner --condition baseline --tasks learn
"""
import argparse
import json
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from .grading import grade                                                      # có sẵn
from .tasks import ROOT, get_task, hash_dir, list_tasks, prepare_sandbox         # có sẵn

# Ba điều kiện thí nghiệm (condition). `skills_dir` là thư mục skill nguồn (tính từ thư mục gốc của lab).
CONDITIONS = {
    "baseline": {"mode": "single", "skills_dir": None},
    "subagents": {"mode": "subagents", "skills_dir": None},
    "skills-auto": {"mode": "single", "skills_dir": "skills/auto"},
}


def render_trace(messages) -> str:
    """CÓ SẴN, KHÔNG SỬA. Chuyển danh sách message của luồng chính thành Markdown (vết - trace).

    Lưu ý: chỉ gồm luồng chính. Việc subagent làm bên trong KHÔNG hiện trong vết;
    chỉ thấy lệnh gọi `task` và báo cáo cuối của subagent.
    """
    home = str(Path.home())

    def clean(text) -> str:
        return str(text).replace(home, "~")[:1500]

    parts = []
    for m in messages:
        if isinstance(m, AIMessage):
            if m.content:
                parts.append(f"### Assistant\n{clean(m.content)}")
            for tc in m.tool_calls:
                parts.append(f"### Tool call: {tc['name']}\n{clean(json.dumps(tc['args'], ensure_ascii=False))}")
        elif isinstance(m, ToolMessage):
            parts.append(f"### Tool result\n{clean(m.content)}")
        else:
            parts.append(f"### {m.type.capitalize()}\n{clean(m.content)}")
    return "\n\n".join(parts)


def run_task(task_id: str, condition: str, results_dir="results", model=None, recursion_limit: int = 60) -> dict:
    """Chạy MỘT tác vụ dưới MỘT điều kiện, chấm điểm, ghi kết quả, và trả về bản ghi (record)."""
    import tempfile, shutil, time
    from datetime import datetime, timezone
    from langchain_core.callbacks import UsageMetadataCallbackHandler
    from .agent import build_agent

    cfg = CONDITIONS[condition]
    task = get_task(task_id)
    skills_dir = ROOT / cfg["skills_dir"] if cfg["skills_dir"] else None
    out = Path(results_dir) / condition / task_id
    out.mkdir(parents=True, exist_ok=True)

    sandbox = Path(tempfile.mkdtemp(prefix="lab-"))
    record: dict = {
        "task": task_id,
        "condition": condition,
        "role": task.role,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    messages: list = []
    final = ""
    try:
        prepare_sandbox(task, sandbox, skills_dir)
        hash_before = hash_dir(sandbox / "skills")
        record["skills_sha256"] = hash_before

        agent = build_agent(
            sandbox,
            mode=cfg["mode"],
            use_skills=(skills_dir is not None),
            model=model,
        )
        usage = UsageMetadataCallbackHandler()
        t0 = time.time()
        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": task.instruction}]},
                config={"callbacks": [usage], "recursion_limit": recursion_limit},
            )
            messages = result.get("messages") or []
            final = str(messages[-1].content) if messages else ""
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["seconds"] = round(time.time() - t0, 1)
        token_totals = {"input": 0, "output": 0, "total": 0}
        for v in (usage.usage_metadata or {}).values():
            token_totals["input"] += v.get("input_tokens", 0) or 0
            token_totals["output"] += v.get("output_tokens", 0) or 0
            token_totals["total"] += v.get("total_tokens", 0) or 0
        record["tokens"] = token_totals

        calls = []
        for m in messages:
            tc = getattr(m, "tool_calls", None) or []
            calls.extend(tc)
        record["tool_calls"] = len(calls)
        record["subagent_calls"] = sum(1 for c in calls if c.get("name") == "task")

        skills_seen = set()
        for c in calls:
            if c.get("name") == "read_file":
                fp = (c.get("args") or {}).get("file_path", "")
                if "skills/" in fp:
                    after = fp.split("skills/", 1)[1]
                    name = after.split("/", 1)[0]
                    if name:
                        skills_seen.add(name)
        record["skills_read"] = len(skills_seen)

        try:
            hash_after = hash_dir(sandbox / "skills")
            record["skills_modified"] = hash_after != hash_before
        except Exception:
            record["skills_modified"] = False
        record["final_message"] = final

        try:
            g = grade(task, sandbox / "workspace")
            record["score"] = g.get("score", 0)
            record["passed"] = g.get("passed", 0)
            record["total"] = g.get("total", 0)
            record["checks"] = g.get("checks", [])
        except Exception as exc:
            record.setdefault("error", "")
            record["error"] += f" | GRADE_ERR: {type(exc).__name__}: {exc}"
            record["score"] = 0
            record["passed"] = 0
            record["total"] = 0
            record["checks"] = []

        (out / "trace.md").write_text(render_trace(messages), encoding="utf-8")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    (out / "run.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


def main(argv=None):
    """CÓ SẴN, KHÔNG SỬA. Giao diện dòng lệnh (CLI): --condition, --tasks (id... | all | learn | eval), --results, --recursion-limit.

    In mỗi lần chạy một dòng: điều kiện, id, passed/total, token, số tool call, số giây, lỗi (nếu có).
    """
    ap = argparse.ArgumentParser(description="Run tasks under one condition.")
    ap.add_argument("--condition", required=True, choices=sorted(CONDITIONS))
    ap.add_argument("--tasks", nargs="+", default=["all"], help="task ids, or 'all', 'learn', 'eval'")
    ap.add_argument("--results", default="results")
    ap.add_argument("--recursion-limit", type=int, default=60)
    args = ap.parse_args(argv)
    if args.tasks == ["all"]:
        ids = [t.id for t in list_tasks()]
    elif args.tasks in (["learn"], ["eval"]):
        ids = [t.id for t in list_tasks(args.tasks[0])]
    else:
        ids = args.tasks
    for tid in ids:
        try:
            r = run_task(tid, args.condition, args.results, recursion_limit=args.recursion_limit)
        except Exception as exc:  # noqa: BLE001
            print(f"{args.condition:13s} {tid:11s} CRASH {type(exc).__name__}: {exc}", flush=True)
            continue
        print(f"{args.condition:13s} {tid:11s} score={r['passed']}/{r['total']} tokens={r['tokens']['total']} "
              f"calls={r['tool_calls']} {r['seconds']}s" + (f" ERROR={r['error']}" if r["error"] else ""), flush=True)


if __name__ == "__main__":
    main()
