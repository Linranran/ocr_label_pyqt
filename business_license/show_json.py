import sys
import os
import json
from pathlib import Path
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QListWidget, QTextEdit,
    QSplitter, QStatusBar, QMenuBar, QAction, QMessageBox,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QSize, QRect, QPoint
from PyQt5.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_folder = ""
        self.json_folder = ""
        self.image_files = []
        self.current_index = 0

        self.init_ui()

    def init_ui(self):
        """初始化用户界面 - LabelImg 风格"""
        self.setWindowTitle("图像和JSON标签查看器 - LabelImg风格")
        self.setGeometry(100, 100, 1400, 900)

        # 创建菜单栏
        self.create_menu_bar()

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # 创建工具栏
        toolbar = self.create_toolbar()
        main_layout.addLayout(toolbar)

        # 创建主显示区域
        display_area = self.create_display_area()
        main_layout.addWidget(display_area, 1)

        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 设置样式 - LabelImg 风格
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QPushButton {
                background-color: #e1e1e1;
                border: 1px solid #c0c0c0;
                padding: 4px 8px;
                border-radius: 2px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #a0a0a0;
                font-size: 11px;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #a0a0a0;
                font-family: Consolas, Monaco, monospace;
                font-size: 11px;
            }
            QLabel#image_label {
                background-color: #333333;
                border: 1px solid #a0a0a0;
                color: #cccccc;
                font-size: 14px;
            }
            QStatusBar {
                background-color: #e0e0e0;
                border-top: 1px solid #a0a0a0;
            }
        """)

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #e0e0e0;
                border-bottom: 1px solid #a0a0a0;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background: #d0d0d0;
            }
            QMenuBar::item:pressed {
                background: #c0c0c0;
            }
        """)

        # 文件菜单
        file_menu = menubar.addMenu('文件')

        open_image_action = QAction('打开图像文件夹', self)
        open_image_action.setShortcut('Ctrl+I')
        open_image_action.triggered.connect(self.open_image_folder)
        file_menu.addAction(open_image_action)

        open_json_action = QAction('打开JSON文件夹', self)
        open_json_action.setShortcut('Ctrl+J')
        open_json_action.triggered.connect(self.open_json_folder)
        file_menu.addAction(open_json_action)

        file_menu.addSeparator()

        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(4)

        # 图像文件夹按钮
        self.image_folder_btn = QPushButton("打开图像文件夹")
        self.image_folder_btn.clicked.connect(self.open_image_folder)
        toolbar_layout.addWidget(self.image_folder_btn)

        # JSON文件夹按钮
        self.json_folder_btn = QPushButton("打开JSON文件夹")
        self.json_folder_btn.clicked.connect(self.open_json_folder)
        toolbar_layout.addWidget(self.json_folder_btn)

        toolbar_layout.addStretch()

        # 导航按钮
        self.prev_btn = QPushButton("← 上一张")
        self.prev_btn.clicked.connect(self.previous_image)
        self.prev_btn.setEnabled(False)
        toolbar_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("下一张 →")
        self.next_btn.clicked.connect(self.next_image)
        self.next_btn.setEnabled(False)
        toolbar_layout.addWidget(self.next_btn)

        return toolbar_layout

    def create_display_area(self):
        """创建显示区域 - LabelImg 风格"""
        # 主分割器（水平分割）
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(4)

        # 左侧：图像显示区域
        left_widget = self.create_image_display()
        main_splitter.addWidget(left_widget)

        # 右侧：文件列表和JSON显示区域
        right_widget = self.create_right_panel()
        main_splitter.addWidget(right_widget)

        # 设置初始大小比例
        main_splitter.setSizes([800, 300])

        return main_splitter

    def create_image_display(self):
        """创建图像显示区域"""
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.setContentsMargins(2, 2, 2, 2)
        image_layout.setSpacing(2)

        # 图像标签
        self.image_label = QLabel("请选择图像文件夹")
        self.image_label.setObjectName("image_label")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 500)

        # 创建滚动区域用于图像
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        image_layout.addWidget(scroll_area)

        return image_widget

    def create_right_panel(self):
        """创建右侧面板（文件列表 + JSON显示）"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(2, 2, 2, 2)
        right_layout.setSpacing(2)

        # 创建垂直分割器
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setHandleWidth(4)

        # 文件列表区域（放在下面）
        file_list_widget = self.create_file_list_area()
        right_splitter.addWidget(file_list_widget)

        # JSON显示区域（放在上面）
        json_widget = self.create_json_display()
        right_splitter.addWidget(json_widget)

        # 设置初始大小比例（JSON显示区域较大）
        right_splitter.setSizes([200, 400])

        right_layout.addWidget(right_splitter)

        return right_widget

    def create_file_list_area(self):
        """创建文件列表区域"""
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(2)

        file_layout.addWidget(QLabel("文件列表:"))
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_file_selected)
        self.file_list.setMinimumHeight(150)
        file_layout.addWidget(self.file_list)

        return file_widget

    def create_json_display(self):
        """创建JSON显示区域"""
        json_widget = QWidget()
        json_layout = QVBoxLayout(json_widget)
        json_layout.setContentsMargins(0, 0, 0, 0)
        json_layout.setSpacing(2)

        json_layout.addWidget(QLabel("JSON标签内容:"))
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(True)
        self.json_text.setFont(QFont("Consolas", 9))
        self.json_text.setMinimumHeight(200)
        json_layout.addWidget(self.json_text)

        return json_widget

    def open_image_folder(self):
        """打开图像文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择图像文件夹")
        if folder:
            self.image_folder = folder
            self.load_image_files()
            self.status_bar.showMessage(f"已加载图像文件夹: {folder}")

    def open_json_folder(self):
        """打开JSON文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择JSON文件夹")
        if folder:
            self.json_folder = folder
            self.status_bar.showMessage(f"已加载JSON文件夹: {folder}")

            # 如果已经有选中的图像，重新加载对应的JSON
            if self.image_files and self.current_index < len(self.image_files):
                self.load_json_for_current_image()

    def load_image_files(self):
        """加载图像文件列表"""
        if not self.image_folder:
            return

        # 支持的图像格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

        self.image_files = []
        for root, _, files in os.walk(self.image_folder):
            for file in files:
                if Path(file).suffix.lower() in image_extensions:
                    self.image_files.append(os.path.join(root, file))

        # 更新文件列表
        self.file_list.clear()
        for file_path in self.image_files:
            file_name = os.path.basename(file_path)
            self.file_list.addItem(file_name)

        # 启用导航按钮
        has_files = len(self.image_files) > 0
        self.prev_btn.setEnabled(has_files)
        self.next_btn.setEnabled(has_files)

        # 如果有文件，显示第一个
        if self.image_files:
            self.current_index = 0
            self.show_current_image()

    def on_file_selected(self, item):
        """文件列表选择事件"""
        row = self.file_list.row(item)
        if 0 <= row < len(self.image_files):
            self.current_index = row
            self.show_current_image()

    def show_current_image(self):
        """显示当前图像"""
        if not self.image_files or self.current_index >= len(self.image_files):
            return

        image_path = self.image_files[self.current_index]
        file_name = os.path.basename(image_path)

        # 更新文件列表选中状态
        self.file_list.setCurrentRow(self.current_index)

        # 加载并显示图像
        self.load_and_display_image(image_path)

        # 加载对应的JSON
        self.load_json_for_current_image()

        # 更新状态栏
        self.status_bar.showMessage(f"显示: {file_name} ({self.current_index + 1}/{len(self.image_files)})")

        # 更新导航按钮状态
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)

    def load_and_display_image(self, image_path):
        """加载并显示图像"""
        try:
            # 使用OpenCV加载图像
            image = cv2.imread(image_path)
            if image is None:
                self.image_label.setText(f"无法加载图像: {os.path.basename(image_path)}")
                return

            # 转换颜色空间
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # 获取图像尺寸
            h, w, ch = image.shape
            bytes_per_line = ch * w

            # 创建QImage
            q_img = QImage(image.data, w, h, bytes_per_line, QImage.Format_RGB888)

            # 缩放图像以适应标签大小，保持比例
            pixmap = QPixmap.fromImage(q_img)
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setAlignment(Qt.AlignCenter)

        except Exception as e:
            self.image_label.setText(f"加载图像出错: {str(e)}")

    def load_json_for_current_image(self):
        """加载当前图像对应的JSON文件"""
        if not self.image_files or not self.json_folder:
            self.json_text.setPlainText("请先选择JSON文件夹")
            return

        if self.current_index >= len(self.image_files):
            return

        image_path = self.image_files[self.current_index]
        image_name = Path(image_path).stem

        # 查找对应的JSON文件
        json_file = None
        for root, _, files in os.walk(self.json_folder):
            for file in files:
                if file.startswith(image_name) and file.endswith('.json'):
                    json_file = os.path.join(root, file)
                    break
            if json_file:
                break

        if json_file and os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                # 格式化JSON显示
                formatted_json = json.dumps(json_data, ensure_ascii=False, indent=2)
                self.json_text.setPlainText(formatted_json)

            except Exception as e:
                self.json_text.setPlainText(f"加载JSON文件出错: {str(e)}")
        else:
            self.json_text.setPlainText(f"未找到对应的JSON文件: {image_name}.json")

    def previous_image(self):
        """显示上一张图像"""
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_image()

    def next_image(self):
        """显示下一张图像"""
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_current_image()

    def resizeEvent(self, event):
        """窗口大小改变事件 - 重新调整图像大小"""
        super().resizeEvent(event)
        if self.image_files and hasattr(self, 'image_label'):
            # 重新显示当前图像以适应新大小
            self.show_current_image()

    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_A:
            self.previous_image()
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_D:
            self.next_image()
        else:
            super().keyPressEvent(event)

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
                          "图像和JSON标签查看器 - LabelImg风格\n\n"
                          "快捷键:\n"
                          "• A/← : 上一张\n"
                          "• D/→ : 下一张\n"
                          "• Ctrl+I : 打开图像文件夹\n"
                          "• Ctrl+J : 打开JSON文件夹\n"
                          "• Ctrl+Q : 退出")


def main():
    app = QApplication(sys.argv)

    # 设置应用程序样式
    app.setStyle('Fusion')

    viewer = ImageViewer()
    viewer.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()