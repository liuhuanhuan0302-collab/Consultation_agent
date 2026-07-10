import argparse
import asyncio
import random
import statistics
import string
import time
from dataclasses import dataclass

import httpx


@dataclass
class RequestResult:
    name: str
    ok: bool
    status_code: int
    elapsed_ms: float
    error: str = ""


def random_text(prefix: str, length: int = 6) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}-{suffix}"


def random_phone() -> str:
    return "1" + random.choice("3456789") + "".join(random.choices(string.digits, k=9))


async def timed_request(client: httpx.AsyncClient, name: str, method: str, path: str, **kwargs) -> tuple[RequestResult, httpx.Response | None]:
    started = time.perf_counter()
    try:
        response = await client.request(method, path, **kwargs)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return RequestResult(name, response.is_success, response.status_code, elapsed_ms), response
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return RequestResult(name, False, 0, elapsed_ms, repr(exc)), None


async def run_virtual_user(client: httpx.AsyncClient, index: int, full_submit: bool) -> list[RequestResult]:
    results: list[RequestResult] = []
    result, response = await timed_request(
        client,
        "create_session",
        "POST",
        "/api/public/sessions",
        json={"source_code": "load_test", "metadata": {"user_index": index}},
    )
    results.append(result)
    if not response or not response.is_success:
        return results
    session_token = response.json()["session_token"]

    result, response = await timed_request(client, "questions", "GET", "/api/public/questions")
    results.append(result)
    if not response or not response.is_success:
        return results
    modules = response.json()
    questions = [question for module in modules for question in module["questions"]]
    if not questions:
        results.append(RequestResult("questions_non_empty", False, 0, 0, "题库为空"))
        return results

    lead_payload = {
        "session_token": session_token,
        "company_name": random_text("压测公司"),
        "industry": random.choice(["制造业", "零售消费", "医疗健康", "专业服务"]),
        "company_size": random.choice(["1-200人", "200-500人", "500-1000人", "2000-5000人", "5000人以上"]),
        "annual_revenue": random.choice(["1000万以下", "1000万-5000万", "5000万-1亿", "1亿以上"]),
        "contact_name": random_text("测试联系人", 4),
            "position": random.choice(["CEO", "总经理", "数字化负责人", "运营负责人"]),
            "phone": random_phone(),
            "email": f"load-test-{index}-{random_text('mail', 4)}@example.com",
            "wechat": "",
        "ai_focus": random.choice(["客服提效", "生产排程", "销售线索跟进", "知识库问答", "流程自动化"]),
        "privacy_accepted": True,
        "contact_authorized": True,
        "source_code": "load_test",
    }
    result, response = await timed_request(client, "submit_lead", "POST", "/api/public/leads", json=lead_payload)
    results.append(result)
    if not response or not response.is_success:
        return results
    submission_id = response.json()["submission_id"]

    draft_answers = [{"question_id": question["id"], "score": random.randint(0, 4)} for question in questions[: min(10, len(questions))]]
    result, _ = await timed_request(
        client,
        "save_draft",
        "PUT",
        f"/api/public/submissions/{submission_id}/draft",
        json={"answers": draft_answers},
    )
    results.append(result)

    if full_submit:
        all_answers = [{"question_id": question["id"], "score": random.randint(0, 4)} for question in questions]
        result, _ = await timed_request(
            client,
            "submit_questionnaire",
            "POST",
            f"/api/public/submissions/{submission_id}/submit",
            json={"answers": all_answers},
        )
        results.append(result)

    return results


def print_summary(results: list[RequestResult], total_seconds: float) -> None:
    grouped: dict[str, list[RequestResult]] = {}
    for result in results:
        grouped.setdefault(result.name, []).append(result)

    print(f"\n压测完成：{len(results)} 个请求，用时 {total_seconds:.2f}s，吞吐约 {len(results) / total_seconds:.2f} req/s")
    print("-" * 86)
    print(f"{'接口':<24}{'次数':>6}{'成功率':>10}{'平均ms':>12}{'P95ms':>12}{'最大ms':>12}{'失败':>8}")
    print("-" * 86)
    for name, items in grouped.items():
        elapsed_values = sorted(item.elapsed_ms for item in items)
        ok_count = sum(1 for item in items if item.ok)
        p95 = elapsed_values[max(0, int(len(elapsed_values) * 0.95) - 1)]
        print(
            f"{name:<24}{len(items):>6}{ok_count / len(items):>9.0%}"
            f"{statistics.mean(elapsed_values):>12.1f}{p95:>12.1f}{max(elapsed_values):>12.1f}{len(items) - ok_count:>8}"
        )

    failures = [item for item in results if not item.ok]
    if failures:
        print("\n失败样例：")
        for item in failures[:10]:
            print(f"- {item.name}: status={item.status_code}, error={item.error}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="咨询诊断 Agent 简易压力测试")
    parser.add_argument("--host", default="http://127.0.0.1:8000", help="后端 API 地址")
    parser.add_argument("--users", type=int, default=20, help="模拟用户数量")
    parser.add_argument("--concurrency", type=int, default=5, help="并发数量")
    parser.add_argument("--full-submit", action="store_true", help="提交完整问卷并生成报告；会触发模型/报告逻辑")
    args = parser.parse_args()

    semaphore = asyncio.Semaphore(args.concurrency)

    started = time.perf_counter()
    timeout = httpx.Timeout(60.0, connect=10.0)
    limits = httpx.Limits(max_connections=max(args.concurrency * 2, 100), max_keepalive_connections=max(args.concurrency, 20))
    async with httpx.AsyncClient(base_url=args.host.rstrip("/"), timeout=timeout, trust_env=False, limits=limits) as client:
        async def limited_user(index: int) -> list[RequestResult]:
            async with semaphore:
                return await run_virtual_user(client, index, args.full_submit)

        batches = await asyncio.gather(*(limited_user(index) for index in range(args.users)))
    elapsed = time.perf_counter() - started
    print_summary([item for batch in batches for item in batch], elapsed)


if __name__ == "__main__":
    asyncio.run(main())
