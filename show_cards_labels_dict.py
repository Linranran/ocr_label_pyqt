import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit, QListWidget,
    QListWidgetItem, QScrollArea, QLineEdit, QMessageBox, QGroupBox,
    QGridLayout
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt


class OCRResultEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR识别结果解析编辑器")
        self.setGeometry(100, 100, 1400, 900)

        # 初始化数据
        self.ocr_data_list = []
        self.current_index = -1
        self.edit_widgets = {}

        # 创建主界面
        self._init_ui()

        # 监听列表选中变化
        self.data_list.currentItemChanged.connect(self.on_current_item_changed)

    def _init_ui(self):
        # 主布局（图像左，文件列表右）
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ========== 左侧：图像预览区 ==========
        left_group = QGroupBox("图像预览区")
        left_layout = QVBoxLayout(left_group)

        self.image_label = QLabel("请加载TXT文件后选择图像")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #cccccc; background-color: #f5f5f5;")
        self.image_label.setMinimumSize(700, 700)

        # 图像缩放按钮
        zoom_layout = QHBoxLayout()
        self.zoom_in_btn = QPushButton("放大 (+)")
        self.zoom_out_btn = QPushButton("缩小 (-)")
        self.fit_window_btn = QPushButton("适应窗口")
        self.zoom_in_btn.clicked.connect(lambda: self._zoom_image(1.1))
        self.zoom_out_btn.clicked.connect(lambda: self._zoom_image(0.9))
        self.fit_window_btn.clicked.connect(self._fit_image_to_window)
        zoom_layout.addWidget(self.zoom_in_btn)
        zoom_layout.addWidget(self.zoom_out_btn)
        zoom_layout.addWidget(self.fit_window_btn)

        # 图像滚动区
        image_scroll = QScrollArea()
        image_scroll.setWidget(self.image_label)
        image_scroll.setWidgetResizable(True)

        left_layout.addWidget(image_scroll)
        left_layout.addLayout(zoom_layout)
        main_layout.addWidget(left_group, stretch=2)

        # ========== 右侧：数据控制区 ==========
        right_group = QGroupBox("数据控制区")
        right_layout = QVBoxLayout(right_group)
        right_layout.setSpacing(8)

        # 功能按钮
        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("加载OCR结果TXT文件")
        self.save_btn = QPushButton("保存修改结果")
        self.load_btn.clicked.connect(self.load_ocr_file)
        self.save_btn.clicked.connect(self.save_modified_data)
        self.save_btn.setEnabled(False)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.save_btn)
        right_layout.addLayout(btn_layout)

        # 文件列表
        list_label = QLabel("文件列表")
        list_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        right_layout.addWidget(list_label)

        self.data_list = QListWidget()
        self.data_list.setFont(QFont("Arial", 10))
        self.data_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.data_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.data_list.setMinimumHeight(150)
        right_layout.addWidget(self.data_list)

        # 识别结果编辑区（左对齐+长文本支持）
        edit_group = QGroupBox("识别结果编辑（word_result字典）")
        edit_scroll = QScrollArea()
        edit_scroll.setWidgetResizable(True)
        edit_widget = QWidget()
        self.edit_layout = QGridLayout(edit_widget)
        self.edit_layout.setSpacing(6)
        self.edit_layout.setContentsMargins(10, 10, 10, 10)
        # 强制左对齐
        self.edit_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        # 列宽：key列固定，value列占满剩余空间
        self.edit_layout.setColumnStretch(0, 1)
        self.edit_layout.setColumnStretch(1, 5)

        edit_scroll.setWidget(edit_widget)
        edit_scroll.setMinimumHeight(300)
        right_layout.addWidget(edit_group)
        right_layout.addWidget(edit_scroll)

        # 原始JSON展示区（左对齐+长文本）
        raw_label = QLabel("原始JSON数据：")
        raw_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        right_layout.addWidget(raw_label)

        self.raw_data_edit = QTextEdit()
        self.raw_data_edit.setReadOnly(True)
        self.raw_data_edit.setFont(QFont("Consolas", 9))
        self.raw_data_edit.setMinimumHeight(200)
        # 强制左对齐，支持长文本换行
        self.raw_data_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.raw_data_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
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

        main_layout.addWidget(right_group, stretch=1)

    def clear_edit_layout(self):
        """清空编辑布局"""
        for key in list(self.edit_widgets.keys()):
            self.edit_widgets[key].deleteLater()
        self.edit_widgets.clear()

        while self.edit_layout.count():
            item = self.edit_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def load_ocr_file(self):
        """加载解析TXT文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择OCR结果文件", "", "Text Files (*.txt);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            self.ocr_data_list.clear()
            self.data_list.clear()
            self.current_index = -1
            self.clear_edit_layout()

            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        self.ocr_data_list.append(data)

                        img_name = os.path.basename(data.get("img_path", f"未知文件_{line_num}"))
                        item = QListWidgetItem(img_name)
                        item.setData(Qt.ItemDataRole.UserRole, line_num - 1)
                        self.data_list.addItem(item)

                    except json.JSONDecodeError as e:
                        QMessageBox.warning(self, "解析错误", f"第{line_num}行JSON解析失败：{str(e)}")

            if self.ocr_data_list:
                QMessageBox.information(self, "加载成功", f"共解析到 {len(self.ocr_data_list)} 条记录")
                self.save_btn.setEnabled(True)
                if self.data_list.count() > 0:
                    self.data_list.setCurrentRow(0)
            else:
                QMessageBox.warning(self, "警告", "未解析到有效数据")

        except Exception as e:
            QMessageBox.critical(self, "文件加载失败", f"加载文件出错：{str(e)}")

    def on_current_item_changed(self, current_item, previous_item):
        """选中项变化时更新界面"""
        self.clear_edit_layout()

        if not current_item:
            self.current_index = -1
            self.image_label.setText("请选择文件列表中的项")
            self.raw_data_edit.clear()
            return

        self.current_index = current_item.data(Qt.ItemDataRole.UserRole)
        if self.current_index < 0 or self.current_index >= len(self.ocr_data_list):
            return

        current_data = self.ocr_data_list[self.current_index]

        # 展示图片
        img_path = current_data.get("img_path", "")
        self._display_image(img_path)

        # 展示word_result字典（左对齐+长文本支持）
        response = current_data.get("response", {})
        word_result = response.get("word_result", {})

        row = 0
        for key in sorted(word_result.keys()):
            # 获取word值
            value_obj = word_result[key]
            if isinstance(value_obj, dict):
                word_value = value_obj.get("word", "")
            else:
                word_value = str(value_obj)

            # Key标签（右对齐，便于视觉对齐）
            key_label = QLabel(f"{key}：")
            key_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            key_label.setMinimumWidth(120)  # 固定key列宽度

            # Word编辑框（强制左对齐，支持长文本）
            if len(word_value) > 50 or "\n" in word_value:
                # 长文本使用QTextEdit，支持换行和滚动
                edit_box = QTextEdit()
                edit_box.setText(word_value)
                edit_box.setMinimumHeight(80)
                # 强制左对齐
                edit_box.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                # 自动换行
                edit_box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
                edit_box.textChanged.connect(self.on_long_text_edit)
            else:
                # 短文本使用QLineEdit
                edit_box = QLineEdit()
                edit_box.setText(word_value)
                # 强制左对齐
                edit_box.setAlignment(Qt.AlignmentFlag.AlignLeft)
                edit_box.textChanged.connect(self.on_short_text_edit)

            # 绑定字段名
            edit_box.setProperty("field_key", key)
            # 设置编辑框样式，确保左对齐无偏移
            edit_box.setStyleSheet("padding-left: 5px;")

            # 添加到布局
            self.edit_layout.addWidget(key_label, row, 0)
            self.edit_layout.addWidget(edit_box, row, 1)
            self.edit_widgets[key] = edit_box

            row += 1

        # 展示原始JSON（左对齐+自动换行）
        raw_data = json.dumps(current_data, ensure_ascii=False, indent=2)
        self.raw_data_edit.setText(raw_data)

    def _display_image(self, img_path):
        """展示图片"""
        if not os.path.exists(img_path):
            self.image_label.setText(f"图片不存在：\n{img_path}")
            return

        try:
            pixmap = QPixmap(img_path)
            if pixmap.isNull():
                self.image_label.setText("无法加载图片（格式不支持）")
                return

            self._fit_image_to_window(pixmap)

        except Exception as e:
            self.image_label.setText(f"图片加载失败：{str(e)}")

    def _fit_image_to_window(self, pixmap=None):
        """适应窗口显示图片"""
        if not pixmap:
            pixmap = self.image_label.pixmap()
            if not pixmap:
                return
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def _zoom_image(self, scale):
        """缩放图片"""
        pixmap = self.image_label.pixmap()
        if not pixmap:
            return
        new_size = pixmap.size() * scale
        scaled_pixmap = pixmap.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def _prev_item(self):
        """上一条"""
        if self.current_index > 0:
            self.current_index -= 1
            self.data_list.setCurrentRow(self.current_index)

    def _next_item(self):
        """下一条"""
        if self.current_index < len(self.ocr_data_list) - 1:
            self.current_index += 1
            self.data_list.setCurrentRow(self.current_index)

    def on_short_text_edit(self):
        """短文本编辑更新"""
        self._update_word_result(self.sender())

    def on_long_text_edit(self):
        """长文本编辑更新"""
        edit_box = self.sender()
        field_key = edit_box.property("field_key")
        new_word = edit_box.toPlainText().strip()
        self._update_word_result(edit_box, new_word)

    def _update_word_result(self, edit_box, new_word=None):
        """统一更新word_result数据"""
        if self.current_index < 0 or self.current_index >= len(self.ocr_data_list):
            return

        field_key = edit_box.property("field_key")
        if not field_key:
            return

        # 获取新值（兼容QLineEdit/QTextEdit）
        if new_word is None:
            new_word = edit_box.text().strip()

        # 更新数据
        current_data = self.ocr_data_list[self.current_index]
        response = current_data.get("response", {})
        word_result = response.get("word_result", {})

        if field_key in word_result:
            if isinstance(word_result[field_key], dict):
                word_result[field_key]["word"] = new_word
            else:
                word_result[field_key] = new_word

        # 同步更新原始JSON展示
        raw_data = json.dumps(current_data, ensure_ascii=False, indent=2)
        self.raw_data_edit.setText(raw_data)

    def save_modified_data(self):
        """保存修改后的数据"""
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OCRResultEditor()
    window.show()
    sys.exit(app.exec())