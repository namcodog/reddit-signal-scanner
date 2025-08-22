"""
Reddit Signal Scanner - FastAPI 主应用入口

基于 Linus Torvalds 设计哲学:
- 简单胜过聪明
- 数据结构优先
- 永不破坏用户空间

TODO: 需要prd02-01完成后实现具体内容
"""

from fastapi import FastAPI

app = FastAPI(
    title="Reddit Signal Scanner API",
    description="30秒输入，5分钟分析，找到目标客户的真实声音",
    version="0.1.0",
)


@app.get("/")
def read_root():
    return {"message": "Reddit Signal Scanner API v0.1.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "reddit-signal-scanner"}
