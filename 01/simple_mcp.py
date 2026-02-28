from pathlib import Path
from typing import Any, Dict, List
from fastmcp import FastMCP

mcp = FastMCP(name="SimpleMCPTestServer")

# helper: 把使用者输入的路径转成绝对路径
def resolve_abs_path(path_str : str) -> Path:
    """
    [功能] 把使用者输入的路径转成绝对路径

    范例：
      file.py -> /Users/home/mihail/modern-software-dev-lectures/file.py  
    """
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path

@mcp.tool
def read_file_tool(filename: str) -> Dict[str, Any]:
    """
    [功能] 读取使用者指定档案的完整内容

    参数:
      filename: 要读取的档案路径（可相对或绝对）
    
    回传：
      - file_path: 档案的绝对路径（字串）
      - content: 档案内容（字串）
    """
    full_path = resolve_abs_path(filename)
    print(full_path)
    if not full_path.exists():
        return {
            "file_path": str(full_path),
            "error": "file not found"
        }
    if not full_path.is_file():
        return {
            "file_path": str(full_path),
            "error": "path is not a file"
        }
    
    try:
        with open(str(full_path), "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "file_path": str(full_path),
            "error": str(exc)
        }
    return {
        "file_path": str(full_path),
        "content": content
    }

@mcp.tool
def list_files_tool(path: str) -> Dict[str, Any]:
    """
    [功能] 列出使用者提供的资料夹底下有哪些档案/子资料夹

    参数：
      path: 要列出内容的资料夹路径
    
    回传：
      - path: 资料夹的绝对路径（字串）
      - files: 一个阵列, 每个元素包含:
          - filename: 文件名
          - type: "file" 或 "dir"
    """
    full_path = resolve_abs_path(path)
    all_files = []
    for item in full_path.iterdir():
        isFile = item.is_file()
        all_files.append({
            "filename": ("💙" if isFile else "📂") + item.name,
            "type": "file" if isFile else "dir"
        })
    return {
        "path": str(full_path),
        "files": all_files
    }

@mcp.tool
def edit_file_tool(path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    """
    [功能] 编辑档案内容
    - 用 new_str 取代第一次出现的 old_str
    - 若 old_str 是空字串 "": 则直接用 new_str 建立/覆写档案

    参数:
      path: 要编辑的档案路径
      old_str: 要被替换的旧字串
      new_str: 替换成的新字串
    
    回传:
      - path: 档案绝对路径（字串）
      - action: 执行结果（created_file / edited / old_str not found)
    """
    full_path = resolve_abs_path(path)
    p = Path(full_path)

    # old_str 是空字串：直接建立或覆写整个档案内容
    if old_str == "":
        p.write_text(new_str, encoding="utf-8")
        return {
            "path": str(full_path),
            "action": "created_file"
        }

    original = p.read_text(encoding="utf-8")

    # 找不到 old_str 就回报
    if original.find(old_str) == -1:
        return {
            "path": str(full_path),
            "action": "old_str not found"
        }

    # 只替换第一次出现的 old_str
    edited = original.replace(old_str, new_str, 1)
    p.write_text(edited, encoding="utf-8")
    return {
        "path": str(full_path),
        "action": "edited"
    }

if __name__ == "__main__":
    mcp.run()