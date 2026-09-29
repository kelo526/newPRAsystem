"""进程内事件总线：后台执行线程 → SSE 客户端广播。

设计：订阅者各持有一个线程安全的 queue.Queue；运行线程状态变化时
publish（直接 put，无 asyncio 依赖）；SSE 端点在自己的事件循环里
轮询取出推给浏览器。断开时取消订阅，队列残留自动清理。
"""
import json
import queue
import threading

_subscribers: list[queue.Queue] = []
_lock = threading.Lock()


def subscribe():
    q = queue.Queue(maxsize=100)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q):
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def publish(event: str, data: dict):
    """线程安全：任何线程可调用（如任务执行线程）。"""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    with _lock:
        for q in list(_subscribers):
            try:
                q.put_nowait((event, payload))
            except queue.Full:
                pass  # 慢客户端丢事件无妨，前端以全量刷新兜底


def publish_run(task_id, run_id, status, attempt=None):
    """任务运行状态变化的标准事件。"""
    publish("run", {
        "task_id": task_id, "run_id": run_id,
        "status": status, "attempt": attempt,
    })
