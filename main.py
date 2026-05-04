import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt  # <--- 补充了这行缺失的导入
from ui.qt_main_window import MainWindow


def main():
    # 确保高分屏缩放渲染清晰 (适配 4K/2K 显示器)
    if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)

    # 实例化我们的 Qt 主窗口
    window = MainWindow()
    window.show()

    # 进入应用主循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()