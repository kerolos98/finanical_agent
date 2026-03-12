import asyncio
from client import MCPClient

def get_stock_price(query):
    agent_client = MCPClient()
    
    async def wrapper():
        await agent_client.connect_to_server(r"server/finance_server.py")
        return await agent_client.ollama_process_query(query)
    
    return asyncio.run(wrapper())

price = get_stock_price("give me apple stock price")
print(price)
