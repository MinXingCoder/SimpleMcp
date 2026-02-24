import anthropic
import json
import os
import inspect

from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict, List, Tuple

# 载入环境变量
load_dotenv()

auth_token = None
with open("env.json", "r") as f:
    json_str = json.loads(f.read())
    auth_token = json_str["ANTHROPIC_AUTH_TOKEN"]

# 建立 Claude 客户端
claude_client = anthropic.Anthropic(
    api_key = auth_token.strip()
)

# 终端颜色设定
YOU_COLOR = "\u001b[94m"        # 使用者输入: 蓝色
ASSISTANT_COLOR = "\u001b[93m"  # AI 回应: 黄色
RESET_COLOR = "\u001b[0m"       # 重置颜色（原本的颜色）

# 系统提示
SYSTEM_PROMPT = """
你是一个程式码助理，目标是协助我们完成程式设计相关的任务。
你可以使用一系列可执行的工具，以下是你可以使用的工具：

{tool_list_repr}

当你想要使用某个工具时，请只回复一行，格式必须完全如下：
tool: TOOL_NAME({{JSON_ARGS}})，不要包含任何其他内容。
请使用精简的单行 JSON，并且使用双引号。
在收到 tool_result(...) 讯息后，请继续完成任务。
如果不需要使用任何工具，请以一般方式回复即可。
"""

# ================ 工具相关设定 ===================

def resolve_abs_path(path_str: str) -> Path:
    """
    将相对路径转成绝对路径。

    范例:
    file.py
    -> /Users/home/mihail/modern-software-dev-lectures/file.py
    """
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path

def read_file_tool(filename: str) -> Dict[str, Any]:
    """
    请取使用者指定的档案完整内容。

    :param filename: 要读取的档案名称或路径
    :return: 包含档案路径与内容的 dict
    """
    full_path = resolve_abs_path(filename)
    print(full_path)    # 印出实际读取的档案路径
    with open(str(full_path), "r") as f:
        content = f.read()
    return {
        "file_path": str(full_path),
        "content": content
    }

def list_files_tool(path: str) -> Dict[str, Any]:
    """
    列出制定资料夹底下的所有档案与子资料夹。

    :param path: 要列出内容的资料夹路径
    :return: 包含档案清单的字典
    """
    full_path = resolve_abs_path(path)
    all_files = []
    for item in full_path.iterdir():
        all_files.append({
            "filename": item.name,
            "type": "file" if item.is_file() else "dir"
        })
    return {
        "path": str(full_path),
        "files": all_files
    }

def edit_file_tool(path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    """
    编辑档案内容：
    - 将档案中 [第一次出现] 的 old_str 换成 new_str
    - 如果 old_str 是空字串，则直接建立或覆写整个档案

    :param path: 要编辑的档案路径
    :param old_str: 要被取代的字串
    :param new_str: 新的字串内容
    :return: 回传一个字典，里面会有档案路径（path）和这次做了什么动作（action）。
    """
    full_path = resolve_abs_path(path)

    # 如果 old_str 是空的，代表直接写入新档案
    if old_str == "":
        full_path.write_text(new_str, encoding="utf-8")
        return {
            "path": str(full_path),
            "action": "created_file"
        }

    original = full_path.read_text(encoding="utf-8")

    # 找不到取代的字串
    if original.find(old_str) == -1:
        return {
            "path": str(full_path),
            "action": "old_str not found"
        }
    
    # 只取代第一次出现的位置
    edited = original.replace(old_str, new_str, 1)
    full_path.write_text(edited, encoding="utf-8")

    return {
        "path": str(full_path),
        "action": "edited"
    }

# 工具注册表：让模型知道有哪些 tool 可以用
TOOL_REGISTRY = {
    "read_file": read_file_tool,
    "list_files": list_files_tool,
    "edit_file": edit_file_tool
}

# 将单一工具转成文字描述（给模型看的）
def get_tool_str_representation(tool_name: str) -> str:
    tool = TOOL_REGISTRY[tool_name]
    return f"""
    Name: {tool_name}
    Description: {tool.__doc__}
    Signature: {inspect.signature(tool)}
    """

# 从模型输出的文字中，解析出工具呼叫
def extract_tool_invocations(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    invocations = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("tool:"):
            continue
        try:
            after = line[len("tool:"):].strip()
            name, rest = after.split("(", 1)
            name = name.strip()
            if not rest.endswith(")"):
                continue
            json_str = rest[:-1].strip()
            args = json.loads(json_str)
            invocations.append((name, args))
        except Exception as e:
            continue
    return invocations

# ================ LLM 呼叫相关设定 ================= #
def get_full_system_prompt():
    """
    组合完整的 system prompt
    （原本的 SYSTEM_PROMPT 加上所有工具的说明）
    """

    tool_str_repr = ""
    for tool_name in TOOL_REGISTRY:
        tool_str_repr += "TOOL\n===" + get_tool_str_representation(tool_name)
        tool_str_repr += f"\n{'='*15}\n"
    return SYSTEM_PROMPT.format(tool_list_repr=tool_str_repr)

def execute_llm_call(conversation: List[Dict[str, str]]):
   """
   调用 Claude API 并返回响应结果
   """ 
   response = claude_client.messages.create(
        model="claude-3-5-sonnet-20240620",
        messages=conversation,
        max_tokens=1024,
        system=get_full_system_prompt()
   )

   return response.content[0].text

# ================== 主程式 =================== #
def run_coding_agent_loop():
    """
    互动回复：
    - 使用者输入
    - 模型回应
    - 若模型要求使用工具，就实际执行
    - 将 tool_result 再丢回给模型
    """
    print(get_full_system_prompt(), "\n\n")

    # conversation = [{
    #     "role": "system",
    #     "content": get_full_system_prompt()
    # }]
    conversation = []

    while True:
        try:
            user_input = input(f"{YOU_COLOR}你: {RESET_COLOR}")
        except (KeyboardInterrupt, EOFError):
            break

        conversation.append({
            "role": "user",
            "content": user_input.strip()
        })    

        while True:
            assistant_response = execute_llm_call(conversation)
            tool_invocations = extract_tool_invocations(assistant_response)

            # 如果没有工具呼叫，直接输出回应
            if not tool_invocations:
                print(f"{ASSISTANT_COLOR}助理: {RESET_COLOR}{assistant_response}", "\n\n")
                conversation.append({
                    "role": "assistant",
                    "content": assistant_response
                })
                break
            
            # 有工具呼叫就逐一执行
            for name, args in tool_invocations:
                tool = TOOL_REGISTRY[name]
                resp = ""
                print("呼叫工具", name, args, "\n\n")

                if name == "read_file":
                    resp = tool(args.get("filename", "."))
                elif name == "list_files":
                    resp = tool(args.get("path", "."))
                elif name == "edit_file":
                    resp = tool(
                        args.get("path", "."),
                        args.get("old_str", ""),
                        args.get("new_str", "")
                    )
                
                # 把工具执行结果回传给模型
                conversation.append({
                    "role": "user",
                    "content": f"tool_result{json.dumps(resp)}"
                })
                print("工具回传结果", resp, "\n\n")
            
if __name__ == "__main__":
    run_coding_agent_loop()