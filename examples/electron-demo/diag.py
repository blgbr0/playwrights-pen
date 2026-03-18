import sys
import asyncio
from playwrights_pen.core.parser import TestParser
from playwrights_pen.config import settings

async def main():
    print(f"LLM base: {settings.llm_base_url}")
    print(f"LLM model: {settings.llm_model}")
    parser = TestParser()
    try:
        desc = "输入姓名PlaywrightsPen，随便输入一些评价意见，点击提交评价按钮"
        print(f"Parsing: {desc}")
        testcase = await parser.create_testcase("test", desc)
        print("Steps:")
        for step in testcase.steps:
            print(f"- {step.action}: {step.description}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
