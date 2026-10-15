
from gpt_researcher import GPTResearcher


async def research_jobs(query: str) -> str:
    researcher = GPTResearcher(
        query=query,
        report_type="research_report",
    )

    await researcher.conduct_research()
    return await researcher.write_report()
