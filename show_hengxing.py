import sys
import os
import json
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QFileDialog, QScrollArea, QLabel,
    QPushButton, QSplitter, QFrame, QTextEdit, QGroupBox
)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QPoint, QRectF


# 图像展示控件（支持缩放、绘制标注框，修复重复图像问题）
class ImageView(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(100, 100)

        # 核心属性
        self.raw_image = None  # 原始图像（OpenCV格式）
        self.qpixmap = None  # 展示用QPixmap（每次加载新图像重置）
        self.annotations = []  # 标注框数据 [{"position": [...], "ptype": "...", "label": "..."}]
        self.current_scale = 1.0  # 缩放因子
        self.auto_fit = False  # 自适应窗口

    def set_image(self, image_path):
        """加载图像并初始化（每次加载新图像，完全重置原有数据，解决重复图像问题）"""
        # 第一步：强制重置所有图像相关属性，清除旧数据
        self.raw_image = None
        self.qpixmap = None
        self.setText("正在加载图像...")

        if not os.path.exists(image_path):
            self.setText("图像不存在")
            return

        # 第二步：重新读取原始图像，不复用任何旧数据
        self.raw_image = cv2.imread(image_path)
        if self.raw_image is None:
            self.setText("无法加载图像")
            return

        # 第三步：转换格式并创建全新Pixmap（不复制旧Pixmap，避免残留）
        rgb_image = cv2.cvtColor(self.raw_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        q_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.qpixmap = QPixmap.fromImage(q_image)  # 直接创建新Pixmap，不使用copy()

        # 第四步：重置缩放比例，确保新图像以原始大小初始化
        self.current_scale = 1.0
        self.update_image_display()

    def set_annotations(self, annotations):
        """设置标注框数据（同时保留label信息，用于右侧展示）"""
        # 重置旧标注数据，避免残留
        self.annotations = []
        for anno in annotations:
            # 保留标注框核心信息+label，确保数据完整性
            self.annotations.append({
                "position": anno.get("position", []),
                "ptype": anno.get("ptype", "rectangle"),
                "label": anno.get("label", "无标签")
            })
        self.update()

    def update_image_display(self):
        """根据缩放因子更新图像展示"""
        if self.qpixmap is None:
            return

        if self.auto_fit:
            parent_rect = self.parent().rect() if self.parent() else self.rect()
            scaled_pixmap = self.qpixmap.scaled(
                parent_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            scaled_pixmap = self.qpixmap.scaled(
                self.qpixmap.size() * self.current_scale,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        self.setPixmap(scaled_pixmap)

    # 鼠标滚轮缩放
    def wheelEvent(self, event):
        if self.qpixmap is None:
            return

        if self.auto_fit:
            self.auto_fit = False
            self.current_scale = 1.0

        delta = event.angleDelta().y()
        if delta > 0:
            self.current_scale *= 1.1
        else:
            self.current_scale *= 0.9

        self.current_scale = max(0.1, min(self.current_scale, 5.0))
        self.update_image_display()
        self.update()

    # 绘制标注框
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.qpixmap is None or not self.annotations:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(255, 0, 0), 2)
        painter.setPen(pen)

        pixmap_rect = self.pixmap().rect() if self.pixmap() else self.rect()
        offset_x = (self.width() - pixmap_rect.width()) // 2
        offset_y = (self.height() - pixmap_rect.height()) // 2

        for anno in self.annotations:
            position = anno.get("position", [])
            ptype = anno.get("ptype", "rectangle")

            if not position:
                continue

            scaled_points = []
            for pos in position:
                if isinstance(pos, (list, tuple)) and len(pos) == 2:
                    x = pos[0] * self.current_scale + offset_x
                    y = pos[1] * self.current_scale + offset_y
                    scaled_points.append(QPoint(int(x), int(y)))

            if not scaled_points:
                continue

            if ptype == "rectangle" and len(scaled_points) >= 2:
                x1, y1 = scaled_points[0].x(), scaled_points[0].y()
                x2, y2 = scaled_points[1].x(), scaled_points[1].y()
                rect = QRectF(min(x1, x2), min(y1, y2), abs(x1 - x2), abs(y1 - y2))
                painter.drawRect(rect)
            elif ptype == "quad" and len(scaled_points) >= 4:
                for i in range(4):
                    start = scaled_points[i]
                    end = scaled_points[(i + 1) % 4]
                    painter.drawLine(start, end)


# 主窗口（解决重复图像+右侧新增JSON Label内容展示）
class JsonImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JSON&图像标注查看器（改进版）")
        self.setGeometry(100, 100, 1600, 800)

        # 核心属性
        self.json_folder = ""  # JSON文件夹路径
        self.image_folder = ""  # 图像文件夹路径
        self.json_files = []  # 加载的JSON文件列表
        self.current_json_data = None  # 存储当前选中JSON的完整数据，用于右侧Label展示

        # 初始化UI
        self.init_ui()

    def init_ui(self):
        """初始化界面布局（右侧新增Label内容展示区域）"""
        # 主分割器（左右布局）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：图像显示区域（带控制按钮、滚动条）
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 左侧控制按钮布局
        ctrl_layout = QHBoxLayout()
        self.select_json_btn = QPushButton("选择JSON文件夹")
        self.select_json_btn.clicked.connect(self.select_json_folder)
        self.select_image_btn = QPushButton("选择图像文件夹")
        self.select_image_btn.clicked.connect(self.select_image_folder)
        self.reset_zoom_btn = QPushButton("重置缩放")
        self.reset_zoom_btn.clicked.connect(self.reset_zoom)

        ctrl_layout.addWidget(self.select_json_btn)
        ctrl_layout.addWidget(self.select_image_btn)
        ctrl_layout.addWidget(self.reset_zoom_btn)
        left_layout.addLayout(ctrl_layout)

        # 状态标签
        self.status_label = QLabel("请先选择JSON文件夹和图像文件夹")
        left_layout.addWidget(self.status_label)

        # 图像滚动区域
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_view = ImageView()
        self.image_scroll.setWidget(self.image_view)
        left_layout.addWidget(self.image_scroll)

        # 右侧：文件列表 + Label内容展示（上下布局，新增核心功能）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 第一部分：JSON文件列表（保留原有功能）
        file_group = QGroupBox("JSON文件列表")
        file_layout = QVBoxLayout(file_group)

        # 分隔线
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        file_layout.addWidget(line1)

        # 文件列表（支持键盘上下键）
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_json_item_clicked)
        self.file_list.keyPressEvent = self.handle_list_key_press
        file_layout.addWidget(self.file_list)
        right_layout.addWidget(file_group)

        # 第二部分：JSON Label内容展示（新增核心功能，带滚动条）
        label_group = QGroupBox("OCR Label 内容详情")
        label_layout = QVBoxLayout(label_group)

        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        label_layout.addWidget(line2)

        # 文本编辑框（只读，展示Label内容，支持滚动）
        self.label_text_edit = QTextEdit()
        self.label_text_edit.setReadOnly(True)
        self.label_text_edit.setFont(QFont("Consolas", 10))  # 等宽字体，便于阅读
        label_layout.addWidget(self.label_text_edit)
        right_layout.addWidget(label_group)

        # 设置右侧上下部分比例
        right_layout.setStretch(0, 1)  # 文件列表占1/3
        right_layout.setStretch(1, 2)  # Label详情占2/3

        # 添加到分割器，设置整体比例
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([1000, 600])

        # 设置主窗口部件
        self.setCentralWidget(main_splitter)

    def reset_zoom(self):
        """重置图像缩放到100%"""
        self.image_view.current_scale = 1.0
        self.image_view.auto_fit = False
        self.image_view.update_image_display()
        self.status_label.setText("缩放已重置为100%")

    def select_json_folder(self):
        """选择JSON文件夹并加载所有.json文件"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择JSON文件夹")
        if not folder_path:
            return

        self.json_folder = folder_path
        self.json_files = [
            f for f in os.listdir(folder_path)
            if f.lower().endswith(".json")
        ]

        # 更新右侧文件列表
        self.file_list.clear()
        for json_file in self.json_files:
            QListWidgetItem(json_file, self.file_list)

        # 清空右侧Label详情
        self.label_text_edit.clear()
        self.status_label.setText(f"已加载{len(self.json_files)}个JSON文件")

    def select_image_folder(self):
        """选择图像文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择图像文件夹")
        if not folder_path:
            return

        self.image_folder = folder_path
        self.status_label.setText(f"已设置图像文件夹：{os.path.basename(folder_path)}")

    def on_json_item_clicked(self, item):
        """点击右侧JSON文件，加载对应内容、图像（解决重复）、Label详情（新增）"""
        json_filename = item.text()
        json_path = os.path.join(self.json_folder, json_filename)

        # 1. 读取JSON文件（完整保留，获取最新数据）
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                self.current_json_data = json.load(f)  # 存储当前完整JSON数据
        except Exception as e:
            self.status_label.setText(f"读取JSON失败：{str(e)}")
            self.label_text_edit.clear()
            self.current_json_data = None
            return

        # 2. 匹配图像文件（JSON文件名前13位作为图像文件名）
        image_base_name = json_filename[:-12]
        image_path = ""
        if self.image_folder:
            image_formats = [".jpg", ".jpeg", ".png", ".bmp"]
            for f in os.listdir(self.image_folder):
                if f.startswith(image_base_name) and any(f.lower().endswith(ext) for ext in image_formats):
                    image_path = os.path.join(self.image_folder, f)
                    break

        # 3. 提取标注框数据（含Label）
        annotations = self.current_json_data.get("result", [])

        # 4. 核心改进：加载新图像（完全重置旧图像，解决重复展示问题）
        self.image_view.set_image(image_path)  # 调用ImageView的set_image，内部已重置所有旧数据
        self.image_view.set_annotations(annotations)

        # 5. 新增功能：解析Label内容，展示到右侧文本框
        self.update_label_text(annotations)

        # 6. 更新状态栏
        self.status_label.setText(f"已加载：{json_filename} | 标注框数量：{len(annotations)}")

    def update_label_text(self, annotations):
        """解析标注框的Label内容，格式化后展示到右侧文本框（新增核心方法）"""
        if not annotations:
            self.label_text_edit.setText("当前JSON无有效Label数据")
            return

        # 格式化Label内容，便于阅读
        label_content = []
        label_content.append("=" * 60)
        label_content.append(f"{'序号':<4} {'Label内容':<40} {'标注类型':<10}")
        label_content.append("=" * 60)

        for idx, anno in enumerate(annotations, 1):
            label = anno.get("label", "无标签")
            ptype = anno.get("ptype", "未知类型")
            # 格式化输出，对齐排版
            label_content.append(f"{idx:<4} {label:<40} {ptype:<10}")

        label_content.append("=" * 60)
        label_content.append(f"总计：{len(annotations)}个Label标注")

        # 写入右侧文本框
        self.label_text_edit.setText("\n".join(label_content))

    def handle_list_key_press(self, event):
        """处理文件列表键盘事件，支持上下键导航"""
        if event.key() == Qt.Key.Key_Up:
            current_index = self.file_list.currentRow()
            if current_index > 0:
                self.file_list.setCurrentRow(current_index - 1)
                self.on_json_item_clicked(self.file_list.currentItem())
        elif event.key() == Qt.Key.Key_Down:
            current_index = self.file_list.currentRow()
            if current_index < len(self.json_files) - 1:
                self.file_list.setCurrentRow(current_index + 1)
                self.on_json_item_clicked(self.file_list.currentItem())
        else:
            super(QListWidget, self.file_list).keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JsonImageViewer()
    window.show()
    sys.exit(app.exec())