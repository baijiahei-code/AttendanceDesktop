/**
 * 相关单位页（对应桌面版 `app/pages_units.py`）。
 *
 * 「单位表」是**全局设置**（与月份无关），本页只负责展示与转发动作：
 * 数据/写盘都在父级（Index.ets）里，通过 @Param / @Event 往返 ——
 * 与桌面版「页面只画 UI、`storage`/`main_window` 负责落盘」的分层一致。
 */
import { UNIT_ROLE_LABELS, UNIT_SELECTABLE_KEYS } from '../core/units';
import { UnitRow } from '../model/Snap';
import { UnitRowView } from './components';
import { BG_CARD, C_ACCENT, C_HINT, C_INPUT_BG, C_LABEL, C_LINE, C_SEL_BG, C_TEXT } from './theme';

@ComponentV2
export struct UnitsPage {
  @Param rows: UnitRow[] = [];
  /** 单位表自己的锁（与月份锁无关） */
  @Param locked: boolean = false;
  /** 状态提示（已保存 / 请先填写… / 读取失败…） */
  @Param stateText: string = '';
  /** 行 key 版本号：父级锁定/解锁瞬间 +1，强制重建所有行 */
  @Param rowsKey: number = 0;
  @Event onToggleLock: () => void = () => {
  };
  @Event onRename: (index: number, v: string) => void = (index: number, v: string) => {
  };
  @Event onCode: (index: number, v: string) => void = (index: number, v: string) => {
  };
  @Event onType: (index: number, k: string) => void = (index: number, k: string) => {
  };
  /** 行尾动作：'copy' 复制 / 'gsxt' 或 'credit' 去搜索 */
  @Event onAction: (row: UnitRow, site: string) => void = (row: UnitRow, site: string) => {
  };
  @Event onEmptyTerm: () => void = () => {
  };
  /** 「＋ 添加单位」选了某个类型（对应桌面版 _open_add_unit_menu） */
  @Event onAdd: (role: string) => void = (role: string) => {
  };
  @Event onDelete: (index: number) => void = (index: number) => {
  };

  build() {
    Column({ space: 10 }) {
      // ---------- 卡片头：标题 + 本页锁 ----------
      Row({ space: 8 }) {
        Text('单位登记表').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
        Blank()
        Button(this.locked ? '🔒 已锁定' : '🔓 已解锁')
          .type(ButtonType.Normal)
          .fontSize(11)
          .height(28)
          .padding({ left: 10, right: 10 })
          .backgroundColor(this.locked ? C_INPUT_BG : C_SEL_BG)
          .fontColor(this.locked ? C_LABEL : C_ACCENT)
          .border({ width: 1, color: this.locked ? C_LINE : '#C7D2FE' })
          .borderRadius(8)
          .onClick(() => this.onToggleLock())
      }
      .width('100%')

      // 状态单独一行：提示（如「请先填写…再去搜索」）较长，挤在标题行会被截断
      if (this.stateText.length > 0) {
        Text(this.stateText)
          .fontSize(11)
          .fontColor(this.stateText.startsWith('请先填写') ? '#B54708' : C_HINT)
          .width('100%')
      }

      Text('已按内置类型各列一行，空的直接填；同一类型可以有多家时点「＋ 添加单位」（例如先后 / 同时签过多份劳动合同）；列表里没有的类型选「其他相关单位」，具体是什么写在「单位名称」栏')
        .fontSize(11)
        .fontColor(C_HINT)
        .width('100%')

      if (this.locked) {
        Text('🔒  单位登记表已锁定 · 名称 / 编号不可修改，「🔍」仍可用')
          .fontSize(11)
          .fontColor('#B54708')
          .backgroundColor('#FEF4E6')
          .borderRadius(8)
          .padding({ left: 10, right: 10, top: 6, bottom: 6 })
          .width('100%')
      }

      // ---------- 表头 ----------
      Row({ space: 8 }) {
        Text('类型').fontSize(11).fontColor('#98A2B3').width(134)
        Text('单位名称').fontSize(11).fontColor('#98A2B3').layoutWeight(1)
        Text('编号').fontSize(11).fontColor('#98A2B3').layoutWeight(1)
        Text('').width(34)
        Text('').width(24)
      }
      .width('100%')
      .padding({ top: 2, bottom: 4 })
      .border({ width: { bottom: 1 }, color: C_LINE })

      // ---------- 数据行 ----------
      if (this.rows.length === 0) {
        Text('单位表是空的 —— 点下面「＋ 添加单位」选一个类型')
          .fontSize(11)
          .fontColor(C_HINT)
          .padding({ top: 16, bottom: 16 })
      } else {
        ForEach(this.rows, (u: UnitRow) => {
          UnitRowView({
            role: u.role,
            roleLabel: u.roleLabel,
            codeLabel: u.codeLabel,
            name: u.name,
            code: u.code,
            locked: this.locked,
            onRename: (v: string) => this.onRename(u.index, v),
            onCode: (v: string) => this.onCode(u.index, v),
            onType: (k: string) => this.onType(u.index, k),
            onAction: (s: string) => this.onAction(u, s),
            onEmptyTerm: () => this.onEmptyTerm(),
            onDelete: () => this.onDelete(u.index)
          })
        }, (u: UnitRow) => `${u.index}-${u.role}-${this.rowsKey}`)
      }

      // ---------- 添加单位 ----------
      Row({ space: 8 }) {
        Button('＋ 添加单位')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .padding({ left: 12, right: 12 })
          .backgroundColor(this.locked ? C_INPUT_BG : C_ACCENT)
          .fontColor(this.locked ? '#98A2B3' : '#FFFFFF')
          .borderRadius(8)
          .enabled(!this.locked)
          .bindMenu(this.addUnitMenu())
        Blank()
      }
      .width('100%')
    }
    .width('100%')
    .padding(16)
    .alignItems(HorizontalAlign.Start)
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }

  /** 「＋ 添加单位」菜单：11 个内置类型（与桌面版 pages_units._open_add_unit_menu 一致）。 */
  private addUnitMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    for (const k of UNIT_SELECTABLE_KEYS) {
      const lab: string | undefined = UNIT_ROLE_LABELS.get(k);
      const label: string = lab === undefined ? k : lab;
      out.push({
        value: label, action: () => {
          this.onAdd(k);
        }
      });
    }
    return out;
  }
}
