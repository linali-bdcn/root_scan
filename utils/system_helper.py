import os
import platform
import ctypes
import string

def is_admin():
    """检查当前是否具有管理员权限"""
    try:
        if platform.system() == "Windows":
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0  # Mac/Linux 判断 root
    except Exception:
        return False

def get_available_drives():
    """获取系统可用盘符 (如 C:\, D:\)"""
    drives = []
    if platform.system() == "Windows":
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
    else:
        # Mac/Linux 默认给根目录和个人目录
        drives = ["/", os.path.expanduser("~")]
    return drives