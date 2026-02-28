import asyncio
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

from ollama import chat

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def format_tools_for_prompt(tools: List[Any]) -> str:
    """
    把 MCP tools/list 回传的工具，整理成适合放进 system prompt 的文字描述。
    """
    lines: List[str] = []
    for t in tools:
        name = getattr(t, "name", None) or t.get("name")
        desc = getattr(t, "description", None) or t.get("description") or ""
        input_schema = getattr(t, "inputSchema", None) or t.get("inputSchema") or {}

        lines.append(f"- name: {name}")
        if desc:
            lines.append(f" description: {desc}")
        
        try:
            schema_str = json.dumps(input_schema, ensure_ascii=False)
        except Exception:
            schema_str = str(input_schema)
        lines.append(f" inputSchema: {schema_str}")
    return "\n".join(lines)

def build_system_prompt(tool_text: str) -> str:
    """
    因为 Ollama 没有内建 tool calling，我们用 prompt 规范输出格式：
    - 若要用工具: 只能输出一个 JSON 物件（不准多字）
    - host 会执行 tool call，然后把 tool_result 再喂回来
    """
    return f"""你是一个能使用外部工具的助理。你可以选择直接回答，或是使用下列工具来取得咨询。

可用工具：
{tool_text}

=== 工具呼叫规则 ===

当你需要呼叫工具时，你必须只输出一个 JSON 物件，且不要输出任何其他文字。
JSON 格式如下：

{{
  "tool": "<tool_name>",
  "args": {{ ... }}
}}

- tool: 必须是上面清单中的工具名称
- args: 必须符合该工具的 inputSchema

当你不需要使用工具时，请用正常自然语言回答。

=== 工具结果回传格式 ===
当你呼叫工具后，我会把工具执行结果以一则 user 讯息回传，格式是：

tool_result: <JSON>

收到 tool_result 后，请根据结果继续推理；如果还需要更多工具呼叫，请再次输出符合规则的 JSON 物件。
"""

def try_parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """
    侦测模型是否输出 [纯 JSON] 的 tool call。
    - 成功：回传 dict（含 tool/args）
    - 失败：回传 None（代表是一般回答）
    """
    text = text.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        obj = json.loads(text)
    except Exception:
        return None
    
    if not isinstance(obj, dict):
        return None
    if "tool" not in obj:
        return None
    
    # args 可省略，预设空 dict
    if "args" not in obj:
        obj["args"] = {}
    return obj

async def main() -> None:
    server_script = "simple_mcp.py"

    # 1) 用 stdio 启动 MCP server
    #    这里 host 会开一个 subprocess 跑你的 server.py，stdin/stdout 用来传 MCP 讯息
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 2) 启动 MCP 的 session 并取得工具清单
            await session.initialize()
            tools_result = await session.list_tools()

            tools = getattr(tools_result, "tools", None) or tools_result.get("tools", [])
            tool_text = format_tools_for_prompt(tools)
            system_prompt = build_system_prompt(tool_text)

            # 3) 进入互动式聊天
            messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
            print(f"🤖 　系统讯息：\n{system_prompt}\n")
            print("✅ 已连上 MCP server（stdio）。输入你的问题开始测试。")
            print("💡 提示：你可以试试：'列出当前资料夹档案' 或 '把 README.md 里的人名换成 John'。\n")

            while True:
                user_input = input("你： ").strip()
                if not user_input:
                    continue
                # 输入 exit or quit 离开
                if user_input.lower() in {"exit", "quit"}:
                    break
                
                messages.append({"role": "user", "content": user_input})

                while True:
                    # 4) 呼叫 Ollama
                    resp = chat(
                        model="qwen3:4b",
                        messages=messages,
                        options={"temperature": 0.2}
                    )
                    assistant_text = resp["message"]["content"]
                    tool_call = try_parse_tool_call(assistant_text)

                    if not tool_call:
                        # 没有使用工具就正常回答
                        messages.append({"role": "assistant", "content": assistant_text})
                        print(f"\nAI：{assistant_text}\n")
                        break
                    
                    tool_name = tool_call["tool"]
                    tool_args = tool_call.get("args", {})
                    print(f"\n🤖 AI 想呼叫工具：{tool_name}，参数：{tool_args}")

                    # 5) 透过 MCP 的 session 去执行工具
                    try:
                        result = await session.call_tool(tool_name, tool_args)
                        if hasattr(result, "model_dump"):
                            result_json = result.model_dump()
                        elif isinstance(result, dict):
                            result_json = result
                        else:
                            result_json = {"result": str(result)}
                    except Exception as e:
                        result_json = {"error": str(e), "tool": tool_name, "args": tool_args}
                    
                    # 6) 把 tool_result 丟回模型，让它接着推理/回答/或再呼叫下一个工具
                    messages.append({"role": "assistant", "content": assistant_text})
                    messages.append(
                        {
                            "role": "user",
                            "content": "tool_result: " + json.dumps(result_json, ensure_ascii=False),
                        }
                    )
                    print(f"🛠 工具执行结果：{result_json}\n")

if __name__ == "__main__":
    asyncio.run(main())