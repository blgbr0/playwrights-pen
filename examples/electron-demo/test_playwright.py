import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        print([m for m in dir(pg) if not m.startswith("_")])
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())
