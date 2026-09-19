import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit, QListWidget,
    QListWidgetItem, QScrollArea, QLineEdit, QMessageBox, QGroupBox,
    QFormLayout
)
from PyQt6.QtGui import QPixmap, QFont, QTransform
from PyQt6.QtCore import Qt


class OCRResultEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR识别结果解析编辑器")
        self.setGeometry(100, 100, 1200, 800)  # 适配目标UI尺寸

        # 初始化数据
        self.ocr_data_list = []  # 存储解析后的所有OCR数据
        self.current_index = -1  # 当前选中的数据索引
        self.original_file_path = ""  # 原始TXT文件路径
        self.image_scale = 1.0  # 图像缩放比例
        self.image_rotation = 0  # 图像旋转角度（0/90/180/270）
        self.current_pixmap = None  # 存储当前原始pixmap，用于旋转/缩放

        # 创建主界面（模拟目标UI：图像左，文件列表右）
        self._init_ui()

        # 监听列表的选中变化（兼容键盘/鼠标/滚轮操作）
        self.data_list.currentItemChanged.connect(self.on_current_item_changed)

    def _init_ui(self):
        # 主部件和水平布局（左侧图像区 + 右侧控制区）
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ========== 左侧：图像预览区（模拟目标UI左侧大区域） ==========
        left_group = QGroupBox("图像预览区")
        left_layout = QVBoxLayout(left_group)

        # 图像显示标签（带滚动，占左侧主要区域）
        self.image_label = QLabel("请加载TXT文件后选择图像")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #cccccc; background-color: #f5f5f5;")
        self.image_label.setMinimumSize(700, 700)  # 左侧大尺寸

        # 图像状态显示（缩放+旋转）
        self.status_label = QLabel("缩放：100% | 旋转：0°")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 10))
        left_layout.addWidget(self.status_label)

        # 图像操作控制按钮（缩放+旋转）
        control_layout = QHBoxLayout()

        # 缩放按钮组
        zoom_layout = QHBoxLayout()
        self.zoom_in_btn = QPushButton("放大 (+)")
        self.zoom_out_btn = QPushButton("缩小 (-)")
        self.fit_window_btn = QPushButton("适应窗口")
        self.reset_zoom_btn = QPushButton("重置缩放")
        zoom_layout.addWidget(self.zoom_in_btn)
        zoom_layout.addWidget(self.zoom_out_btn)
        zoom_layout.addWidget(self.fit_window_btn)
        zoom_layout.addWidget(self.reset_zoom_btn)

        # 旋转按钮组
        rotate_layout = QHBoxLayout()
        self.rotate_left_btn = QPushButton("逆时针旋转")
        self.rotate_right_btn = QPushButton("顺时针旋转")
        self.reset_rotate_btn = QPushButton("重置旋转")
        rotate_layout.addWidget(self.rotate_left_btn)
        rotate_layout.addWidget(self.rotate_right_btn)
        rotate_layout.addWidget(self.reset_rotate_btn)

        # 绑定按钮事件
        self.zoom_in_btn.clicked.connect(lambda: self._zoom_image(1.1))
        self.zoom_out_btn.clicked.connect(lambda: self._zoom_image(0.9))
        self.fit_window_btn.clicked.connect(self._fit_image_to_window)
        self.reset_zoom_btn.clicked.connect(self._reset_zoom)
        self.rotate_left_btn.clicked.connect(lambda: self._rotate_image(-90))
        self.rotate_right_btn.clicked.connect(lambda: self._rotate_image(90))
        self.reset_rotate_btn.clicked.connect(self._reset_rotate)

        control_layout.addLayout(zoom_layout)
        control_layout.addLayout(rotate_layout)

        # 图像滚动区域（支持拖动查看放大/旋转后的图像）
        image_scroll = QScrollArea()
        image_scroll.setWidget(self.image_label)
        image_scroll.setWidgetResizable(False)  # 关闭自动调整，支持拖动
        image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        left_layout.addWidget(image_scroll)
        left_layout.addLayout(control_layout)
        main_layout.addWidget(left_group, stretch=2)  # 左侧占比2

        # ========== 右侧：文件列表+编辑区（模拟目标UI右侧控制区） ==========
        right_group = QGroupBox("数据控制区")
        right_layout = QVBoxLayout(right_group)
        right_layout.setSpacing(8)

        # 顶部：功能按钮（覆盖保存+另存为）
        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("加载OCR结果TXT文件")
        self.save_btn = QPushButton("另存为新文件")
        self.overwrite_btn = QPushButton("覆盖原始文件")
        self.load_btn.clicked.connect(self.load_ocr_file)
        self.save_btn.clicked.connect(self.save_modified_data)
        self.overwrite_btn.clicked.connect(self.overwrite_original_file)
        self.save_btn.setEnabled(False)
        self.overwrite_btn.setEnabled(False)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.overwrite_btn)
        right_layout.addLayout(btn_layout)

        # 中间：文件列表（右侧核心区域）
        list_label = QLabel("文件列表")
        list_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        right_layout.addWidget(list_label)

        self.data_list = QListWidget()
        self.data_list.setFont(QFont("Arial", 10))
        self.data_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.data_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.data_list.setMinimumHeight(300)
        right_layout.addWidget(self.data_list)

        # 底部：识别结果编辑区（表单式布局，模拟目标UI编辑风格）
        edit_group = QGroupBox("识别结果编辑")
        edit_layout = QFormLayout(edit_group)
        # 设置表单布局标签靠左对齐，字段填满空间
        edit_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        edit_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        edit_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # 识别文字编辑框（核心编辑项 - 多行+左对齐）
        self.word_edit_label = QLabel("识别文字：")
        self.word_edit = QTextEdit()
        self.word_edit.setPlaceholderText("请编辑识别结果...")
        self.word_edit.setMinimumHeight(100)
        self.word_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.word_edit.textChanged.connect(self.on_word_edit)
        edit_layout.addRow(self.word_edit_label, self.word_edit)

        # 辅助信息展示（靠左对齐）
        self.img_path_label = QLabel("当前路径：")
        self.img_path_display = QLineEdit()
        self.img_path_display.setReadOnly(True)
        self.img_path_display.setStyleSheet("background-color: #f0f0f0;")
        self.img_path_display.setAlignment(Qt.AlignmentFlag.AlignLeft)
        edit_layout.addRow(self.img_path_label, self.img_path_display)

        self.request_time_label = QLabel("请求耗时：")
        self.request_time_display = QLineEdit()
        self.request_time_display.setReadOnly(True)
        self.request_time_display.setStyleSheet("background-color: #f0f0f0;")
        self.request_time_display.setAlignment(Qt.AlignmentFlag.AlignLeft)
        edit_layout.addRow(self.request_time_label, self.request_time_display)

        # 原始数据展示区（靠左对齐）
        raw_label = QLabel("原始JSON数据：")
        raw_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        right_layout.addWidget(raw_label)

        self.raw_data_edit = QTextEdit()
        self.raw_data_edit.setReadOnly(True)
        self.raw_data_edit.setFont(QFont("Consolas", 9))
        self.raw_data_edit.setMinimumHeight(200)
        self.raw_data_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        right_layout.addWidget(edit_group)
        right_layout.addWidget(raw_label)
        right_layout.addWidget(self.raw_data_edit)

        # 翻页按钮
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("上一条")
        self.next_btn = QPushButton("下一条")
        self.prev_btn.clicked.connect(self._prev_item)
        self.next_btn.clicked.connect(self._next_item)
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)
        right_layout.addLayout(nav_layout)

        main_layout.addWidget(right_group, stretch=1)  # 右侧占比1

    def load_ocr_file(self):
        """加载并解析OCR结果TXT文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择OCR结果文件", "", "Text Files (*.txt);;All Files (*.*)"
        )
        if not file_path:
            return

        # 保存原始文件路径
        self.original_file_path = file_path

        try:
            # 清空原有数据
            self.ocr_data_list.clear()
            self.data_list.clear()
            self.current_index = -1
            # 重置图像状态
            self.image_scale = 1.0
            self.image_rotation = 0
            self.current_pixmap = None
            self.status_label.setText("缩放：100% | 旋转：0°")

            # 解析TXT文件（每行一个JSON）
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        self.ocr_data_list.append(data)

                        # 添加到列表（显示图片路径的最后部分）
                        img_name = os.path.basename(data.get("img_path", f"未知文件_{line_num}"))
                        item = QListWidgetItem(img_name)
                        item.setData(Qt.ItemDataRole.UserRole, line_num - 1)
                        self.data_list.addItem(item)

                    except json.JSONDecodeError as e:
                        QMessageBox.warning(
                            self, "解析错误",
                            f"第{line_num}行JSON解析失败：{str(e)}"
                        )

            if self.ocr_data_list:
                QMessageBox.information(
                    self, "加载成功",
                    f"共解析到 {len(self.ocr_data_list)} 条记录"
                )
                self.save_btn.setEnabled(True)
                self.overwrite_btn.setEnabled(True)
                # 默认选中第一条
                if self.data_list.count() > 0:
                    self.data_list.setCurrentRow(0)
            else:
                QMessageBox.warning(self, "警告", "未解析到有效数据")

        except Exception as e:
            QMessageBox.critical(self, "文件加载失败", f"加载文件出错：{str(e)}")

    def on_current_item_changed(self, current_item, previous_item):
        """列表选中项变化时更新预览和标签"""
        if not current_item:
            self.current_index = -1
            self.image_label.setText("请选择文件列表中的项")
            self.word_edit.clear()
            self.img_path_display.clear()
            self.request_time_display.clear()
            self.raw_data_edit.clear()
            self.current_pixmap = None
            return

        # 获取当前选中的索引
        self.current_index = current_item.data(Qt.ItemDataRole.UserRole)
        if self.current_index < 0 or self.current_index >= len(self.ocr_data_list):
            return

        # 获取当前数据
        current_data = self.ocr_data_list[self.current_index]

        # ========== 展示图片 ==========
        img_path = current_data.get("img_path", "")
        self._display_image(img_path)

        # ========== 展示辅助信息 ==========
        self.img_path_display.setText(img_path)
        self.request_time_display.setText(f"{current_data.get('request_time', 0)} 秒")

        # ========== 展示识别结果 ==========
        words = ""
        response = current_data.get("response", {})
        words_result = response.get("words_result", {})

        # 兼容字典格式（word_result）
        # 车牌识别的格式和vin不一样
        words_result = response.get("words_result", {})
        if isinstance(words_result, dict):
            words = words_result.get("number", "")


        # 设置编辑框内容
        self.word_edit.blockSignals(True)
        self.word_edit.setText(words)
        self.word_edit.blockSignals(False)

        # 展示原始JSON
        raw_data = json.dumps(current_data, ensure_ascii=False, indent=2)
        self.raw_data_edit.setText(raw_data)

    def _display_image(self, img_path):
        """展示图片（应用缩放+旋转）"""
        if not os.path.exists(img_path):
            self.image_label.setText(f"图片不存在：\n{img_path}")
            self.current_pixmap = None
            return

        try:
            # 加载原始pixmap
            self.current_pixmap = QPixmap(img_path)
            if self.current_pixmap.isNull():
                self.image_label.setText("无法加载图片（格式不支持）")
                return

            # 应用旋转和缩放
            self._apply_image_transform()

        except Exception as e:
            self.image_label.setText(f"图片加载失败：{str(e)}")
            self.current_pixmap = None

    def _apply_image_transform(self):
        """应用旋转和缩放变换到图像"""
        if self.current_pixmap is None:
            return

        # 1. 应用旋转
        transform = QTransform()
        transform.rotate(self.image_rotation)
        rotated_pixmap = self.current_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # 2. 应用缩放
        scaled_pixmap = rotated_pixmap.scaled(
            int(rotated_pixmap.width() * self.image_scale),
            int(rotated_pixmap.height() * self.image_scale),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # 更新显示
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setFixedSize(scaled_pixmap.size())

        # 更新状态显示
        self.status_label.setText(f"缩放：{int(self.image_scale * 100)}% | 旋转：{self.image_rotation}°")

    def _fit_image_to_window(self):
        """图像适应窗口显示"""
        if self.current_pixmap is None:
            return

        # 重置缩放，保留旋转
        self.image_scale = 1.0
        transform = QTransform()
        transform.rotate(self.image_rotation)
        rotated_pixmap = self.current_pixmap.transformed(transform)

        # 适应窗口大小
        scaled_pixmap = rotated_pixmap.scaled(
            self.image_label.parent().size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # 更新显示
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setFixedSize(scaled_pixmap.size())

        # 计算实际缩放比例
        self.image_scale = scaled_pixmap.width() / rotated_pixmap.width()
        self.status_label.setText(f"缩放：{int(self.image_scale * 100)}% | 旋转：{self.image_rotation}°")

    def _zoom_image(self, scale_factor):
        """缩放图像（累积缩放）"""
        if self.current_pixmap is None:
            return

        # 更新缩放比例（限制0.1-5倍）
        self.image_scale = max(0.1, min(self.image_scale * scale_factor, 5.0))
        self._apply_image_transform()

    def _reset_zoom(self):
        """重置缩放为100%"""
        self.image_scale = 1.0
        self._apply_image_transform()

    def _rotate_image(self, angle):
        """旋转图像（顺时针/逆时针）"""
        if self.current_pixmap is None:
            return

        # 更新旋转角度（0-360°循环）
        self.image_rotation = (self.image_rotation + angle) % 360
        self._apply_image_transform()

    def _reset_rotate(self):
        """重置旋转为0°"""
        self.image_rotation = 0
        self._apply_image_transform()

    def _prev_item(self):
        """上一条数据"""
        if self.current_index > 0:
            self.current_index -= 1
            self.data_list.setCurrentRow(self.current_index)

    def _next_item(self):
        """下一条数据"""
        if self.current_index < len(self.ocr_data_list) - 1:
            self.current_index += 1
            self.data_list.setCurrentRow(self.current_index)

    def on_word_edit(self):
        """编辑识别结果时更新数据"""
        if self.current_index < 0 or self.current_index >= len(self.ocr_data_list):
            return

        new_word = self.word_edit.toPlainText().strip()
        current_data = self.ocr_data_list[self.current_index]
        response = current_data.get("response", {})
        words_result = response.get("words_result", [])

        # 兼容列表格式
        if words_result and isinstance(words_result, list):
            if not words_result:
                words_result.append({"words": new_word, "location": {"width": 0, "height": 0, "top": 0, "left": 0}})
            else:
                words_result[0]["words"] = new_word
            current_data["response"]["words_result"] = words_result
        else:
            # 兼容字典格式
            word_result = response.get("words_result", {})
            if isinstance(word_result, dict):
                words_result["number"] = new_word


        # 同步更新原始JSON
        raw_data = json.dumps(current_data, ensure_ascii=False, indent=2)
        self.raw_data_edit.setText(raw_data)

    def save_modified_data(self):
        """另存为新文件"""
        if not self.ocr_data_list:
            QMessageBox.warning(self, "警告", "暂无数据可保存")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存修改后的结果", "", "Text Files (*.txt);;All Files (*.*)"
        )
        if not save_path:
            return

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                for data in self.ocr_data_list:
                    json_str = json.dumps(data, ensure_ascii=False)
                    f.write(json_str + "\n")

            QMessageBox.information(self, "保存成功", f"修改后的数据已保存至：\n{save_path}")

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件出错：{str(e)}")

    def overwrite_original_file(self):
        """覆盖原始TXT文件"""
        if not self.ocr_data_list or not self.original_file_path:
            QMessageBox.warning(self, "警告", "暂无数据或原始文件路径为空")
            return

        # 二次确认
        reply = QMessageBox.question(
            self, "确认覆盖",
            f"确定要覆盖原始文件吗？\n{self.original_file_path}\n\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with open(self.original_file_path, 'w', encoding='utf-8') as f:
                for data in self.ocr_data_list:
                    json_str = json.dumps(data, ensure_ascii=False)
                    f.write(json_str + "\n")

            QMessageBox.information(self, "覆盖成功", f"已成功覆盖原始文件：\n{self.original_file_path}")

        except Exception as e:
            QMessageBox.critical(self, "覆盖失败", f"覆盖原始文件出错：{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OCRResultEditor()
    window.show()
    sys.exit(app.exec())