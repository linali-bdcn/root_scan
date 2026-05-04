import os
from config.settings import IGNORE_DIRS


class DiskScanner:
    def __init__(self, root_path, threshold_bytes):
        self.root_path = root_path
        self.threshold_bytes = threshold_bytes

    def scan(self, path):
        """递归扫描目录并计算大小，带智能剪枝"""
        total_size = 0
        children = []
        name = os.path.basename(path) if os.path.basename(path) else path

        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.name in IGNORE_DIRS:
                        continue

                    try:
                        if entry.is_file(follow_symlinks=False):
                            size = entry.stat(follow_symlinks=False).st_size
                            total_size += size
                            if size > self.threshold_bytes:
                                children.append({
                                    "name": entry.name,
                                    "path": entry.path,
                                    "size": size,
                                    "type": "file",
                                    "children": []
                                })
                        elif entry.is_dir(follow_symlinks=False):
                            dir_info = self.scan(entry.path)
                            total_size += dir_info["size"]
                            children.append(dir_info)
                    except (PermissionError, FileNotFoundError, OSError):
                        pass
        except (PermissionError, FileNotFoundError, OSError):
            pass

        # === 智能判断与剪枝 ===
        if total_size < self.threshold_bytes:
            children = []
        else:
            large_children = []
            small_size_sum = 0
            for child in children:
                if child["size"] >= (self.threshold_bytes / 5):
                    large_children.append(child)
                else:
                    small_size_sum += child["size"]

            if small_size_sum > 0:
                large_children.append({
                    "name": "其他小文件(合并)",
                    "path": os.path.join(path, "_others"),
                    "size": small_size_sum,
                    "type": "others",
                    "children": []
                })
            children = large_children

        return {
            "name": name,
            "path": path,
            "size": total_size,
            "type": "dir",
            "children": children
        }