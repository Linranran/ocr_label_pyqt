import math
from PIL import Image



import sys
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QFileDialog,
                             QLabel, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea,
                             QListWidget, QListWidgetItem, QSplitter, QFrame, QCheckBox)
from PyQt6.QtGui import QPixmap, QPainter, QPen, QFont, QColor
from PyQt6.QtCore import Qt, QSize


class OCRVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_files = []  # 存储图像文件路径列表
        self.current_pixmap = None  # 当前显示的图像
        self.current_scale = 1.0  # 当前缩放比例
        self.auto_fit = True  # 图像自适应标志
        self.normalized_coords = True  # 坐标是否为归一化坐标（0-1000范围） False True
        self.init_ui()

    def init_ui(self):
        # 设置窗口基本属性
        self.setWindowTitle("OCR识别结果可视化")
        self.setGeometry(100, 100, 1200, 800)

        # 创建主布局和分割器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：图像显示区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 缩放控制按钮
        scale_layout = QHBoxLayout()
        self.zoom_in_btn = QPushButton("放大")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn = QPushButton("缩小")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.reset_btn = QPushButton("重置大小")
        self.reset_btn.clicked.connect(self.reset_scale)
        self.fit_btn = QPushButton("自适应窗口")
        self.fit_btn.setCheckable(True)
        self.fit_btn.setChecked(self.auto_fit)
        self.fit_btn.clicked.connect(self.toggle_auto_fit)

        # 添加坐标归一化开关
        self.normalize_check = QCheckBox("坐标已归一化(0-1000)")
        self.normalize_check.stateChanged.connect(self.on_normalize_toggled)

        scale_layout.addWidget(self.zoom_in_btn)
        scale_layout.addWidget(self.zoom_out_btn)
        scale_layout.addWidget(self.reset_btn)
        scale_layout.addWidget(self.fit_btn)
        scale_layout.addWidget(self.normalize_check)
        left_layout.addLayout(scale_layout)

        # 状态标签
        self.status_label = QLabel("请选择包含JSON文件的文件夹")
        left_layout.addWidget(self.status_label)

        # 图像显示区域
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_layout.addWidget(self.image_label)
        self.image_scroll.setWidget(self.image_container)
        left_layout.addWidget(self.image_scroll)

        # 右侧：文件列表和控制按钮
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 选择文件夹按钮
        self.select_btn = QPushButton("选择JSON文件夹")
        self.select_btn.clicked.connect(self.select_folder)
        right_layout.addWidget(self.select_btn)

        # 上下切换按钮
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("上一个")
        self.prev_btn.clicked.connect(self.show_previous)
        self.prev_btn.setEnabled(False)
        self.next_btn = QPushButton("下一个")
        self.next_btn.clicked.connect(self.show_next)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)
        right_layout.addLayout(nav_layout)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        right_layout.addWidget(line)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_file_clicked)
        # 支持键盘上下键导航
        self.file_list.keyPressEvent = self.handle_list_key_press
        right_layout.addWidget(self.file_list)

        # 添加到分割器
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        # 设置初始大小比例
        main_splitter.setSizes([800, 400])

        # 设置主窗口部件
        self.setCentralWidget(main_splitter)

        # 窗口大小改变时重新适应图像
        self.resizeEvent = self.on_window_resize

    def select_folder(self):
        # 打开文件夹选择对话框
        folder_path = QFileDialog.getExistingDirectory(self, "选择JSON文件夹")
        if not folder_path:
            return

        self.status_label.setText(f"正在处理文件夹: {folder_path}")
        self.image_files = []
        self.file_list.clear()

        # 遍历文件夹中的JSON文件
        for filename in os.listdir(folder_path):
            if filename.endswith(".json"):
                json_path = os.path.join(folder_path, filename)
                # 尝试解析JSON获取图像信息
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    if "image_path" in data:
                        image_path = data["image_path"]
                        # 检查图像文件是否存在
                        if not os.path.exists(image_path):
                            # 尝试相对路径查找
                            json_dir = os.path.dirname(json_path)
                            relative_path = os.path.join(json_dir, image_path)
                            if os.path.exists(relative_path):
                                image_path = relative_path
                            else:
                                continue  # 图像不存在则跳过

                        # 存储图像路径和对应的JSON数据
                        self.image_files.append({
                            "json_path": json_path,
                            "image_path": image_path,
                            "data": data
                        })

                        # 添加到文件列表
                        item = QListWidgetItem(os.path.basename(image_path))
                        self.file_list.addItem(item)
                except Exception as e:
                    self.status_label.setText(f"处理文件 {filename} 时出错: {str(e)}")

        # 更新导航按钮状态
        self.update_nav_buttons()
        self.status_label.setText(f"共找到 {len(self.image_files)} 个有效图像文件")

    def on_file_clicked(self, item):
        # 获取点击的文件索引
        index = self.file_list.row(item)
        if 0 <= index < len(self.image_files):
            file_info = self.image_files[index]
            self.display_image(file_info)
            self.update_nav_buttons()

    def display_image(self, file_info):
        try:
            # 每次都从文件重新加载原始图像（关键修复）
            original_pixmap = QPixmap(file_info["image_path"])
            if original_pixmap.isNull():
                self.status_label.setText(f"无法加载图像 {file_info['image_path']}")
                return

            # 创建副本用于绘制，避免修改原始pixmap（关键修复）
            self.current_pixmap = original_pixmap.copy()

            # 绘制OCR信息
            self.draw_ocr_info(self.current_pixmap, file_info["data"]["model_response"])
            print(f"归一化状态: {self.normalized_coords} (当前图像尺寸: {original_pixmap.width()}x{original_pixmap.height()})")

            # 重置缩放比例
            self.current_scale = 1.0
            self.update_image_display()

            self.status_label.setText(f"显示图像: {os.path.basename(file_info['image_path'])}")
        except Exception as e:
            self.status_label.setText(f"显示图像时出错: {str(e)}")

    import math

    def map_coords_to_original(self, original_w, original_h, model_bbox):
        original_pixels = original_w * original_h
        max_pixels = 1254400

        if original_pixels > max_pixels:
            scale = math.sqrt(max_pixels / original_pixels)
            proc_w = int(original_w * scale)
            proc_h = int(original_h * scale)
            # 但 Qwen3-VL 可能会对齐到 patch size（如 14 的倍数）
            # 所以更准确：proc_w = round(original_w * scale / 14) * 14
            print('归一化', proc_w, proc_h)
        else:
            proc_w, proc_h = original_w, original_h

        # 使用实际处理尺寸计算缩放
        scale_x = original_w / proc_w
        scale_y = original_h / proc_h

        x1, y1, x2, y2 = model_bbox
        return [
            round(x1 * scale_x),
            round(y1 * scale_y),
            round(x2 * scale_x),
            round(y2 * scale_y)
        ]

    def draw_ocr_info(self, pixmap, ocr_results):
        # 获取图像实际尺寸
        img_width = pixmap.width()
        img_height = pixmap.height()

        # 创建画家对象
        painter = QPainter(pixmap)

        # 设置画笔 - 红色边框
        pen = QPen(QColor(200, 200, 200), 5)
        painter.setPen(pen)

        # 设置字体
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)

        # 绘制每个识别结果（适配JSON中的格式）
        for result in ocr_results:
            if "bbox_2d" in result and "text_content" in result:
                bbox = result["bbox_2d"]
                text = result["text_content"]

                # 确保边界框是4个数值
                if len(bbox) == 4:
                    # 先复制原始坐标
                    x1, y1, x2, y2 = bbox

                    # 如果启用了坐标归一化，转换为实际像素坐标
                    if self.normalized_coords:
                        x1,y1,x2,y2 = self.map_coords_to_original(img_width,img_height, bbox)


                    print('图像尺寸',img_width,img_height,'原始坐标',bbox,'坐标归一化', x1, y1, x2, y2)

                    # 绘制矩形边界框
                    painter.drawRect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))

                    # 绘制文本（在边界框上方）
                    painter.drawText(int(x1), max(10, int(y1) - 5), text)

        painter.end()
    def update_image_display(self):
        if self.current_pixmap:
            if self.auto_fit:
                # 自适应窗口大小
                scroll_rect = self.image_scroll.viewport().rect()
                scaled_pixmap = self.current_pixmap.scaled(
                    scroll_rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            else:
                # 按当前缩放比例显示
                scaled_pixmap = self.current_pixmap.scaled(
                    self.current_pixmap.size() * self.current_scale,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            self.image_label.setPixmap(scaled_pixmap)

    def zoom_in(self):
        # 放大时自动关闭自适应
        if self.auto_fit:
            self.auto_fit = False
            self.fit_btn.setChecked(False)

        self.current_scale *= 1.2
        self.update_image_display()
        self.status_label.setText(f"缩放比例: {int(self.current_scale * 100)}%")

    def zoom_out(self):
        # 缩小时自动关闭自适应
        if self.auto_fit:
            self.auto_fit = False
            self.fit_btn.setChecked(False)

        self.current_scale *= 0.8
        if self.current_scale < 0.1:  # 最小缩放限制
            self.current_scale = 0.1
        self.update_image_display()
        self.status_label.setText(f"缩放比例: {int(self.current_scale * 100)}%")

    def reset_scale(self):
        self.current_scale = 1.0
        self.update_image_display()
        self.status_label.setText("缩放比例: 100%")

    def toggle_auto_fit(self):
        self.auto_fit = self.fit_btn.isChecked()
        self.update_image_display()
        if self.auto_fit:
            self.status_label.setText("图像已自适应窗口")

    def on_normalize_toggled(self, state):
        self.normalized_coords = (state == Qt.CheckState.Checked)
        current_index = self.file_list.currentRow()
        if 0 <= current_index < len(self.image_files):
            self.display_image(self.image_files[current_index])
        # 更清晰的状态提示
        self.status_label.setText(f"坐标归一化: {'启用（0-1000→像素坐标）' if self.normalized_coords else '禁用（直接使用原始坐标）'}")

    def on_window_resize(self, event):
        # 窗口大小改变时，如果启用了自适应则重新调整图像
        if self.auto_fit and self.current_pixmap:
            self.update_image_display()
        super().resizeEvent(event)

    def show_previous(self):
        current_index = self.file_list.currentRow()
        if current_index > 0:
            self.file_list.setCurrentRow(current_index - 1)
            self.on_file_clicked(self.file_list.currentItem())

    def show_next(self):
        current_index = self.file_list.currentRow()
        if current_index < len(self.image_files) - 1:
            self.file_list.setCurrentRow(current_index + 1)
            self.on_file_clicked(self.file_list.currentItem())

    def update_nav_buttons(self):
        current_index = self.file_list.currentRow()
        self.prev_btn.setEnabled(current_index > 0)
        self.next_btn.setEnabled(current_index < len(self.image_files) - 1 and len(self.image_files) > 0)

    def handle_list_key_press(self, event):
        # 处理列表的键盘事件，支持上下键导航
        if event.key() == Qt.Key.Key_Up:
            current_index = self.file_list.currentRow()
            if current_index > 0:
                self.file_list.setCurrentRow(current_index - 1)
                self.on_file_clicked(self.file_list.currentItem())
        elif event.key() == Qt.Key.Key_Down:
            current_index = self.file_list.currentRow()
            if current_index < len(self.image_files) - 1:
                self.file_list.setCurrentRow(current_index + 1)
                self.on_file_clicked(self.file_list.currentItem())
        else:
            # 其他按键交给默认处理
            super(QListWidget, self.file_list).keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OCRVisualizer()
    window.show()
    sys.exit(app.exec())