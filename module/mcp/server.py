# coding:utf-8
"""March7thAssistant MCP Server — 基于 FastMCP 的服务器实现"""

from typing import Literal

from mcp.server.fastmcp import FastMCP

from module.mcp.tools import register_tools, register_resources


class McpServer:
    """MCP 服务器，将 March7thAssistant 的自动化能力暴露为标准 MCP 工具和资源。

    使用 FastMCP 提供高层 API，支持 sse / stdio 传输。
    默认使用 sse 传输，通过 HTTP 提供 MCP 服务。
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8765

    def __init__(self):
        self.mcp = FastMCP(
            "march7th-assistant",
            # version="v2026.5.27",
        )
        self._register()

    def _register(self):
        """注册所有工具和资源。"""
        register_tools(self.mcp)
        register_resources(self.mcp)

    def run(self, transport: Literal["stdio", "sse", "streamable-http"] = "sse", host: str | None = None, port: int | None = None):
        """启动 MCP 服务器。

        Args:
            transport: 传输方式，"sse"（HTTP）或 "stdio"
            host: 监听地址，默认 127.0.0.1
            port: 监听端口，默认 8765
        """
        host = host or self.DEFAULT_HOST
        port = port or self.DEFAULT_PORT
        self.mcp.settings.host = host
        self.mcp.settings.port = port
        self.mcp.run(transport=transport)


# 模块级单例（同其他模块的 pattern）
mcp_server = McpServer()
