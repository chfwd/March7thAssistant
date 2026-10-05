# coding:utf-8
"""MCP Tools — 将 module/automation、module/ocr 等底层能力暴露为 MCP 工具"""

import base64
import io
import json
from typing import Optional

import cv2
import numpy as np
from PIL import Image as PILImage

from mcp.server.fastmcp import FastMCP, Image as MCPImage
from mcp.types import ImageContent, TextContent

# 项目内部模块（延迟导入，避免在 mcp_server.py 未初始化时出错）
from module.automation import auto
from module.ocr import ocr
from module.config import cfg
from module.game import get_game_controller
from module.screen import screen as screen_info


# ─────────────────────────────────────────────
# 截图与屏幕
# ─────────────────────────────────────────────

def _register_screenshot_tools(mcp: FastMCP):

    @mcp.tool()
    def take_screenshot(
        crop_x: float = 0.0,
        crop_y: float = 0.0,
        crop_w: float = 1.0,
        crop_h: float = 1.0,
    ) -> ImageContent:
        """截取游戏窗口截图并返回 base64 编码的 PNG 图片。

        Args:
            crop_x: 裁剪区域左上角 X（相对比例 0~1）
            crop_y: 裁剪区域左上角 Y（相对比例 0~1）
            crop_w: 裁剪区域宽度（相对比例 0~1）
            crop_h: 裁剪区域高度（相对比例 0~1）

        Returns:
            base64 编码的 PNG 图片字符串
        """
        crop = (crop_x, crop_y, crop_w, crop_h)
        result = auto.take_screenshot(crop)
        if not result:
            return ImageContent(type="image", data="", mimeType="")
            # return ImageContent(type="image", data="", mimeType=""), TextContent(type="text", text="截图失败：没有找到游戏窗口")

        screenshot_img = result[0]
        buf = io.BytesIO()
        screenshot_img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return ImageContent(type="image", data=b64, mimeType="image/png")
        # return ImageContent(type="image", data=b64, mimeType="image/png"), TextContent(
        #         type="text",
        #         text=f"已截取屏幕（分辨率 {screenshot_img.width}x{screenshot_img.height}），请分析图片内容。"
        #     )

    @mcp.tool()
    def get_screen_info() -> str:
        """获取游戏窗口的屏幕信息，包括分辨率、窗口位置等。

        Returns:
            JSON 字符串，包含 width、height、window_position 等信息
        """
        controller = get_game_controller()
        resolution = controller.get_resolution()
        is_running = controller.is_game_running()

        info = {
            "is_game_running": is_running,
            "resolution": {"width": resolution[0], "height": resolution[1]} if resolution else None,
            "cloud_game": cfg.cloud_game_enable,
        }
        return json.dumps(info, ensure_ascii=False)


# ─────────────────────────────────────────────
# 图像查找
# ─────────────────────────────────────────────

def _register_image_tools(mcp: FastMCP):

    @mcp.tool()
    def find_image(
        target: str,
        threshold: Optional[float] = None,
        scale_range: Optional[str] = None,
        crop_x: float = 0.0,
        crop_y: float = 0.0,
        crop_w: float = 1.0,
        crop_h: float = 1.0,
        max_retries: int = 1,
    ) -> str:
        """在游戏屏幕上查找图像元素（模板匹配）。

        Args:
            target: 目标图片路径（项目相对路径，如 ./assets/images/xxx.png）
            threshold: 相似度阈值（0~1），不传则使用默认值
            scale_range: 缩放范围，格式如 "0.8,1.2"，不传则不缩放
            crop_x/crop_y/crop_w/crop_h: 裁剪区域（相对比例 0~1）
            max_retries: 最大重试次数

        Returns:
            JSON 字符串，包含 top_left、bottom_right、confidence，未找到则返回 null
        """
        crop = (crop_x, crop_y, crop_w, crop_h)
        sr = None
        if scale_range:
            parts = scale_range.split(",")
            sr = (float(parts[0]), float(parts[1])) if len(parts) == 2 else None

        top_left, bottom_right, confidence = auto.find_image_element(
            target, threshold, sr, relative=False
        )

        if top_left is None:
            return json.dumps({"found": False}, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "top_left": {"x": top_left[0], "y": top_left[1]},
            "bottom_right": {"x": bottom_right[0], "y": bottom_right[1]},
            "confidence": round(confidence, 4) if confidence else None,
        }, ensure_ascii=False)

    @mcp.tool()
    def find_images(
        target: str,
        threshold: Optional[float] = None,
        scale_range: Optional[str] = None,
    ) -> str:
        """在游戏屏幕上查找多个匹配的图像目标。

        Args:
            target: 目标图片路径（项目相对路径）
            threshold: 相似度阈值
            scale_range: 缩放范围，格式如 "0.8,1.2"

        Returns:
            JSON 数组字符串，每个元素包含 top_left 和 bottom_right
        """
        sr = None
        if scale_range:
            parts = scale_range.split(",")
            sr = (float(parts[0]), float(parts[1])) if len(parts) == 2 else None

        matches = auto.find_image_with_multiple_targets(target, threshold, sr)
        results = []
        for top_left, bottom_right in matches:
            results.append({
                "top_left": {"x": top_left[0], "y": top_left[1]},
                "bottom_right": {"x": bottom_right[0], "y": bottom_right[1]},
            })
        return json.dumps(results, ensure_ascii=False)

    @mcp.tool()
    def find_image_and_count(
        target: str,
        threshold: float,
        pixel_r: int,
        pixel_g: int,
        pixel_b: int,
    ) -> str:
        """查找图像并统计匹配数量（用于计数场景，如星琼数量）。

        Args:
            target: 目标图片路径
            threshold: 匹配阈值
            pixel_r/pixel_g/pixel_b: 目标像素的 RGB 值，用于生成黑白图

        Returns:
            JSON 字符串，包含 count
        """
        count = auto.find_image_and_count(target, threshold, (pixel_b, pixel_g, pixel_r))
        return json.dumps({"count": count}, ensure_ascii=False)


# ─────────────────────────────────────────────
# 文字识别（OCR）
# ─────────────────────────────────────────────

def _register_ocr_tools(mcp: FastMCP):

    @mcp.tool()
    def ocr_screen(
        crop_x: float = 0.0,
        crop_y: float = 0.0,
        crop_w: float = 1.0,
        crop_h: float = 1.0,
    ) -> str:
        """对当前游戏截图执行 OCR 文字识别。

        Args:
            crop_x/crop_y/crop_w/crop_h: 裁剪区域（相对比例 0~1）

        Returns:
            JSON 数组字符串，每个元素包含 text、confidence、box（四个角坐标）
        """
        crop = (crop_x, crop_y, crop_w, crop_h)
        auto.take_screenshot(crop)
        auto.perform_ocr()

        results = []
        for item in auto.ocr_result:
            box, (text, confidence) = item
            results.append({
                "text": text,
                "confidence": round(confidence, 4),
                "box": [{"x": int(p[0]), "y": int(p[1])} for p in box],
            })
        return json.dumps(results, ensure_ascii=False)

    @mcp.tool()
    def ocr_region(
        crop_x: float,
        crop_y: float,
        crop_w: float,
        crop_h: float,
        blacklist: Optional[str] = None,
    ) -> str:
        """对指定裁剪区域执行单行 OCR 文字识别。

        Args:
            crop_x/crop_y/crop_w/crop_h: 裁剪区域（相对比例 0~1）
            blacklist: 需要过滤的字符（逗号分隔），不传则不过滤

        Returns:
            JSON 字符串，包含 text 和 confidence
        """
        crop = (crop_x, crop_y, crop_w, crop_h)
        bl = blacklist.split(",") if blacklist else None
        result = auto.get_single_line_text(crop, blacklist=bl)
        if result:
            text, confidence = result
            return json.dumps({
                "text": text,
                "confidence": round(confidence, 4),
            }, ensure_ascii=False)
        return json.dumps({"text": None, "confidence": 0}, ensure_ascii=False)

    @mcp.tool()
    def ocr_image(image_base64: str) -> str:
        """对传入的 base64 编码图片执行 OCR 文字识别。

        Args:
            image_base64: base64 编码的图片字符串

        Returns:
            JSON 数组字符串，每个元素包含 text、confidence、box
        """
        img_bytes = base64.b64decode(image_base64)
        img = PILImage.open(io.BytesIO(img_bytes))
        img_array = np.array(img)

        # 如果是 RGBA 转 RGB
        if img_array.ndim == 3 and img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)

        results_raw = ocr.recognize_multi_lines(img_array)
        results = []
        if results_raw:
            for box, (text, confidence) in results_raw:
                results.append({
                    "text": text,
                    "confidence": round(confidence, 4),
                    "box": [{"x": int(p[0]), "y": int(p[1])} for p in box],
                })
        return json.dumps(results, ensure_ascii=False)

    @mcp.tool()
    def find_text(
        target: str,
        include: bool = True,
        crop_x: float = 0.0,
        crop_y: float = 0.0,
        crop_w: float = 1.0,
        crop_h: float = 1.0,
    ) -> str:
        """在游戏屏幕上查找指定文字，返回其位置。

        Args:
            target: 目标文字
            include: True=包含匹配，False=精确匹配
            crop_x/crop_y/crop_w/crop_h: 裁剪区域（相对比例 0~1）

        Returns:
            JSON 字符串，包含 found、top_left、bottom_right
        """
        crop = (crop_x, crop_y, crop_w, crop_h)
        auto.take_screenshot(crop)
        top_left, bottom_right = auto.find_text_element(target, include, need_ocr=True)

        if top_left is None:
            return json.dumps({"found": False}, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "top_left": {"x": top_left[0], "y": top_left[1]},
            "bottom_right": {"x": bottom_right[0], "y": bottom_right[1]},
            "matched_text": auto.matched_text,
        }, ensure_ascii=False)


# ─────────────────────────────────────────────
# 颜色与 HSV 检测
# ─────────────────────────────────────────────

def _register_color_tools(mcp: FastMCP):

    @mcp.tool()
    def find_hsv(
        h_lower: int,
        s_lower: int,
        v_lower: int,
        h_upper: int,
        s_upper: int,
        v_upper: int,
    ) -> str:
        """通过 HSV 颜色范围在屏幕上查找最大连通区域。

        Args:
            h_lower/s_lower/v_lower: HSV 下界
            h_upper/s_upper/v_upper: HSV 上界

        Returns:
            JSON 字符串，包含 found、top_left、bottom_right
        """
        lower = np.array([h_lower, s_lower, v_lower])
        upper = np.array([h_upper, s_upper, v_upper])

        auto.take_screenshot()
        top_left, bottom_right = auto.find_hsv_element((lower, upper))

        if top_left is None:
            return json.dumps({"found": False}, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "top_left": {"x": top_left[0], "y": top_left[1]},
            "bottom_right": {"x": bottom_right[0], "y": bottom_right[1]},
        }, ensure_ascii=False)

    @mcp.tool()
    def check_rgb_ratio(
        crop_x: float,
        crop_y: float,
        crop_w: float,
        crop_h: float,
        r: int,
        g: int,
        b: int,
        threshold: float,
        tolerance: float = 0.0,
    ) -> str:
        """检查指定区域中目标 RGB 像素占比是否超过阈值。

        Args:
            crop_x/crop_y/crop_w/crop_h: 裁剪区域（相对比例 0~1）
            r/g/b: 目标颜色 RGB 值（0~255）
            threshold: 占比阈值（0~1）
            tolerance: RGB 通道允许偏差（0~1）

        Returns:
            JSON 字符串，包含 matched（bool）
        """
        crop = (crop_x, crop_y, crop_w, crop_h)
        auto.take_screenshot()
        result = auto.is_rgb_ratio_above_threshold(crop, (r, g, b), threshold, tolerance)
        return json.dumps({"matched": result}, ensure_ascii=False)


# ─────────────────────────────────────────────
# YOLO 目标检测
# ─────────────────────────────────────────────

def _register_yolo_tools(mcp: FastMCP):

    @mcp.tool()
    def find_yolo(
        model_path: str,
        names: list[str],
        target_class: Optional[str] = None,
        threshold: float = 0.25,
        input_size: Optional[int] = None,
    ) -> str:
        """使用 YOLO 模型在屏幕上查找置信度最高的目标。

        Args:
            model_path: ONNX 模型文件路径（项目相对路径）
            names: 类别名列表（如 ["monster", "chest"]）
            target_class: 目标类别名（不传则匹配所有类别）
            threshold: 置信度阈值（0~1）
            input_size: 模型输入尺寸（不传则自动检测）

        Returns:
            JSON 字符串，包含 found、top_left、bottom_right、class_name、confidence
        """
        target_config = {
            "model_path": model_path,
            "names": names,
        }
        if target_class:
            target_config["target_class"] = target_class
        if input_size:
            target_config["input_size"] = input_size

        auto.take_screenshot()
        top_left, bottom_right = auto.find_yolo_element(target_config, threshold)

        if top_left is None:
            return json.dumps({"found": False}, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "top_left": {"x": top_left[0], "y": top_left[1]},
            "bottom_right": {"x": bottom_right[0], "y": bottom_right[1]},
        }, ensure_ascii=False)

    @mcp.tool()
    def find_yolo_all(
        model_path: str,
        names: list[str],
        target_class: Optional[str] = None,
        threshold: float = 0.25,
        input_size: Optional[int] = None,
    ) -> str:
        """使用 YOLO 模型在屏幕上查找所有匹配的目标。

        Args:
            model_path: ONNX 模型文件路径（项目相对路径）
            names: 类别名列表
            target_class: 目标类别名（不传则匹配所有类别）
            threshold: 置信度阈值
            input_size: 模型输入尺寸

        Returns:
            JSON 数组字符串，每个元素包含 top_left、bottom_right
        """
        target_config = {
            "model_path": model_path,
            "names": names,
        }
        if target_class:
            target_config["target_class"] = target_class
        if input_size:
            target_config["input_size"] = input_size

        auto.take_screenshot()
        matches = auto.find_yolo_with_multiple_targets(target_config, threshold)

        results = []
        for top_left, bottom_right in matches:
            results.append({
                "top_left": {"x": top_left[0], "y": top_left[1]},
                "bottom_right": {"x": bottom_right[0], "y": bottom_right[1]},
            })
        return json.dumps(results, ensure_ascii=False)


# ─────────────────────────────────────────────
# 输入模拟
# ─────────────────────────────────────────────

def _register_input_tools(mcp: FastMCP):

    @mcp.tool()
    def click(
        x: int,
        y: int,
        button: str = "left",
        count: int = 1,
    ) -> str:
        """在指定坐标点击鼠标。

        Args:
            x: 屏幕 X 坐标
            y: 屏幕 Y 坐标
            button: 鼠标按键，"left" 或 "right"
            count: 点击次数

        Returns:
            JSON 字符串，包含 success
        """
        try:
            for _ in range(count):
                auto.mouse_click(x, y)
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def click_element(
        find_type: str,
        target: str,
        threshold: Optional[float] = None,
        include: bool = True,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> str:
        """查找并点击屏幕上的元素。

        Args:
            find_type: 查找类型，"image"（图片）/ "text"（文字）/ "crop"（坐标）
            target: 查找目标（图片路径、文字内容、或坐标 "x,y,w,h"）
            threshold: 图片查找时的相似度阈值
            include: 文字查找时是否包含匹配
            offset_x/offset_y: 点击偏移量

        Returns:
            JSON 字符串，包含 success 和 found
        """
        try:
            if find_type == "crop":
                parts = target.split(",")
                crop = tuple(float(p) for p in parts)
                result = auto.click_element(
                    target=crop, find_type="crop",
                    offset=(offset_x, offset_y),
                )
            elif find_type == "image":
                result = auto.click_element(
                    target=target, find_type="image",
                    threshold=threshold, max_retries=3,
                    offset=(offset_x, offset_y),
                )
            elif find_type == "text":
                result = auto.click_element(
                    target=target, find_type="text",
                    include=include, max_retries=3,
                    offset=(offset_x, offset_y),
                )
            else:
                return json.dumps({"success": False, "error": f"不支持的查找类型: {find_type}"}, ensure_ascii=False)

            return json.dumps({"success": bool(result), "found": bool(result)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def press_key(key: str, duration: float = 0.0) -> str:
        """按下键盘按键。

        Args:
            key: 按键名称（如 "esc", "space", "enter", "w", "a", "s", "d" 等）
            duration: 按住时长（秒），0 表示瞬间按下并释放

        Returns:
            JSON 字符串，包含 success
        """
        try:
            if duration > 0:
                auto.press_key_down(key)
                import time
                time.sleep(duration)
                auto.press_key_up(key)
            else:
                auto.press_key(key)
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def mouse_move(x: int, y: int) -> str:
        """移动鼠标到指定位置。

        Args:
            x: 目标 X 坐标
            y: 目标 Y 坐标

        Returns:
            JSON 字符串，包含 success
        """
        try:
            auto.mouse_move(x, y)
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def mouse_scroll(amount: int, x: Optional[int] = None, y: Optional[int] = None) -> str:
        """鼠标滚轮滚动。

        Args:
            amount: 滚动量（正数向上，负数向下）
            x: 滚动位置 X（不传则在当前位置）
            y: 滚动位置 Y（不传则在当前位置）

        Returns:
            JSON 字符串，包含 success
        """
        try:
            if x is not None and y is not None:
                auto.mouse_move(x, y)
            auto.mouse_scroll(amount)
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def type_text(text: str) -> str:
        """通过剪贴板输入文字到游戏。

        Args:
            text: 要输入的文字

        Returns:
            JSON 字符串，包含 success
        """
        try:
            controller = get_game_controller()
            controller.copy(text)
            auto.press_key("ctrl", "v")
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ─────────────────────────────────────────────
# 游戏控制
# ─────────────────────────────────────────────

def _register_game_tools(mcp: FastMCP):

    @mcp.tool()
    def start_game() -> str:
        """启动游戏进程。

        Returns:
            JSON 字符串，包含 success
        """
        try:
            controller = get_game_controller()
            result = controller.start_game_process()
            return json.dumps({"success": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def stop_game() -> str:
        """终止游戏进程。

        Returns:
            JSON 字符串，包含 success
        """
        try:
            controller = get_game_controller()
            result = controller.stop_game()
            return json.dumps({"success": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def switch_to_game() -> str:
        """将游戏窗口切换到前台。

        Returns:
            JSON 字符串，包含 success
        """
        try:
            controller = get_game_controller()
            result = controller.switch_to_game()
            return json.dumps({"success": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool()
    def is_game_running() -> str:
        """检查游戏是否正在运行。

        Returns:
            JSON 字符串，包含 running（bool）
        """
        controller = get_game_controller()
        result = controller.is_game_running()
        return json.dumps({"running": result}, ensure_ascii=False)

    @mcp.tool()
    def get_resolution() -> str:
        """获取游戏窗口分辨率。

        Returns:
            JSON 字符串，包含 width 和 height
        """
        controller = get_game_controller()
        resolution = controller.get_resolution()
        if resolution:
            return json.dumps({"width": resolution[0], "height": resolution[1]}, ensure_ascii=False)
        return json.dumps({"width": None, "height": None, "error": "无法获取分辨率"}, ensure_ascii=False)


# ─────────────────────────────────────────────
# 配置读写
# ─────────────────────────────────────────────

def _register_config_tools(mcp: FastMCP):

    @mcp.tool()
    def get_config(key: str) -> str:
        """读取配置项的值。

        Args:
            key: 配置项名称（如 "game_title_name"、"cloud_game_enable" 等）

        Returns:
            JSON 字符串，包含 key 和 value
        """
        value = cfg.get_value(key)
        return json.dumps({"key": key, "value": value}, ensure_ascii=False)

    @mcp.tool()
    def set_config(key: str, value: str) -> str:
        """写入配置项（会修改 config.yaml）。

        Args:
            key: 配置项名称
            value: 新值（字符串格式，会尝试自动转换类型）

        Returns:
            JSON 字符串，包含 success
        """
        try:
            # 尝试自动转换类型
            parsed_value = value
            if value.lower() == "true":
                parsed_value = True
            elif value.lower() == "false":
                parsed_value = False
            else:
                try:
                    parsed_value = int(value)
                except ValueError:
                    try:
                        parsed_value = float(value)
                    except ValueError:
                        pass  # 保持字符串

            cfg.set_value(key, parsed_value)
            return json.dumps({"success": True, "key": key, "value": parsed_value}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ─────────────────────────────────────────────
# 注册入口
# ─────────────────────────────────────────────

def register_tools(mcp: FastMCP):
    """注册所有 MCP 工具"""
    _register_screenshot_tools(mcp)
    _register_image_tools(mcp)
    _register_ocr_tools(mcp)
    _register_color_tools(mcp)
    _register_yolo_tools(mcp)
    _register_input_tools(mcp)
    _register_game_tools(mcp)
    _register_config_tools(mcp)


# ─────────────────────────────────────────────
# Resources
# ─────────────────────────────────────────────

def register_resources(mcp: FastMCP):

    @mcp.resource("march7th://config")
    def get_config_resource() -> str:
        """当前完整配置（YAML 格式）"""
        import io
        buf = io.StringIO()
        cfg.yaml.dump(cfg.data, buf)
        return buf.getvalue()

    @mcp.resource("march7th://version")
    def get_version() -> str:
        """版本号"""
        try:
            with open("./assets/config/version.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return "unknown"

    @mcp.resource("march7th://status")
    def get_status() -> str:
        """游戏与助手运行状态"""
        controller = get_game_controller()
        return json.dumps({
            "is_game_running": controller.is_game_running(),
            "cloud_game": cfg.cloud_game_enable,
            "resolution": controller.get_resolution(),
        }, ensure_ascii=False)
