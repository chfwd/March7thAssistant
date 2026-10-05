import conftest  # noqa: F401
from module.automation import auto
from module.logger import log
from module.ocr import ocr
import numpy as np
import pygetwindow as gw
from PIL import ImageGrab
from pyautogui import click

def _capture_window_region(window_title, region=None):
    """
    window_title: 窗口标题关键词（模糊匹配）
    region: 相对窗口客户区的 (x, y, width, height)，None 则截整个窗口
    """
    # 1. 获取窗口
    win = gw.getWindowsWithTitle(window_title)[0]
    
    # 2. 获取窗口在屏幕上的绝对坐标 (left, top, right, bottom)
    left, top = win.left, win.top
    right, bottom = win.right, win.bottom
    
    # 3. 如果指定了区域，换算成绝对屏幕坐标
    if region:
        rx, ry, rw, rh = region
        box = (left + rx, top + ry, left + rx + rw, top + ry + rh)
    else:
        box = (left, top, right, bottom)
    
    # 4. 截图
    img = ImageGrab.grab(bbox=box)
    return img

def capture_window_region(window_title, region=None):
    if region:
        region = (region[0], region[1], region[2]-region[0], region[3]-region[1])
    return _capture_window_region(window_title, region)

log.logger.setLevel("DEBUG")
auto._init_input()
results = {}
def screenshot_and_ocr():
    screenshot = capture_window_region("崩坏", (821, 908, 2452, 1400))
    ocr_result = ocr.recognize_multi_lines(np.array(screenshot))
    texts = [item[1][0] for item in ocr_result] # type: ignore
    if len(texts) > 1:
        key = texts[0]
        text = "".join(texts[1:])
        if key not in results:
            results[key] = []
        results[key].append(text)
    else:
        print("len<2 ???", texts)
for i in range(75):
    screenshot_and_ocr()
    click(1800, 1460)
print(results)