import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.goto("https://example.com")
        
        client = await pg.context.new_cdp_session(pg)
        try:
            tree = await client.send("Accessibility.getFullAXTree")
            print("Got AX tree with", len(tree.get("nodes", [])), "nodes")
            print(tree["nodes"][:2])
        except Exception as e:
            print("Error:", e)
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())
