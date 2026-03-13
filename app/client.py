import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import ollama

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from google import genai
from google.genai import types

from dotenv import load_dotenv
import os
import sys

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.gemini = genai.Client(api_key=os.getenv("GEMINI_KEY")) if os.getenv("GEMINI_KEY") else None

    async def connect_to_server(self, server_script_path: str):
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
    
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
    
        command = sys.executable if is_python else "node"
    
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )
    
        # FIX: We enter the transport first
        # This keeps the stdio_client alive across the session
        self.transport = stdio_client(server_params)
        self.stdio, self.write = await self.exit_stack.enter_async_context(self.transport)
    
        # FIX: Initialize the session within the same stack
        self.session = ClientSession(self.stdio, self.write)
        await self.exit_stack.enter_async_context(self.session)
    
        await self.session.initialize()
    
        response = await self.session.list_tools()
        print("\nConnected to server with tools:", [tool.name for tool in response.tools])

    async def ollama_process_query(self, query: str) -> str:
        """Process a query using Ollama + MCP tools with prompts, resources, and automatic ticker extraction."""

        # -------------------------------
        # 1. Get MCP tools and map to Ollama
        # -------------------------------
        mcp_tools_resp = await self.session.list_tools()
        ollama_tools = [map_ollama_tool(tool) for tool in mcp_tools_resp.tools]

        query_lower = query.lower()
        ticker = None

        # -------------------------------
        # 2. Determine if this is a stock query
        # -------------------------------
        stock_keywords = [
            "stock",
            "analyze",
            "price",
            "fundamentals",
            "valuation",
            "ma",
            "rsi",
        ]
        is_stock_query = any(kw in query_lower for kw in stock_keywords)

        if is_stock_query:
            # Fetch the ticker extraction prompt
            prompt_resp = await self.session.get_prompt("extract_ticker_prompt")
            extract_prompt = prompt_resp.messages[0].content.text

            # Ask Ollama to extract ticker
            extraction_messages = [
                {"role": "system", "content": extract_prompt},
                {"role": "user", "content": query},
            ]

            extraction_resp = ollama.chat(
                model="llama3.2:1b", messages=extraction_messages, options={"temperature": 0.1}
            )

            ticker_candidate = extraction_resp["message"]["content"].strip().upper()
            if ticker_candidate != "UNKNOWN":
                ticker = ticker_candidate

        # -------------------------------
        # 3. Select main prompt
        # -------------------------------
        if "portfolio" in query_lower:
            prompt_resp = await self.session.get_prompt("portfolio_analysis_prompt")
        elif is_stock_query:
            prompt_resp = (
                await self.session.get_prompt(
                    "stock_analysis_prompt", {"ticker": ticker or "UNKNOWN"}
                )
                if "analyze" in query_lower
                else None
            )
        else:
            # fallback generic prompt if needed
            prompt_resp = await self.session.get_prompt("portfolio_analysis_prompt")

        if prompt_resp:
            system_prompt = prompt_resp.messages[0].content.text
        else:
            system_prompt = "You are a stock market and a finance expert please help with the following:"

        # -------------------------------
        # 4. Fetch resources
        # -------------------------------
        portfolio = await self.session.read_resource("portfolio://main")
        rules = await self.session.read_resource("knowledge://investing_rules")

        # -------------------------------
        # 5. Initialize message history
        # -------------------------------
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "system",
                "content": f"User portfolio:\n{portfolio.contents[0].text}",
            },
            {
                "role": "system",
                "content": f"Investment rules:\n{rules.contents[0].text}",
            },
            {"role": "user", "content": query},
        ]

        final_output = []

        # -------------------------------
        # 6. Tool-handling loop
        # -------------------------------

        while True:
            response = ollama.chat(
                model="llama3.2:1b", messages=messages, tools=ollama_tools, options={"temperature": 0.1}, keep_alive=-1
            )

            message = response["message"]
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                final_output.append(message["content"])
                break

            messages.append(message)

            # Execute each requested tool
            for call in tool_calls:
                tool_name = call["function"]["name"]
                tool_args = call["function"]["arguments"]

                result = await self.session.call_tool(tool_name, tool_args)

                messages.append(
                    {"role": "tool", "name": tool_name, "content": str(result.content)}
                )

        return "\n".join(final_output)

    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and MCP tools"""

        # 1. Fetch and map MCP tools to Gemini Function Declarations
        mcp_tools_resp = await self.session.list_tools()
        gemini_tools = [map_mcp_to_gemini(tool) for tool in mcp_tools_resp.tools]

        # 2. Start a Chat Session (This manages conversation state/history automatically)

        chat = self.gemini.chats.create(
            model="gemini-2.5-flash-lite",
            config={"tools": [{"function_declarations": gemini_tools}]},
        )

        final_output_parts = []

        # 3. Initial request
        response = chat.send_message(query)

        # 4. Enter the tool-handling loop
        while True:
            # We look at the actual Parts of the response
            # Gemini 3 might include 'text', 'thought', and 'function_call' parts
            parts = response.candidates[0].content.parts

            # Find all function calls in this turn
            function_calls = [p.function_call for p in parts if p.function_call]

            if not function_calls:
                # If no more calls, we are done
                final_output_parts.append(response.text)
                break

            # 5. Process all calls found in the current turn
            tool_responses = []
            for call in function_calls:
                tool_name = call.name
                tool_args = call.args

                # Execute the tool via MCP
                # Note: result.content from MCP is often a list of content blocks
                result = await self.session.call_tool(tool_name, tool_args)

                # Gemini 3 is strict: the response must be a map
                # We wrap the MCP result in a 'content' key
                tool_responses.append(
                    {
                        "function_response": {
                            "name": tool_name,
                            "response": {"content": result.content},
                        }
                    }
                )

            # 6. Send the responses back to the chat session
            # The 'chat' object handles the 'thought_signature' under the hood
            # as long as we are responding to the *immediate* previous turn.
            try:
                response = chat.send_message(tool_responses)
            except Exception as e:
                # If you still get the signature error, it means the session
                # state was desynced. We log it here.
                print(f"Error sending tool results: {e}")
                raise

        return "\n".join(final_output_parts)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.ollama_process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Safe cleanup to prevent AnyIO RuntimeError"""
        try:
            # Close the stack in LIFO order
            await self.exit_stack.aclose()
        except RuntimeError as e:
            if "cancel scope" in str(e):
                # This suppresses the noisy AnyIO error during forced shutdown
                pass
            else:
                raise e


async def main():
    """if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()"""
    agent_client = MCPClient()
    try:
        await agent_client.connect_to_server(r"./server/finance_server.py")
        await agent_client.chat_loop()
    finally:
        await agent_client.cleanup()


def map_mcp_to_gemini(mcp_tool):
    """
    Cleans MCP tool schema for Gemini/Pydantic compatibility.
    """
    # Deep copy or dictionary comprehension to avoid mutating original
    schema = mcp_tool.inputSchema.copy()

    # 1. Remove 'additionalProperties' which causes the 'extra_forbidden' error
    if "additionalProperties" in schema:
        del schema["additionalProperties"]

    # Recursively remove it from nested objects if necessary
    if "properties" in schema:
        for prop in schema["properties"].values():
            if isinstance(prop, dict) and "additionalProperties" in prop:
                del prop["additionalProperties"]

    return {
        "name": mcp_tool.name,
        "description": mcp_tool.description,
        "parameters": schema,
    }


def map_ollama_tool(mcp_tool):
    schema = mcp_tool.inputSchema.copy()
    if "additionalProperties" in schema:
        del schema["additionalProperties"]
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            "parameters": schema,
        },
    }


if __name__ == "__main__":
    import sys

    asyncio.run(main())
