import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QComboBox, QLabel, QListWidget,
                               QMessageBox, QSplitter, QListWidgetItem, QSpinBox,
                               QTreeWidget, QTreeWidgetItem, QHeaderView)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

from config import settings
from utils.system_helper import is_admin, get_available_drives
from utils.formatters import format_size
from core.scanner import DiskScanner
from ui.html_renderer import generate_ui


# ==========================================
# 0. 动态样式表生成引擎 (修复了 SpinBox 点击问题)
# ==========================================
def get_dynamic_style():
    return f"""
    QWidget {{
        background-color: {settings.THEME_BG_COLOR}; 
        color: {settings.THEME_TEXT_COLOR};
        font-family: "Microsoft YaHei", sans-serif;
        font-size: 10pt;
    }}
    QSplitter::handle {{ background-color: {settings.THEME_BORDER}; width: 2px; }}

    QListWidget, QTreeWidget, QComboBox {{
        background-color: {settings.THEME_PANEL_BG};
        border: 1px solid {settings.THEME_BORDER};
        border-radius: 6px; padding: 4px;
    }}

    /* 🌟 单独修复 QSpinBox (渲染深度调节器)，保证上下按钮足够大且可点击 */
    QSpinBox {{
        background-color: {settings.THEME_PANEL_BG};
        border: 1px solid {settings.THEME_BORDER};
        border-radius: 4px; 
        padding: 4px;
        min-height: 24px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 20px; /* 加宽按钮区域 */
        background-color: {settings.THEME_BORDER};
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background-color: {settings.THEME_ACCENT};
    }}

    QTreeWidget::item {{ padding: 4px; border-bottom: 1px solid {settings.THEME_BORDER}; }}
    QTreeWidget::item:selected {{ background-color: {settings.THEME_ACCENT}; color: #FFFFFF; border-radius: 4px; }}
    QHeaderView::section {{ background-color: {settings.THEME_BORDER}; color: {settings.THEME_TEXT_COLOR}; padding: 5px; border: none; font-weight: bold; }}

    QPushButton {{
        background-color: {settings.THEME_ACCENT}; color: #FFFFFF;
        border: none; border-radius: 6px; padding: 8px 12px; font-weight: bold;
    }}
    QPushButton:hover {{ background-color: {settings.THEME_ACCENT_HOVER}; }}
    QPushButton:disabled {{ background-color: {settings.THEME_BORDER}; color: gray; }}

    QScrollBar:vertical {{ border: none; background: transparent; width: 8px; }}
    QScrollBar::handle:vertical {{ background: {settings.THEME_BORDER}; border-radius: 4px; min-height: 20px; }}
    QScrollBar::handle:vertical:hover {{ background: {settings.THEME_ACCENT}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; }}
    """

# ==========================================
# 1. 后台工作线程
# ==========================================
class ScannerThread(QThread):
    finished_signal = Signal(str, dict)
    error_signal = Signal(str)
    progress_signal = Signal(str)

    def __init__(self, target_drive, depth):
        super().__init__()
        self.target_drive = target_drive
        self.depth = depth

    def run(self):
        try:
            self.progress_signal.emit(f"正在扫描 {self.target_drive}，请耐心等待...")
            scanner = DiskScanner(self.target_drive, settings.SIZE_THRESHOLD_BYTES)
            tree_data = scanner.scan(self.target_drive)

            if tree_data['size'] == 0:
                self.finished_signal.emit("EMPTY", {})
                return

            self.progress_signal.emit("🎨 正在渲染首发视图...")
            filepath = generate_ui(tree_data, self.target_drive, self.depth)
            self.finished_signal.emit(filepath, tree_data)
        except Exception as e:
            self.error_signal.emit(str(e))


# ==========================================
# 2. 主窗口界面
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("💽 磁盘空间智能分析专家 (高能丝滑版)")
        self.resize(1400, 850)

        # 🌟 核心修改：删除了 self.setAttribute(Qt.WA_TranslucentBackground) ！！
        # 回归稳定纯色渲染，彻底解决拖影和变黑的问题
        self.setStyleSheet(get_dynamic_style())


        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # ==================== [左栏] 控制面板 ====================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)

        left_layout.addWidget(QLabel("<b>1. 目标盘符:</b>"))
        self.drive_cb = QComboBox()
        self.drive_cb.addItems(get_available_drives())
        self.drive_cb.currentTextChanged.connect(self.check_permission)
        left_layout.addWidget(self.drive_cb)

        self.warning_label = QLabel("⚠️ 扫C盘需管理员权限！")
        self.warning_label.setStyleSheet(f"color: {settings.THEME_WARNING}; font-weight: bold;")
        left_layout.addWidget(self.warning_label)
        self.warning_label.hide()

        left_layout.addSpacing(10)

        # 🌟 2. 新增：UI 模式选择器
        left_layout.addWidget(QLabel("<b>2. 视图显示模式:</b>"))
        self.mode_cb = QComboBox()
        self.mode_cb.addItems([
            "1. 仅显示树状目录",
            "2. 仅显示区域图表",
            "3. 同时显示 (独立操作)",
            "4. 同时显示 (联动操作 🌟)"
        ])
        self.mode_cb.setCurrentIndex(3)  # 默认联动模式
        self.mode_cb.currentIndexChanged.connect(self.change_view_mode)
        left_layout.addWidget(self.mode_cb)

        left_layout.addSpacing(10)

        left_layout.addWidget(QLabel("<b>3. 图表渲染深度:</b>"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 8)
        self.depth_spin.setValue(settings.DEFAULT_RENDER_DEPTH)  # 从配置读取默认值
        left_layout.addWidget(self.depth_spin)

        left_layout.addSpacing(10)

        self.scan_btn = QPushButton("🚀 开始深度扫描")
        self.scan_btn.clicked.connect(self.start_scan)
        left_layout.addWidget(self.scan_btn)

        self.status_label = QLabel("准备就绪。")
        self.status_label.setStyleSheet(f"color: {settings.THEME_BORDER};")
        left_layout.addWidget(self.status_label)

        left_layout.addSpacing(20)

        left_layout.addWidget(QLabel("<b>📂 历史扫描记录:</b>"))
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.load_history_report)
        left_layout.addWidget(self.history_list)

        # ==================== [中栏] 树状目录视图 ====================
        self.mid_panel = QWidget()
        mid_layout = QVBoxLayout(self.mid_panel)
        mid_layout.setContentsMargins(0, 0, 10, 0)
        mid_layout.addWidget(QLabel("<b>🌲 目录结构分析:</b>"))

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["名称", "大小", "类型"])
        self.tree_widget.setColumnWidth(0, 220)
        self.tree_widget.setColumnWidth(1, 100)
        # 🌟 绑定点击事件，用于实现“联动渲染”
        self.tree_widget.itemClicked.connect(self.on_tree_item_clicked)
        mid_layout.addWidget(self.tree_widget)

        # ==================== [右栏] 色块图表视图 ====================
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet(f"background-color: {settings.THEME_PANEL_BG};")
        self.web_view.setHtml("<body style='background-color:{settings.THEME_PANEL_BG};'><h2 style='color:#6C7086; text-align:center; margin-top:20%;'>👈 请在左侧选择盘符并点击开始扫描<br><br>左侧树状图与本区域将联动显示结果</h2></body>")
        right_layout.addWidget(self.web_view)

        # 加入 Splitter
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(self.mid_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 15)
        self.splitter.setStretchFactor(1, 25)
        self.splitter.setStretchFactor(2, 60)

        # 初始化调用
        self.check_permission(self.drive_cb.currentText())
        self.refresh_history()
        self.change_view_mode(3)  # 初始应用显示模式
        self.current_thread = None

    # --- 核心逻辑函数 ---

    def change_view_mode(self, index):
        """🌟 核心：控制树状图与网页视图的显示与隐藏"""
        if index == 0:  # 1. 仅显示树状目录
            self.mid_panel.show()
            self.right_panel.hide()
        elif index == 1:  # 2. 仅显示区域色块
            self.mid_panel.hide()
            self.right_panel.show()
        elif index in [2, 3]:  # 3或4. 同时显示
            self.mid_panel.show()
            self.right_panel.show()

    def on_tree_item_clicked(self, item, column):
        """🌟 核心：当在树状图上点击某一个文件夹时"""
        mode = self.mode_cb.currentIndex()
        if mode == 3:  # 如果是联动模式
            node_data = item.data(0, Qt.UserRole)
            if node_data and node_data["type"] == "dir":
                self.status_label.setText(f"瞬间联动加载中: {node_data['name']} ...")
                depth = self.depth_spin.value()

                # 🌟 关键修改：传入 is_temp=True
                # 这样它只会飞速覆写 temp_linked_view.html，不占用额外磁盘空间，不增加历史记录
                filepath = generate_ui(node_data, node_data['name'], depth, is_temp=True)

                # 重新加载右侧网页
                self.web_view.load(QUrl.fromLocalFile(filepath))
                self.status_label.setText(f"✅ 局部联动完成: {node_data['name']}")

    def populate_tree(self, parent_item, node_data):
        """递归遍历字典数据，生成界面树状节点并绑定数据"""
        item = QTreeWidgetItem(parent_item)
        item.setText(0, node_data["name"])
        item.setText(1, format_size(node_data["size"]))

        if node_data["type"] == "dir":
            item.setText(2, "文件夹")
            if node_data["size"] > 1024 * 1024 * 500:
                item.setForeground(1, Qt.GlobalColor.yellow)
        elif node_data["type"] == "file":
            item.setText(2, "文件")
            item.setForeground(0, Qt.GlobalColor.cyan)
        else:
            item.setText(2, "碎片")
            item.setForeground(0, Qt.GlobalColor.gray)

        # 🌟 超级核心：将这整个文件夹的字典数据，全部藏到这个 UI 节点里面！
        # 这样在触发点击联动时，我们就不需要重新扫描硬盘了。
        item.setData(0, Qt.UserRole, node_data)

        for child in node_data.get("children", []):
            self.populate_tree(item, child)

    def check_permission(self, drive_text):
        if "C:" in drive_text and not is_admin():
            self.warning_label.show()
        else:
            self.warning_label.hide()

    def refresh_history(self):
        """刷新历史记录列表"""
        self.history_list.clear()
        if os.path.exists(settings.HISTORY_DIR):
            files = [f for f in os.listdir(settings.HISTORY_DIR) if f.endswith('.html')]
            for f in sorted(files, reverse=True):
                # 🌟 过滤掉临时缓存文件，不让它显示在历史列表里
                if f == "temp_linked_view.html":
                    continue
                item = QListWidgetItem("📊 " + f)
                item.setData(Qt.UserRole, os.path.abspath(os.path.join(settings.HISTORY_DIR, f)).replace("\\", "/"))
                self.history_list.addItem(item)

    def load_history_report(self, item):
        # 1. 加载旧的网页
        self.web_view.load(QUrl.fromLocalFile(item.data(Qt.UserRole)))

        # 2. 清空树状目录，并给出明确提示
        self.tree_widget.clear()
        hint_item = QTreeWidgetItem(self.tree_widget)
        hint_item.setText(0, "⚠️ 历史记录仅支持查看图表")
        hint_item.setText(1, "-")
        hint_item.setText(2, "提示")
        hint_item.setForeground(0, Qt.GlobalColor.yellow)  # 搞个黄色高亮提示

    def start_scan(self):
        target = self.drive_cb.currentText()
        if not target: return
        depth = self.depth_spin.value()
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("⏳ 扫描进行中...")
        self.tree_widget.clear()
        self.web_view.setHtml("<body style='background-color:#{settings.THEME_PANEL_BG};'><h2 style='color:#89B4FA; text-align:center; margin-top:20%;'>🚀 引擎全开扫描中，请稍候...</h2></body>")

        self.current_thread = ScannerThread(target, depth)
        self.current_thread.progress_signal.connect(lambda msg: self.status_label.setText(msg))
        self.current_thread.finished_signal.connect(self.on_scan_finished)
        self.current_thread.error_signal.connect(self.on_scan_error)
        self.current_thread.start()

    def on_scan_finished(self, filepath, tree_data):
        if filepath == "EMPTY":
            QMessageBox.warning(self, "提示", "扫描结果为空或无权限！")
        else:
            self.status_label.setText("✅ 扫描与渲染全部完成！")
            self.web_view.load(QUrl.fromLocalFile(filepath))

            root_item = QTreeWidgetItem(self.tree_widget)
            root_item.setText(0, f"[{tree_data['name']}] 根目录")
            root_item.setText(1, format_size(tree_data["size"]))
            root_item.setData(0, Qt.UserRole, tree_data)  # 根节点也绑定数据

            for child in tree_data.get("children", []):
                self.populate_tree(root_item, child)
            root_item.setExpanded(True)
            self.refresh_history()
        self.reset_btn()

    def on_scan_error(self, err_msg):
        QMessageBox.critical(self, "错误", f"扫描崩溃啦: {err_msg}")
        self.reset_btn()

    def reset_btn(self):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("🚀 开始深度扫描")