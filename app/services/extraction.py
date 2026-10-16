
import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.schemas.job import JobPosting

load_dotenv()


class JobBatch(BaseModel):
    jobs: list[JobPosting]


SYSTEM_PROMPT = """
你是招聘公告结构化解析助手。

任务：从用户提供的招聘公告原文中提取岗位信息。

要求：
1. 只使用公告原文，不使用外部知识。
2. 一份公告可能包含多个岗位。
3. 每个岗位分别输出一个对象。
4. 没有明确提供的信息填 null。
5. 不得猜测学历、专业、时间或招聘人数。
6. majors 必须是字符串数组。
7. graduation_year 必须是四位整数或 null。
8. deadline 使用 YYYY-MM-DD 或 null。
9. evidence 保存字段对应的原文片段。
10. evidence 的内容必须逐字摘自公告。
11. 如专业要求为“专业不限”，不要自行列举专业。
12. 不要判断用户是否符合招聘资格。

只返回 JSON，不要返回 Markdown。

JSON 顶层格式：
{
  "jobs": [
    {
      "organization": null,
      "position": null,
      "city": null,
      "degree_required": null,
      "majors": [],
      "graduation_year": null,
      "headcount": null,
      "deadline": null,
      "evidence": {}
    }
  ]
}

如果未发现可识别的招聘岗位，返回：
{"jobs": []}
"""


async def extract_jobs(content: str) -> list[JobPosting]:
    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY 未配置"
        )

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=90.0,
    )

    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": content,
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=3000,
    )

    raw = response.choices[0].message.content

    if not raw:
        raise ValueError("模型返回内容为空")

    try:
        data = json.loads(raw)
        result = JobBatch.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            "模型返回的职位 JSON 不符合结构要求"
        ) from exc

    return result.jobs
