"""
数据源元数据管理器
负责下载、缓存、查询外部数据源的说明文档
"""
import re
import requests
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

import io
import pydoc
import importlib

# 文档存放目录
DOCS_DIR = Path(__file__).resolve().parent / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# 已注册的数据源清单
DATA_SOURCES = {
    "baostock": {
        "name": "Baostock",
        "doc_url": "https://www.baostock.com/mainContent?file=pythonAPI.md",
        "local_file": "baostock_api.md",
        "description": "A股历史行情与财务数据",
    },
    "searxng": {
        "name": "SearXNG",
        "doc_url": "",
        "local_file": "",
        "description": "免费元搜索引擎，用于联网搜索",
        "update_interval_days": 9999,
    },
    "anysearch": {
        "name": "AnySearch",
        "doc_url": "https://raw.githubusercontent.com/anysearch-ai/anysearch-skill/main/SKILL.md",
        "local_file": "anysearch_api.md",
        "description": "面向 AI 的统一实时搜索服务",
    },
     "Ashare": {
        "name": "Ashare",
        "doc_url": "https://raw.githubusercontent.com/mpquant/Ashare/main/README.md",
        "local_file": "Ashare_api.md",
        "description": "A股实时行情数据（腾讯/新浪双核心）",
        "update_interval_days": 30,
    },
        "mytt": {
        "name": "MyTT",
        "doc_url": "https://raw.githubusercontent.com/mpquant/MyTT/main/README.md",
        "local_file": "mytt_api.md",
        "description": "通达信/同花顺技术指标库，提供 MACD、RSI、BOLL 等 50+ 指标",
        "update_interval_days": 14,
    },
        "easytdx": {
        "name": "easy_tdx",
        "doc_url": "https://raw.githubusercontent.com/handsomejustin/easy_tdx/main/README.md",
        "local_file": "easytdx_api.md",
        "description": "通达信毫秒级实时行情、资金流向、板块分析、市场异动等数据",
        "update_interval_days": 30,
    },
        "openbb": {
        "name": "OpenBB",
        "doc_url": "https://raw.githubusercontent.com/OpenBB-finance/OpenBB/develop/README.md",
        "local_file": "openbb_api.md",
        "description": "全球金融市场数据聚合平台，覆盖美股、港股、期货、外汇、加密货币等",
        "update_interval_days": 30,
    },
        "akshare": {
        "name": "AKShare",
        "doc_url": "https://raw.githubusercontent.com/akfamily/akshare/main/README.md",
        "local_file": "akshare_api.md",
        "description": "中国金融产品数据接口，覆盖基金、期货、期权、黄金、加密货币等",
        "update_interval_days": 30,
    },
}

def get_function_help(function_path: str) -> Dict[str, Any]:
    """
    动态查询指定模块或函数的帮助文档。
    
    参数：
        function_path: 完整的函数路径，例如 "akshare.futures_main_sina"
    
    返回：
        {"success": True/False, "data": "帮助文本"}
    """
    try:
        # 分割路径，例如 "akshare.futures_main_sina" -> ("akshare", "futures_main_sina")
        parts = function_path.rsplit('.', 1)
        module_name = parts[0]
        func_name = parts[1] if len(parts) > 1 else None

        # 动态导入模块
        module = importlib.import_module(module_name)
        target = getattr(module, func_name) if func_name else module

        # 捕获 help() 输出
        output = io.StringIO()
        pydoc.pager = lambda text: output.write(text)
        help(target)
        help_text = output.getvalue()
        output.close()

        return {"success": True, "data": help_text}
    except Exception as e:
        return {"success": False, "error": f"查询帮助信息失败: {str(e)}"}
    
def download_document(source_name: str) -> Dict[str, Any]:
    """下载指定数据源的最新文档"""
    if source_name not in DATA_SOURCES:
        return {"success": False, "error": f"未知数据源: {source_name}"}
    
    info = DATA_SOURCES[source_name]
    try:
        print(f"[DocManager] 正在下载 {info['name']} 文档...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = requests.get(info["doc_url"], headers=headers, timeout=30)
        response.raise_for_status()
        
        content = response.text
        
        # 如果是 HTML 页面（Baostock），尝试提取正文
        if "<html" in content[:200].lower():
            print(f"[DocManager] 检测到 HTML 页面，正在提取正文...")
            # 尝试提取 <pre> 标签内的内容（Baostock 的 API 文档通常在里面）
            pre_match = re.search(r'<pre[^>]*>(.*?)</pre>', content, re.DOTALL | re.IGNORECASE)
            if pre_match:
                content = pre_match.group(1)
                # 解码 HTML 实体
                content = content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
            else:
                # 备用方案：移除所有 HTML 标签
                content = re.sub(r'<[^>]+>', '', content)
                # 移除多余空行
                content = re.sub(r'\n\s*\n', '\n\n', content)
        
        file_path = DOCS_DIR / info["local_file"]
        file_path.write_text(content, encoding="utf-8")
        
        print(f"[DocManager] {info['name']} 文档已保存至 {file_path}")
        return {"success": True, "data": f"文档已更新，保存至 {file_path}"}
    
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"下载失败: {str(e)}"}

def get_datasource_info(source_name: str) -> Dict[str, Any]:
    """获取数据源的能力说明（从本地缓存读取，不存在则自动下载）"""
    if source_name not in DATA_SOURCES:
        return {"success": False, "error": f"未知数据源: {source_name}"}
    
    info = DATA_SOURCES[source_name]
    file_path = DOCS_DIR / info["local_file"]

    # 如果该数据源没有在线文档，直接返回说明
    if not info.get("doc_url"):
        return {
            "success": True,
            "data": {
                "source": source_name,
                "name": info["name"],
                "description": info["description"],
                "content": f"{info['name']} 没有在线文档，如需了解详情请参考其官方资料。"
            }
        }
    
    # 检查是否需要更新（过期检查）
    need_download = False
    if not file_path.exists():
        need_download = True
    else:
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        interval = info.get("update_interval_days", 30)
        if (datetime.now() - mtime).days >= interval:
            need_download = True

    if need_download:
        download_result = download_document(source_name)
        if not download_result["success"]:
            if file_path.exists():
                print(f"[DocManager] {info['name']} 文档更新失败，使用本地缓存版本")
            else:
                return {"success": False, "error": f"文档未下载且下载失败: {download_result['error']}"}
    
    try:
        content = file_path.read_text(encoding="utf-8")
        return {
            "success": True,
            "data": {
                "source": source_name,
                "name": info["name"],
                "description": info["description"],
                "content": content[:5000],  # 限制长度避免超出上下文
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def update_all_sources() -> Dict[str, Any]:
    """强制更新所有数据源的文档"""
    results = {}
    for source in DATA_SOURCES:
        results[source] = download_document(source)
    return {"success": True, "data": results}