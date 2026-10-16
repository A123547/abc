
# app/api/extraction.py

import logging

from fastapi import APIRouter, HTTPException
from openai import APIError

from app.schemas.job import (
    ExtractionRequest,
    ExtractionResponse,
)
from app.services.extraction_pipeline import (
    extract_document,
)


router = APIRouter(tags=["招聘信息提取"])
logger = logging.getLogger(__name__)


@router.post(
    "/extract",
    response_model=ExtractionResponse,
)
async def extract_job_postings(
    request: ExtractionRequest,
):
    try:
        result = await extract_document(
            request.content
        )

    except APIError:
        logger.exception("DeepSeek API 调用失败")
        raise HTTPException(
            status_code=502,
            detail="模型服务调用失败",
        )

    except ValueError:
        logger.exception("招聘公告解析失败")
        raise HTTPException(
            status_code=502,
            detail="模型返回的数据格式无效",
        )

    except RuntimeError:
        logger.exception("服务配置错误")
        raise HTTPException(
            status_code=503,
            detail="模型服务配置错误",
        )

    logger.info(
        "Extraction completed: mode=%s jobs=%s reasons=%s",
        result.mode,
        len(result.jobs),
        result.reasons,
    )

    return ExtractionResponse(
        source_url=request.source_url,
        jobs=result.jobs,
        total=len(result.jobs),
    )
