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
    QScrollArea, QFrame, QSizePolicy, QInputDialog, QDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QGroupBox, QFormLayout, QLineEdit, QGridLayout,
    QToolBar, QShortcut  # 新增 QShortcut
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QRectF, QPointF
from PyQt5.QtGui import QImage, QPixmap, QFont, QCursor, QTransform, QKeySequence  # 新增 QKeySequence


class EditableLabel(QLabel):
    """可直接编辑的标签类"""
    editingFinished = pyqtSignal(str, str, str)  # field_name, old_value, new_value

    def __init__(self, text="", field_name="", parent=None):
        super().__init__(text, parent)
        self.field_name = field_name
        self.original_text = text
        self.is_editing = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet("""
            QLabel {
                background-color: #f8f8f8;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
            }
            QLabel:hover {
                background-color: #e8f4f8;
                border: 1px solid #2196F3;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_editing:
            self.start_editing()
        super().mousePressEvent(event)

    def start_editing(self):
        """开始编辑模式"""
        self.is_editing = True
        old_text = self.text()

        # 创建行编辑器
        from PyQt5.QtWidgets import QLineEdit
        self.editor = QLineEdit(old_text)
        self.editor.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 2px solid #2196F3;
                border-radius: 4px;
                padding: 3px;
                font-size: 12px;
            }
        """)

        # 获取标签在布局中的位置
        layout = self.parent().layout()
        if layout:
            # 替换标签为编辑器
            for i in range(layout.count()):
                if layout.itemAt(i).widget() == self:
                    layout.takeAt(i)
                    layout.addWidget(self.editor, self.property("row"), self.property("col"))
                    break

        self.editor.selectAll()
        self.editor.setFocus()

        # 连接信号
        self.editor.returnPressed.connect(lambda: self.finish_editing())
        self.editor.editingFinished.connect(lambda: self.finish_editing())

        # 点击其他地方也能完成编辑
        self.editor.installEventFilter(self)

    def finish_editing(self):
        """完成编辑模式"""
        if not self.is_editing:
            return

        new_text = self.editor.text()
        old_text = self.text()

        # 恢复标签显示
        layout = self.parent().layout()
        if layout:
            # 替换编辑器为标签
            for i in range(layout.count()):
                if layout.itemAt(i).widget() == self.editor:
                    layout.takeAt(i)
                    layout.addWidget(self, self.property("row"), self.property("col"))
                    break

        self.editor.deleteLater()
        self.is_editing = False
        self.setText(new_text)

        # 发射编辑完成信号
        if old_text != new_text:
            self.editingFinished.emit(self.field_name, old_text, new_text)

    def eventFilter(self, obj, event):
        """事件过滤器，处理点击其他地方完成编辑"""
        if event.type() == event.FocusOut and obj == self.editor:
            self.finish_editing()
            return True
        return super().eventFilter(obj, event)


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_folder = ""
        self.json_folder = ""
        self.image_files = []
        self.current_index = 0
        self.current_json_path = ""
        self.current_json_data = None

        # 图像显示相关的新属性
        self.current_pixmap = None  # 存储当前加载的原始 QPixmap
        self.display_pixmap = None  # 存储当前用于显示的缩放/旋转后的 QPixmap
        self.scale_factor = 1.0  # 当前缩放因子
        self.rotation_angle = 0  # 当前旋转角度

        # 存储字段标签的引用，便于更新
        self.field_labels = {}
        self.field_types = {}

        self.init_ui()

    def init_ui(self):
        """初始化用户界面 - LabelImg 风格"""
        self.setWindowTitle("图像标注编辑器 - LabelImg风格")
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
            QPushButton#save_btn {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton#save_btn:hover {
                background-color: #45a049;
            }
            QPushButton#create_btn {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
            }
            QPushButton#create_btn:hover {
                background-color: #1976D2;
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
            QLabel#field_name {
                font-weight: bold;
                color: #333;
            }
            QLabel#field_name:hover {
                color: #2196F3;
            }
            QStatusBar {
                background-color: #e0e0e0;
                border-top: 1px solid #a0a0a0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
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

        save_action = QAction('保存JSON', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_json)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        # --- 新增 删除图像 动作 ---
        self.delete_image_action = QAction('删除当前图像及标签', self)
        self.delete_image_action.setShortcut('Delete')
        self.delete_image_action.triggered.connect(self.delete_current_image)
        self.delete_image_action.setEnabled(False)  # 初始化时禁用
        file_menu.addAction(self.delete_image_action)
        # --------------------------

        file_menu.addSeparator()

        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')

        edit_json_action = QAction('编辑完整JSON标签', self)
        edit_json_action.setShortcut('Ctrl+E')
        edit_json_action.triggered.connect(self.edit_full_json)
        edit_menu.addAction(edit_json_action)

        create_json_action = QAction('创建新JSON标签', self)
        create_json_action.setShortcut('Ctrl+N')
        create_json_action.triggered.connect(self.create_new_json)
        edit_menu.addAction(create_json_action)

        edit_menu.addSeparator()

        # 添加图像缩放菜单项
        self.zoom_in_action = QAction('放大', self)
        self.zoom_in_action.setShortcut('+')
        # self.zoom_in_action.setShortcut('+')
        self.zoom_in_action.triggered.connect(self.zoom_in)
        edit_menu.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction('缩小', self)
        self.zoom_out_action.setShortcut('-')
        self.zoom_out_action.triggered.connect(self.zoom_out)
        edit_menu.addAction(self.zoom_out_action)

        # --- 新增：添加图像旋转菜单项 ---
        edit_menu.addSeparator()  # 在缩放和旋转之间加个分隔线，更清晰
        self.rotate_cw_action = QAction('顺时针旋转90度', self)
        self.rotate_cw_action.setShortcut('R')  # 设置快捷键 Ctrl+R
        self.rotate_cw_action.triggered.connect(lambda: self.rotate_image(90))
        edit_menu.addAction(self.rotate_cw_action)

        self.rotate_ccw_action = QAction('逆时针旋转90度', self)
        self.rotate_ccw_action.setShortcut('L')  # 设置快捷键 Ctrl+L (或者 Ctrl+Shift+R)
        self.rotate_ccw_action.triggered.connect(lambda: self.rotate_image(-90))
        edit_menu.addAction(self.rotate_ccw_action)
        # --------------------------

        # --- 新增 设置 菜单 ---
        settings_menu = menubar.addMenu('设置')
        self.shortcut_settings_action = QAction('快捷键设置', self)
        # self.shortcut_settings_action.setShortcut('Ctrl+,') # 可选快捷键
        self.shortcut_settings_action.triggered.connect(self.open_shortcut_settings)
        settings_menu.addAction(self.shortcut_settings_action)
        # -----------------------

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

        # 创建新JSON按钮
        self.create_btn = QPushButton("创建新JSON")
        self.create_btn.setObjectName("create_btn")
        self.create_btn.clicked.connect(self.create_new_json)
        toolbar_layout.addWidget(self.create_btn)

        # 保存按钮
        self.save_btn = QPushButton("保存JSON")
        self.save_btn.setObjectName("save_btn")
        self.save_btn.clicked.connect(self.save_json)
        toolbar_layout.addWidget(self.save_btn)

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

        # 右侧：文件列表、JSON显示、关键字段显示区域
        right_widget = self.create_right_panel()
        main_splitter.addWidget(right_widget)

        # 设置初始大小比例
        main_splitter.setSizes([800, 400])

        return main_splitter

    def create_image_display(self):
        """创建图像显示区域"""
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.setContentsMargins(2, 2, 2, 2)
        image_layout.setSpacing(2)

        # 图像标签 (修改：不再直接显示图像，而是作为容器)
        self.image_label = QLabel("请选择图像文件夹")
        self.image_label.setObjectName("image_label")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 500)
        # 启用鼠标跟踪以支持滚轮
        self.image_label.setMouseTracking(True)
        # 使 QLabel 能够接收鼠标事件
        self.image_label.mousePressEvent = self.on_image_mouse_press
        self.image_label.mouseMoveEvent = self.on_image_mouse_move
        self.image_label.mouseReleaseEvent = self.on_image_mouse_release
        # 保存鼠标状态
        self._is_dragging = False
        self._last_mouse_pos = None

        # 创建滚动区域用于图像
        self.scroll_area = QScrollArea()  # 将 scroll_area 保存为实例变量，方便后续操作
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)  # 这个可以保持，但实际显示由 pixmap 控制
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # 安装事件过滤器以捕获滚轮事件
        self.scroll_area.installEventFilter(self)

        image_layout.addWidget(self.scroll_area)

        # 添加图像操作工具栏 (放在图像显示区域下方)
        image_toolbar = QToolBar("图像工具")
        image_toolbar.setIconSize(QSize(16, 16))  # 可根据需要调整图标大小

        # 缩放按钮
        self.zoom_in_btn = QPushButton("放大 (+)")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        image_toolbar.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("缩小 (-)")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        image_toolbar.addWidget(self.zoom_out_btn)

        self.zoom_fit_btn = QPushButton("适应窗口")
        self.zoom_fit_btn.clicked.connect(self.fit_to_window)
        image_toolbar.addWidget(self.zoom_fit_btn)

        self.zoom_100_btn = QPushButton("100%")
        self.zoom_100_btn.clicked.connect(self.normal_size)
        image_toolbar.addWidget(self.zoom_100_btn)

        # 旋转按钮
        self.rotate_left_btn = QPushButton("左转90°")
        self.rotate_left_btn.clicked.connect(lambda: self.rotate_image(-90))
        image_toolbar.addWidget(self.rotate_left_btn)

        self.rotate_right_btn = QPushButton("右转90°")
        self.rotate_right_btn.clicked.connect(lambda: self.rotate_image(90))
        image_toolbar.addWidget(self.rotate_right_btn)

        image_toolbar.addSeparator()

        # 显示当前缩放比例
        self.zoom_label = QLabel("100%")
        image_toolbar.addWidget(self.zoom_label)

        image_layout.addWidget(image_toolbar)

        return image_widget

    def create_right_panel(self):
        """创建右侧面板（文件列表 + JSON显示 + 关键字段显示）"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(2, 2, 2, 2)
        right_layout.setSpacing(2)

        # 创建垂直分割器
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setHandleWidth(4)

        # 文件列表区域（放在最下面）
        file_list_widget = self.create_file_list_area()
        right_splitter.addWidget(file_list_widget)

        # JSON显示区域（放在中间）
        json_widget = self.create_json_display()
        right_splitter.addWidget(json_widget)

        # 关键字段显示区域（放在最上面）
        fields_widget = self.create_fields_display()
        right_splitter.addWidget(fields_widget)

        # 设置初始大小比例
        right_splitter.setSizes([150, 250, 300])

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
        self.file_list.setMinimumHeight(100)
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
        self.json_text.setMinimumHeight(150)
        json_layout.addWidget(self.json_text)

        return json_widget

    def create_fields_display(self):
        """创建关键字段显示区域"""
        fields_widget = QWidget()
        fields_layout = QVBoxLayout(fields_widget)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(2)

        fields_layout.addWidget(QLabel("关键字段信息 (点击字段值可直接编辑):"))

        # 创建滚动区域用于字段显示
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 创建网格布局显示关键字段
        self.fields_grid_widget = QWidget()
        self.fields_grid = QGridLayout(self.fields_grid_widget)
        self.fields_grid.setSpacing(4)
        self.fields_grid.setContentsMargins(4, 4, 4, 4)

        scroll_area.setWidget(self.fields_grid_widget)
        fields_layout.addWidget(scroll_area)

        # 初始化字段显示
        self.init_field_labels()

        return fields_widget

    def init_field_labels(self):
        """初始化字段标签"""
        # 清除现有布局
        for i in reversed(range(self.fields_grid.count())):
            widget = self.fields_grid.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        self.field_labels = {}
        self.field_types = {}

        # 定义字段配置：全部使用文本输入（移除下拉框）
        field_configs = [
            ("图像ID", "model_response.image_id", "text"),
            ("质量标签", "model_response.quality_tags", "text"),
            ("版式类型", "model_response.layout_type", "text"),
            ("年份", "model_response.year", "text"),
            ("省份", "model_response.province", "text"),
            ("统一社会信用代码", "model_response.annotations.统一社会信用代码", "text"),
            ("企业名称", "model_response.annotations.企业名称", "text"),
            ("法定代表人", "model_response.annotations.法定代表人", "text"),
            ("注册资本", "model_response.annotations.注册资本", "text"),
            ("成立日期", "model_response.annotations.成立日期", "text"),
            ("经营范围", "model_response.annotations.经营范围", "text")
        ]

        for i, (display_name, json_path, field_type) in enumerate(field_configs):
            row = i
            col = 0

            # 字段标签（只显示，不可编辑）
            field_label = QLabel(display_name)
            field_label.setObjectName("field_name")
            self.fields_grid.addWidget(field_label, row, col)

            # 字段值显示（可直接编辑）
            value_label = EditableLabel("暂无数据", display_name)
            value_label.editingFinished.connect(self.on_field_value_changed)

            # 设置布局属性
            value_label.setProperty("row", row)
            value_label.setProperty("col", col + 1)
            value_label.setWordWrap(True)
            value_label.setMinimumHeight(25)

            self.fields_grid.addWidget(value_label, row, col + 1)

            self.field_labels[display_name] = value_label
            self.field_types[display_name] = (json_path, field_type)

    def get_field_value_from_json(self, json_path):
        """从JSON数据中获取字段值"""
        if not self.current_json_data:
            return ""

        try:
            # 特殊处理 annotations 路径
            if json_path.startswith("model_response.annotations."):
                field_name = json_path.split(".")[-1]
                annotations = self.current_json_data.get("model_response", {}).get("annotations", [])
                for item in annotations:
                    if item.get("field_name") == field_name:
                        return item.get("text", "")
                return ""
            else:
                # 普通路径处理
                path_parts = json_path.split('.')
                current = self.current_json_data

                # 导航到目标
                for part in path_parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                        current = current[int(part)]
                    else:
                        # 特殊处理 quality_tags（列表）
                        if json_path == "model_response.quality_tags" and isinstance(current, list):
                            return current[0] if current else ""
                        return ""

                # 特殊处理 quality_tags（列表）
                if json_path == "model_response.quality_tags" and isinstance(current, list):
                    return current[0] if current else ""

                return str(current) if current is not None else ""
        except Exception as e:
            print(f"获取字段值出错 {json_path}: {e}")
            return ""

    def set_field_value_in_json(self, json_path, value):
        """设置JSON数据中的字段值"""
        if not self.current_json_data:
            return False

        try:
            # 特殊处理 annotations 路径
            if json_path.startswith("model_response.annotations."):
                field_name = json_path.split(".")[-1]
                model_response = self.current_json_data.setdefault("model_response", {})
                annotations = model_response.setdefault("annotations", [])

                # 查找或创建字段
                field_found = False
                for item in annotations:
                    if item.get("field_name") == field_name:
                        item["text"] = value
                        field_found = True
                        break

                if not field_found:
                    annotations.append({
                        "field_name": field_name,
                        "text": value,
                        "is_handwritten": False,
                        "is_covered_by_stamp": False
                    })

                return True
            else:
                # 普通路径处理
                path_parts = json_path.split('.')
                current = self.current_json_data

                # 导航到倒数第二层
                for part in path_parts[:-1]:
                    if part not in current:
                        current[part] = {} if not part.isdigit() else []
                    current = current[part]

                # 设置最后一层的值
                last_part = path_parts[-1]
                if last_part == "quality_tags":
                    current[last_part] = [value] if value else []
                elif last_part == "year":
                    try:
                        current[last_part] = int(value) if value else 0
                    except:
                        current[last_part] = 0
                else:
                    current[last_part] = value

                return True
        except Exception as e:
            print(f"设置字段值出错 {json_path}: {e}")
            return False

    def update_fields_display(self):
        """更新关键字段显示"""
        if not hasattr(self, 'field_labels') or not self.field_labels:
            return

        # 更新所有字段显示
        for field_name, label in self.field_labels.items():
            if field_name in self.field_types:
                json_path, _ = self.field_types[field_name]
                value = self.get_field_value_from_json(json_path)
                label.setText(value if value else "暂无数据")

    def on_field_value_changed(self, field_name, old_value, new_value):
        """字段值改变事件"""
        if not self.current_json_data:
            return

        # 获取对应的JSON路径
        if field_name in self.field_types:
            json_path, _ = self.field_types[field_name]

            # 更新JSON数据
            if self.set_field_value_in_json(json_path, new_value):
                # 更新JSON文本显示
                if self.current_json_data:
                    formatted_json = json.dumps(self.current_json_data, ensure_ascii=False, indent=2)
                    self.json_text.setPlainText(formatted_json)

                self.status_bar.showMessage(f"已更新字段: {field_name} ({old_value} -> {new_value})")
            else:
                self.status_bar.showMessage(f"更新字段 {field_name} 失败")

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
            # --- 新增：没有图像时禁用删除 ---
            self.delete_image_action.setEnabled(False)
            # --------------------------------
            return

        image_path = self.image_files[self.current_index]
        file_name = os.path.basename(image_path)

        # 更新文件列表选中状态
        self.file_list.setCurrentRow(self.current_index)

        # 加载并显示图像 (会重置缩放和旋转)
        self.load_and_display_image(image_path)

        # 加载对应的JSON
        self.load_json_for_current_image()

        # 更新状态栏
        self.status_bar.showMessage(f"显示: {file_name} ({self.current_index + 1}/{len(self.image_files)})")

        # 更新导航按钮状态
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)
        # --- 新增：有图像时启用删除 ---
        self.delete_image_action.setEnabled(True)
        # -----------------------------

    def load_and_display_image(self, image_path):
        """加载并显示图像，初始适应窗口"""
        try:
            # 使用OpenCV加载图像
            image = cv2.imread(image_path)
            if image is None:
                self.image_label.setText(f"无法加载图像: {os.path.basename(image_path)}")
                self.current_pixmap = None
                self.display_pixmap = None
                # 重置变换状态
                self.scale_factor = 1.0
                self.rotation_angle = 0
                return

            # 转换颜色空间
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # 获取图像尺寸
            h, w, ch = image.shape
            bytes_per_line = ch * w

            # 创建QImage
            q_img = QImage(image.data, w, h, bytes_per_line, QImage.Format_RGB888)

            # 创建原始 QPixmap
            self.current_pixmap = QPixmap.fromImage(q_img)

            # --- 修改：计算初始适应窗口的缩放因子 ---
            if self.current_pixmap and self.scroll_area and self.scroll_area.viewport():
                viewport_size = self.scroll_area.viewport().size()
                pixmap_size = self.current_pixmap.size()

                if pixmap_size.width() > 0 and pixmap_size.height() > 0:
                    factor_x = viewport_size.width() / pixmap_size.width()
                    factor_y = viewport_size.height() / pixmap_size.height()
                    # 选择较小的因子以确保整个图像可见
                    self.scale_factor = min(factor_x, factor_y)
                    # 可选：如果图像小则不放大
                    # self.scale_factor = min(self.scale_factor, 1.0)
                else:
                    self.scale_factor = 1.0
            else:
                self.scale_factor = 1.0  # 如果无法计算，则默认1.0

            # 重置旋转
            self.rotation_angle = 0

            # 显示图像
            self.update_image_display()
            self.update_zoom_label()  # 更新缩放标签

        except Exception as e:
            self.image_label.setText(f"加载图像出错: {str(e)}")
            self.current_pixmap = None
            self.display_pixmap = None
            self.scale_factor = 1.0
            self.rotation_angle = 0

    def update_image_display(self):
        """根据当前的缩放和旋转因子更新图像显示"""
        if self.current_pixmap is None:
            return

        # 创建变换
        transform = QTransform()
        # 先缩放
        transform.scale(self.scale_factor, self.scale_factor)
        # 再旋转 (围绕 pixmap 中心)
        # pixmap 的中心点在 (width/2, height/2)
        # pixmap 经过缩放后的尺寸
        scaled_width = self.current_pixmap.width() * self.scale_factor
        scaled_height = self.current_pixmap.height() * self.scale_factor
        # 修正：旋转应该以缩放后图像的中心为轴心
        transform.translate(scaled_width / 2 / self.scale_factor, scaled_height / 2 / self.scale_factor)
        transform.rotate(self.rotation_angle)
        transform.translate(-scaled_width / 2 / self.scale_factor, -scaled_height / 2 / self.scale_factor)

        # 应用变换
        self.display_pixmap = self.current_pixmap.transformed(transform, Qt.SmoothTransformation)

        # 在 QLabel 上绘制 pixmap
        self.image_label.setPixmap(self.display_pixmap)
        # 调整 QLabel 大小以适应 pixmap
        self.image_label.resize(self.display_pixmap.size())
        # 确保滚动区域可以正确工作
        self.image_label.setFixedSize(self.display_pixmap.size())

    def zoom_in(self):
        """放大图像"""
        self.scale_image(1.1)
    def zoom_out(self):
        """缩小图像"""
        self.scale_image(0.9)
    def scale_image(self, factor):
        """缩放图像"""
        if self.current_pixmap is None:
            return

        self.scale_factor *= factor
        # 限制缩放范围
        self.scale_factor = max(0.1, min(self.scale_factor, 10.0))

        self.update_image_display()
        self.update_zoom_label()

        # 调整滚动条以保持焦点
        self.adjust_scrollbar(factor, factor)

    def adjust_scrollbar(self, factor_x, factor_y):
        """调整滚动条位置以保持缩放中心"""
        # 获取当前滚动条位置
        scroll_area = self.scroll_area
        horizontal_bar = scroll_area.horizontalScrollBar()
        vertical_bar = scroll_area.verticalScrollBar()

        # 计算新的滚动条位置
        # PyQt 的滚动条值是相对于可见区域左上角的
        # 我们希望放大/缩小时，视图中心保持不变
        viewport_center_x = scroll_area.viewport().width() / 2.0
        viewport_center_y = scroll_area.viewport().height() / 2.0

        # 当前视图中心在内容中的坐标
        old_center_x = horizontal_bar.value() + viewport_center_x
        old_center_y = vertical_bar.value() + viewport_center_y

        # 新的视图中心坐标 (理论上应该不变)
        new_center_x = old_center_x * factor_x
        new_center_y = old_center_y * factor_y

        # 新的滚动条值
        new_value_x = new_center_x - viewport_center_x
        new_value_y = new_center_y - viewport_center_y

        horizontal_bar.setValue(int(new_value_x))
        vertical_bar.setValue(int(new_value_y))

    def normal_size(self):
        """恢复正常大小 (100%)"""
        if self.current_pixmap is None:
            return
        self.scale_factor = 1.0
        self.update_image_display()
        self.update_zoom_label()

    def fit_to_window(self):
        """适应窗口大小 - 重新计算缩放因子并应用"""
        if self.current_pixmap is None or not self.scroll_area:
            return

        # 获取 QLabel (内容) 和 QScrollArea (视口) 的尺寸
        # 注意：这里我们关心的是图像（pixmap）如何适应视口
        viewport_size = self.scroll_area.viewport().size()
        pixmap_original_size = self.current_pixmap.size()  # 使用原始pixmap尺寸计算

        if pixmap_original_size.width() <= 0 or pixmap_original_size.height() <= 0:
            return

        # 计算缩放因子，使原始图像适应视口
        factor_x = viewport_size.width() / pixmap_original_size.width()
        factor_y = viewport_size.height() / pixmap_original_size.height()
        # 选择较小的因子以确保整个图像可见
        fit_factor = min(factor_x, factor_y)

        # --- 修改: 更新 scale_factor 并刷新显示 ---
        self.scale_factor = fit_factor
        self.update_image_display()  # 使用新的 scale_factor 更新显示
        self.update_zoom_label()  # 更新缩放标签

        # 可选：重置滚动条到顶部/左侧
        self.scroll_area.horizontalScrollBar().setValue(0)
        self.scroll_area.verticalScrollBar().setValue(0)

    def rotate_image(self, angle):
        """旋转图像"""
        if self.current_pixmap is None:
            return
        self.rotation_angle = (self.rotation_angle + angle) % 360
        self.update_image_display()

    def update_zoom_label(self):
        """更新缩放比例标签"""
        percentage = int(self.scale_factor * 100)
        self.zoom_label.setText(f"{percentage}%")

    # 事件处理
    def eventFilter(self, source, event):
        """事件过滤器，用于处理滚轮事件"""
        if source is self.scroll_area and event.type() == event.Wheel:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return True # 事件已处理
        return super().eventFilter(source, event) # 调用父类的事件过滤器

    # # 事件处理
    # def eventFilter(self, source, event):
    #     """事件过滤器，用于处理滚轮事件"""
    #     if source is self.scroll_area and event.type() == event.Wheel:
    #         # 检查是否按下了 Ctrl 键
    #         if event.modifiers() == Qt.ControlModifier:
    #             if event.angleDelta().y() > 0:
    #                 self.zoom_in()
    #             else:
    #                 self.zoom_out()
    #             return True  # 事件已处理
    #     return super().eventFilter(source, event)  # 调用父类的事件过滤器

    # 鼠标拖动相关方法 (可选，用于拖动图像)
    def on_image_mouse_press(self, event):
        """图像区域鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._last_mouse_pos = event.pos()
            # 设置鼠标光标
            self.image_label.setCursor(Qt.ClosedHandCursor)
        super(QLabel, self.image_label).mousePressEvent(event)

    def on_image_mouse_move(self, event):
        """图像区域鼠标移动事件"""
        if self._is_dragging and self._last_mouse_pos is not None:
            # 计算鼠标移动的偏移量
            delta = event.pos() - self._last_mouse_pos
            # 滚动条反向移动，实现拖动效果
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x()
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y()
            )
            self._last_mouse_pos = event.pos()
        super(QLabel, self.image_label).mouseMoveEvent(event)

    def on_image_mouse_release(self, event):
        """图像区域鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            self._last_mouse_pos = None
            # 恢复鼠标光标
            self.image_label.setCursor(Qt.ArrowCursor)
        super(QLabel, self.image_label).mouseReleaseEvent(event)

    # ... (剩下的方法保持不变) ...

    def load_json_for_current_image(self):
        """加载当前图像对应的JSON文件"""
        if not self.image_files:
            return

        image_path = self.image_files[self.current_index]
        image_name = Path(image_path).stem

        # 如果没有选择JSON文件夹，自动创建
        if not self.json_folder:
            # 创建与图像文件夹同级的json_labels文件夹
            self.json_folder = os.path.join(os.path.dirname(self.image_folder), "json_labels")
            os.makedirs(self.json_folder, exist_ok=True)
            self.status_bar.showMessage(f"自动创建JSON文件夹: {self.json_folder}")

        # 查找对应的JSON文件
        json_file = None
        for root, _, files in os.walk(self.json_folder):
            for file in files:
                if file.startswith(image_name) and file.endswith('.json'):
                    json_file = os.path.join(root, file)
                    break
            if json_file:
                break

        self.current_json_path = json_file

        if json_file and os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                # 保存当前JSON数据
                self.current_json_data = json_data

                # 格式化JSON显示
                formatted_json = json.dumps(json_data, ensure_ascii=False, indent=2)
                self.json_text.setPlainText(formatted_json)

                # 更新关键字段显示
                self.update_fields_display()

                self.status_bar.showMessage(f"已加载JSON文件: {os.path.basename(json_file)}")

            except Exception as e:
                self.json_text.setPlainText(f"加载JSON文件出错: {str(e)}")
                self.current_json_data = None
                self.update_fields_display()
        else:
            # 自动创建新的JSON标签
            self.auto_create_new_json()

    def auto_create_new_json(self):
        """自动创建新的JSON标注"""
        if not self.image_files or self.current_index >= len(self.image_files):
            return

        image_path = self.image_files[self.current_index]
        image_name = Path(image_path).stem

        # 生成JSON文件路径
        json_filename = f"{image_name}.json"
        json_file_path = os.path.join(self.json_folder, json_filename)

        # 创建默认JSON结构
        default_json = {
            "image_path": image_path,
            "status": "success",
            "model_response": {
                "image_id": image_name + ".jpg",
                "quality_tags": "",
                "layout_type": "",
                "year": 0,
                "province": "",
                "complexity_tags": [],
                "annotations": []
            },
            "error": "",
            "processing_time": 0,
            "total_time": 0
        }

        # 更新当前数据
        self.current_json_data = default_json
        self.current_json_path = json_file_path

        # 更新显示
        formatted_json = json.dumps(default_json, ensure_ascii=False, indent=2)
        self.json_text.setPlainText(formatted_json)

        # 更新关键字段显示
        self.update_fields_display()

        # 自动保存
        self.save_json(auto_save=True)

        self.status_bar.showMessage(f"已自动创建并保存JSON文件: {json_filename}")

    def create_new_json(self):
        """手动创建新的JSON标注"""
        if not self.image_files or self.current_index >= len(self.image_files):
            QMessageBox.warning(self, "警告", "请先选择一个图像文件")
            return

        image_path = self.image_files[self.current_index]
        image_name = Path(image_path).stem

        # 如果没有选择JSON文件夹，提示用户选择
        if not self.json_folder:
            json_folder = QFileDialog.getExistingDirectory(self, "选择JSON保存文件夹")
            if not json_folder:
                return
            self.json_folder = json_folder
            self.status_bar.showMessage(f"已设置JSON文件夹: {json_folder}")

        # 生成JSON文件名
        json_filename = f"{image_name}.json"
        json_file_path = os.path.join(self.json_folder, json_filename)

        # 检查文件是否已存在
        if os.path.exists(json_file_path):
            reply = QMessageBox.question(self, "文件已存在",
                                         f"JSON文件 {json_filename} 已存在，是否覆盖？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

        # 创建默认JSON结构
        default_json = {
            "image_path": image_path,
            "status": "success",
            "model_response": {
                "image_id": image_name + ".jpg",
                "quality_tags": "",
                "layout_type": "",
                "year": 0,
                "province": "",
                "complexity_tags": [],
                "annotations": []
            },
            "error": "",
            "processing_time": 0,
            "total_time": 0
        }

        # 更新当前数据
        self.current_json_data = default_json
        self.current_json_path = json_file_path

        # 更新显示
        formatted_json = json.dumps(default_json, ensure_ascii=False, indent=2)
        self.json_text.setPlainText(formatted_json)

        # 更新关键字段显示
        self.update_fields_display()

        # 自动保存
        self.save_json(auto_save=True)

        self.status_bar.showMessage(f"已创建并保存JSON文件: {json_filename}")

    def edit_full_json(self):
        """编辑完整JSON标签（原来的编辑功能）"""
        if not self.image_files or self.current_index >= len(self.image_files):
            QMessageBox.warning(self, "警告", "请先选择一个图像文件")
            return

        image_path = self.image_files[self.current_index]

        # 如果没有JSON数据，自动创建
        if not hasattr(self, 'current_json_data') or self.current_json_data is None:
            self.auto_create_new_json()
            return

        # 这里可以添加完整的JSON编辑对话框（如果需要）
        QMessageBox.information(self, "提示", "点击关键字段可以直接编辑。\n如需编辑完整JSON，请使用其他编辑器或重新创建。")

    def save_json(self, auto_save=False):
        """保存JSON文件"""
        if not hasattr(self, 'current_json_data') or self.current_json_data is None:
            if not auto_save:
                QMessageBox.warning(self, "警告", "没有可保存的JSON数据")
            return

        if not self.current_json_path:
            # 生成JSON文件路径
            if not self.json_folder:
                # 如果没有选择JSON文件夹，自动创建
                self.json_folder = os.path.join(os.path.dirname(self.image_folder), "json_labels")
                os.makedirs(self.json_folder, exist_ok=True)

            if not self.image_files or self.current_index >= len(self.image_files):
                if not auto_save:
                    QMessageBox.warning(self, "警告", "请先选择一个图像文件")
                return

            image_path = self.image_files[self.current_index]
            image_name = Path(image_path).stem
            json_filename = f"{image_name}.json"
            json_file_path = os.path.join(self.json_folder, json_filename)
            self.current_json_path = json_file_path
        else:
            json_file_path = self.current_json_path

        try:
            # 保存JSON文件
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_json_data, f, ensure_ascii=False, indent=2)

            if not auto_save:
                self.status_bar.showMessage(f"JSON文件已保存: {json_file_path}")
                # 不再弹出成功通知对话框
            else:
                self.status_bar.showMessage(f"已创建JSON文件: {os.path.basename(json_file_path)}")

        except Exception as e:
            error_msg = f"保存JSON文件失败: {str(e)}"
            if not auto_save:
                QMessageBox.critical(self, "错误", error_msg)
            else:
                self.status_bar.showMessage(error_msg)

    def previous_image(self):
        """显示上一张图像"""
        if self.current_index > 0:
            # 自动保存当前JSON
            if self.current_json_data:
                self.save_json(auto_save=True)

            self.current_index -= 1
            self.show_current_image()

    def next_image(self):
        """显示下一张图像"""
        if self.current_index < len(self.image_files) - 1:
            # 自动保存当前JSON
            if self.current_json_data:
                self.save_json(auto_save=True)

            self.current_index += 1
            self.show_current_image()

    def resizeEvent(self, event):
        """窗口大小改变事件 - 重新调整图像大小"""
        super().resizeEvent(event)
        if self.image_files and hasattr(self, 'image_label'):
            # 重新显示当前图像以适应新大小
            # self.show_current_image() # 这会导致在调整窗口时总是回到第一张图
            # 更好的做法是在调整大小时保持当前图像的显示，但可能需要重新适应窗口
            # 例如，如果用户调整窗口大小是为了更好地查看当前图像，可以触发 fit_to_window
            # 但这可能会干扰用户的手动缩放。这里我们不做任何特殊处理。
            pass

    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_A:
            self.previous_image()
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_D:
            self.next_image()
        elif event.key() == Qt.Key_S and event.modifiers() == Qt.ControlModifier:
            self.save_json()
        elif event.key() == Qt.Key_N and event.modifiers() == Qt.ControlModifier:
            self.create_new_json()
        # --- 新增：处理 Delete 键 ---
        elif event.key() == Qt.Key_Delete:
            self.delete_current_image()
        # --------------------------
        else:
            super().keyPressEvent(event)

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
                          "图像标注编辑器 - LabelImg风格\n\n"
                          "功能:\n"
                          "• 浏览图像和JSON标签\n"
                          "• 自动创建新的JSON标注\n"
                          "• 点击关键字段值直接编辑\n"
                          "• 自动保存修改后的JSON\n"
                          "• 实时显示关键字段\n"
                          "• 支持营业执照模板字段\n"
                          "• 快捷键操作\n\n"
                          "快捷键:\n"
                          "• A/← : 上一张\n"
                          "• D/→ : 下一张\n"
                          "• Ctrl+N : 创建新JSON\n"
                          "• Ctrl+S : 保存JSON\n"
                          "• Ctrl+I : 打开图像文件夹\n"
                          "• Ctrl+J : 打开JSON文件夹\n"
                          "• Ctrl+Q : 退出\n"
                          "• Delete : 删除当前图像及标签\n"
                          "• Ctrl++ : 放大\n"
                          "• Ctrl+- : 缩小\n\n"
                          "点击关键字段信息区域的字段值可直接编辑！")

    # --- 新增方法：删除图像和快捷键设置 ---
    def delete_current_image(self):
        """删除当前选中的图像文件及其对应的JSON标签文件"""
        if not self.image_files or self.current_index >= len(self.image_files):
            QMessageBox.warning(self, "警告", "没有选中的图像文件")
            return

        current_image_path = self.image_files[self.current_index]
        image_name = Path(current_image_path).stem

        # 确认删除
        reply = QMessageBox.question(
            self,
            '确认删除',
            f'确定要删除图像 "{os.path.basename(current_image_path)}" 及其对应的JSON标签文件吗？\n\n此操作不可撤销！',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 1. 删除图像文件
                os.remove(current_image_path)
                self.status_bar.showMessage(f"已删除图像: {os.path.basename(current_image_path)}")

                # 2. 查找并删除对应的JSON文件
                json_deleted = False
                if self.json_folder:
                    for root, _, files in os.walk(self.json_folder):
                        for file in files:
                            if file.startswith(image_name) and file.endswith('.json'):
                                json_file_path = os.path.join(root, file)
                                try:
                                    os.remove(json_file_path)
                                    self.status_bar.showMessage(
                                        f"已删除图像: {os.path.basename(current_image_path)} 及其标签: {file}")
                                    json_deleted = True
                                    break  # 假设只有一个匹配的JSON文件
                                except OSError as e:
                                    self.status_bar.showMessage(f"删除JSON文件失败: {file} - {e}")
                                    QMessageBox.warning(self, "警告", f"删除JSON文件失败: {file}\n{e}")
                        if json_deleted:
                            break

                # 3. 从内部列表中移除
                del self.image_files[self.current_index]

                # 4. 更新UI
                self.file_list.takeItem(self.current_index)  # 从列表中移除项

                # 5. 调整当前索引和显示
                if self.image_files:
                    # 如果删除后还有文件，显示下一个或上一个
                    if self.current_index >= len(self.image_files):
                        self.current_index = len(self.image_files) - 1
                    # 重新显示当前图像
                    self.show_current_image()
                else:
                    # 如果没有文件了，清空显示
                    self.image_label.clear()
                    self.image_label.setText("图像已被全部删除")
                    self.json_text.clear()
                    self.current_index = 0
                    self.prev_btn.setEnabled(False)
                    self.next_btn.setEnabled(False)
                    self.delete_image_action.setEnabled(False)  # 没有文件时禁用删除
                    self.status_bar.showMessage("所有图像均已删除")

            except OSError as e:
                error_msg = f"删除文件失败: {e}"
                self.status_bar.showMessage(error_msg)
                QMessageBox.critical(self, "错误", error_msg)

    def open_shortcut_settings(self):
        """打开快捷键设置对话框"""
        # 创建一个简单的信息对话框来展示快捷键
        # TODO: 可以扩展为一个真正的设置对话框，允许用户自定义快捷键
        shortcuts_info = """
<h3>当前快捷键列表</h3>
<ul>
<li><b>文件操作:</b></li>
<ul>
<li>打开图像文件夹: Ctrl+I</li>
<li>打开JSON文件夹: Ctrl+J</li>
<li>保存JSON: Ctrl+S</li>
<li>删除当前图像及标签: Delete</li>
<li>退出: Ctrl+Q</li>
</ul>
<li><b>编辑操作:</b></li>
<ul>
<li>编辑完整JSON标签: Ctrl+E</li>
<li>创建新JSON标签: Ctrl+N</li>
<li>放大: Ctrl++</li>
<li>缩小: Ctrl+-</li>
</ul>
<li><b>导航操作:</b></li>
<ul>
<li>上一张: A / ←</li>
<li>下一张: D / →</li>
</ul>
<li><b>其他:</b></li>
<ul>
<li>适应窗口 (按钮): </li>
<li>100%大小 (按钮): </li>
</ul>
</ul>
<p><i>注意：快捷键自定义功能将在后续版本中实现。</i></p>
"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("快捷键设置")
        msg_box.setTextFormat(Qt.RichText)  # 允许HTML
        msg_box.setText(shortcuts_info)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
    # --------------------------------------------------


def main():
    app = QApplication(sys.argv)

    # 设置应用程序样式
    app.setStyle('Fusion')

    viewer = ImageViewer()
    viewer.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
