"""
Reddit Signal Scanner - 分析报告端点

Linus原则："数据结构决定一切"
- 统一的响应格式消除特殊情况
- 数据库驱动的真实报告
- 清晰的错误处理机制
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import ReportResponse, ResponseStatus, SuccessResponse
from ...services.report_formatter import get_formatted_report

router = APIRouter(prefix="/report", tags=["分析报告"])


@router.get("/{task_id}", response_model=ReportResponse, summary="获取分析报告")
async def get_analysis_report(
    task_id: str,
    format: str = Query(default="full", description="报告格式：full/summary/insights"),
    db: Session = Depends(get_db),
) -> ReportResponse:
    """
    获取指定任务的分析报告

    Args:
        task_id: 任务ID (UUID格式)
        format: 报告格式 (full/summary/insights)
        db: 数据库会话

    Returns:
        ReportResponse: 标准化的报告响应

    Raises:
        HTTPException: 参数验证失败或数据查询失败
    """

    # 参数验证
    if not task_id or len(task_id) < 8:
        raise HTTPException(status_code=400, detail="无效的任务ID格式，需要有效的UUID")

    if format not in ["full", "summary", "insights"]:
        raise HTTPException(
            status_code=400, detail="不支持的报告格式，支持: full/summary/insights"
        )

    try:
        # 使用报告格式化服务获取真实数据
        report_data = get_formatted_report(db, task_id, format)

        # 统一响应格式 - 消除特殊情况
        if report_data.get("success"):
            return ReportResponse(
                status=ResponseStatus.SUCCESS,
                message=f"分析报告获取成功（{format}格式）",
                timestamp=report_data["timestamp"],
                data=report_data["data"],
            )
        else:
            # 数据不存在的情况
            raise HTTPException(
                status_code=404, detail=report_data.get("message", "未找到分析报告")
            )

    except ValueError as e:
        # 参数格式错误
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # 数据库查询错误
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # 其他未预期错误
        raise HTTPException(status_code=500, detail=f"报告获取失败: {str(e)}")


@router.get("/{task_id}/export", response_model=SuccessResponse, summary="导出分析报告")
async def export_analysis_report(
    task_id: str,
    format: str = Query(default="json", description="导出格式：json/pdf/csv"),
    db: Session = Depends(get_db),
) -> SuccessResponse:
    """
    导出分析报告到指定格式

    Args:
        task_id: 任务ID
        format: 导出格式 (json/pdf/csv)
        db: 数据库会话

    Returns:
        SuccessResponse: 包含下载链接的响应

    Note:
        当前实现为Mock版本，返回模拟下载链接
        TODO: prd02-07实现真实报告导出服务
    """

    # 参数验证
    if format not in ["json", "pdf", "csv"]:
        raise HTTPException(
            status_code=400, detail="不支持的导出格式，支持: json/pdf/csv"
        )

    try:
        # 验证任务是否存在
        report_data = get_formatted_report(db, task_id, "full")

        if not report_data.get("success"):
            raise HTTPException(status_code=404, detail="任务不存在，无法导出报告")

        # Mock导出链接（TODO: 实现真实导出服务）
        download_url = (
            f"/api/v1/report/{task_id}/download?format={format}&token=export_token"
        )

        from datetime import datetime, timezone

        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return SuccessResponse(
            status=ResponseStatus.SUCCESS,
            message=f"报告导出准备完成（{format.upper()}格式）",
            timestamp=current_time,
            data={
                "download_url": download_url,
                "expires_in": 3600,  # 1小时后过期
                "format": format.upper(),
                "task_id": task_id,
                "estimated_size_kb": 150,  # 预估文件大小
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出准备失败: {str(e)}")
