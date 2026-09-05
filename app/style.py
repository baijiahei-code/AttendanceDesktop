"""视觉：现代 SaaS 浅色 + 白底侧栏 + 靛紫→天青品牌渐变（设计令牌与网页原型一致）。

token 速查：
  品牌:   --brand #6366F1 / deep #4F46E5 / soft #EEF2FF / 渐变 #6366F1→#22D3EE
  中性:   bg #F6F7FB / card #FFFFFF / line #E6E8F0 / ink #101828 / ink2 #667085
  语义:   ok #12B76A / warn #F79009 / err #F04438
"""

STYLE = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #101828;
    outline: none;
}
QMainWindow, QWidget#root { background: #F6F7FB; }
QStackedWidget { background: #F6F7FB; }
/* 滚动区统一浅灰底（视口透出父背景），保证各页背景一致 */
QScrollArea { background: #F6F7FB; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QToolTip { background:#101828; color:#fff; border:none; padding:4px 8px; border-radius:6px; }

/* ---------- 浅色侧栏（白底） ---------- */
QFrame#sidebar { background: #FFFFFF; border: none; border-right: 1px solid #E6E8F0; }
QLabel#brand { color: #101828; font-size: 17px; font-weight: 800; letter-spacing: .5px; }
QLabel#brandSub { color: #667085; font-size: 11px; }
QLabel#sideSec { color: #98A2B3; font-size: 10.5px; letter-spacing: 2px; padding: 2px 6px; }
QPushButton#navBtn {
    color: #667085; text-align: left; border: none; border-radius: 10px;
    padding: 9px 12px; font-size: 13.5px; background: transparent; font-weight: 500;
    margin: 0 2px;
}
QPushButton#navBtn:hover { background: #F1F2F7; color: #101828; }
QPushButton#navBtn:checked {
    background: #EEF2FF; color: #4F46E5; font-weight: 700;
    border: 1px solid rgba(99,102,241,0.18);
}
QFrame#sideCard {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #101828, stop:1 #27304f);
    border: none; border-radius: 14px;
}
QLabel#sideMon { color: #E2E8F0; font-size: 13px; font-weight: 600; }
QLabel#sideData { color: #94A3B8; font-size: 10.5px; }
QPushButton#ghostInCard { background: rgba(255,255,255,.08); color: #E2E8F0; border-radius: 8px; border:none; padding: 5px 8px; font-size: 12px; }
QPushButton#ghostInCard:hover { background: rgba(255,255,255,.18); color: #FFFFFF; }

/* ---------- 顶栏 / 月份条 ---------- */
QFrame#header {
    background: rgba(255,255,255,0.86); border: none; border-bottom: 1px solid #E6E8F0;
    min-height: 60px;
}
QFrame#monthbar { background: transparent; border: none; }
QLabel#pageTitle { font-size: 21px; font-weight: 800; color: #0F172A; }
QLabel#pageSub { color: #667085; font-size: 12.5px; }
QLabel#statusOk { color: #087443; font-size: 12px; background: #E8F8F0; border-radius: 999px; padding: 4px 10px; font-weight: 600; }
QLabel#statusWarn { color: #B54708; font-size: 12px; background: #FEF4E6; border-radius: 999px; padding: 4px 10px; font-weight: 600; }
QLabel#statusErr { color: #C01048; font-size: 12px; background: #FEEEEE; border-radius: 999px; padding: 4px 10px; font-weight: 600; }

/* ---------- 按钮 ---------- */
QPushButton {
    background: #FFFFFF; border: 1px solid #E6E8F0; border-radius: 10px;
    padding: 6px 14px; color: #344054; font-size: 13px; min-height: 30px;
}
QPushButton:hover { background: #F8FAFC; border-color: #6366F1; color: #4F46E5; }
QPushButton:pressed { background: #EEF2FF; }
QPushButton:disabled { color: #98A2B3; background: #F3F4F6; border-color: #E9ECF2; }
QPushButton#primary {
    background: #6366F1; color: #FFFFFF; border: none; font-weight: 600;
}
QPushButton#primary:hover { background: #4F46E5; color: #FFFFFF; }
QPushButton#danger { background: #FFFFFF; color: #D92D20; border: 1px solid #FCD0CB; }
QPushButton#danger:hover { background: #FEF3F2; }
QPushButton#ghost { background: transparent; border: none; color: #667085; padding: 6px 8px; }
QPushButton#ghost:hover { background: #F1F2F7; color: #101828; border-radius: 9px; }
QPushButton#chip {
    border-radius: 999px; padding: 5px 12px; background: #FFFFFF;
    border: 1px solid #E6E8F0; color: #475467; min-height: 26px;
}
QPushButton#chip:hover { border-color: #6366F1; color: #4F46E5; }
QPushButton#chip:checked { background: #EEF2FF; border-color: #6366F1; color: #4F46E5; font-weight: 600; }

/* ---------- 输入控件 ---------- */
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background: #FFFFFF; border: 1px solid #E6E8F0; border-radius: 9px;
    padding: 5px 9px; selection-background-color: #DDD6FE; min-height: 30px;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #6366F1;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #475467; margin-right: 8px; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button { width: 14px; background: #F1F2F7; border: none; }
QCheckBox { background: transparent; color: #344054; font-size: 12px; font-weight: 600; spacing: 7px; }
QLabel { background: transparent; }
QLabel#fldLabel { color: #475467; font-size: 12px; }
QLabel#secHint { color: #667085; font-size: 12px; }

/* ---------- 卡片 ---------- */
QFrame#card {
    background: #FFFFFF; border: 1px solid #E6E8F0; border-radius: 16px;
}
QLabel#cardTitle { font-size: 14px; font-weight: 800; color: #0F172A; letter-spacing: 0.1px; }
QLabel#moneyBig { color: #4F46E5; font-size: 26px; font-weight: 800; }
QFrame#heroCard {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #5B6AE8, stop:.45 #6C6FF4, stop:1 #5EC7FF);
    border: none; border-radius: 16px;
    min-height: 128px;
}
QFrame#monthbar { background: transparent; border: none; }
QFrame#header { background: rgba(255,255,255,0.72); border-bottom: 1px solid #E6E8F0; }
QLabel#heroTitle { color: rgba(255,255,255,215); font-size: 12px; }
QLabel#heroValue { color: #FFFFFF; font-size: 24px; font-weight: 800; }
QFrame#statCard { background: #FFFFFF; border: 1px solid #E6E8F0; border-radius: 16px; }
QLabel#statTitle { color: #667085; font-size: 12px; }
QLabel#statValue { color: #0F172A; font-size: 20px; font-weight: 800; }

/* ---------- 工作台快捷入口 ---------- */
QFrame#quickCard { background: #FFFFFF; border: 1px solid #E6E8F0; border-radius: 16px; }
QFrame#quickCard[hover="true"] { background: #EEF2FF; border: 1px solid #C7D2FE; }
QLabel#quickTitle { color: #4F46E5; font-size: 15px; font-weight: 800; }
QLabel#quickDesc { color: #667085; font-size: 12px; }
QLabel#emptyTip {
    color: #B54708; background: #FEF4E6; border: 1px solid #FEDF89;
    border-radius: 10px; padding: 10px 12px;
}

/* ---------- 表格 ---------- */
QTableWidget {
    background: #FFFFFF; alternate-background-color: #F8FAFC;
    border: 1px solid #E6E8F0; border-radius: 12px; gridline-color: #F1F2F7;
    selection-background-color: #EEF2FF; selection-color: #4F46E5;
}
QTableWidget::item { padding: 4px; }
QHeaderView::section {
    background: #F8FAFC; color: #475467; font-weight: 700;
    border: none; border-bottom: 1px solid #E6E8F0; padding: 8px;
}
QTableCornerButton::section { background: #F8FAFC; border: none; }
QListWidget#historyList { background: transparent; border: none; }
QListWidget#historyList::item { color: #475467; border-radius: 9px; padding: 7px 10px; }
QListWidget#historyList::item:hover { background: #F1F2F7; color: #101828; }
QListWidget#historyList::item:selected { background: #EEF2FF; color: #4F46E5; font-weight: 600; }

/* ---------- 滚动条 ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #D0D5DD; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #98A2B3; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #D0D5DD; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ---------- 工作台向导（样式随页面内联 QSS，此处全局规则已无引用） ---------- */

/* ---------- 薪酬 ---------- */
QLabel#salaryStripVal { font-size: 19px; font-weight: 800; color: #0F172A; }
QLabel#piTotal { color: #4F46E5; font-weight: 800; font-size: 13px; }

/* ---------- 工资项列表（详细的可调样式）---------- */
/* 数据行（含 hover）：改圆角/底色/边框 → 这里改 */
QFrame#pirow {
    background: #FBFBFD; border: 1px solid #EEF0F6; border-radius: 10px;
}
QFrame#pirow:hover { background: #FFFFFF; border: 1px solid #C7D2FE; }
/* 列头：底部 1px 分隔线与列名样式 */
QFrame#piHeader {
    background: transparent; border: none;
    border-bottom: 1px solid #E6E8F0;
}
QLabel#piHdrCell {
    color: #98A2B3; font-size: 10.5px; font-weight: 700;
    letter-spacing: 0.5px; padding: 0; margin: 0;
}

/* 类型 chip —— 默认样式（在 PayItemRow 内用 config.TYPE_CHIP 重写为彩色） */
QPushButton#piChip {
    border-radius: 999px; padding: 4px 11px;
    background: #FFFFFF; border: 1px solid #E6E8F0; color: #475467;
    font-size: 11.5px; font-weight: 700;
    min-height: 22px; max-height: 26px;
}
QPushButton#piChip::menu-indicator { image: none; width: 0; }

/* 名称输入框：透明常态 → hover/focus 显边框 */
QLineEdit#piName { border: none; background: transparent; padding: 0 4px; }
QLineEdit#piName:hover {
    background: #FFFFFF; border: 1px solid #E6E8F0;
    border-radius: 8px; padding: 0 4px;
}
QLineEdit#piName:focus {
    background: #FFFFFF; border: 1px solid #6366F1;
    border-radius: 8px; padding: 0 4px;
}

/* 行内删除按钮 ✕：hover 变红 */
QPushButton#piDelete {
    background: transparent; border: none; color: #98A2B3;
    border-radius: 8px; font-size: 14px;
}
QPushButton#piDelete:hover { background: #FEE2E2; color: #B91C1C; }
QPushButton#piDelete:pressed { background: #FECACA; }

/* 自动个税 checkbox（绿色边框） */
QCheckBox#taxAuto {
    border: 1px solid #065F46; border-radius: 6px; padding: 4px 6px;
}

/* ---------- 报表文本 ---------- */
QTextBrowser { background: transparent; border: none; color: #0F172A; }
"""
