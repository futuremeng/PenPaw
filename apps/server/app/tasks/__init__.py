"""异步任务层。

M1：Stage 3 走进程内线程（app/services/task_registry.py），SSE 直接轮询内存状态。
M3：接入真实 DiffVG 后引入 Celery + Redis 跨进程队列（PRD §4.2 队列深度 20、
排队 > 60s 提示），任务状态写入 Redis，SSE 端点改为读 Redis，接口不变。
"""
