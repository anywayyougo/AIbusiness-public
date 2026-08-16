"""
量化AI助手 - 主对话脚本
基于 DeepSeek + 信息源 + 模块化工具架构
"""

import json
import datetime
import sys
import io
import re
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI
from tools.registry import TOOLS, get_tools_manifest_text
from tools.dispatcher import execute_tool
from data_sources.baostock_source import close as baostock_close
from datasource_manager.datasource_manager import DATA_SOURCES

import os
from dotenv import load_dotenv

# 加载 AIbusiness 根目录下的 .env 文件
# 当前文件在 quant/ 子目录，父目录即 AIbusiness
ENV_PATH = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(ENV_PATH)

# ================== UTF-8 编码保障 ==================
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ================== DeepSeek 配置 ==================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY_MARKET")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("未找到 DEEPSEEK_API_KEY_MARKET，请在 .env 文件中配置")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# ================== 追加动态工具清单查询工具 ==================
TOOLS.append({
    "type": "function",
    "function": {
        "name": "list_available_tools",
        "description": "返回当前系统所有可用工具的名称和功能说明。当你不确定某个工具是否存在时，务必调用此函数确认。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
})

# ================== System Prompt（静态部分） ==================
SYSTEM_PROMPT = """你是一个专业的量化投资助手，拥有强大的本地金融数据库和网络搜索能力。你的核心价值在于：**结合本地金融数据与公开网络信息，给出专业、严谨、可验证的投资分析。**

### 核心行为准则（违反将导致严重后果）
1. **绝对诚实与工具验证**：严禁编造任何数据、工具名或函数名。无法获取信息时，如实告知用户。
2. **工具调用优先**：对于结构化金融数据（行情、财报、估值等），优先使用本地工具，本地工具不可用时，自动切换至联网搜索。
3. **信息来源透明**：每个关键数据必须标注来源【本地数据库】或【公开网络信息】。引用网络信息时请附上链接或来源名称。

### 工具使用
- **能力自检**：不确定时先调用 `list_available_tools` 或 `get_baostock_capabilities`。
- **高成本警告**：`get_financial_summary` 消耗6次API调用，仅在用户要求全面分析时使用。
- **宏观工具**：货币供应量等宏观工具仅在用户询问宏观经济时使用。    
- **估值限制**：指数估值可能返回N/A，此时直接使用 `search_web` 搜索。
- **文档查询**：需要了解数据源的具体参数时，可调用 `get_datasource_info` 查看文档。
- **故障排查**：Baostock 工具返回连接超时或网络错误时，可调用 `check_baostock_blacklist` 排查 IP 是否被屏蔽。

### 联网搜索
- `search_web` 目前是你获取网络公开信息的唯一方式，支持通过 tag 和 params 进行金融专业搜索。
- 搜索结果需标注来源。

### 综合分析原则
1. **先本地，后网络**：先获取准确的本地结构化数据，再用网络信息补充定性判断。
2. **数据与逻辑并重**：展示数据后，解释背后逻辑和市场观点。
3. **风险提示不可少**：任何投资结论都必须附带风险提示。
4. **高效分析**：在获取足够数据后，请直接给出结论，避免反复调用工具确认同类信息。

请以专业、谨慎的态度交流，现在开始。"""

# ================== 对话核心（支持多轮工具调用，最多 8 轮） ==================
def chat_with_ai(user_input: str, messages: List[Dict[str, Any]]) -> str | None:
    # 注入当前时间
    now = datetime.datetime.now()
    time_str = now.strftime("%Y年%m月%d日 %H:%M:%S")
    weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    messages.append({"role": "user", "content": f"[当前时间: {time_str} {weekday}] {user_input}"})

    max_turns = 8
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages,               # type: ignore[arg-type]
            tools=TOOLS,                     # type: ignore[arg-type]
            tool_choice="auto",
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
            max_tokens=51200
        )

        assistant_message = response.choices[0].message

        # 打印思考链
        reasoning = getattr(assistant_message, 'reasoning_content', None)
        if reasoning:
            print(f"\n[AI 思考过程 (第{turn_count}轮)]\n{reasoning[:500]}...\n")

        # 如果没有工具调用，直接返回回复内容
        if not assistant_message.tool_calls:
            reply_content = assistant_message.content or ""
            messages.append(assistant_message.model_dump(exclude_unset=True))
            return reply_content

        # 有工具调用：将助手消息加入上下文
        messages.append(assistant_message.model_dump(exclude_unset=True))

        # 执行所有工具调用，并将结果加入上下文
        for tool_call in assistant_message.tool_calls:
            tc: Any = tool_call
            if not hasattr(tc, 'function'):
                continue
            tool_name = tc.function.name
            arguments = json.loads(tc.function.arguments)
            print(f"[工具调用] {tool_name} 参数: {arguments}")

            result = execute_tool(tool_name, arguments)
            if not result.get("success"):
                result["error_hint"] = "该工具返回错误，请检查代码或网络，也可尝试其他数据源。"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

        # 回到循环顶部，再次请求模型处理工具返回结果

    # 达到最大轮数仍未结束
    print(f"[系统] 已达到最大调用轮数 {max_turns}，强制终止。")
    return "抱歉，分析过程中需要的信息较多，已达到系统设定的最大查询轮数。请尝试缩小问题范围，或稍后重试。"

# ================== 主程序 ==================
if __name__ == "__main__":
    print("=" * 50)
    datasource_names = [info['name'] for info in DATA_SOURCES.values()]
    datasource_str = "、".join(datasource_names)
    print(f"数据源：{datasource_str}，模型：DeepSeek V4 Pro")
    print("量化助手已启动！（输入exit或按Ctrl+C可退出）。")
    print(" -- 很高兴再见面！请问有什么可以帮助你的？")
    print("=" * 50)

    # 动态生成当前所有可用工具清单文本
    tool_list_text = get_tools_manifest_text()

    # 将静态规则与动态工具清单合并，作为初始 system 消息
    initial_system_content = SYSTEM_PROMPT + "\n\n" + tool_list_text

    messages: List[Dict[str, Any]] = [{"role": "system", "content": initial_system_content}]

    try:
        while True:
            user_input = input("\n>>> ")
            if user_input.lower() in ["exit", "quit", "退出"]:
                break
            if not user_input.strip():
                continue

            print("AI思考中...")
            answer = chat_with_ai(user_input, messages)
            if answer:
                print("\n" + answer)
            else:
                print("\n(无回复)")
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n程序异常: {e}")
    finally:
        baostock_close()
        print("\n量化AI助手已退出。")