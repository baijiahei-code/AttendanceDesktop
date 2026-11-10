/**
 * 可复用的 ArkUI 组件（状态管理 V2：@Param 按引用同步）。
 *
 * ⚠ 两条纪律（踩过两次，见 docs/porting-plan.md 第七节）：
 * 1. 会变的值走 @Param 组件，不要通过 @Builder 参数传；
 * 2. 内部别用 layoutWeight：父容器只认直接子组件，调用处再 .layoutWeight(1)。
 */
import { UNIT_ROLE_LABELS, UNIT_SELECTABLE_KEYS } from '../core/units';
import { BG_CARD, C_ACCENT, C_BAD, C_HINT, C_SUB, C_TEXT } from './theme';

@ComponentV2
export struct Chip {
  @Param label: string = '';
  @Param active: boolean = false;
  @Param disabled: boolean = false;
  @Event onTap: () => void = () => {
  };

  build() {
    Text(this.label)
      .fontSize(12)
      .enabled(!this.disabled)
      .opacity(this.disabled ? 0.45 : 1)
      .fontColor(this.active ? '#FFFFFF' : C_TEXT)
      .backgroundColor(this.active ? C_ACCENT : '#EEF0F6')
      .padding({ left: 9, right: 9, top: 5, bottom: 5 })
      .borderRadius(6)
      .onClick(() => this.onTap())
  }
}

@ComponentV2
export struct StripItem {
  @Param title: string = '';
  @Param value: string = '';
  @Param accent: string = C_TEXT;

  build() {
    Row({ space: 8 }) {
      Text(this.title).fontSize(12).fontColor(C_SUB)
      Text(`¥ ${this.value}`).fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.accent)
    }
    .width('100%')
  }
}

@ComponentV2
export struct MetaItem {
  @Param title: string = '';
  @Param value: string = '';

  build() {
    Row({ space: 6 }) {
      Text(this.title).fontSize(12).fontColor(C_SUB)
      Text(this.value).fontSize(14).fontWeight(FontWeight.Medium).fontColor(C_TEXT)
    }
  }
}

@ComponentV2
export struct StatCard {
  @Param title: string = '';
  @Param value: string = '';
  @Param sub: string = '';
  @Param accent: string = C_TEXT;

  build() {
    Column({ space: 6 }) {
      Text(this.title).fontSize(12).fontColor(C_SUB)
      Text(this.value).fontSize(24).fontWeight(FontWeight.Bold).fontColor(this.accent)
      Text(this.sub).fontSize(11).fontColor(C_HINT)
    }
    .alignItems(HorizontalAlign.Start)
    .padding(16)
    .width('100%')
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }
}

@ComponentV2
export struct DayCell {
  @Param num: number = 0;
  @Param midText: string = '未填';
  @Param hoursText: string = '';
  @Param selected: boolean = false;
  @Param bg: string = '#FCFCFD';
  @Param fg: string = '#475569';
  /** 周末且未填 → 桌面版用粉红虚线提醒 */
  @Param weekendEmpty: boolean = false;
  /** 月份锁定 → 格子不可点（桌面版 `_set_calendar_locked` 逐个 setEnabled(False)） */
  @Param disabled: boolean = false;
  @Event onPick: () => void = () => {
  };

  build() {
    Column({ space: 1 }) {
      Text(this.num.toString())
        .fontSize(11)
        .fontWeight(FontWeight.Bold)
        .fontColor(this.fg)
      Text(this.midText)
        .fontSize(11)
        .fontColor(this.fg)
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
      Text(this.hoursText)
        .fontSize(11)
        .fontColor('#B45309')
        .maxLines(1)
    }
    .width('100%')
    .height(62)
    .justifyContent(FlexAlign.Center)
    .backgroundColor(this.bg)
    .borderRadius(9)
    .border({
      width: this.selected ? 2 : 1,
      color: this.selected ? '#6366F1' : (this.weekendEmpty ? '#FDA29B' : '#E6E8F0')
    })
    .clip(true)
    .enabled(!this.disabled)
    .onClick(() => this.onPick())
  }
}

@ComponentV2
export struct OtRow {
  @Param label: string = '';
  @Param hours: string = '0';
  @Param wage: string = '0.00';
  @Param badge: string = '';
  @Param badgeFg: string = '#15803D';
  @Param badgeBg: string = '#DCFCE7';
  @Event onEdit: (v: string) => void = (v: string) => {
  };

  build() {
    Row({ space: 6 }) {
      Text(this.label).fontSize(12).fontColor(C_SUB).width(76)
      if (this.badge.length > 0) {
        Text(this.badge)
          .fontSize(11)
          .fontWeight(FontWeight.Bold)
          .fontColor(this.badgeFg)
          .backgroundColor(this.badgeBg)
          .padding({ left: 5, right: 5, top: 1, bottom: 1 })
          .borderRadius(6)
      }
      TextInput({ text: this.hours })
        .type(InputType.NUMBER_DECIMAL)
        .height(30)
        .fontSize(12)
        .width(64)
        .onChange((v: string) => this.onEdit(v))
      Text('h').fontSize(11).fontColor(C_HINT).width(12)
      Text(`¥ ${this.wage}`).fontSize(12).fontColor(C_TEXT).layoutWeight(1).textAlign(TextAlign.End)
    }
    .width('100%')
  }
}

@ComponentV2
export struct RoRow {
  @Param label: string = '';
  @Param value: string = '0.00';

  build() {
    Row() {
      Text(this.label).fontSize(12).fontColor(C_SUB).layoutWeight(1)
      Text(`¥ ${this.value}`).fontSize(12).fontColor(C_SUB)
    }
    .width('100%')
  }
}

@ComponentV2
export struct AnnualRowView {
  @Param month: number = 1;
  @Param hasData: boolean = false;
  @Param isTotal: boolean = false;
  @Param workText: string = '—';
  @Param otText: string = '—';
  @Param leaveText: string = '—';
  @Param gross: string = '—';
  @Param deduct: string = '—';
  @Param leaveDeduct: string = '—';
  @Param takeHome: string = '—';
  @Param companyCost: string = '—';
  @Param legal: boolean = true;

  private filled(): boolean {
    return this.hasData || this.isTotal;
  }

  build() {
    Row() {
      Text(this.isTotal ? '合计' : `${this.month} 月`)
        .fontSize(11)
        .fontColor('#6B7280')
        .fontWeight(this.isTotal ? FontWeight.Bold : FontWeight.Normal)
        .width(60)
        .textAlign(TextAlign.Center)
      Text(this.filled() ? this.workText : '—')
        .fontSize(11).fontColor(this.filled() ? '#0F172A' : '#9CA3AF')
        .width(64).textAlign(TextAlign.End)
      Text(this.filled() ? this.otText : '—')
        .fontSize(11).fontColor(this.filled() ? '#0F172A' : '#9CA3AF')
        .width(72).textAlign(TextAlign.End)
      Text(this.filled() ? this.leaveText : '—')
        .fontSize(11).fontColor(this.filled() ? '#0F172A' : '#9CA3AF')
        .width(72).textAlign(TextAlign.End)
      Text(this.filled() ? this.gross : '—')
        .fontSize(11).fontColor(this.filled() ? '#0F172A' : '#9CA3AF')
        .width(108).textAlign(TextAlign.End)
      Text(this.filled() ? this.deduct : '—')
        .fontSize(11).fontColor(this.filled() ? '#0F172A' : '#9CA3AF')
        .width(108).textAlign(TextAlign.End)
      Text(this.filled() ? this.leaveDeduct : '—')
        .fontSize(11).fontColor(this.filled() ? '#0F172A' : '#9CA3AF')
        .width(108).textAlign(TextAlign.End)
      Text(this.filled() ? this.takeHome : '—')
        .fontSize(11)
        .fontWeight(FontWeight.Bold)
        .fontColor(this.filled() ? '#0F172A' : '#9CA3AF')
        .width(108).textAlign(TextAlign.End)
      Text(this.filled() ? this.companyCost : '—')
        .fontSize(11).fontColor(this.filled() ? '#0F172A' : '#9CA3AF')
        .width(108).textAlign(TextAlign.End)
      Text(this.isTotal ? '' : (this.hasData ? (this.legal ? '合规' : '违法') : '—'))
        .fontSize(11)
        .fontWeight(this.hasData ? FontWeight.Bold : FontWeight.Normal)
        .fontColor(this.hasData ? (this.legal ? '#0B7A3B' : '#C00000') : '#9CA3AF')
        .width(72)
        .textAlign(TextAlign.Center)
    }
    .width(900)
    .padding({ top: 5, bottom: 5 })
    .backgroundColor(this.isTotal ? '#F8FAFC' : '#FFFFFF')
    .border({ width: { bottom: 1 }, color: '#F3F4F6' })
  }
}

@ComponentV2
export struct UnitRowView {
  @Param role: string = 'contract';
  @Param roleLabel: string = '';
  @Param codeLabel: string = '';
  @Param name: string = '';
  @Param code: string = '';
  @Param locked: boolean = false;
  /** 输入框自己持有文本：不直接绑 @Param，否则父组件一重绘就会把用户刚敲的字冲掉。 */
  @Local nameText: string = '';
  @Local codeText: string = '';
  @Event onRename: (v: string) => void = (v: string) => {
  };
  @Event onCode: (v: string) => void = (v: string) => {
  };
  @Event onType: (k: string) => void = (k: string) => {
  };
  @Event onAction: (site: string) => void = (site: string) => {
  };
  /** 关键词为空时点「🔍」：父级负责提示「请先填写…再去搜索」。 */
  @Event onEmptyTerm: () => void = () => {
  };
  @Event onDelete: () => void = () => {
  };

  aboutToAppear(): void {
    this.nameText = this.name;
    this.codeText = this.code;
  }

  private roleOptions(): SelectOption[] {
    const out: SelectOption[] = [];
    for (const k of UNIT_SELECTABLE_KEYS) {
      const lab: string | undefined = UNIT_ROLE_LABELS.get(k);
      const label: string = lab === undefined ? k : lab;
      out.push({ value: label });
    }
    return out;
  }

  private roleIndex(): number {
    const i: number = UNIT_SELECTABLE_KEYS.indexOf(this.role);
    return i < 0 ? UNIT_SELECTABLE_KEYS.length - 1 : i;
  }

  /** 搜索关键词：优先统一社会信用代码（唯一、精确），没填则用单位名称（同桌面版）。
   *  用本地副本取值，所以刚敲完一个字就能用（不必等父级回写）。 */
  private term(): string {
    const code: string = this.codeText.trim();
    return code.length > 0 ? code : this.nameText.trim();
  }

  /** 「🔍」菜单：先选站点再查（与桌面版 UNIT_SEARCH_SITES 一致）。
   *  ⚠ 必须用 Menu + MenuItem：点 MenuItem 后菜单会自动收起；
   *    自定义按钮放在里面点了不会关，得再点一下空白处。 */
  @Builder
  searchMenuPanel() {
    Menu() {
      MenuItem({ content: `去搜索：${this.term()}` })
        .enabled(false)
      MenuItem({ content: '国家企业信用信息公示系统' })
        .onClick(() => this.onAction('gsxt'))
      MenuItem({ content: '信用中国' })
        .onClick(() => this.onAction('credit'))
    }
  }

  build() {
    Row({ space: 8 }) {
      if (this.locked) {
        // ⚠ 这里必须直接用 Text（@Builder 按值传参不刷新，会把旧文字一直显示下去）
        Text(this.roleLabel.length > 0 ? this.roleLabel : '—')
          .fontSize(12)
          .fontColor('#667085')
          .height(30)
          .width(134)
          .padding({ left: 8, right: 8 })
          .backgroundColor('#F2F4F7')
          .borderRadius(6)
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .textAlign(TextAlign.Start)
        Text(this.name.length > 0 ? this.name : '—')
          .fontSize(12)
          .fontColor('#667085')
          .height(30)
          .layoutWeight(1)
          .padding({ left: 8, right: 8 })
          .backgroundColor('#F2F4F7')
          .borderRadius(6)
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .textAlign(TextAlign.Start)
        Text(this.code.length > 0 ? this.code : this.codeLabel)
          .fontSize(12)
          .fontColor('#667085')
          .height(30)
          .layoutWeight(1)
          .padding({ left: 8, right: 8 })
          .backgroundColor('#F2F4F7')
          .borderRadius(6)
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .textAlign(TextAlign.Start)
      } else {
        Select(this.roleOptions())
          .selected(this.roleIndex())
          .value(this.roleLabel)
          .font({ size: 12 })
          .optionWidth(220)
          .width(134)
          .height(30)
          .fontColor('#0F172A')
          .backgroundColor('#FFFFFF')
          .onSelect((index: number, value?: string) => {
            this.onType(UNIT_SELECTABLE_KEYS[index]);
          })
        TextInput({ text: this.nameText, placeholder: '单位名称' })
          .height(30)
          .fontSize(12)
          .layoutWeight(1)
          .fontColor('#0F172A')
          .backgroundColor('#FFFFFF')
          // 更新本地副本以便锁定→解锁后仍显示最新文字；同时上报父级
          .onChange((v: string) => {
            this.nameText = v;
            this.onRename(v);
          })
          .onBlur(() => this.onRename(this.nameText))
        TextInput({ text: this.codeText, placeholder: this.codeLabel })
          .height(30)
          .fontSize(12)
          .layoutWeight(1)
          .fontColor('#0F172A')
          .backgroundColor('#FFFFFF')
          .onChange((v: string) => {
            this.codeText = v;
            this.onCode(v);
          })
          .onBlur(() => this.onCode(this.codeText))
      }
      // 行尾动作：工资代发银行 = 「📋 复制」两个值；其它 = 「🔍 选站点去搜索」。两者都是只读动作，锁定时仍可用
      if (this.role === 'bank') {
        Button('📋')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(28)
          .width(34)
          .padding(0)
          .backgroundColor('#F8FAFC')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(7)
          .onClick(() => this.onAction('copy'))
      } else {
        // 关键词为空时不弹菜单，直接提示（与桌面版 _open_unit_search_menu 一致）；
        // 有词才绑菜单，所以这里必须写成两个分支：修饰器不能条件绑定。
        if (this.term().length === 0) {
          Button('🔍')
            .type(ButtonType.Normal)
            .fontSize(12)
            .height(28)
            .width(34)
            .padding(0)
            .backgroundColor('#F8FAFC')
            .fontColor('#475467')
            .border({ width: 1, color: '#E6E8F0' })
            .borderRadius(7)
            .onClick(() => this.onEmptyTerm())
        } else {
          Button('🔍')
            .type(ButtonType.Normal)
            .fontSize(12)
            .height(28)
            .width(34)
            .padding(0)
            .backgroundColor('#F8FAFC')
            .fontColor('#475467')
            .border({ width: 1, color: '#E6E8F0' })
            .borderRadius(7)
            .bindMenu(this.searchMenuPanel)
        }
      }
      if (this.locked) {
        Text('').width(24)
      } else {
        Text('✕')
          .fontSize(13)
          .fontColor(C_BAD)
          .width(24)
          .textAlign(TextAlign.Center)
          .onClick(() => this.onDelete())
      }
    }
    .width('100%')
    .padding({ top: 3, bottom: 3 })
  }
}

@ComponentV2
export struct FieldRow {
  @Param label: string = '';
  @Param value: string = '';
  @Param unit: string = '';
  /** 字段下方小字提示（对应桌面版 secHint） */
  @Param tip: string = '';
  /** 是否锁定（仅 lockable 时有意义） */
  @Param locked: boolean = false;
  /** 是否显示 🔒/🔓 锁按钮（最低工资 / 加班基数 / 公积金基数） */
  @Param lockable: boolean = false;
  /** 覆盖锁按钮文案（默认用桌面版两条文案） */
  @Param lockTitle: string = '';
  /** 强制只读（如整月锁定） */
  @Param disabled: boolean = false;
  @Event onEdit: (v: string) => void = (v: string) => {
  };
  @Event onToggleLock: () => void = () => {
  };

  build() {
    Column({ space: 3 }) {
      Text(this.label).fontSize(11).fontColor('#667085').width('100%')
      Row({ space: 8 }) {
        TextInput({ text: this.value })
          .type(InputType.NUMBER_DECIMAL)
          .height(32)
          .fontSize(13)
          .layoutWeight(1)
          .enabled(!this.locked && !this.disabled)
          .backgroundColor(this.locked || this.disabled ? '#F5F7FA' : '#FFFFFF')
          .fontColor(this.locked || this.disabled ? '#667085' : C_TEXT)
          .onChange((v: string) => this.onEdit(v))
        if (this.unit.length > 0) {
          Text(this.unit).fontSize(11).fontColor(C_HINT)
        }
        if (this.lockable) {
          Button(this.locked ? '🔒 已锁定 · 冻结当前值' : '🔓 已解锁 · 可手动修改')
            .type(ButtonType.Normal)
            .fontSize(11)
            .height(28)
            .padding({ left: 8, right: 8 })
            .enabled(!this.disabled)
            .backgroundColor(this.locked ? '#F5F7FA' : '#EEF2FF')
            .fontColor(this.locked ? '#667085' : '#4F46E5')
            .border({ width: 1, color: this.locked ? '#E6E8F0' : '#C7D2FE' })
            .borderRadius(8)
            .onClick(() => this.onToggleLock())
        }
      }
      .width('100%')

      if (this.tip.length > 0) {
        Text(this.tip).fontSize(11).fontColor(C_HINT).width('100%')
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }
}
