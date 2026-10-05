#!/usr/bin/env python3
# coding:utf-8
"""March7thAssistant MCP Server 入口

通过 HTTP (SSE) 传输运行 MCP 服务器，暴露游戏自动化能力给 AI 助手。

使用方式：
    python mcp_server.py
    python mcp_server.py --port 8765
    python mcp_server.py --host 0.0.0.0 --port 8765

Claude Code / Cursor MCP 配置示例：
    {
        "mcpServers": {
            "march7th": {
                "url": "http://127.0.0.1:8765/sse"
            }
        }
    }
"""

import argparse
import os
import sys

# 设置工作目录（同 main.py）
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)))

import module.mcp  # noqa: E402 — 必须在 os.chdir 之后导入


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="March7thAssistant MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="监听端口 (默认 8765)")
    args = parser.parse_args()

    print(f"Starting MCP server on http://{args.host}:{args.port}/sse ...")
    mcp = module.mcp.mcp_server
    mcp.mcp.settings.transport_security = None
    module.mcp.mcp_server.run(transport="streamable-http", host=args.host, port=args.port)
