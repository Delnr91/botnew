import asyncio
import sys
sys.path.insert(0, '.')

from src.main import process_and_send_news, init_db, init_llm_clients
import src.main as m

async def test():
    init_db()
    m.llm_clients = init_llm_clients()
    try:
        await process_and_send_news('1781908570', limit=2)
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())

asyncio.run(test())
