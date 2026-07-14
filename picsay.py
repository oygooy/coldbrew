# -*- coding: utf-8 -*-
"""
사진 설명 입력 도구 (PicSay) - v6
==============================================================
[v6 변경 사항]
- "설명 일괄 삭제"도 더 이상 즉시 저장하지 않음. 체크된 사진들의 설명 입력란만
  비워지고 "● 미저장" 상태로 표시되며, 실제 저장은 "전체 저장"을 눌러야 이루어짐.
- [버그 수정] "전체 저장"이 설명을 빈 값으로 "바꾼"(비운) 사진을 저장 대상에서
  빠뜨리던 문제 수정. 기존에는 입력란에 글자가 남아있는 사진만 저장 대상으로
  간주해서, 설명을 지운 사진은 "변경할 것이 없음" 알림과 함께 저장되지 않고
  넘어갔음. 이제는 마지막 저장 상태와 달라진(= 미저장 상태인) 모든 사진이
  저장 대상에 포함되며, 빈 설명으로 지우는 것도 정상적으로 파일에 반영됨.
==============================================================
[v5 변경 사항]
- "설명 일괄 변경" 버튼을 눌러도 더 이상 즉시 저장하지 않음.
  체크된 사진들의 설명 입력란에만 텍스트가 반영되고 "● 미저장" 상태로 표시됨.
  실제 파일 저장은 우상단의 "전체 저장" 버튼을 눌러야 이루어짐.
- "설명 일괄 삭제"는 기존과 동일하게 즉시 저장(파일에서도 삭제)됨.
==============================================================
[v4 변경 사항]
- 상단 툴바에 "전체 삭제" 버튼 추가 (목록에서 모든 사진을 한 번에 제거, 실행 전 확인 팝업 포함)
- 파일 자체는 삭제되지 않고 PicSay 목록에서만 제거됨
==============================================================
[v3 변경 사항]
- 각 사진 줄에 체크박스를 추가하고, 상단에 "전체 선택" 체크박스를 추가함.
- 체크된 사진들을 대상으로 한 번에 처리하는 두 버튼 추가:
    "설명 일괄 변경" : 입력한 텍스트로 선택된 사진들의 설명을 모두 동일하게 바꿈
    "설명 일괄 삭제" : 선택된 사진들의 설명을 모두 비우고 즉시 저장 (파일에서도 삭제됨)
- 둘 다 실행 전 확인 팝업을 띄워 실수로 인한 일괄 변경/삭제를 방지함.
==============================================================
[v2 변경 사항]
- 윈도우 탐색기 속성 > 자세히 > 설명 필드가 EXIF XPComment(40092)를 보여주는 경우가 많아,
  v1에서는 저장은 됐지만 탐색기 속성창에는 안 보이는 문제가 있었음.
- v2부터는 ImageDescription과 XPComment 두 태그에 동시에 기록하도록 수정.
- XPComment는 윈도우 규격상 UTF-16LE 인코딩 + null 종료 필요해서 별도 처리 추가.
==============================================================

하루에 찍은 여러 장의 사진을 한 화면에서 작은 썸네일 + 설명 입력란으로 죽 나열하고,
저장 버튼을 누르면 그 설명이 이미지 파일의 [속성 > 자세히 > 설명] 항목에 기록됨.

★ 외부 프로그램(exiftool 등) 설치가 전혀 필요 없음 ★
   - jpg/jpeg/tif/tiff : piexif 로 EXIF ImageDescription + XPComment 태그에 직접 기록
   - png               : Pillow 로 PNG 텍스트 청크(Description)에 직접 기록 (픽셀 무손실)
   - webp              : Pillow + piexif 로 EXIF 기록 (무손실/손실 자동 감지해서 동일하게 재저장)

사진 추가 방법 3가지:
  1) 리스트 영역에 파일을 드래그 앤 드롭
  2) "파일 선택" 버튼으로 여러 장 선택
  3) "폴더 선택" 버튼으로 폴더를 지정하면 그 안의 이미지 파일을 모두 자동으로 불러옴

설명 저장 방법:
  1) 각 사진 줄의 "저장" 버튼 -> 그 사진만 저장
  2) 상단의 "전체 저장" 버튼 -> 미저장/변경된 항목을 일괄 저장
  3) 체크박스로 사진을 선택 후 "설명 일괄 변경" / "설명 일괄 삭제"
     (둘 다 입력란에만 반영되며, 실제 저장은 "전체 저장"을 눌러야 이루어짐)

지원 형식: jpg, jpeg, png, tif, tiff, webp
"""

import os
import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QFileDialog, QFrame, QSizePolicy,
    QMessageBox, QToolButton, QSpacerItem, QCheckBox, QInputDialog
)

import piexif
from PIL import Image, PngImagePlugin

IMAGE_EXTS  = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
EXIF_EXTS   = {".jpg", ".jpeg", ".tif", ".tiff"}
PNG_EXTS    = {".png"}
WEBP_EXTS   = {".webp"}
THUMB_SIZE  = 96
XP_COMMENT_TAG = 40092   # 윈도우 전용 EXIF 태그: 탐색기 "설명" 필드에 표시됨


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------
def _detect_webp_lossless(filepath):
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        return b"VP8L" in data[:64] or b"VP8L" in data
    except Exception:
        return False


def _encode_xp(text):
    return text.encode("utf-16-le") + b"\x00\x00"


def _decode_xp(raw):
    if raw is None:
        return ""
    try:
        if isinstance(raw, (tuple, list)):
            raw = bytes(raw)
        return raw.rstrip(b"\x00").decode("utf-16-le", errors="ignore").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 설명 읽기 / 쓰기
# ---------------------------------------------------------------------------
def read_description(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext in EXIF_EXTS:
            d = piexif.load(filepath)
            xp = _decode_xp(d.get("0th", {}).get(XP_COMMENT_TAG))
            if xp:
                return xp
            raw = d.get("0th", {}).get(piexif.ImageIFD.ImageDescription, b"")
            return (raw if isinstance(raw, bytes) else str(raw).encode()).decode("utf-8", errors="ignore").rstrip("\x00").strip()

        elif ext in PNG_EXTS:
            img = Image.open(filepath)
            t = getattr(img, "text", {}) or {}
            return t.get("Description", "") or t.get("Comment", "")

        elif ext in WEBP_EXTS:
            img = Image.open(filepath)
            eb = img.info.get("exif")
            if not eb:
                return ""
            d = piexif.load(eb)
            xp = _decode_xp(d.get("0th", {}).get(XP_COMMENT_TAG))
            if xp:
                return xp
            raw = d.get("0th", {}).get(piexif.ImageIFD.ImageDescription, b"")
            return (raw if isinstance(raw, bytes) else str(raw).encode()).decode("utf-8", errors="ignore").rstrip("\x00").strip()
    except Exception:
        return ""
    return ""


def write_description(filepath, text):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext in EXIF_EXTS:
            try:
                d = piexif.load(filepath)
            except Exception:
                d = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            d.setdefault("0th", {})
            d["0th"][piexif.ImageIFD.ImageDescription] = text.encode("utf-8")
            d["0th"][XP_COMMENT_TAG] = _encode_xp(text)
            piexif.insert(piexif.dump(d), filepath)
            return True, ""

        elif ext in PNG_EXTS:
            img = Image.open(filepath)
            img.load()
            meta = PngImagePlugin.PngInfo()
            for k, v in (getattr(img, "text", {}) or {}).items():
                if k != "Description":
                    try:
                        meta.add_text(k, v)
                    except Exception:
                        pass
            meta.add_text("Description", text)
            kw = {"pnginfo": meta}
            if "icc_profile" in img.info:
                kw["icc_profile"] = img.info["icc_profile"]
            img.save(filepath, "PNG", **kw)
            return True, ""

        elif ext in WEBP_EXTS:
            img = Image.open(filepath)
            img.load()
            lossless = _detect_webp_lossless(filepath)
            eb = img.info.get("exif")
            try:
                d = piexif.load(eb) if eb else {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            except Exception:
                d = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            d.setdefault("0th", {})
            d["0th"][piexif.ImageIFD.ImageDescription] = text.encode("utf-8")
            d["0th"][XP_COMMENT_TAG] = _encode_xp(text)
            kw = {"exif": piexif.dump(d)}
            if lossless:
                kw["lossless"] = True
                kw["quality"] = 100
            else:
                kw["quality"] = img.info.get("quality", 90)
            img.save(filepath, "WEBP", **kw)
            return True, ""

        else:
            return False, f"지원하지 않는 형식: {ext}"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# 백그라운드 저장 워커
# ---------------------------------------------------------------------------
class SaveWorker(QThread):
    one_done = pyqtSignal(str, bool, str)
    all_done = pyqtSignal()

    def __init__(self, items):
        super().__init__()
        self.items = items  # list of (filepath, text)

    def run(self):
        for filepath, text in self.items:
            ok, err = write_description(filepath, text)
            self.one_done.emit(filepath, ok, err)
        self.all_done.emit()


# ---------------------------------------------------------------------------
# 사진 한 줄 위젯
# ---------------------------------------------------------------------------
class PhotoRow(QFrame):
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.saved_text = None
        self._remove_cb = None
        self._check_cb  = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("photoRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 체크박스
        self.checkbox = QCheckBox()
        self.checkbox.setToolTip("선택 (일괄 변경/삭제 대상)")
        self.checkbox.stateChanged.connect(self._on_check)
        layout.addWidget(self.checkbox)

        # 썸네일
        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet("background-color:#2b2b2b; border-radius:6px;")
        self._load_thumb()
        layout.addWidget(self.thumb)

        # 파일명 + 설명입력
        mid = QVBoxLayout()
        mid.setSpacing(4)
        name = QLabel(os.path.basename(filepath))
        name.setStyleSheet("font-weight:600; color:#ddd;")
        name.setToolTip(filepath)
        mid.addWidget(name)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("이 사진에 대한 설명을 입력하세요...")
        existing = read_description(filepath)
        if existing:
            self.desc_edit.setText(existing)
            self.saved_text = existing
        self.desc_edit.textChanged.connect(lambda _: self._update_status())
        mid.addWidget(self.desc_edit)
        layout.addLayout(mid, stretch=1)

        # 상태 라벨
        self.status_lbl = QLabel("")
        self.status_lbl.setFixedWidth(70)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_lbl)
        self._update_status()

        # 개별 저장 버튼
        self.save_btn = QPushButton("저장")
        self.save_btn.setFixedWidth(60)
        self.save_btn.clicked.connect(self._on_save)
        layout.addWidget(self.save_btn)

        # 목록 제거 버튼
        rm = QToolButton()
        rm.setText("✕")
        rm.setToolTip("목록에서 제거 (파일은 삭제되지 않음)")
        rm.clicked.connect(self._on_remove)
        layout.addWidget(rm)

    # ---- 썸네일 ----
    def _load_thumb(self):
        pix = QPixmap(self.filepath)
        if pix.isNull():
            self.thumb.setText("미리보기\n없음")
            self.thumb.setStyleSheet("background-color:#2b2b2b; border-radius:6px; color:#888; font-size:10px;")
        else:
            self.thumb.setPixmap(pix.scaled(THUMB_SIZE, THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    # ---- 상태 ----
    def is_dirty(self):
        return self.desc_edit.text() != (self.saved_text or "")

    def has_text(self):
        return bool(self.desc_edit.text().strip())

    def _update_status(self):
        if not self.has_text():
            self.status_lbl.setText("")
            self.status_lbl.setStyleSheet("color:#888;")
        elif self.is_dirty():
            self.status_lbl.setText("● 미저장")
            self.status_lbl.setStyleSheet("color:#e0a030;")
        else:
            self.status_lbl.setText("✓ 저장됨")
            self.status_lbl.setStyleSheet("color:#4caf50;")

    def mark_saved(self, text):
        self.saved_text = text
        self._update_status()

    def mark_failed(self):
        self.status_lbl.setText("⚠ 실패")
        self.status_lbl.setStyleSheet("color:#e05252;")

    # ---- 개별 저장 ----
    def _on_save(self):
        text = self.desc_edit.text()
        self.save_btn.setEnabled(False)
        self.status_lbl.setText("저장중...")
        self.status_lbl.setStyleSheet("color:#888;")
        QApplication.processEvents()
        ok, err = write_description(self.filepath, text)
        self.save_btn.setEnabled(True)
        if ok:
            self.mark_saved(text)
        else:
            self.mark_failed()
            QMessageBox.warning(self, "저장 실패", f"{os.path.basename(self.filepath)}\n\n{err}")

    # ---- 제거 ----
    def set_remove_callback(self, cb):
        self._remove_cb = cb

    def _on_remove(self):
        if self._remove_cb:
            self._remove_cb(self)

    # ---- 체크박스 ----
    def set_check_callback(self, cb):
        self._check_cb = cb

    def _on_check(self, _state):
        if self._check_cb:
            self._check_cb(self)

    def is_checked(self):
        return self.checkbox.isChecked()

    def set_checked(self, checked, silent=False):
        if silent:
            self.checkbox.blockSignals(True)
            self.checkbox.setChecked(checked)
            self.checkbox.blockSignals(False)
        else:
            self.checkbox.setChecked(checked)


# ---------------------------------------------------------------------------
# 메인 윈도우
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("사진 설명 입력 도구 - PicSay")
        self.resize(860, 620)
        self.setAcceptDrops(True)
        self.rows = []
        self.rows_by_path = {}
        self._build_ui()

    # ---- UI 구성 ----
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        # ── 1행: 파일/폴더 선택 + 전체 저장
        row1 = QHBoxLayout()
        btn_file = QPushButton("파일 선택")
        btn_file.clicked.connect(self.on_add_files)
        row1.addWidget(btn_file)
        btn_folder = QPushButton("폴더 선택")
        btn_folder.clicked.connect(self.on_add_folder)
        row1.addWidget(btn_folder)
        row1.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding))
        self.clear_all_btn = QPushButton("목록에서 제거")
        self.clear_all_btn.setToolTip("목록의 모든 사진을 제거합니다 (파일 자체는 삭제되지 않음)")
        self.clear_all_btn.setStyleSheet("QPushButton{color:#e05252;}")
        self.clear_all_btn.clicked.connect(self.on_clear_all)
        row1.addWidget(self.clear_all_btn)
        self.save_all_btn = QPushButton("전체 저장")
        self.save_all_btn.setStyleSheet(
            "QPushButton{background:#3a7bd5;color:white;padding:6px 16px;font-weight:600;border-radius:4px;}"
            "QPushButton:disabled{background:#555;color:#999;}"
        )
        self.save_all_btn.clicked.connect(self.on_save_all)
        row1.addWidget(self.save_all_btn)
        outer.addLayout(row1)

        # ── 2행: 전체선택 체크박스 + 일괄 변경/삭제
        row2 = QHBoxLayout()
        self.select_all_cb = QCheckBox("전체 선택")
        self.select_all_cb.stateChanged.connect(self.on_select_all)
        row2.addWidget(self.select_all_cb)
        row2.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding))
        self.bulk_edit_btn = QPushButton("설명 일괄 변경")
        self.bulk_edit_btn.setToolTip("체크된 사진들의 설명 입력란만 바꿉니다. 저장하려면 '전체 저장'을 눌러주세요.")
        self.bulk_edit_btn.clicked.connect(self.on_bulk_edit)
        row2.addWidget(self.bulk_edit_btn)
        self.bulk_del_btn = QPushButton("설명 일괄 삭제")
        self.bulk_del_btn.setStyleSheet("QPushButton{color:#e05252;}")
        self.bulk_del_btn.clicked.connect(self.on_bulk_delete)
        row2.addWidget(self.bulk_del_btn)
        outer.addLayout(row2)

        # ── 드롭 안내
        self.hint = QLabel("여기에 사진을 드래그 앤 드롭하세요  (또는 위의 버튼 사용)")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet("color:#777;padding:30px;border:2px dashed #444;border-radius:8px;font-size:13px;")
        outer.addWidget(self.hint)

        # ── 스크롤 영역
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(6)
        self.scroll_layout.addStretch(1)
        self.scroll.setWidget(self.scroll_content)
        outer.addWidget(self.scroll, stretch=1)

        # ── 하단 상태
        self.bottom_lbl = QLabel("0장의 사진")
        self.bottom_lbl.setStyleSheet("color:#888;font-size:11px;")
        outer.addWidget(self.bottom_lbl)

        self.setStyleSheet("""
            QMainWindow,QWidget{background:#1e1e1e;color:#ddd;}
            #photoRow{background:#262626;border-radius:8px;border:1px solid #333;}
            QLineEdit{background:#2f2f2f;border:1px solid #444;border-radius:4px;padding:6px;color:#eee;}
            QPushButton{background:#3a3a3a;border:1px solid #4a4a4a;border-radius:4px;padding:6px 10px;color:#eee;}
            QPushButton:hover{background:#454545;}
            QToolButton{background:transparent;border:none;color:#999;font-size:14px;}
            QToolButton:hover{color:#e05252;}
            QScrollArea{border:none;}
            QCheckBox{spacing:6px;}
            QCheckBox::indicator{width:16px;height:16px;}
        """)

    # ---- 드래그앤드롭 ----
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = []
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isdir(p):
                paths.extend(self._imgs_in(p))
            elif self._is_img(p):
                paths.append(p)
        self._add_photos(paths)

    # ---- 파일/폴더 선택 ----
    def on_add_files(self):
        exts = " ".join(f"*{e}" for e in IMAGE_EXTS)
        files, _ = QFileDialog.getOpenFileNames(self, "사진 선택", "", f"이미지 파일 ({exts});;모든 파일 (*.*)")
        if files:
            self._add_photos(files)

    def on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            paths = self._imgs_in(folder)
            if not paths:
                QMessageBox.information(self, "알림", "선택한 폴더에 이미지 파일이 없습니다.")
                return
            self._add_photos(paths)

    @staticmethod
    def _is_img(p):
        return os.path.splitext(p)[1].lower() in IMAGE_EXTS

    @classmethod
    def _imgs_in(cls, folder):
        result = []
        try:
            for name in sorted(os.listdir(folder)):
                full = os.path.join(folder, name)
                if os.path.isfile(full) and cls._is_img(full):
                    result.append(full)
        except Exception:
            pass
        return result

    # ---- 사진 추가 ----
    def _add_photos(self, paths):
        added = 0
        for p in paths:
            p = os.path.normpath(p)
            if not self._is_img(p) or p in self.rows_by_path:
                continue
            row = PhotoRow(p)
            row.set_remove_callback(self._remove_row)
            row.set_check_callback(self._on_row_checked)
            self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, row)
            self.rows.append(row)
            self.rows_by_path[p] = row
            added += 1
        if added:
            self.hint.setVisible(False)
        self._update_bottom()

    def _remove_row(self, row):
        self.scroll_layout.removeWidget(row)
        row.setParent(None)
        self.rows = [r for r in self.rows if r is not row]
        self.rows_by_path.pop(row.filepath, None)
        self._update_bottom()
        self._sync_select_all()
        if not self.rows:
            self.hint.setVisible(True)

    def _update_bottom(self):
        total = len(self.rows)
        dirty = sum(1 for r in self.rows if r.is_dirty())
        self.bottom_lbl.setText(f"{total}장의 사진  ·  미저장 {dirty}건")

    # ---- 전체 선택 ----
    def _on_row_checked(self, _row):
        self._sync_select_all()

    def _sync_select_all(self):
        if not self.rows:
            return
        all_checked = all(r.is_checked() for r in self.rows)
        self.select_all_cb.blockSignals(True)
        self.select_all_cb.setChecked(all_checked)
        self.select_all_cb.blockSignals(False)

    def on_select_all(self, _state):
        checked = self.select_all_cb.isChecked()
        for r in self.rows:
            r.set_checked(checked, silent=True)

    def on_clear_all(self):
        if not self.rows:
            QMessageBox.information(self, "알림", "목록이 이미 비어있습니다.")
            return
        if QMessageBox.question(
            self, "전체 삭제 확인",
            f"목록의 사진 {len(self.rows)}장을 모두 제거하시겠습니까?\n"
            "(파일 자체는 삭제되지 않습니다)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        for row in list(self.rows):
            self.scroll_layout.removeWidget(row)
            row.setParent(None)
        self.rows.clear()
        self.rows_by_path.clear()
        self.select_all_cb.blockSignals(True)
        self.select_all_cb.setChecked(False)
        self.select_all_cb.blockSignals(False)
        self.hint.setVisible(True)
        self._update_bottom()

    def _checked_rows(self):
        return [r for r in self.rows if r.is_checked()]

    # ---- 설명 일괄 변경 (v5: 즉시 저장하지 않고 입력란에만 반영) ----
    def on_bulk_edit(self):
        targets = self._checked_rows()
        if not targets:
            QMessageBox.information(self, "알림", "체크박스로 선택된 사진이 없습니다.")
            return
        text, ok = QInputDialog.getText(
            self, "설명 일괄 변경",
            f"체크된 {len(targets)}장의 설명을 아래 텍스트로 한꺼번에 바꿉니다.\n"
            "(입력란에만 반영되며, 저장은 되지 않습니다. 저장하려면 '전체 저장'을 눌러주세요.)\n새 설명:"
        )
        if not ok:
            return
        if QMessageBox.question(
            self, "일괄 변경 확인",
            f"체크된 {len(targets)}장의 설명을 모두\n\n\"{text}\"\n\n으로 변경하시겠습니까?\n"
            "(파일에는 저장되지 않으며, '전체 저장'을 눌러야 저장됩니다)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        for r in targets:
            r.desc_edit.setText(text)
        # 저장은 하지 않음 - textChanged 시그널로 상태 라벨(● 미저장)이 자동 갱신됨
        self._update_bottom()

    # ---- 설명 일괄 삭제 (v6: 즉시 저장하지 않고 입력란만 비움) ----
    def on_bulk_delete(self):
        targets = self._checked_rows()
        if not targets:
            QMessageBox.information(self, "알림", "체크박스로 선택된 사진이 없습니다.")
            return
        if QMessageBox.question(
            self, "일괄 삭제 확인",
            f"체크된 {len(targets)}장의 설명을 모두 비우시겠습니까?\n"
            "(입력란만 비워지며, 저장은 되지 않습니다. 저장하려면 '전체 저장'을 눌러주세요.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        for r in targets:
            r.desc_edit.setText("")
        # 저장은 하지 않음 - textChanged 시그널로 상태 라벨(● 미저장)이 자동 갱신됨
        self._update_bottom()

    # ---- 전체 저장 ----
    def on_save_all(self):
        # is_dirty() 만으로 대상을 판단해야, 설명을 비운(빈 문자열로 바꾼) 사진도
        # "변경 사항 없음"으로 잘못 제외되지 않고 저장 대상에 포함된다.
        targets = [r for r in self.rows if r.is_dirty()]
        if not targets:
            QMessageBox.information(self, "알림", "저장할 변경 사항이 없습니다.")
            return
        self.save_all_btn.setEnabled(False)
        self.save_all_btn.setText(f"저장 중... (0/{len(targets)})")
        for r in targets:
            r.status_lbl.setText("대기중")
            r.status_lbl.setStyleSheet("color:#888;")
        self._save_total = len(targets)
        self._save_done  = 0
        self.worker = SaveWorker([(r.filepath, r.desc_edit.text()) for r in targets])
        self.worker.one_done.connect(self._on_save_one)
        self.worker.all_done.connect(self._on_save_done)
        self.worker.start()

    def _on_save_one(self, filepath, ok, err):
        self._save_done += 1
        self.save_all_btn.setText(f"저장 중... ({self._save_done}/{self._save_total})")
        row = self.rows_by_path.get(filepath)
        if row:
            if ok:
                row.mark_saved(row.desc_edit.text())
            else:
                row.mark_failed()
        self._update_bottom()

    def _on_save_done(self):
        self.save_all_btn.setEnabled(True)
        self.save_all_btn.setText("전체 저장")
        self._update_bottom()
        QMessageBox.information(self, "완료", f"{self._save_total}건 저장을 완료했습니다.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PicSay")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()