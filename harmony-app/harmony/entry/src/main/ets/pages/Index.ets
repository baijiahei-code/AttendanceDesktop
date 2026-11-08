/**
 * 应用外壳 + 工作台 + 考勤日历 + 参数页（状态管理 **V2** 范式）。
 *
 * 为什么是 V2：官方文档明确「对于新开发的应用，建议直接使用 V2 版本范式」。
 * V2 用 @Local / @Param / @Event 明确组件的输入输出，@Param 按引用同步、不做深拷贝。
 *
 * 注意（仍成立的两条）：
 * 1. `core/` 保持纯 TS —— 它要同时在 Node 里跑与桌面版 Python 的数值对拍，
 *    不能加 @ObservedV2/@Trace（那些只有 ArkTS 有）。
 * 2. `@Builder` 的按值传参不刷新 —— 会变的值一律走 @Param 组件，不通过 @Builder 参数传。
 */

import { MonthBook, MonthBookDict, PayItem, STATUS_LABELS, createBook } from '../core/model';
import { HolidaySets, classifyDay, yearSets } from '../core/holidays';
import { CalCell, CalStat, AnnualRow, PayRow, RecGroup, RecLine, Snap, UnitRow } from '../model/Snap';
import { MonthStorage, SettingsStorage } from '../model/Storage';
import {
  ApiConfig,
  ChatResult,
  fetchHolidaysApi,
  fetchWageApi,
  providers,
  testConnection
} from '../model/ApiClient';
import { HolidayApiResult, WageApiResult } from '../core/api';
import {
  RelatedUnit, UnitDict, UNIT_ROLE_LABELS, UNIT_SELECTABLE_KEYS,
  defaultUnits, unitsFromJson
} from '../core/units';
import { common } from '@kit.AbilityKit';
import { pasteboard } from '@kit.BasicServicesKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { util } from '@kit.ArkTS';
import { compute, Result, overtimeHourlyTip } from '../core/calc';
import { pyGroupedFixed, pyGeneral } from '../core/num';
import { MIN_WAGE_PROVINCES, MinWageRow, minWageOf, minWageRegions } from '../core/minwage.data';
import { PAYITEM_DEFAULT_NAME, PAYITEM_GROUPS, PayCatalogGroup } from '../core/paycatalog';
import { PI_COL_OP, PI_COL_STD, PI_COL_SUB, PI_COL_TYPE, TYPE_CHIPS, TypeChip, typeChipOf, DAY_PALETTES, DayPalette, dayPaletteOf } from '../core/config';
import { reportCsv, reportFileName, csvRow } from '../core/csv';
import { ExportResult, Exporter } from '../model/Exporter';

// ================= 常量 =================
const BG_PAGE: string = '#F6F7FB';
const BG_CARD: string = '#FFFFFF';
const C_TEXT: string = '#111827';
const C_SUB: string = '#6B7280';
const C_HINT: string = '#9CA3AF';
const C_ACCENT: string = '#4F46E5';
const C_OK: string = '#0B7A3B';
const C_BAD: string = '#C00000';
/** 月份存档写盘防抖（毫秒）：连续输入合并成一次 HUKS 加密 + 写盘。 */
const SAVE_DEBOUNCE_MS: number = 400;
/** 首次安装（从未选过）时的默认工作地：与桌面版 `pages_params` 的兜底完全一致。 */
const DEFAULT_PROVINCE: string = '安徽';
const DEFAULT_REGION: string = '池州';

function pad2(n: number): string {
  return (n < 10 ? '0' : '') + n.toString();
}

// ================= 可复用组件（V2：@Param 按引用同步）=================
@ComponentV2
struct Chip {
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
struct StripItem {
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
struct MetaItem {
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
struct StatCard {
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
struct DayCell {
  @Param num: number = 0;
  @Param midText: string = '未填';
  @Param hoursText: string = '';
  @Param selected: boolean = false;
  @Param bg: string = '#FCFCFD';
  @Param fg: string = '#475569';
  /** 周末且未填 → 桌面版用粉红虚线提醒 */
  @Param weekendEmpty: boolean = false;
  @Event onPick: () => void = () => {
  };

  build() {
    Column({ space: 1 }) {
      Text(this.num.toString())
        .fontSize(11)
        .fontWeight(FontWeight.Bold)
        .fontColor(this.fg)
      Text(this.midText)
        .fontSize(9)
        .fontColor(this.fg)
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
      Text(this.hoursText)
        .fontSize(9)
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
    .onClick(() => this.onPick())
  }
}

@ComponentV2
struct SumRow {
  @Param label: string = '';
  @Param value: string = '';
  @Param accent: string = C_TEXT;

  build() {
    Row() {
      Text(this.label).fontSize(12).fontColor(C_SUB).layoutWeight(1)
      Text(this.value).fontSize(15).fontWeight(FontWeight.Bold).fontColor(this.accent)
    }
    .width('100%')
    .padding({ top: 4, bottom: 4 })
  }
}

const TYPE_KEYS: string[] = ['wage', 'subsidy', 'fixed_allow', 'perday_allow'];
const TYPE_SHORT: Map<string, string> = new Map<string, string>([
  ['wage', '最低工资'],
  ['subsidy', '补贴'],
  ['fixed_allow', '固定'],
  ['perday_allow', '按出勤']
]);

@ComponentV2
struct PayRowView {
  @Param name: string = '';
  @Param type: string = 'wage';
  @Param amountText: string = '0';
  @Param subText: string = '0.00';
  @Event onRename: (v: string) => void = (v: string) => {
  };
  @Event onAmount: (v: string) => void = (v: string) => {
  };
  @Event onType: (t: string) => void = (t: string) => {
  };
  @Event onDelete: () => void = () => {
  };

  private shortOf(t: string): string {
    const s: string | undefined = TYPE_SHORT.get(t);
    return s === undefined ? t : s;
  }

  private typeOptions(): SelectOption[] {
    const out: SelectOption[] = [];
    for (const t of TYPE_KEYS) {
      const o: SelectOption = { value: this.shortOf(t) };
      out.push(o);
    }
    return out;
  }

  private typeIndex(): number {
    const i: number = TYPE_KEYS.indexOf(this.type);
    return i < 0 ? 0 : i;
  }

  build() {
    Row({ space: 6 }) {
      Select(this.typeOptions())
        .selected(this.typeIndex())
        .value(this.shortOf(this.type))
        .font({ size: 11 })
        .optionFont({ size: 12 })
        .height(30)
        .width(90)
        .backgroundColor('#00000000')
        .onSelect((index: number) => {
          this.onType(TYPE_KEYS[index]);
        })

      TextInput({ text: this.name })
        .height(30)
        .fontSize(12)
        .layoutWeight(1)
        .onChange((v: string) => this.onRename(v))
      TextInput({ text: this.amountText })
        .type(InputType.NUMBER_DECIMAL)
        .height(30)
        .fontSize(12)
        .width(92)
        .onChange((v: string) => this.onAmount(v))
      Text(`¥ ${this.subText}`)
        .fontSize(12)
        .fontColor(C_TEXT)
        .width(92)
        .textAlign(TextAlign.End)
      Text('✕')
        .fontSize(13)
        .fontColor(C_BAD)
        .width(24)
        .textAlign(TextAlign.Center)
        .onClick(() => this.onDelete())
    }
    .width('100%')
    .padding({ top: 3, bottom: 3 })
  }
}

@ComponentV2
struct OtRow {
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
          .fontSize(9)
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
struct RoRow {
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
struct AnnualRowView {
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
struct UnitRowView {
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

  /** 「🔍」菜单：先选站点再查（与桌面版 UNIT_SEARCH_SITES 一致）。 */
  private searchMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    out.push({
      value: '国家企业信用信息公示系统', action: () => {
        this.onAction('gsxt');
      }
    });
    out.push({
      value: '信用中国', action: () => {
        this.onAction('credit');
      }
    });
    return out;
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
          .bindMenu(this.searchMenu())
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
struct FieldRow {
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
            .fontSize(10)
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
        Text(this.tip).fontSize(10).fontColor(C_HINT).width('100%')
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }
}

/** 参数模板的字段顺序（与桌面版 `_param_spins` 一致，序列化按此顺序）。 */
const PARAM_KEYS: string[] = [
  'social_base', 'personal_social_rate', 'company_social_rate',
  'personal_fund_rate', 'company_fund_rate', 'fund_base',
  'min_wage', 'parttime_min', 'overtime_base',
  'hours_per_day', 'agreed_work_days'
];

/** 一组参数模板（对应桌面版 templates.json 里的一项）。 */
class ParamTpl {
  name: string = '';
  vals: number[] = [];
  note: string = '';
}

/** 打包在 rawfile 里的种子月份（测试用，与桌面版存档同构）。 */
interface SeedMonth {
  year: number;
  month: number;
  book: MonthBookDict;
}

// ================= 侧栏数据 =================
class HistRow {
  y: number = 0;
  m: number = 0;
  label: string = '';
  locked: boolean = false;
  current: boolean = false;
}

class NavItem {
  key: string;
  label: string;
  icon: string;

  constructor(key: string, label: string, icon: string) {
    this.key = key;
    this.label = label;
    this.icon = icon;
  }
}

class NavGroup {
  title: string;
  items: NavItem[];

  constructor(title: string, items: NavItem[]) {
    this.title = title;
    this.items = items;
  }
}

@Entry
@ComponentV2
struct Index {
  @Local pageKey: string = 'overview';
  @Local monthLabel: string = '';
  /** 界面唯一数据源。 */
  @Local snap: Snap = new Snap();

  // 参数页表单
  @Local fSocialBase: string = '';
  @Local fPersonalSocialRate: string = '';
  @Local fCompanySocialRate: string = '';
  @Local fFundBase: string = '';
  @Local fPersonalFundRate: string = '';
  @Local fCompanyFundRate: string = '';
  @Local fMinWage: string = '';
  @Local fParttimeMin: string = '';
  /** 参数页：最低工资地区选择（数据来自 core/minwage.data） */
  @Local fProvince: string = '';
  @Local fRegion: string = '';
  @Local wageHint: string = '';
  /** 报表导出状态文字 */
  @Local exportState: string = '';
  /** 加班费基数是否锁定（锁定时 = 月最低工资，与桌面版一致） */
  @Local otBaseLocked: boolean = true;
  @Local fOvertimeBase: string = '';
  @Local fAgreedDays: string = '';
  @Local fHoursPerDay: string = '';
  @Local fNote: string = '';
  /** 三个可锁字段（桌面版 _wage_locked / _ot_base_locked / _fund_base_locked） */
  @Local fWageLocked: boolean = true;
  @Local fFundBaseLocked: boolean = true;
  // ---- 参数模板 ----
  @Local tplNames: string[] = [];
  @Local tplSel: string = '';
  @Local tplHint: string = '';
  @Local tplDlgOpen: boolean = false;
  @Local tplDlgMode: string = 'save';
  @Local tplDlgText: string = '';
  @Local tplDlgTitle: string = '';
  /** 报表页 6 个分组卡的折叠状态（true = 展开） */
  @Local groupOpen: boolean[] = [true, true, true, true, true, true];

  // 日历：当天两个输入框
  @Local selOt: string = '0';
  @Local selLeave: string = '0';
  @Local saveState: string = '';

  // 年度汇总
  @Local annualRows: AnnualRow[] = [];
  @Local annualGross: string = '0.00';
  @Local annualTakeHome: string = '0.00';
  @Local annualYear: number = 0;
  @Local annualState: string = '';

  // 相关单位（全局数据）
  @Local unitRows: UnitRow[] = [];
  @Local unitsState: string = '';
  /** 单位登记表自己的锁（与月份无关，存 settings） */
  @Local unitsLocked: boolean = false;
  /** 复制工资项弹窗 */
  @Local copyDlgOpen: boolean = false;
  @Local copyYear: number = 0;
  @Local copyMonth: string = '1';
  @Local copyHint: string = '';
  /** 关于 / 免责声明对话框 */
  @Local aboutOpen: boolean = false;
  /** 当前月份是否锁定（= book.locked，只读） */
  @Local isLocked: boolean = false;
  /** 历史月份列表（侧栏） */
  @Local historyRows: HistRow[] = [];
  // ---- API 配置（最低工资 / 节假日联网查询）----
  @Local apiUrl: string = '';
  @Local apiModel: string = '';
  @Local apiKey: string = '';
  @Local apiDlgOpen: boolean = false;
  @Local apiTestState: string = '';
  @Local apiBusy: boolean = false;
  @Local apiHint: string = '';

  private store: MonthStorage | null = null;
  private settings: SettingsStorage | null = null;
  private exporter: Exporter | null = null;
  /** 单位列表的 key 版本：锁定瞬间 +1，强制 ForEach 重建所有行（确保读最新值）。 */
  @Local rowsKey: number = 0;
  /** 工作台「合规判定」卡实测高度：用于把右侧「公司每小时成本」卡拉到同高（桌面版 QHBoxLayout 行为）。 */
  @Local cmpCardHeight: number = 0;
  /** 单位表写盘是否进行中 / 是否有新的待写内容。 */
  private unitsSaving: boolean = false;
  private unitsPending: boolean = false;
  /** 输入防抖定时器（-1 表示未启动）。 */
  private unitsTimer: number = -1;
  /** 月份存档写盘：防抖定时器 / 是否有待写改动 / 是否有在途的写盘。 */
  private saveTimer: number = -1;
  private savePending: boolean = false;
  private saving: boolean = false;
  /**
   * 业务提示的驻留截止时间（毫秒时间戳）。
   *
   * ⚠ 铺设 / 锁定这类操作会顺带落盘，而 `persist()` 写完后会把状态栏改成「已保存…」
   * —— 不驻留的话业务提示只活几百毫秒（桌面版用 `STATUS_HOLD_MS` 同一套思路）。
   */
  private statusHoldUntil: number = 0;
  /** 是否有「改动但还没落盘」的单位数据。 */
  private unitsDirty: boolean = false;
  private units: RelatedUnit[] = [];
  /** 本次运行内已载入过的月份（磁盘写失败也不会丢改动）。 */
  private cache: Map<string, MonthBook> = new Map<string, MonthBook>();

  private book: MonthBook = createBook(2026, 11);
  private groups: NavGroup[] = [
    new NavGroup('', [new NavItem('units', '相关单位', '🏢')]),
    new NavGroup('功 能', [
      new NavItem('overview', '工作台', '🏠'),
      new NavItem('calendar', '考勤', '📅'),
      new NavItem('salary', '薪酬构成', '💰'),
      new NavItem('params', '参数', '⚙️'),
      new NavItem('report', '报表', '📊'),
      new NavItem('annual', '年度汇总', '📆')
    ])
  ];

  aboutToAppear(): void {
    this.initData();
  }

  /** 页面销毁前把待写的单位表与月份存档落盘（防抖窗口内的改动不丢）。 */
  aboutToDisappear(): void {
    this.flushPendingUnits();
    this.flushSave();
  }

  /** 启动加载。HUKS 只有异步接口，所以整条链路都是 Promise。 */
  private async initData(): Promise<void> {
    const ctx = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.store = new MonthStorage(ctx);
    this.settings = new SettingsStorage(ctx);
    this.exporter = new Exporter(ctx);
    const keyOk: boolean = await this.settings.warmUp();
    hilog.info(0x0000, 'ATTD', 'key ready=%{public}s err=%{public}s', String(keyOk), this.settings.cryptoError());
    await this.loadUnits();
    await this.importSeedIfNeeded();
    const st = this.store;
    const now: Date = new Date();
    const y: number = now.getFullYear();
    const m: number = now.getMonth() + 1;
    const key: string = this.monthKey(y, m);
    const loaded: MonthBook | null = await st.loadMonth(y, m);
    if (loaded !== null) {
      this.book = loaded;
      this.saveState = st.cryptoOk() ? `已读取 ${key}` : `已读取 ${key}（未加密：${st.cryptoError()}）`;
    } else {
      // 新建月份带常用工资项（金额 0），与桌面版从 UI 新建月一致；不自动落盘
      this.book = createBook(y, m, '', true);
      this.saveState = `新月份 ${key}（未保存）`;
    }
    this.cache.set(this.monthKey(this.book.year, this.book.month), this.book);
    this.isLocked = this.book.locked;
    this.loadParamsForm();
    await this.loadWorkRegion();
    await this.refreshTemplates();
    await this.loadApiConfig();
    await this.refreshHistory();
    this.refresh(false);
  }

  /**
   * 唯一重算入口（persist=true 时**调度**落盘）。
   *
   * ⚠ 不能在这里直接写盘：HUKS 加密是异步的，连续输入会并发多个 saveMonth，
   * 加密耗时不均 → 后完成的「旧快照」可能覆盖「新快照」（数据丢失）。
   * 因此这里只做 400ms 防抖 + 串行写（与相关单位页同一套模式）。
   */
  private refresh(persist: boolean = true): void {
    this.monthLabel = `${this.book.year} 年 ${this.book.month} 月`;
    this.snap = Snap.from(this.book, this.snap.selDay);
    if (persist) {
      this.scheduleSave();
    }
  }

  /** 防抖调度：连续改动只在停止后写一次盘。 */
  private scheduleSave(): void {
    this.savePending = true;
    if (this.saveTimer !== -1) {
      clearTimeout(this.saveTimer);
    }
    this.saveTimer = setTimeout(() => {
      this.saveTimer = -1;
      this.flushSave();
    }, SAVE_DEBOUNCE_MS);
  }

  /** 立即落盘（手动保存 / 切月 / 删除 / 关闭前调用）；正在写时排队等下一轮。 */
  private flushSave(): void {
    if (this.saveTimer !== -1) {
      clearTimeout(this.saveTimer);
      this.saveTimer = -1;
    }
    if (!this.savePending) {
      return;
    }
    if (this.saving) {
      // 已在写：把本轮标记留到写完后由 persist() 的收尾再跑一次
      return;
    }
    this.savePending = false;
    this.persist();
  }

  /** 真正写盘（串行：一次只有一个在途）。 */
  private persist(): void {
    const st = this.store;
    // 固定住这本书：写盘是异步的，期间可能已经切月（this.book 变新对象）
    const book: MonthBook = this.book;
    const key: string = this.monthKey(book.year, book.month);
    this.cache.set(key, book);
    if (st === null) {
      this.savePending = false;
      return;
    }
    this.saving = true;
    if (!this.holdStatus()) {
      this.saveState = '保存中…';
    }
    st.saveMonth(book).then((ok: boolean) => {
      this.saving = false;
      // 补偿：写盘期间用户点了「删除本月」→ 这次写会把已删的月份复活，删掉它
      if (!this.cache.has(key)) {
        st.deleteMonth(book.year, book.month);
        this.saveState = '已删除本月';
        this.afterSave();
        return;
      }
      if (!this.holdStatus()) {
        this.saveState = ok
          ? (st.cryptoOk() ? `已保存 ${key}（加密）` : `已保存 ${key}（未加密：${st.cryptoError()}）`)
          : `仅内存（${st.lastError}）`;
      }
      this.afterSave();
    }).catch((e: Error) => {
      this.saving = false;
      this.saveState = `保存异常：${e.message}`;
      this.afterSave();
    });
  }

  /** 业务提示是否还在驻留期内（驻留期内不让「保存中…/已保存…」顶掉它）。 */
  private holdStatus(): boolean {
    return Date.now() < this.statusHoldUntil;
  }

  /** 显示一条业务提示并让它驻留一会儿（桌面版 `_set_status(..., hold_ms)` 的精简版）。 */
  private setBusinessState(text: string, holdMs: number = 4000): void {
    this.saveState = text;
    this.statusHoldUntil = Date.now() + holdMs;
  }

  /** 写完后若期间又有改动，补一次（保证最后一次改动一定落盘）。 */
  private afterSave(): void {
    if (this.savePending) {
      this.savePending = false;
      this.persist();
    }
  }

  /** 取消尚未开始的写盘（如「删除本月」前，避免删完又被写回）。 */
  private cancelPendingSave(): void {
    if (this.saveTimer !== -1) {
      clearTimeout(this.saveTimer);
      this.saveTimer = -1;
    }
    this.savePending = false;
  }

  private monthKey(y: number, m: number): string {
    return `${y}-${pad2(m)}`;
  }

  /** 把 book 里的参数回填到参数页表单（纯展示，不做任何跟随覆盖）。 */
  private loadParamsForm(): void {
    const b: MonthBook = this.book;
    this.fSocialBase = b.social_base.toString();
    this.fPersonalSocialRate = b.personal_social_rate.toString();
    this.fCompanySocialRate = b.company_social_rate.toString();
    this.fFundBase = b.fund_base.toString();
    this.fPersonalFundRate = b.personal_fund_rate.toString();
    this.fCompanyFundRate = b.company_fund_rate.toString();
    this.fMinWage = b.min_wage.toString();
    this.fParttimeMin = b.parttime_min.toString();
    this.fOvertimeBase = b.overtime_base.toString();
    this.fAgreedDays = b.agreed_work_days.toString();
    this.fHoursPerDay = b.hours_per_day.toString();
    this.fNote = b.note;
  }

  private async changeMonth(delta: number): Promise<void> {
    // 切月前把当前月立即落盘（否则在途的防抖改动会随对象切走而丢）
    this.flushSave();
    // 先把当前月的对象放回缓存（切回来一定拿到最新版本）
    this.cache.set(this.monthKey(this.book.year, this.book.month), this.book);

    let m: number = this.book.month + delta;
    let y: number = this.book.year;
    if (m > 12) {
      m = 1;
      y = y + 1;
    } else if (m < 1) {
      m = 12;
      y = y - 1;
    }

    const key: string = this.monthKey(y, m);
    let next: MonthBook | null = this.cache.get(key) ?? null;
    const st = this.store;
    if (next === null && st !== null) {
      next = await st.loadMonth(y, m);
    }
    if (next !== null) {
      this.book = next;
      this.saveState = (st !== null && !st.cryptoOk()) ? `已读取 ${key}（未加密：${st.cryptoError()}）` : `已读取 ${key}`;
    } else {
      this.book = createBook(y, m, '', true);
      this.saveState = '新月份（未保存）';
    }
    this.cache.set(key, this.book);

    this.loadParamsForm();
    this.snap = Snap.from(this.book, 1);
    this.selOt = this.book.day(1).overtime_hours.toString();
    this.selLeave = this.book.day(1).leave_hours.toString();
    this.monthLabel = `${y} 年 ${m} 月`;
    this.isLocked = this.book.locked;
    this.refreshHistory();
  }

  // ================= 数据操作 =================
  private selectDay(d: number): void {
    this.snap = Snap.from(this.book, d);
    this.selOt = this.book.day(d).overtime_hours.toString();
    this.selLeave = this.book.day(d).leave_hours.toString();
  }

  private setStatus(value: string): void {
    if (this.isLocked) {
      return;
    }
    this.book.day(this.snap.selDay).status = value;
    this.refresh();
  }

  private setMark(value: number): void {
    if (this.isLocked) {
      return;
    }
    this.book.day(this.snap.selDay).mark = value;
    this.refresh();
  }

  private setOt(text: string): void {
    if (this.isLocked) {
      return;
    }
    this.selOt = text;
    const v: number = parseFloat(text);
    if (isNaN(v)) {
      return;
    }
    this.book.day(this.snap.selDay).overtime_hours = v;
    this.refresh();
  }

  private setLeave(text: string): void {
    if (this.isLocked) {
      return;
    }
    this.selLeave = text;
    const v: number = parseFloat(text);
    if (isNaN(v)) {
      return;
    }
    this.book.day(this.snap.selDay).leave_hours = v;
    this.refresh();
  }

  /**
   * 按官方安排铺设（与桌面版 `_apply_holidays` 完全同口径）。
   *
   * - **状态**：只覆盖「法定 / 放假调休 / 补班」三类日期 + 普通周末；
   *   范围之外的日期（普通工作日）**不动**，保留用户手填的请假 / 缺勤等。
   * - **「法定节假日」标记**：整月重写 —— 只有法定日为 1，其余一律清 0
   *   （否则被错误数据标过的 mark 永远洗不掉，×3 加班工资会一直算错）。
   *
   * @param sets 三组 MM-DD 集合
   * @param label 入口名（用于提示文案）
   * @returns 实际被改动的天数
   */
  private applyHolidaySets(sets: HolidaySets, label: string): number {
    let changed: number = 0;
    for (const d of this.book.days) {
      const key: string = `${pad2(this.book.month)}-${pad2(d.day)}`;
      const kind: string | null = classifyDay(key, sets);
      let newStatus: string | null = null;
      const newMark: number = kind === 'statutory' ? 1 : 0;
      if (kind === 'makeup') {
        newStatus = '上班';
      } else if (kind === 'statutory') {
        newStatus = '休息';
      } else if (kind === 'rest') {
        newStatus = '休息';
      } else if (d.isWeekendDt(this.book.year, this.book.month)) {
        newStatus = '休息';
      }
      if (d.mark !== newMark || (newStatus !== null && d.status !== newStatus)) {
        if (newStatus !== null) {
          d.status = newStatus;
        }
        d.mark = newMark;
        changed++;
      }
    }
    this.refresh();
    this.setBusinessState(`${label}完成 · ${this.book.year} 年 · 影响 ${changed} 天`
      + `（法定 ${sets.statutory.size} / 放假 ${sets.rest.size} / 补班 ${sets.makeup.size} 日）`);
    return changed;
  }

  /** Set 内容相等（用于「API 结果 vs 内置官方表」的差异提示）。 */
  private sameSet(a: Set<string>, b: Set<string>): boolean {
    if (a.size !== b.size) {
      return false;
    }
    let same: boolean = true;
    a.forEach((v: string) => {
      if (!b.has(v)) {
        same = false;
      }
    });
    return same;
  }

  /** 「📋 铺本地表（法定节假日/调休）」：用内置 official 表铺设（不联网）。 */
  private fillOfficial(): void {
    if (this.isLocked) {
      this.setBusinessState('月份已锁定，无法铺设');
      return;
    }
    const sets: HolidaySets | null = yearSets(this.book.year);
    if (sets === null) {
      this.setBusinessState(`内置表没有 ${this.book.year} 年安排（国务院通常在上年 11 月发布）；`
        + '可配置 API 后用「🌐 API 一键铺」试试');
      return;
    }
    this.applyHolidaySets(sets, '📋 铺本地表');
  }

  /** 一键铺：只区分周末/工作日，且不覆盖已填的状态（桌面版 `_fill_default_calendar`）。 */
  private fillDefaultCalendar(): void {
    if (this.isLocked) {
      this.setBusinessState('月份已锁定，无法铺设');
      return;
    }
    let workCount: number = 0;
    let restCount: number = 0;
    for (const d of this.book.days) {
      if (d.status.length > 0) {
        continue;
      }
      const weekend: boolean = d.isWeekendDt(this.book.year, this.book.month);
      d.status = weekend ? '休息' : '上班';
      if (weekend) {
        restCount++;
      } else {
        workCount++;
      }
    }
    this.refresh();
    this.setBusinessState(`✨ 一键铺完成：工作日上班 ${workCount} 天，周末休息 ${restCount} 天（已填日期未覆盖）`);
  }

  private clearAttendance(): void {
    if (this.isLocked) {
      return;
    }
    for (const d of this.book.days) {
      d.status = '';
      d.mark = 0;
      d.overtime_hours = 0;
      d.leave_hours = 0;
    }
    this.selOt = '0';
    this.selLeave = '0';
    this.refresh();
  }

  // ================= 参数页：输入 → 模型 =================
  private applyParam(key: string, text: string): void {
    if (this.isLocked) {
      return;
    }
    const v: number = parseFloat(text);
    if (isNaN(v)) {
      return;
    }
    const b: MonthBook = this.book;
    if (key === 'social_base') {
      b.social_base = v;
    } else if (key === 'personal_social_rate') {
      b.personal_social_rate = v;
    } else if (key === 'company_social_rate') {
      b.company_social_rate = v;
    } else if (key === 'fund_base') {
      b.fund_base = v;
    } else if (key === 'personal_fund_rate') {
      b.personal_fund_rate = v;
    } else if (key === 'company_fund_rate') {
      b.company_fund_rate = v;
    } else if (key === 'min_wage') {
      b.min_wage = v;
      // 桌面版：min_wage 变化 → 同步「加班费计算基数 / 公积金缴费基数」（仅限各自处于锁定态时）
      this.syncDerivedFromMinWage();
    } else if (key === 'parttime_min') {
      b.parttime_min = v;
    } else if (key === 'overtime_base') {
      b.overtime_base = v;
    } else if (key === 'agreed_work_days') {
      b.agreed_work_days = v;
    } else if (key === 'hours_per_day') {
      b.hours_per_day = v;
    }
    this.refresh();
  }

  /**
   * 月最低工资变化后的联动（对应桌面版 pages_params 里的
   * `_sync_ot_base_with_min_wage()` / `_sync_fund_base_with_min_wage()`）：
   * 只有对应字段处于「锁定」状态才跟随，解锁后用户自定义值不被覆盖。
   */
  private syncDerivedFromMinWage(): void {
    const b: MonthBook = this.book;
    if (this.otBaseLocked) {
      b.overtime_base = b.min_wage;
      this.fOvertimeBase = b.overtime_base.toString();
    }
    if (this.fFundBaseLocked) {
      b.fund_base = b.min_wage;
      this.fFundBase = b.fund_base.toString();
    }
  }

  // ================= 参数页：字段级锁 / 一键填入 =================
  /** 最低工资锁同时管「月最低工资」与「非全日制小时最低工资」两个字段。 */
  private toggleWageLock(): void {
    this.fWageLocked = !this.fWageLocked;
  }

  private toggleFundBaseLock(): void {
    this.fFundBaseLocked = !this.fFundBaseLocked;
  }

  /** 「一键填入提供正常劳动天数」：把统计出的正常劳动天数写进约定工作天数。 */
  private fillAgreedDays(): void {
    if (this.isLocked) {
      return;
    }
    const r: Result = compute(this.book);
    const v: number = r.counts.normal_labor_days;
    this.book.agreed_work_days = v;
    this.fAgreedDays = `${v}`;
    this.refresh();
    this.tplHint = `已按考勤填入约定工作天数：${v} 天`;
  }

  private paramNum(key: string): number {
    const b: MonthBook = this.book;
    if (key === 'social_base') {
      return b.social_base;
    } else if (key === 'personal_social_rate') {
      return b.personal_social_rate;
    } else if (key === 'company_social_rate') {
      return b.company_social_rate;
    } else if (key === 'personal_fund_rate') {
      return b.personal_fund_rate;
    } else if (key === 'company_fund_rate') {
      return b.company_fund_rate;
    } else if (key === 'fund_base') {
      return b.fund_base;
    } else if (key === 'min_wage') {
      return b.min_wage;
    } else if (key === 'parttime_min') {
      return b.parttime_min;
    } else if (key === 'overtime_base') {
      return b.overtime_base;
    } else if (key === 'hours_per_day') {
      return b.hours_per_day;
    } else if (key === 'agreed_work_days') {
      return b.agreed_work_days;
    }
    return 0;
  }

  private setParamNum(key: string, v: number): void {
    const b: MonthBook = this.book;
    if (key === 'social_base') {
      b.social_base = v;
    } else if (key === 'personal_social_rate') {
      b.personal_social_rate = v;
    } else if (key === 'company_social_rate') {
      b.company_social_rate = v;
    } else if (key === 'personal_fund_rate') {
      b.personal_fund_rate = v;
    } else if (key === 'company_fund_rate') {
      b.company_fund_rate = v;
    } else if (key === 'fund_base') {
      b.fund_base = v;
    } else if (key === 'min_wage') {
      b.min_wage = v;
    } else if (key === 'parttime_min') {
      b.parttime_min = v;
    } else if (key === 'overtime_base') {
      b.overtime_base = v;
    } else if (key === 'hours_per_day') {
      b.hours_per_day = v;
    } else if (key === 'agreed_work_days') {
      b.agreed_work_days = v;
    }
  }

  // ================= 参数模板 =================
  private tplToLine(t: ParamTpl): string {
    const cells: string[] = [t.name.split('\t').join(' ').split('\n').join(' ')];
    for (const v of t.vals) {
      cells.push(`${v}`);
    }
    cells.push(t.note.split('\t').join(' ').split('\n').join(' '));
    return cells.join('\t');
  }

  private tplFromLine(line: string): ParamTpl | null {
    const cells: string[] = line.split('\t');
    if (cells.length < 2) {
      return null;
    }
    const t: ParamTpl = new ParamTpl();
    t.name = cells[0];
    const vals: number[] = [];
    for (let i = 1; i < cells.length - 1; i++) {
      const v: number = parseFloat(cells[i]);
      vals.push(isNaN(v) ? 0 : v);
    }
    while (vals.length < PARAM_KEYS.length) {
      vals.push(0);
    }
    t.vals = vals;
    t.note = cells[cells.length - 1];
    return t;
  }

  private async loadTemplates(): Promise<ParamTpl[]> {
    const out: ParamTpl[] = [];
    const st = this.settings;
    if (st === null) {
      return out;
    }
    const txt: string | null = await st.loadText('templates');
    if (txt === null || txt.length === 0) {
      return out;
    }
    for (const line of txt.split('\n')) {
      if (line.length === 0) {
        continue;
      }
      const t: ParamTpl | null = this.tplFromLine(line);
      if (t !== null && t.name.length > 0) {
        out.push(t);
      }
    }
    return out;
  }

  private async persistTemplates(list: ParamTpl[]): Promise<boolean> {
    const st = this.settings;
    if (st === null) {
      this.tplHint = '设置首选项未初始化';
      return false;
    }
    const lines: string[] = [];
    for (const t of list) {
      lines.push(this.tplToLine(t));
    }
    const ok: boolean = await st.saveText('templates', lines.join('\n'));
    if (!ok) {
      this.tplHint = `模板保存失败：${st.lastError}`;
    }
    return ok;
  }

  private async refreshTemplates(): Promise<void> {
    const list: ParamTpl[] = await this.loadTemplates();
    const names: string[] = [];
    for (const t of list) {
      names.push(t.name);
    }
    this.tplNames = names;
    let sel: string = this.tplSel;
    if (names.indexOf(sel) < 0) {
      sel = names.length > 0 ? names[0] : '';
    }
    this.tplSel = sel;
  }

  private newTplSnapshot(name: string): ParamTpl {
    const t: ParamTpl = new ParamTpl();
    t.name = name;
    const vals: number[] = [];
    for (const k of PARAM_KEYS) {
      vals.push(this.paramNum(k));
    }
    t.vals = vals;
    t.note = this.book.note;
    return t;
  }

  private openTplDialog(mode: string): void {
    this.tplDlgMode = mode;
    if (mode === 'save') {
      this.tplDlgTitle = '保存参数模板';
      this.tplDlgText = `${this.book.year}-${pad2(this.book.month)} 参数`;
    } else if (mode === 'rename') {
      this.tplDlgTitle = '重命名参数模板';
      this.tplDlgText = this.tplSel;
    } else {
      this.tplDlgTitle = '删除参数模板';
      this.tplDlgText = this.tplSel;
    }
    this.tplDlgOpen = true;
  }

  private confirmTplDialog(): void {
    const mode: string = this.tplDlgMode;
    const text: string = this.tplDlgText.trim();
    this.tplDlgOpen = false;
    if (mode === 'delete') {
      this.deleteTemplate();
      return;
    }
    if (this.tplSel.length === 0 && mode === 'rename') {
      this.tplHint = '还没有可重命名的模板';
      return;
    }
    if (text.length === 0) {
      this.tplHint = '模板名称不能为空';
      return;
    }
    if (mode === 'save') {
      this.saveTemplate(text);
    } else {
      this.renameTemplate(text);
    }
  }

  private async saveTemplate(name: string): Promise<void> {
    if (this.isLocked) {
      return;
    }
    const list: ParamTpl[] = await this.loadTemplates();
    let hit: ParamTpl | null = null;
    for (const t of list) {
      if (t.name === name) {
        hit = t;
      }
    }
    const cur: ParamTpl = this.newTplSnapshot(name);
    if (hit !== null) {
      hit.vals = cur.vals;
      hit.note = cur.note;
      if (!await this.persistTemplates(list)) {
        return;
      }
      this.tplSel = name;
      await this.refreshTemplates();
      this.tplHint = `模板已更新：${name}`;
      return;
    }
    list.push(cur);
    if (!await this.persistTemplates(list)) {
      return;
    }
    this.tplSel = name;
    await this.refreshTemplates();
    this.tplHint = `模板已保存：${name}`;
  }

  private async renameTemplate(newName: string): Promise<void> {
    const oldName: string = this.tplSel;
    if (oldName.length === 0) {
      this.tplHint = '还没有可重命名的模板';
      return;
    }
    if (newName === oldName) {
      return;
    }
    const list: ParamTpl[] = await this.loadTemplates();
    for (const t of list) {
      if (t.name === newName) {
        this.tplHint = `已存在同名模板：${newName}`;
        return;
      }
    }
    let found: boolean = false;
    for (const t of list) {
      if (t.name === oldName) {
        t.name = newName;
        found = true;
        break;
      }
    }
    if (!found) {
      this.tplHint = `模板不存在：${oldName}`;
      return;
    }
    if (!await this.persistTemplates(list)) {
      return;
    }
    this.tplSel = newName;
    await this.refreshTemplates();
    this.tplHint = `模板已重命名：${oldName} → ${newName}`;
  }

  private async deleteTemplate(): Promise<void> {
    const name: string = this.tplSel;
    if (name.length === 0) {
      this.tplHint = '还没有可删除的模板';
      return;
    }
    const list: ParamTpl[] = await this.loadTemplates();
    const left: ParamTpl[] = [];
    for (const t of list) {
      if (t.name !== name) {
        left.push(t);
      }
    }
    if (left.length === list.length) {
      this.tplHint = `模板不存在：${name}`;
      return;
    }
    if (!await this.persistTemplates(left)) {
      return;
    }
    this.tplSel = '';
    await this.refreshTemplates();
    this.tplHint = `模板已删除：${name}`;
  }

  /**
   * 进入参数页时的「跟随锁定态」同步（对应桌面版参数卡片构造时的
   * `if self._ot_base_locked and mw > 0: ot_init = mw` / `_fund_base_locked`）。
   * ⚠ 只在进参数页时做：薪酬页仍显示数据里保存的值（与 Windows 行为一致）。
   */
  private syncLockedParamsOnEnter(): void {
    const b: MonthBook = this.book;
    if (b.min_wage <= 0) {
      return;
    }
    let changed: boolean = false;
    if (this.otBaseLocked && Math.abs(b.overtime_base - b.min_wage) > 1e-9) {
      b.overtime_base = b.min_wage;
      changed = true;
    }
    if (this.fFundBaseLocked && Math.abs(b.fund_base - b.min_wage) > 1e-9) {
      b.fund_base = b.min_wage;
      changed = true;
    }
    if (changed) {
      this.loadParamsForm();
      this.refresh();
    }
  }

  private async applyTemplate(): Promise<void> {
    if (this.isLocked) {
      this.tplHint = '月份已锁定，无法套用模板（先点 🔒 解锁）';
      return;
    }
    const name: string = this.tplSel;
    if (name.length === 0) {
      this.tplHint = '还没有已存模板';
      return;
    }
    const list: ParamTpl[] = await this.loadTemplates();
    let hit: ParamTpl | null = null;
    for (const t of list) {
      if (t.name === name) {
        hit = t;
      }
    }
    if (hit === null) {
      this.tplHint = `模板不存在：${name}`;
      return;
    }
    const vals: number[] = hit.vals;
    for (let i = 0; i < PARAM_KEYS.length; i++) {
      if (i < vals.length) {
        this.setParamNum(PARAM_KEYS[i], vals[i]);
      }
    }
    this.book.note = hit.note;
    // 套用模板：保留模板里的加班费基数 / 公积金基数，不被月最低工资覆盖
    this.loadParamsForm();
    this.refresh();
    this.tplHint = `已套用模板：${name}`;
  }

  // ---- 报表导出 CSV ----
  private exportReport(): void {
    const ex: Exporter | null = this.exporter;
    if (ex === null) {
      this.exportState = '导出器未就绪';
      return;
    }
    const r: Result = compute(this.book);
    const text: string = reportCsv(this.book, r);
    const name: string = reportFileName(this.book);
    this.exportState = '导出中…';
    ex.saveText(name, text).then((res: ExportResult) => {
      this.exportState = res.ok ? `${res.message}：${res.path}` : `导出失败：${res.message}`;
    }).catch((e: Error) => {
      this.exportState = `导出异常：${e.message}`;
    });
  }

  /** 年度汇总导出 CSV（桌面版导出 xlsx，鸿蒙用 CSV，Excel 可直接打开）。 */
  private exportAnnual(): void {
    const ex: Exporter | null = this.exporter;
    if (ex === null) {
      this.annualState = '导出器未就绪';
      return;
    }
    const head: string[] = ['月份', '出勤(天)', '加班(小时)', '请假(小时)', '应发工资',
      '个人扣除', '请假扣款', '实发工资', '公司成本', '工时合规'];
    let text: string = csvRow(head);
    for (const row of this.annualRows) {
      const cells: string[] = [];
      if (row.isTotal) {
        cells.push('合计');
      } else {
        cells.push(`${row.month} 月`);
      }
      const has: boolean = row.hasData || row.isTotal;
      cells.push(has ? row.workText : '—');
      cells.push(has ? row.otText : '—');
      cells.push(has ? row.leaveText : '—');
      cells.push(has ? row.gross : '—');
      cells.push(has ? row.deduct : '—');
      cells.push(has ? row.leaveDeduct : '—');
      cells.push(has ? row.takeHome : '—');
      cells.push(has ? row.companyCost : '—');
      cells.push(row.isTotal ? '' : (row.hasData ? (row.legal ? '合规' : '违法') : '—'));
      text = text + csvRow(cells);
    }
    const name: string = `年度汇总_${this.annualYear}.csv`;
    this.annualState = '导出中…';
    ex.saveText(name, text).then((res: ExportResult) => {
      this.annualState = res.ok ? `${res.message}：${res.path}` : `导出失败：${res.message}`;
    }).catch((e: Error) => {
      this.annualState = `导出异常：${e.message}`;
    });
  }

  // ---- 最低工资：按省 / 地区选（内置表，来自桌面版导出） ----
  private provinceMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    for (const p of MIN_WAGE_PROVINCES) {
      const item: MenuElement = {
        value: p,
        action: () => {
          this.pickProvince(p);
        }
      };
      out.push(item);
    }
    return out;
  }

  private regionMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    if (this.fProvince.length === 0) {
      const tip: MenuElement = {
        value: '请先选择省份',
        action: () => {
        }
      };
      out.push(tip);
      return out;
    }
    for (const r of minWageRegions(this.fProvince)) {
      const item: MenuElement = {
        value: r,
        action: () => {
          this.pickRegion(r);
        }
      };
      out.push(item);
    }
    return out;
  }

  /**
   * 选省份（桌面版 `_on_province_changed` 同口径）：
   * 记下省份 → **自动带出第一个地区** → 写入全局设置（工作地与月份无关）→ 按内置表填最低工资。
   */
  private pickProvince(p: string): void {
    if (this.isLocked) {
      this.wageHint = '月份已锁定，无法修改工作地';
      return;
    }
    this.fProvince = p;
    const regions: string[] = minWageRegions(p);
    const first: string = regions.length > 0 ? regions[0] : '';
    this.fRegion = first;
    // ⚠ 必须落盘：工作地存的是「全局设置」（SettingsStorage），不是月度账本
    this.saveWorkRegion();
    if (first.length === 0) {
      this.wageHint = `${p}：内置表没有地区，请手动填写最低工资`;
      return;
    }
    this.applyRegionLocal(p, first);
  }

  /** 选地区：写全局设置 → 按内置表填最低工资（桌面版 `_on_region_changed`）。 */
  private pickRegion(r: string): void {
    if (this.isLocked) {
      this.wageHint = '月份已锁定，无法修改工作地';
      return;
    }
    if (this.fProvince.length === 0) {
      this.wageHint = '请先选择省份';
      return;
    }
    this.fRegion = r;
    this.saveWorkRegion();
    this.applyRegionLocal(this.fProvince, r);
  }

  /**
   * 只从内置静态表取值填入（桌面版 `_apply_region_local`），不联网。
   * 会改写本月账本的 min_wage / parttime_min，并按锁定态联动加班费基数与公积金基数。
   */
  private applyRegionLocal(province: string, region: string): void {
    const row: MinWageRow | null = minWageOf(province, region);
    if (row === null) {
      this.wageHint = `${province} ${region}：无内置标准，请手动填写`;
      return;
    }
    this.fMinWage = `${row.month}`;
    this.fParttimeMin = `${row.hour}`;
    const b: MonthBook = this.book;
    b.min_wage = row.month;
    b.parttime_min = row.hour;
    this.syncDerivedFromMinWage();
    this.wageHint = `${row.month} 元/月 · ${row.hour} 元/时`;
    this.refresh();
  }

  /** 工作地 = 全局设置（与月份无关），存两行文本：省份 / 地区。 */
  private saveWorkRegion(): void {
    const st = this.settings;
    if (st === null) {
      return;
    }
    const text: string = `${this.fProvince}\n${this.fRegion}`;
    st.saveText('work_region', text).then((ok: boolean) => {
      if (!ok) {
        this.wageHint = `保存工作地失败：${st.lastError}`;
      }
    });
  }

  /**
   * 启动时读回上次选的工作地（只回填显示，**不改任何账本数据**）。
   *
   * ⚠ 这里刻意不重放 `applyRegionLocal`：否则每次打开软件都会把账本里的
   *   最低工资冲成内置表的值（用户手改过的标准就丢了）。选工作地时才会填。
   */
  private async loadWorkRegion(): Promise<void> {
    const st = this.settings;
    let p: string = '';
    let r: string = '';
    if (st !== null) {
      const line: string | null = await st.loadText('work_region');
      if (line !== null && line.length > 0) {
        const cells: string[] = line.split('\n');
        p = cells.length > 0 ? cells[0].trim() : '';
        r = cells.length > 1 ? cells[1].trim() : '';
      }
    }
    if (p.length === 0) {
      // 从未选过：与桌面版一致，默认「安徽 · 池州」（只在界面显示，不写设置、不改账本）
      p = DEFAULT_PROVINCE;
      r = DEFAULT_REGION;
      if (minWageOf(p, r) === null) {
        const regs: string[] = minWageRegions(p);
        r = regs.length > 0 ? regs[0] : '';
      }
    }
    this.fProvince = p;
    this.fRegion = r;
    if (r.length === 0) {
      this.wageHint = `${p}：请选择地区`;
      return;
    }
    const row: MinWageRow | null = minWageOf(p, r);
    this.wageHint = row === null ? `${p} ${r}：无内置标准，请手动填写`
      : `${row.month} 元/月 · ${row.hour} 元/时`;
  }

  private useLocalWageTable(): void {
    if (this.isLocked) {
      this.wageHint = '月份已锁定，无法改最低工资';
      return;
    }
    if (this.fProvince.length === 0 || this.fRegion.length === 0) {
      this.wageHint = '请先选择省份和地区';
      return;
    }
    this.applyRegionLocal(this.fProvince, this.fRegion);
  }

  private tplMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    if (this.tplNames.length === 0) {
      out.push({
        value: '（暂无已存模板）', action: () => {
        }
      });
      return out;
    }
    for (const n of this.tplNames) {
      out.push({
        value: n, action: () => {
          this.tplSel = n;
        }
      });
    }
    return out;
  }

  private pageTitle(): string {
    if (this.pageKey === 'units') {
      return '相关单位';
    } else if (this.pageKey === 'overview') {
      return '工作台';
    } else if (this.pageKey === 'calendar') {
      return '考勤';
    } else if (this.pageKey === 'salary') {
      return '薪酬构成';
    } else if (this.pageKey === 'params') {
      return '参数';
    } else if (this.pageKey === 'report') {
      return '报表';
    }
    return '年度汇总';
  }

  /** 页面说明（与桌面版 PAGE_TITLES 的第二项一致）。 */
  private pageSub(): string {
    if (this.pageKey === 'units') {
      return '劳动合同 / 社保 / 公积金 / 工资发放 / 个税等涉及的多家公司';
    } else if (this.pageKey === 'overview') {
      return '本月关键数据 · 合规判定';
    } else if (this.pageKey === 'calendar') {
      return '逐日标记状态，点选后右侧编辑加班 / 请假';
    } else if (this.pageKey === 'salary') {
      return '工资项可增删；补贴只需一条，按出勤自动折算';
    } else if (this.pageKey === 'params') {
      return '社保公积金基数 / 比例与各项标准，可存为模板';
    } else if (this.pageKey === 'report') {
      return '应发、扣除、实发与合规判定明细';
    }
    return '全年 12 个月考勤与工资一览，可导出 Excel';
  }

  private cellKey(c: CalCell): string {
    const sel: string = c.day === this.snap.selDay ? 'S' : 'n';
    return `${c.day}-${c.status}-${c.mark}-${sel}`;
  }

  private rowKey(week: CalCell[]): string {
    let s: string = `sel${this.snap.selDay}`;
    for (const c of week) {
      s = s + '|' + c.day + c.status + c.mark;
    }
    return s;
  }

  private chipActive(label: string): boolean {
    return this.snap.selStatus === label;
  }

  private lineColor(kind: string, bold: boolean): string {
    if (kind === 'ok') {
      return '#0B7A3B';
    } else if (kind === 'bad') {
      return '#C00000';
    } else if (kind === 'sec') {
      return '#7C8AA5';
    } else if (bold) {
      return '#1D4ED8';
    }
    return '#0F172A';
  }

  private lineBold(kind: string, bold: boolean): FontWeight {
    if (kind === 'ok' || kind === 'bad' || kind === 'sec' || bold) {
      return FontWeight.Bold;
    }
    return FontWeight.Normal;
  }

  // ================= 薪酬页：数据操作 =================
  private addPayItem(): void {
    if (this.isLocked) {
      return;
    }
    const def: string | undefined = PAYITEM_DEFAULT_NAME.get('wage');
    this.book.pay_items.push(new PayItem(def === undefined ? '自定义项' : def, 'wage', 0));
    this.refresh();
  }

  /** 当前月份里是否已经有同名工资项。 */
  private hasPayItem(name: string): boolean {
    for (const it of this.book.pay_items) {
      if (it.name === name) {
        return true;
      }
    }
    return false;
  }

  /** 某类目下还没添加的可选项数量（菜单里显示「可选 N 项」）。 */
  private catalogLeft(type: string): number {
    let left: number = 0;
    for (const g of PAYITEM_GROUPS) {
      if (g.type !== type) {
        continue;
      }
      for (const n of g.items) {
        if (!this.hasPayItem(n)) {
          left = left + 1;
        }
      }
    }
    return left;
  }

  private payItemMenuText(name: string): string {
    return this.hasPayItem(name) ? `✓ ${name}（已添加）` : name;
  }

  private addPayItemNamed(name: string, type: string): void {
    if (this.isLocked) {
      return;
    }
    if (this.hasPayItem(name)) {
      return;
    }
    this.book.pay_items.push(new PayItem(name, type, 0));
    this.refresh();
  }

  private removePayItem(i: number): void {
    if (this.isLocked) {
      return;
    }
    if (i >= 0 && i < this.book.pay_items.length) {
      this.book.pay_items.splice(i, 1);
      this.refresh();
    }
  }

  private renamePayItem(i: number, v: string): void {
    if (this.isLocked) {
      return;
    }
    if (i >= 0 && i < this.book.pay_items.length) {
      this.book.pay_items[i].name = v;
      this.refresh();
    }
  }

  private setPayAmount(i: number, v: string): void {
    if (this.isLocked) {
      return;
    }
    if (i < 0 || i >= this.book.pay_items.length) {
      return;
    }
    const n: number = parseFloat(v);
    this.book.pay_items[i].amount = isNaN(n) ? 0 : n;
    this.refresh();
  }

  private setPayType(i: number, t: string): void {
    if (this.isLocked) {
      return;
    }
    if (i >= 0 && i < this.book.pay_items.length) {
      this.book.pay_items[i].type = t;
      this.refresh();
    }
  }

  /** 工资项类型下拉菜单（桌面版：单个 chip 按钮带菜单，非 4 个并排）。 */
  private rowTypeMenu(p: PayRow): MenuElement[] {
    const out: MenuElement[] = [];
    for (const c of TYPE_CHIPS) {
      const item: MenuElement = {
        value: p.type === c.key ? `${c.short}  ✓` : c.short,
        action: () => {
          this.setPayType(p.index, c.key);
        }
      };
      out.push(item);
    }
    return out;
  }

  private chipOf(t: string): TypeChip {
    return typeChipOf(t);
  }

  private setOtHours(kind: string, v: string): void {
    if (this.isLocked) {
      return;
    }
    const n: number = parseFloat(v);
    if (isNaN(n)) {
      return;
    }
    if (kind === 'workday') {
      this.book.workday_ot_hours = n;
    } else if (kind === 'restday') {
      this.book.restday_ot_hours = n;
    } else {
      this.book.holiday_ot_hours = n;
    }
    this.refresh();
  }

  private setFixedOt(v: string): void {
    if (this.isLocked) {
      return;
    }
    const n: number = parseFloat(v);
    if (!isNaN(n)) {
      this.book.fixed_overtime_wage = n;
      this.refresh();
    }
  }

  private setOtBase(v: string): void {
    if (this.isLocked) {
      return;
    }
    const n: number = parseFloat(v);
    if (!isNaN(n)) {
      this.book.overtime_base = n;
      // 薪酬页改了基数 → 参数页字段同步（桌面版 `_sync_ot_base_value_salary` 的反向同步）
      this.fOvertimeBase = n.toString();
      this.refresh();
    }
  }

  /**
   * 锁定 / 解锁加班费计算基数（对齐桌面版 `_toggle_ot_base_lock()`）：
   * 重锁时仅冻结当前值（不立刻用月最低工资覆盖）；之后最低工资变化时锁定态仍会跟随。
   */
  private toggleOtBaseLock(): void {
    if (this.isLocked) {
      return;
    }
    this.otBaseLocked = !this.otBaseLocked;
    this.fOvertimeBase = this.book.overtime_base.toString();
    this.refresh();
  }

  private setBigDisease(v: string): void {
    if (this.isLocked) {
      return;
    }
    const n: number = parseFloat(v);
    if (!isNaN(n)) {
      this.book.big_disease = n;
      this.refresh();
    }
  }

  private setIncomeTax(v: string): void {
    if (this.isLocked) {
      return;
    }
    const n: number = parseFloat(v);
    if (!isNaN(n)) {
      this.book.income_tax = n;
      this.refresh();
    }
  }

  private toggleTaxAuto(on: boolean): void {
    if (this.isLocked) {
      return;
    }
    this.book.income_tax_auto = on;
    this.refresh();
  }

  // ================= 年度汇总 =================
  /** 读取全年 12 个月（只算真的已存档的月份）并汇总。target=0 时用当前年份。 */
  private async rebuildAnnual(target: number = 0): Promise<void> {
    const year: number = target > 0 ? target : this.book.year;
    const rows: AnnualRow[] = [];
    const sums: number[] = [0, 0, 0, 0, 0, 0, 0, 0];
    const st = this.store;
    for (let m = 1; m <= 12; m++) {
      const row: AnnualRow = new AnnualRow();
      row.month = m;
      // 只统计「真的已存档」的月份 —— 否则未保存的新月份会用演示数据污染年度汇总
      if (st === null || !st.hasMonth(year, m)) {
        rows.push(row);
        continue;
      }
      let b: MonthBook | null = this.cache.get(this.monthKey(year, m)) ?? null;
      if (b === null && st !== null) {
        b = await st.loadMonth(year, m);
        if (b !== null) {
          this.cache.set(this.monthKey(year, m), b);
        }
      }
      if (b === null) {
        rows.push(row);
        continue;
      }
      const r: Result = compute(b);
      row.hasData = true;
      row.workText = pyGeneral(r.counts.work, 6);
      row.otText = r.total_daily_ot_hours.toFixed(1);
      row.leaveText = r.daily_leave_hours.toFixed(1);
      row.gross = pyGroupedFixed(r.gross_wage, 2);
      row.deduct = pyGroupedFixed(r.personal_deductions_total, 2);
      row.leaveDeduct = pyGroupedFixed(r.leave_deduction_total, 2);
      row.takeHome = pyGroupedFixed(r.take_home, 2);
      row.companyCost = pyGroupedFixed(r.gross_wage + r.company_social + r.company_fund, 2);
      row.legal = r.work_time_legal;
      sums[0] += r.counts.work;
      sums[1] += r.total_daily_ot_hours;
      sums[2] += r.daily_leave_hours;
      sums[3] += r.gross_wage;
      sums[4] += r.personal_deductions_total;
      sums[5] += r.leave_deduction_total;
      sums[6] += r.take_home;
      sums[7] += r.gross_wage + r.company_social + r.company_fund;
      rows.push(row);
    }

    const total: AnnualRow = new AnnualRow();
    total.month = 0;
    total.isTotal = true;
    total.workText = pyGeneral(sums[0], 6);
    total.otText = sums[1].toFixed(1);
    total.leaveText = sums[2].toFixed(1);
    total.gross = pyGroupedFixed(sums[3], 2);
    total.deduct = pyGroupedFixed(sums[4], 2);
    total.leaveDeduct = pyGroupedFixed(sums[5], 2);
    total.takeHome = pyGroupedFixed(sums[6], 2);
    total.companyCost = pyGroupedFixed(sums[7], 2);
    rows.push(total);

    this.annualYear = year;
    this.annualRows = rows;
    this.annualGross = total.gross;
    this.annualTakeHome = total.takeHome;
  }

  private annualShift(delta: number): void {
    const y: number = (this.annualYear > 0 ? this.annualYear : this.book.year) + delta;
    this.rebuildAnnual(y);
  }

  // ================= 相关单位（数据）=================
  /** 首次启动把打包的种子月份写入加密存档（测试用；导入一次后写标记）。 */
  private async importSeedIfNeeded(): Promise<void> {
    const store = this.store;
    const settings = this.settings;
    if (store === null || settings === null) {
      return;
    }
    const done: string | null = await settings.loadText('seed_imported');
    if (done === '1') {
      return;
    }
    try {
      const ctx = this.getUIContext().getHostContext() as common.UIAbilityContext;
      const bytes: Uint8Array = ctx.resourceManager.getRawFileContentSync('seed_months.json');
      const text: string = util.TextDecoder.create('utf-8').decodeToString(bytes);
      const items: SeedMonth[] = JSON.parse(text) as SeedMonth[];
      for (const it of items) {
        const b: MonthBook = MonthBook.fromDict(it.book);
        await store.saveMonth(b);
      }
      await settings.saveText('seed_imported', '1');
      hilog.info(0x0000, 'ATTD', 'seed imported %{public}d months ok=%{public}s',
        items.length, String(store.cryptoOk()));
    } catch (e) {
      hilog.info(0x0000, 'ATTD', 'seed import failed: %{public}s', `${e}`);
    }
  }

  private async loadUnits(): Promise<void> {
    const st = this.settings;
    if (st === null) {
      return;
    }
    const text: string | null = await st.loadUnitsText();
    if (text === null) {
      this.units = defaultUnits();
      this.unitsState = st.lastError.length > 0 ? `读取失败：${st.lastError}` : '默认模板（未保存）';
    } else {
      try {
        this.units = unitsFromJson(JSON.parse(text) as UnitDict[]);
        this.unitsState = st.cryptoOk() ? `已读取 ${this.units.length} 家` : `已读取 ${this.units.length} 家（未加密：${st.cryptoError()}）`;
      } catch (e) {
        this.units = defaultUnits();
        this.unitsState = `读取失败：${e}`;
      }
    }
    const lockedTxt: string | null = await st.loadText('units_locked');
    this.unitsLocked = lockedTxt === '1';
    hilog.info(0x0000, 'ATTD', 'read units_locked=%{public}s locked=%{public}s err=%{public}s',
      String(lockedTxt), String(this.unitsLocked), st.lastError);
    this.rebuildUnitRows();
  }

  /**
   * 保存单位表。
   * HUKS 加密是异步且较慢的，名称/编号是「每敲一个字」都会触发保存，
   * 所以这里做两件事：输入用防抖（scheduleUnitsSave），写盘串行化（避免并发互相覆盖）。
   */
  private persistUnits(): void {
    const st = this.settings;
    if (st === null) {
      return;
    }
    if (this.unitsSaving) {
      this.unitsPending = true;
      return;
    }
    const list: UnitDict[] = this.units.map((u: RelatedUnit): UnitDict => u.toDict());
    const text: string = JSON.stringify(list);
    this.unitsDirty = false;
    this.unitsSaving = true;
    this.unitsState = '保存中…';
    st.saveUnitsText(text).then((ok: boolean) => {
      this.unitsSaving = false;
      hilog.info(0x0000, 'ATTD', 'units save ok=%{public}s len=%{public}d err=%{public}s',
        String(ok), text.length, st.lastError);
      if (ok) {
        this.unitsState = st.cryptoOk() ? '已保存（加密）' : `已保存（未加密：${st.cryptoError()}）`;
      } else {
        this.unitsState = `仅内存（${st.lastError}）`;
      }
      if (this.unitsPending) {
        this.unitsPending = false;
        this.persistUnits();
      }
    }).catch((e: Error) => {
      this.unitsSaving = false;
      hilog.info(0x0000, 'ATTD', 'units save error: %{public}s', e.message);
      this.unitsState = `保存异常：${e.message}`;
      if (this.unitsPending) {
        this.unitsPending = false;
        this.persistUnits();
      }
    });
  }

  /** 输入防抖：停止输入 500ms 后才真正落盘，避免每次按键都发起一次 HUKS 加密。 */
  private scheduleUnitsSave(): void {
    if (this.unitsTimer >= 0) {
      clearTimeout(this.unitsTimer);
    }
    // 只在第一次改动时改状态文案，减少连续输入期间的重绘次数
    if (!this.unitsDirty) {
      this.unitsState = '待保存…';
    }
    this.unitsDirty = true;
    this.unitsTimer = setTimeout(() => {
      this.unitsTimer = -1;
      this.persistUnits();
    }, 500);
  }

  /** 马上落盘：切页 / 点「保存」/ 页面销毁时调用，避免防抖窗口内的改动丢掉。 */
  private flushPendingUnits(): void {
    if (this.unitsTimer >= 0) {
      clearTimeout(this.unitsTimer);
      this.unitsTimer = -1;
    }
    if (this.unitsDirty) {
      this.persistUnits();
    }
  }

  private rebuildUnitRows(): void {
    const rows: UnitRow[] = [];
    let i: number = 0;
    for (const u of this.units) {
      const row: UnitRow = new UnitRow();
      row.index = i;
      row.role = u.role;
      row.roleLabel = u.typeName();
      row.codeLabel = u.codeLabel();
      row.name = u.name;
      row.code = u.code;
      rows.push(row);
      i = i + 1;
    }
    this.unitRows = rows;
  }

  private afterUnitsChanged(): void {
    this.persistUnits();
    this.rebuildUnitRows();
  }

  private addUnit(role: string = 'contract'): void {
    if (this.unitsLocked) {
      return;
    }
    const r: string = UNIT_SELECTABLE_KEYS.indexOf(role) >= 0 ? role : 'other';
    const target: number = UNIT_SELECTABLE_KEYS.indexOf(r);
    let pos: number = 0;
    for (let i = 0; i < this.units.length; i++) {
      const idx: number = UNIT_SELECTABLE_KEYS.indexOf(this.units[i].role);
      const v: number = idx < 0 ? UNIT_SELECTABLE_KEYS.length : idx;
      if (v <= target) {
        pos = i + 1;
      }
    }
    this.units.splice(pos, 0, new RelatedUnit(r, '', ''));
    this.afterUnitsChanged();
  }

  private addUnitMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    for (const k of UNIT_SELECTABLE_KEYS) {
      const lab: string | undefined = UNIT_ROLE_LABELS.get(k);
      const label: string = lab === undefined ? k : lab;
      out.push({
        value: label, action: () => {
          this.addUnit(k);
        }
      });
    }
    return out;
  }

  private copyText(t: string): void {
    try {
      const data: pasteboard.PasteData = pasteboard.createData(pasteboard.MIMETYPE_TEXT_PLAIN, t);
      pasteboard.getSystemPasteboard().setData(data).catch((e: Error) => {
        this.unitsState = `复制失败：${e.message}`;
      });
    } catch (e) {
      this.unitsState = `复制失败：${e}`;
    }
  }

  /** 行尾动作：工资代发银行 = 复制名称+联行号；其它 = 复制关键词并打开公示系统。 */
  private unitAction(u: UnitRow, site: string): void {
    // 行对象是快照；名称/编号取内存里的实时值，否则改完立刻点会用到旧值
    const real: RelatedUnit = this.units[u.index];
    const name: string = (real === undefined ? u.name : real.name).trim();
    const code: string = (real === undefined ? u.code : real.code).trim();
    if (site === 'copy') {
      const vals: string[] = [];
      if (name.length > 0) {
        vals.push(name);
      }
      if (code.length > 0) {
        vals.push(code);
      }
      if (vals.length === 0) {
        this.unitsState = '请先填写「银行名称」或「联行号 / 账号」，再复制';
        return;
      }
      this.copyText(vals.join('\n'));
      this.unitsState = `已复制到剪贴板：${vals.join(' / ')}`;
      return;
    }
    const term: string = code.length > 0 ? code : name;
    if (term.length === 0) {
      this.unitsState = '请先填写「统一社会信用代码」或「单位名称」，再去搜索';
      return;
    }
    this.copyText(term);
    const siteName: string = site === 'credit' ? '信用中国' : '国家企业信用信息公示系统';
    const url: string = site === 'credit'
      ? 'https://www.creditchina.gov.cn/'
      : 'https://www.gsxt.gov.cn/index.html';
    const ctx = this.getUIContext().getHostContext() as common.UIAbilityContext;
    ctx.openLink(url).catch((e: Error) => {
      this.unitsState = `打开浏览器失败：${e.message}（关键词已复制：${term}）`;
    });
    this.unitsState = `已复制到剪贴板：${term} —— 在「${siteName}」搜索框里粘贴即可`;
  }

  private async toggleUnitsLock(): Promise<void> {
    // 锁之前先把待写内容落盘（输入框可能还在防抖窗口内）
    this.flushPendingUnits();
    this.unitsLocked = !this.unitsLocked;
    // 强制重建所有行：ForEach 对相同 key 不会重新求值，锁定时必须重建才能读到最新文字
    this.rowsKey = this.rowsKey + 1;
    const st = this.settings;
    if (st !== null) {
      const ok: boolean = await st.saveText('units_locked', this.unitsLocked ? '1' : '0');
      hilog.info(0x0000, 'ATTD', 'save units_locked=%{public}s ok=%{public}s err=%{public}s',
        String(this.unitsLocked), String(ok), st.lastError);
    }
    this.rebuildUnitRows();
    this.unitsState = this.unitsLocked
      ? `已锁定（${this.units.length} 家单位）· 名称/编号不可改，「🔍」仍可用`
      : `已解锁（${this.units.length} 家单位）· 可以增删 / 修改单位`;
  }

  // ================= API 配置（最低工资 / 节假日联网查询）=================
  private apiConfig(): ApiConfig {
    const c: ApiConfig = new ApiConfig();
    c.url = this.apiUrl.trim();
    c.model = this.apiModel.trim();
    c.key = this.apiKey.trim();
    return c;
  }

  private async loadApiConfig(): Promise<void> {
    const st = this.settings;
    if (st !== null) {
      const line: string | null = await st.loadText('api_config');
      if (line !== null && line.length > 0) {
        const cells: string[] = line.split('\n');
        this.apiUrl = cells.length > 0 ? cells[0] : '';
        this.apiModel = cells.length > 1 ? cells[1] : '';
        this.apiKey = cells.length > 2 ? cells[2] : '';
      }
    }
    this.refreshApiHint();
  }

  private async saveApiConfig(): Promise<boolean> {
    const st = this.settings;
    if (st === null) {
      return false;
    }
    const text: string = `${this.apiUrl.trim()}\n${this.apiModel.trim()}\n${this.apiKey.trim()}`;
    const ok: boolean = await st.saveText('api_config', text);
    this.refreshApiHint();
    return ok;
  }

  private refreshApiHint(): void {
    const url: string = this.apiUrl.trim();
    if (url.length > 0) {
      const model: string = this.apiModel.trim().length > 0
        ? this.apiModel.trim() : '（未填，联网查询会失败）';
      const keyTag: string = this.apiKey.trim().length > 0 ? '已填 Key' : '无 Key（供不校验 Key 的网关）';
      this.apiHint = `✅ 已配置 API：${url} · 模型 ${model} · ${keyTag}\n` +
        '「🌐 联网查询」「🌐 API 一键铺」会用它；点「📋 用本地表」则完全不联网';
    } else {
      this.apiHint = 'ℹ️ 未配置 API：最低工资/节假日都用内置官方表；未公布年份（如次年）可配 API 后用「🌐 联网查询」获取';
    }
  }

  private apiProviderMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    out.push({
      value: '手动输入', action: () => {
      }
    });
    for (const p of providers()) {
      out.push({
        value: `${p.name} · ${p.base}`, action: () => {
          this.apiUrl = p.base;
          this.apiModel = p.model;
        }
      });
    }
    return out;
  }

  private confirmApiDialog(): void {
    const u: string = this.apiUrl.trim();
    if (u.length > 0 && !u.toLowerCase().startsWith('https://')) {
      this.apiTestState = '为保护 API Key 传输安全，API 地址必须以 https:// 开头';
      return;
    }
    this.apiTestState = '';
    this.saveApiConfig();
    this.apiDlgOpen = false;
  }

  private async runApiTest(): Promise<void> {
    if (this.apiBusy) {
      return;
    }
    this.apiBusy = true;
    this.apiTestState = '⏳ 测试中…';
    const r: ChatResult = await testConnection(this.apiConfig());
    this.apiBusy = false;
    this.apiTestState = r.ok ? `✅ 连接成功：${r.text}` : `❌ ${r.error}`;
  }

  /** 「🌐 联网查询（API）」：只走 API，不回退内置表。 */
  private async fetchWageFromApi(): Promise<void> {
    if (this.isLocked) {
      return;
    }
    if (this.fProvince.length === 0 || this.fRegion.length === 0) {
      this.wageHint = '请先选择省份和地区';
      return;
    }
    if (this.apiUrl.trim().length === 0) {
      this.wageHint = '未配置 API 地址（请先点「⚙️ API 设置」）';
      return;
    }
    this.wageHint = '🌐 正在联网查询…';
    const r: WageApiResult = await fetchWageApi(this.apiConfig(), this.fProvince, this.fRegion,
      this.book.year, this.book.month);
    if (!r.ok) {
      this.wageHint = `联网查询失败：${r.error}`;
      return;
    }
    this.fMinWage = `${r.minWage}`;
    this.fParttimeMin = `${r.parttimeMin}`;
    const b: MonthBook = this.book;
    b.min_wage = r.minWage;
    b.parttime_min = r.parttimeMin;
    // 与桌面版一致：API 取数后，锁定态的加班费/公积金基数跟随新最低工资
    this.syncDerivedFromMinWage();
    this.wageHint = `🌐 API：${r.minWage} 元/月 · ${r.parttimeMin} 元/时（请自行核对）`;
    this.refresh();
  }

  /** 「🌐 API 一键铺（联网）」：用 API 查到的节假日安排铺考勤（失败不回退内置表）。 */
  private async fillOfficialByApi(): Promise<void> {
    if (this.isLocked) {
      this.setBusinessState('月份已锁定，无法 API 铺设');
      return;
    }
    if (this.apiUrl.trim().length === 0) {
      this.setBusinessState('未配置 API 地址（请先到参数页点「⚙️ API 设置」）');
      return;
    }
    this.setBusinessState('🌐 正在联网获取节假日安排…', 60000);
    const r: HolidayApiResult = await fetchHolidaysApi(this.apiConfig(), this.book.year);
    if (!r.ok) {
      this.setBusinessState(`API 一键铺失败：${r.error}`);
      return;
    }
    const sets: HolidaySets = new HolidaySets();
    for (const s of r.statutory) {
      sets.statutory.add(s);
    }
    for (const s of r.rest) {
      sets.rest.add(s);
    }
    for (const s of r.makeup) {
      sets.makeup.add(s);
    }
    if (sets.statutory.size === 0 && sets.rest.size === 0 && sets.makeup.size === 0) {
      // 联网成功但什么都没解析出来：不能拿空数据把整月的 mark 清掉
      this.setBusinessState('获取节假日失败：未返回任何日期（本月未改动）');
      return;
    }
    this.applyHolidaySets(sets, '🌐 API 一键铺');
    // 与内置官方表比对（只提示、不改数据）—— 实测同一模型同一年会给出不同答案
    const official: HolidaySets | null = yearSets(this.book.year);
    if (official !== null) {
      const diff: string[] = [];
      if (!this.sameSet(sets.statutory, official.statutory)) {
        diff.push('法定');
      }
      if (!this.sameSet(sets.rest, official.rest)) {
        diff.push('放假');
      }
      if (!this.sameSet(sets.makeup, official.makeup)) {
        diff.push('补班');
      }
      if (diff.length > 0) {
        this.setBusinessState(this.saveState + ` · ⚠ 与内置官方表不一致（官方 法定${official.statutory.size}/`
          + `放假${official.rest.size}/补班${official.makeup.size}）——差异：${diff.join('、')}，请核对`, 8000);
      }
    }
  }

  // ---- 复制工资项（对应桌面版「📋 复制工资项」）----
  private openCopyDialog(): void {
    this.copyYear = this.book.year;
    this.copyMonth = `${this.book.month}`;
    this.copyHint = '';
    this.copyDlgOpen = true;
  }

  // ================= 月份：历史列表 / 锁定 / 删除 =================
  private async refreshHistory(): Promise<void> {
    const st = this.store;
    const rows: HistRow[] = [];
    if (st !== null) {
      const keys: string[] = st.listMonths();
      for (const k of keys) {
        const parts: string[] = k.split('-');
        const y: number = parseInt(parts[0]);
        const m: number = parseInt(parts[1]);
        const row: HistRow = new HistRow();
        row.y = y;
        row.m = m;
        if (y === this.book.year && m === this.book.month) {
          row.locked = this.book.locked;
          row.current = true;
        } else {
          let b: MonthBook | null = this.cache.get(k) ?? null;
          if (b === null) {
            b = await st.loadMonth(y, m);
            if (b !== null) {
              this.cache.set(k, b);
            }
          }
          row.locked = b !== null && b.locked;
        }
        row.label = `${y} 年 ${m} 月`;
        rows.push(row);
      }
    }
    // 新的月份排在前面（与桌面版侧栏一致）
    rows.sort((a: HistRow, b: HistRow): number => (b.y * 100 + b.m) - (a.y * 100 + a.m));
    this.historyRows = rows;
  }

  /** 切换到指定年月（读存档；无存档则新建带常用工资项的空账本）。 */
  private async goMonth(y: number, m: number): Promise<void> {
    if (y === this.book.year && m === this.book.month) {
      return;
    }
    this.cache.set(this.monthKey(this.book.year, this.book.month), this.book);
    const key: string = this.monthKey(y, m);
    let next: MonthBook | null = this.cache.get(key) ?? null;
    const st = this.store;
    if (next === null && st !== null) {
      next = await st.loadMonth(y, m);
    }
    if (next !== null) {
      this.book = next;
      this.saveState = (st !== null && !st.cryptoOk()) ? `已读取 ${key}（未加密）` : `已读取 ${key}`;
    } else {
      this.book = createBook(y, m, '', true);
      this.saveState = '新月份（未保存）';
    }
    this.cache.set(key, this.book);
    this.isLocked = this.book.locked;
    this.loadParamsForm();
    this.snap = Snap.from(this.book, 1);
    this.selOt = this.book.day(1).overtime_hours.toString();
    this.selLeave = this.book.day(1).leave_hours.toString();
    this.monthLabel = `${y} 年 ${m} 月`;
    await this.refreshHistory();
  }

  /** 月份下拉菜单：已存档月份（🔒 标记锁定）+ 锁定/解锁该月。 */
  private monthMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    if (this.historyRows.length === 0) {
      out.push({
        value: '（暂无已存月份）', action: () => {
        }
      });
      return out;
    }
    for (const r of this.historyRows) {
      const mark: string = r.locked ? '🔒 ' : '';
      const cur: string = r.current ? '✓ ' : '';
      out.push({
        value: `${cur}${mark}${r.label}`, action: () => {
          this.goMonth(r.y, r.m);
        }
      });
    }
    return out;
  }

  private toggleMonthLock(): void {
    const b: MonthBook = this.book;
    const next: boolean = !b.locked;
    b.locked = next;
    this.isLocked = next;
    this.persist();
    this.refreshHistory();
    this.saveState = next ? `已锁定 ${b.year}-${pad2(b.month)} · 只读` : `已解锁 ${b.year}-${pad2(b.month)}`;
  }

  /** 从历史月份右键菜单：锁定 / 解锁指定月份（不切换当前月份）。 */
  private async setMonthLock(y: number, m: number, locked: boolean): Promise<void> {
    const st = this.store;
    if (st === null) {
      return;
    }
    const key: string = this.monthKey(y, m);
    let b: MonthBook | null = this.cache.get(key) ?? null;
    if (b === null) {
      b = await st.loadMonth(y, m);
    }
    if (b === null) {
      return;
    }
    b.locked = locked;
    const ok: boolean = await st.saveMonth(b);
    if (!ok) {
      this.saveState = `切换锁定失败：${st.lastError}`;
      return;
    }
    this.cache.set(key, b);
    if (b.year === this.book.year && b.month === this.book.month) {
      this.book.locked = locked;
      this.isLocked = locked;
    }
    this.saveState = `${locked ? '已锁定' : '已解锁'} ${y}-${pad2(m)}`;
    await this.refreshHistory();
  }

  /** 删除当前月份（锁定月不允许删除）。 */
  private async deleteCurrentMonth(): Promise<void> {
    const b: MonthBook = this.book;
    if (b.locked) {
      this.saveState = '已取消：月份已锁定（先解锁再删除）';
      return;
    }
    const st: MonthStorage | null = this.store;
    if (st === null) {
      return;
    }
    // 删除前清掉待写标记：否则防抖窗口内的那次写盘会把刚删的月份又写回去
    this.cancelPendingSave();
    const y: number = b.year;
    const m: number = b.month;
    const ok: boolean = st.deleteMonth(y, m);
    if (!ok) {
      this.saveState = `删除失败：${st.lastError}`;
      return;
    }
    this.cache.delete(this.monthKey(y, m));
    this.book = createBook(y, m, '', true);
    this.isLocked = false;
    this.loadParamsForm();
    this.refresh(false);
    this.monthLabel = `${y} 年 ${m} 月`;
    this.saveState = `已删除 ${y}-${pad2(m)}（现为空月份）`;
    await this.refreshHistory();
  }
  private shiftCopyMonth(delta: number): void {
    let y: number = this.copyYear;
    let m: number = parseInt(this.copyMonth);
    if (isNaN(m)) {
      m = this.book.month;
    }
    m = m + delta;
    if (m > 12) {
      m = 1;
      y = y + 1;
    } else if (m < 1) {
      m = 12;
      y = y - 1;
    }
    this.copyYear = y;
    this.copyMonth = `${m}`;
  }

  /** 把当前月「工资项 + 固定加班工资 + 大病医疗补助」复制到目标年月（不存在则新建）。 */
  private async doCopyPayItems(): Promise<void> {
    if (this.isLocked) {
      this.copyHint = '月份已锁定，无法复制工资项（先点 🔒 解锁）';
      return;
    }
    const y: number = this.copyYear;
    const m: number = parseInt(this.copyMonth);
    if (isNaN(m) || m < 1 || m > 12) {
      this.copyHint = '月份需在 1–12 之间';
      return;
    }
    if (y === this.book.year && m === this.book.month) {
      this.copyHint = '不能复制到当前月份';
      return;
    }
    const st = this.store;
    if (st === null) {
      this.copyHint = '存储未初始化';
      return;
    }
    const key: string = this.monthKey(y, m);
    let tgt: MonthBook | null = this.cache.get(key) ?? null;
    if (tgt === null) {
      tgt = await st.loadMonth(y, m);
    }
    const created: boolean = tgt === null;
    if (tgt === null) {
      tgt = createBook(y, m);
      tgt.pay_items = [];
    }
    // 深拷贝工资项；按出勤津贴会在目标月按实际上班天数自动重算
    const items: PayItem[] = [];
    for (const it of this.book.pay_items) {
      items.push(new PayItem(it.name, it.type, it.amount));
    }
    tgt.pay_items = items;
    tgt.fixed_overtime_wage = this.book.fixed_overtime_wage;
    tgt.big_disease = this.book.big_disease;
    this.cache.set(key, tgt);
    const ok: boolean = await st.saveMonth(tgt);
    if (!ok) {
      this.copyHint = `保存失败：${st.lastError}`;
      return;
    }
    this.copyDlgOpen = false;
    this.saveState = `已${created ? '新建' : '覆盖'} ${y} 年 ${m} 月（工资项已复制）`;
  }

  private setUnitName(i: number, v: string): void {
    if (this.unitsLocked) {
      return;
    }
    if (i < 0 || i >= this.units.length) {
      return;
    }
    this.units[i].name = v;
    // 同步快照：ForEach 用的是 unitRows，不同步的话一旦重绘就回退成旧文字
    if (i < this.unitRows.length) {
      this.unitRows[i].name = v;
    }
    // 只落盘，不重建行：重建会换掉 TextInput 节点 → 每敲一个字就失焦
    this.scheduleUnitsSave();
  }

  private setUnitCode(i: number, v: string): void {
    if (this.unitsLocked) {
      return;
    }
    if (i < 0 || i >= this.units.length) {
      return;
    }
    this.units[i].code = v;
    // 同步快照，理由同上
    if (i < this.unitRows.length) {
      this.unitRows[i].code = v;
    }
    this.scheduleUnitsSave();
  }

  private setUnitType(i: number, k: string): void {
    if (this.unitsLocked) {
      return;
    }
    if (i >= 0 && i < this.units.length) {
      this.units[i].role = k;
      this.afterUnitsChanged();
    }
  }

  private removeUnit(i: number): void {
    if (this.unitsLocked) {
      return;
    }
    if (i >= 0 && i < this.units.length) {
      this.units.splice(i, 1);
      this.afterUnitsChanged();
    }
  }

  // ================= 侧栏 =================
  /** 历史月份右键菜单：跳转 / 锁定解锁（对应桌面版的 _show_history_menu）。 */
  @Builder
  histMenu(r: HistRow) {
    Menu() {
      MenuItem({ content: `${r.label} · ${r.locked ? '🔒 已锁定' : '🔓 未锁定'}` })
        .enabled(false)
      MenuItem({ content: '↪ 跳转到该月' })
        .onClick(() => this.goMonth(r.y, r.m))
      MenuItem({ content: r.locked ? '🔓 解除锁定' : '🔒 锁定该月' })
        .onClick(() => this.setMonthLock(r.y, r.m, !r.locked))
    }
  }

  @Builder
  navButton(item: NavItem) {
    Row({ space: 10 }) {
      Text(item.icon).fontSize(16)
      Text(item.label)
        .fontSize(14)
        .fontColor(this.pageKey === item.key ? '#FFFFFF' : '#3F4A5A')
        .fontWeight(this.pageKey === item.key ? FontWeight.Medium : FontWeight.Normal)
        .layoutWeight(1)
    }
    .width('100%')
    .height(40)
    .padding({ left: 12, right: 12 })
    .borderRadius(8)
    .backgroundColor(this.pageKey === item.key ? C_ACCENT : '#00000000')
    .onClick(() => {
      this.flushPendingUnits();
      if (item.key === 'annual') {
        this.rebuildAnnual();
      }
      if (item.key === 'params' && this.pageKey !== 'params') {
        // 桌面版每次进入参数页都会重建卡片 → 锁定态的加班费/公积金基数取月最低工资
        this.syncLockedParamsOnEnter();
      }
      this.pageKey = item.key;
    })
  }

  @Builder
  sidebar() {
    Column() {
      Column({ space: 2 }) {
        Text('📋 工作考勤表').fontSize(16).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
        Text('月度考勤 · 工资核算').fontSize(11).fontColor(C_HINT)
      }
      .alignItems(HorizontalAlign.Start)
      .width('100%')
      .padding({ left: 12, top: 4, bottom: 16 })

      ForEach(this.groups, (g: NavGroup) => {
        Column({ space: 4 }) {
          if (g.title.length > 0) {
            Text(g.title)
              .fontSize(11)
              .fontColor(C_HINT)
              .padding({ left: 12, top: 8, bottom: 2 })
              .width('100%')
          }
          ForEach(g.items, (it: NavItem) => {
            this.navButton(it)
          }, (it: NavItem) => `${it.key}-${this.pageKey === it.key}`)
        }
        .width('100%')
      }, (g: NavGroup) => `${g.title}-${this.pageKey}`)

      Text('历史月份')
        .fontSize(11)
        .fontColor(C_HINT)
        .width('100%')
        .padding({ left: 12, top: 14, bottom: 4 })

      List({ space: 2 }) {
        ForEach(this.historyRows, (r: HistRow) => {
          ListItem() {
            Row({ space: 4 }) {
              if (r.locked) {
                Text('🔒').fontSize(10)
              }
              Text(r.label)
                .fontSize(12)
                .fontColor(r.current ? C_ACCENT : C_SUB)
                .fontWeight(r.current ? FontWeight.Bold : FontWeight.Normal)
                .layoutWeight(1)
            }
            .width('100%')
            .padding({ left: 10, right: 8, top: 6, bottom: 6 })
            .borderRadius(7)
            .backgroundColor(r.current ? '#EEF2FF' : '#00000000')
            .onClick(() => this.goMonth(r.y, r.m))
            .bindContextMenu(this.histMenu(r), ResponseType.RightClick)
          }
        }, (r: HistRow) => `${r.y}-${r.m}-${r.locked}-${r.current}`)
      }
      .layoutWeight(1)
      .width('100%')
      .scrollBar(BarState.Auto)
    }
    .width(208)
    .height('100%')
    .padding({ left: 12, right: 12, top: 18 })
    .backgroundColor(BG_CARD)
    .border({ width: { right: 1 }, color: '#E5E7EB' })
  }

  // ================= 顶栏 / 数值条 =================
  @Builder
  topBar() {
    Row({ space: 10 }) {
      Column({ space: 1 }) {
        Text(this.pageTitle()).fontSize(16).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
        Text(this.pageSub()).fontSize(11).fontColor(C_HINT)
      }
      .alignItems(HorizontalAlign.Start)
      Blank()
      Text(this.saveState).fontSize(11).fontColor(C_HINT)
      Button('保存')
        .type(ButtonType.Normal)
        .fontSize(12)
        .height(30)
        .padding({ left: 14, right: 14 })
        .backgroundColor(C_ACCENT)
        .fontColor('#FFFFFF')
        .borderRadius(8)
        .onClick(() => {
          this.flushPendingUnits();
          // 用户主动点保存：即使没有待写改动也写一次（给明确反馈）
          this.savePending = true;
          this.flushSave();
        })
      Button('关于')
        .type(ButtonType.Normal)
        .fontSize(12)
        .height(30)
        .padding({ left: 12, right: 12 })
        .backgroundColor('#FFFFFF')
        .fontColor('#667085')
        .border({ width: 1, color: '#E6E8F0' })
        .borderRadius(8)
        .onClick(() => {
          this.aboutOpen = true;
        })
    }
    .width('100%')
    .height(56)
    .padding({ left: 20, right: 20 })
    .backgroundColor(BG_CARD)
    .border({ width: { bottom: 1 }, color: '#E5E7EB' })
  }

  /** 月份操作条：上月 / 月份下拉 / 锁定 / 下月 / 删除本月（相关单位页不显示）。 */
  @Builder
  monthBar() {
    Column() {
      Row({ space: 8 }) {
        Button('‹ 上月')
          .type(ButtonType.Normal)
          .fontSize(13)
          .height(32)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => this.changeMonth(-1))
        Text(`${this.monthLabel} ▾`)
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor(C_TEXT)
          .constraintSize({ minWidth: 132 })
          .textAlign(TextAlign.Center)
          .padding({ left: 14, right: 14, top: 6, bottom: 6 })
          .backgroundColor('#FFFFFF')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .bindMenu(this.monthMenu())
        Button(this.isLocked ? '🔒' : '🔓')
          .type(ButtonType.Normal)
          .fontSize(14)
          .height(32)
          .width(38)
          .padding(0)
          .backgroundColor(this.isLocked ? '#FEF4E6' : '#FFFFFF')
          .fontColor(this.isLocked ? '#B54708' : '#475467')
          .border({ width: 1, color: this.isLocked ? '#FEDF89' : '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => this.toggleMonthLock())
        Button('下月 ›')
          .type(ButtonType.Normal)
          .fontSize(13)
          .height(32)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => this.changeMonth(1))
        Blank()
        Button('删除本月')
          .type(ButtonType.Normal)
          .fontSize(13)
          .height(32)
          .padding({ left: 14, right: 14 })
          .backgroundColor('#FFFFFF')
          .fontColor(this.isLocked ? '#D1D5DB' : '#D92D20')
          .border({ width: 1, color: this.isLocked ? '#E6E8F0' : '#FCD0CB' })
          .borderRadius(8)
          .enabled(!this.isLocked)
          .onClick(() => this.deleteCurrentMonth())
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 8, bottom: 8 })

      if (this.isLocked) {
        Row() {
          Text('🔒  当前月份已锁定 · 仅供查看，所有修改操作已屏蔽')
            .fontSize(11)
            .fontColor('#B54708')
        }
        .width('100%')
        .padding({ left: 20, right: 20, top: 6, bottom: 6 })
        .backgroundColor('#FEF4E6')
      }
    }
    .width('100%')
    .backgroundColor(BG_CARD)
    .border({ width: { bottom: 1 }, color: '#E5E7EB' })
  }

  @Builder
  strip() {
    Row({ space: 0 }) {
      StripItem({ title: '应发合计', value: this.snap.gross, accent: C_TEXT }).layoutWeight(1)
      StripItem({ title: '计入最低工资', value: this.snap.inWage, accent: C_ACCENT }).layoutWeight(1)
      StripItem({ title: '不计入', value: this.snap.outWage, accent: C_SUB }).layoutWeight(1)
      StripItem({ title: '预计到手', value: this.snap.takeHome, accent: C_OK }).layoutWeight(1)
      Divider().vertical(true).height(22).color('#E5E7EB').margin({ left: 6, right: 12 })
      MetaItem({ title: '上班', value: `${this.snap.workDays} 天` })
      MetaItem({ title: '月工时', value: `${this.snap.monthlyHours}h` })
    }
    .width('100%')
    .height(56)
    .padding({ left: 18, right: 18 })
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }

  // ================= 工作台 =================
  @Builder
  overviewPage() {
    // 与桌面版一致：lay.addWidget(left, 1) + lay.addStretch(1) → 内容占一半，右半留白
    Row() {
      Column({ space: 12 }) {
      // hero：实际到手工资（桌面版 pages_overview 的 hero 卡）
      Column({ space: 6 }) {
        Text(`实际到手工资 · ${this.snap.year} 年 ${this.snap.month} 月`)
          .fontSize(12)
          .fontColor('#C7D2FE')
        Text(`¥ ${this.snap.takeHome}`)
          .fontSize(32)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')
        Text(`应发 ¥ ${this.snap.gross} · 个人扣除 ¥ ${this.snap.deductTotal} · 请假扣 ¥ ${this.snap.leaveDeductionTotal}`)
          .fontSize(12)
          .fontColor('#CBD5E1')
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 18, bottom: 18 })
      .alignItems(HorizontalAlign.Start)
      .backgroundColor('#1E3A8A')
      .borderRadius(14)

      Row({ space: 8 }) {
        StatCard({ title: '应发工资合计', value: `¥ ${this.snap.gross}`, sub: '', accent: C_TEXT })
          .layoutWeight(1)
        StatCard({ title: '公司总成本', value: `¥ ${this.snap.companyCost}`, sub: '', accent: '#0F766E' })
          .layoutWeight(1)
        StatCard({ title: '提供正常劳动', value: this.snap.normalLaborText, sub: '', accent: C_ACCENT })
          .layoutWeight(1)
        StatCard({ title: '加班 / 请假', value: this.snap.otLeaveText, sub: '', accent: '#B54708' })
          .layoutWeight(1)
      }
      .width('100%')

      // 合规判定（左） + 公司每小时成本（右）并排
      // ⚠ 不能用 Flex：Flex 默认高度撑满父容器剩余空间，两卡会被拉到很高
      Row({ space: 12 }) {
        Column({ space: 10 }) {
          Text('合规判定').fontSize(14).fontWeight(FontWeight.Bold).fontColor('#334155')
          Row({ space: 10 }) {
            Text(this.snap.minWageOk ? '✓' : '!')
              .fontSize(12)
              .fontWeight(FontWeight.Bold)
              .fontColor('#FFFFFF')
              .width(20)
              .height(20)
              .textAlign(TextAlign.Center)
              .backgroundColor(this.snap.minWageOk ? '#12B76A' : '#F79009')
              .borderRadius(10)
            Column({ space: 1 }) {
              Text('计入最低工资标准的工资').fontSize(12).fontWeight(FontWeight.Bold).fontColor('#101828')
              Text(this.snap.minWageDetail).fontSize(11).fontColor('#667085')
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
          }
          .width('100%')
          Row({ space: 10 }) {
            Text(this.snap.workTimeLegal ? '✓' : '!')
              .fontSize(12)
              .fontWeight(FontWeight.Bold)
              .fontColor('#FFFFFF')
              .width(20)
              .height(20)
              .textAlign(TextAlign.Center)
              .backgroundColor(this.snap.workTimeLegal ? '#12B76A' : '#F79009')
              .borderRadius(10)
            Column({ space: 1 }) {
              Text('工时与加班合规').fontSize(12).fontWeight(FontWeight.Bold).fontColor('#101828')
              Text(this.snap.workTimeDetail).fontSize(11).fontColor('#667085')
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
          }
          .width('100%')
        }
        .layoutWeight(1)
        .onAreaChange((_old: Area, now: Area) => {
          const h = Number(now.height);
          if (h > 0 && Math.abs(h - this.cmpCardHeight) > 0.5) {
            this.cmpCardHeight = h;
          }
        })
        .padding(16)
        .alignItems(HorizontalAlign.Start)
        .backgroundColor(BG_CARD)
        .borderRadius(12)

        Column({ space: 6 }) {
          Text('公司每小时成本（仅参考）').fontSize(12).fontColor(C_SUB)
          // 桌面版 Card 的 body 只有一行 QLabel，卡片被拉平后文字在剩余空间里垂直居中
          Column() {
            Text(this.snap.hasHourlyCost
              ? `¥ ${this.snap.companyHourlyCost} / h  （参考最低 ¥ ${this.snap.parttimeMinText} / h）`
              : '待录入考勤 / 工时后显示')
              .fontSize(13)
              .fontWeight(FontWeight.Bold)
              .fontColor(this.snap.hasHourlyCost ? '#0F766E' : '#98A2B3')
          }
          .width('100%')
          .layoutWeight(1)
          .justifyContent(FlexAlign.Center)
          .alignItems(HorizontalAlign.Start)
        }
        // 桌面版 width = sizeHint（实测 1920 窗口下约 196），这里取 220 保证文字不折行
        .width(220)
        // 高度跟随左侧合规卡（桌面版两卡在同一个 QHBoxLayout 里会被拉平）。
        // ⚠ 不能用 alignSelf(ItemAlign.Stretch)：它会让外层 Row 被撑满剩余高度。
        .height(this.cmpCardHeight > 0 ? this.cmpCardHeight : 132)
        // 桌面版 margins=(12, 10, 12, 10)
        .padding({ left: 12, right: 12, top: 10, bottom: 10 })
        .alignItems(HorizontalAlign.Start)
        .backgroundColor(BG_CARD)
        .borderRadius(12)
      }
      .width('100%')
      .alignItems(VerticalAlign.Top)
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }
    .width('100%')
    .alignItems(VerticalAlign.Top)
  }

  // ================= 考勤日历 =================
  @Builder
  calendarPage() {
    Row({ space: 14 }) {
      Column({ space: 8 }) {
        Row({ space: 8 }) {
          Blank()
          Button('🌐 API 一键铺（联网）')
            .type(ButtonType.Normal)
            .fontSize(11)
            .height(30)
            .enabled(!this.isLocked)
            .backgroundColor('#ECFDF5')
            .fontColor('#065F46')
            .onClick(() => this.fillOfficialByApi())
          Button('📋 铺本地表（法定节假日/调休）')
            .type(ButtonType.Normal)
            .fontSize(11)
            .height(30)
            .enabled(!this.isLocked)
            .backgroundColor('#F5F3FF')
            .fontColor('#5B21B6')
            .onClick(() => this.fillOfficial())
          Button('✨ 一键铺（周末休/工作日上）')
            .type(ButtonType.Normal)
            .fontSize(11)
            .height(30)
            .enabled(!this.isLocked)
            .backgroundColor('#EEF2FF')
            .fontColor('#4F46E5')
            .onClick(() => this.fillDefaultCalendar())
          Button('清空考勤')
            .type(ButtonType.Normal)
            .fontSize(11)
            .height(30)
            .enabled(!this.isLocked)
            .backgroundColor('#FEF2F2')
            .fontColor(C_BAD)
            .onClick(() => this.clearAttendance())
        }
        .width('100%')

        Text('「铺本地表 / API 一键铺」只覆盖周末、法定节假日、调休三类日期（并把「法定节假日」标记整月重写）；' +
          '其余普通工作日的状态不动，手填的请假不受影响。')
          .fontSize(10)
          .fontColor(C_HINT)
          .width('100%')

        Flex({ wrap: FlexWrap.Wrap }) {
          ForEach(this.snap.calStats, (s: CalStat) => {
            Text(`${s.label} ${s.value}`)
              .fontSize(11)
              .fontColor('#475467')
              .backgroundColor('#F8FAFC')
              .border({ width: 1, color: '#E6E8F0' })
              .borderRadius(999)
              .padding({ left: 9, right: 9, top: 4, bottom: 4 })
              .margin({ right: 6, bottom: 6 })
          }, (s: CalStat) => `${s.label}-${s.value}`)
        }
        .width('100%')

        Text(`考勤 · ${this.snap.year} 年 ${this.snap.month} 月`)
          .fontSize(13)
          .fontWeight(FontWeight.Bold)
          .fontColor('#334155')
          .width('100%')

        Row({ space: 6 }) {
          ForEach(['一', '二', '三', '四', '五', '六', '日'], (w: string) => {
            Text(w).fontSize(11).fontColor(C_HINT).layoutWeight(1).textAlign(TextAlign.Center)
          }, (w: string) => w)
        }
        .width('100%')

        ForEach(this.snap.weeks, (week: CalCell[], wi: number) => {
          Row({ space: 6 }) {
            ForEach(week, (c: CalCell, ci: number) => {
              if (c.day === 0) {
                Column().layoutWeight(1).height(62)
              } else {
                DayCell({
                  num: c.day,
                  midText: c.midText,
                  hoursText: c.hoursText,
                  selected: c.day === this.snap.selDay,
                  bg: dayPaletteOf(c.status).bg,
                  fg: dayPaletteOf(c.status).fg,
                  weekendEmpty: c.weekend && c.status.length === 0,
                  onPick: () => {
                    this.selectDay(c.day);
                  }
                })
                  .layoutWeight(1)
              }
              // ⚠ key 必须带索引：月初多个占位格 day 都是 0，否则 key 重复会被丢弃
            }, (c: CalCell, ci: number) => `${ci}-${this.cellKey(c)}`)
          }
          .width('100%')
        }, (week: CalCell[], wi: number) => `${wi}-${this.rowKey(week)}`)

        Flex({ wrap: FlexWrap.Wrap }) {
          ForEach(DAY_PALETTES, (p: DayPalette) => {
            Text(p.status)
              .fontSize(9)
              .fontColor(p.fg)
              .backgroundColor(p.bg)
              .borderRadius(4)
              .padding({ left: 6, right: 6, top: 2, bottom: 2 })
              .margin({ right: 5, top: 4 })
          }, (p: DayPalette) => p.status)
        }
        .width('100%')
      }
      .layoutWeight(1)
      .padding(16)
      .alignItems(HorizontalAlign.Start)
      .backgroundColor(BG_CARD)
      .borderRadius(12)

      // 右侧当天编辑
      Column({ space: 10 }) {
        Text(`${this.snap.month} 月 ${this.snap.selDay} 日`)
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor(C_TEXT)
        Text(this.snap.selSubtitle).fontSize(11).fontColor(C_HINT)

        Text('状态').fontSize(12).fontColor(C_SUB).width('100%')
        Row({ space: 6 }) {
          ForEach(STATUS_LABELS.slice(0, 5), (s: string) => {
            Chip({
              label: s,
              active: this.chipActive(s),
              disabled: this.isLocked,
              onTap: () => {
                this.setStatus(s);
              }
            })
          }, (s: string) => `${s}-${this.chipActive(s)}`)
        }
        .width('100%')

        Row({ space: 6 }) {
          ForEach(STATUS_LABELS.slice(5), (s: string) => {
            Chip({
              label: s,
              active: this.chipActive(s),
              disabled: this.isLocked,
              onTap: () => {
                this.setStatus(s);
              }
            })
          }, (s: string) => `${s}-${this.chipActive(s)}`)
          Chip({
            label: '未填',
            active: this.snap.selStatus.length === 0,
            disabled: this.isLocked,
            onTap: () => {
              this.setStatus('');
            }
          })
        }
        .width('100%')

        Text('标记').fontSize(12).fontColor(C_SUB).width('100%')
        Row({ space: 6 }) {
          Chip({ label: '无', active: this.snap.selMark === 0, disabled: this.isLocked, onTap: () => this.setMark(0) })
          Chip({ label: '法定节假日', active: this.snap.selMark === 1, disabled: this.isLocked, onTap: () => this.setMark(1) })
          Chip({ label: '视为正常劳动', active: this.snap.selMark === 2, disabled: this.isLocked, onTap: () => this.setMark(2) })
        }
        .width('100%')

        Text('当天工时').fontSize(12).fontColor(C_SUB).width('100%')
        Row({ space: 10 }) {
          Text('加班').fontSize(12).fontColor(C_SUB).width(40)
          TextInput({ text: this.selOt })
            .type(InputType.NUMBER_DECIMAL)
            .height(32)
            .fontSize(13)
            .layoutWeight(1)
            .enabled(!this.isLocked)
            .onChange((v: string) => this.setOt(v))
          Text('小时').fontSize(11).fontColor(C_HINT).width(32)
        }
        .width('100%')

        Row({ space: 10 }) {
          Text('请假').fontSize(12).fontColor(C_SUB).width(40)
          TextInput({ text: this.selLeave })
            .type(InputType.NUMBER_DECIMAL)
            .height(32)
            .fontSize(13)
            .layoutWeight(1)
            .enabled(!this.isLocked)
            .onChange((v: string) => this.setLeave(v))
          Text('小时').fontSize(11).fontColor(C_HINT).width(32)
        }
        .width('100%')
      }
      .width(300)
      .padding(16)
      .alignItems(HorizontalAlign.Start)
      .backgroundColor(BG_CARD)
      .borderRadius(12)
    }
    .width('100%')
    .alignItems(VerticalAlign.Top)
  }

  // ================= 参数页 =================
  @Builder
  paramsPage() {
    Stack() {
      Scroll() {
        Column({ space: 12 }) {
          // ---------- 参数模板条 ----------
          Row({ space: 10 }) {
            Text('参数模板').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
            Text(this.tplNames.length === 0 ? '（暂无已存模板）' : `${this.tplSel} ▾`)
              .fontSize(12)
              .fontColor(this.tplNames.length === 0 ? C_HINT : C_ACCENT)
              .padding({ left: 10, right: 10, top: 5, bottom: 5 })
              .borderRadius(8)
              .backgroundColor('#FFFFFF')
              .border({ width: 1, color: '#E6E8F0' })
              .bindMenu(this.tplMenu())
            Button('存为模板…')
              .type(ButtonType.Normal)
              .fontSize(12)
              .height(30)
              .backgroundColor('#FFFFFF')
              .fontColor('#475467')
              .border({ width: 1, color: '#E6E8F0' })
              .borderRadius(8)
              .onClick(() => this.openTplDialog('save'))
            Button('重命名')
              .type(ButtonType.Normal)
              .fontSize(12)
              .height(30)
              .backgroundColor('#FFFFFF')
              .fontColor('#475467')
              .border({ width: 1, color: '#E6E8F0' })
              .borderRadius(8)
              .onClick(() => this.openTplDialog('rename'))
            Button('删除')
              .type(ButtonType.Normal)
              .fontSize(12)
              .height(30)
              .backgroundColor('#FFFFFF')
              .fontColor('#D92D20')
              .border({ width: 1, color: '#FCD0CB' })
              .borderRadius(8)
              .onClick(() => this.openTplDialog('delete'))
            Button('套用到本月')
              .type(ButtonType.Normal)
              .fontSize(12)
              .height(30)
              .backgroundColor(C_ACCENT)
              .fontColor('#FFFFFF')
              .borderRadius(8)
              .onClick(() => this.applyTemplate())
            Blank()
            Text('整组参数存为模板，新建月份 / 换人时一键套用')
              .fontSize(10)
              .fontColor(C_HINT)
          }
          .width('100%')
          .padding(16)
          .backgroundColor(BG_CARD)
          .borderRadius(12)

          // ---------- 4 张参数卡（宽屏两列 / 窄屏单列） ----------
          Flex({ wrap: FlexWrap.Wrap, justifyContent: FlexAlign.SpaceBetween }) {
            this.socialCard()
            this.wageCard()
            this.leaveCard()
            this.noteCard()
          }
          .width('100%')

          if (this.tplHint.length > 0) {
            Text(this.tplHint).fontSize(11).fontColor(C_SUB).width('100%')
          }
          Text(`存档：${this.store === null ? '—' : this.store.location()}`)
            .fontSize(10)
            .fontColor(C_HINT)
            .width('100%')
        }
        .width('100%')
        .padding({ left: 18, right: 18, top: 14, bottom: 18 })
        .alignItems(HorizontalAlign.Start)
      }
      .width('100%')
      .height('100%')
      .scrollBar(BarState.Auto)

      if (this.tplDlgOpen) {
        this.tplDialog()
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  socialCard() {
    Column({ space: 10 }) {
      Text('社保 / 公积金').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text('五险一金基数与比例（比例填小数，0.105 = 10.5%；公积金基数默认=最低工资，可点 🔓 解锁手动改）')
        .fontSize(10)
        .fontColor(C_HINT)
        .width('100%')
      FieldRow({
        label: '社保缴费基数', value: this.fSocialBase, unit: '元',
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fSocialBase = v;
          this.applyParam('social_base', v);
        }
      })
      FieldRow({
        label: '个人社保比例', value: this.fPersonalSocialRate, unit: '', tip: '小数，0.105 = 10.5%',
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fPersonalSocialRate = v;
          this.applyParam('personal_social_rate', v);
        }
      })
      FieldRow({
        label: '公司社保比例', value: this.fCompanySocialRate, unit: '', tip: '小数，0.24 = 24%',
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fCompanySocialRate = v;
          this.applyParam('company_social_rate', v);
        }
      })
      FieldRow({
        label: '个人公积金比例', value: this.fPersonalFundRate, unit: '', tip: '小数，0.07 = 7%',
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fPersonalFundRate = v;
          this.applyParam('personal_fund_rate', v);
        }
      })
      FieldRow({
        label: '公司公积金比例', value: this.fCompanyFundRate, unit: '', tip: '小数，0.07 = 7%',
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fCompanyFundRate = v;
          this.applyParam('company_fund_rate', v);
        }
      })
      FieldRow({
        label: '公积金缴费基数', value: this.fFundBase, unit: '元',
        disabled: this.isLocked,
        tip: '默认与本地月最低工资同步；如需特殊基数，请点击右侧「🔒」解锁后修改',
        locked: this.fFundBaseLocked,
        lockable: true,
        onEdit: (v: string) => {
          this.fFundBase = v;
          this.applyParam('fund_base', v);
        },
        onToggleLock: () => this.toggleFundBaseLock()
      })
    }
    .width('48%')
    .constraintSize({ minWidth: 360 })
    .padding(16)
    .margin({ bottom: 12 })
    .alignItems(HorizontalAlign.Start)
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }

  @Builder
  wageCard() {
    Column({ space: 10 }) {
      Text('工资与工时标准').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text(this.apiHint)
        .fontSize(10)
        .fontColor(this.apiUrl.length > 0 ? '#0B7A3B' : C_HINT)
        .width('100%')
      Row({ space: 8 }) {
        Button('⚙️ API 设置')
          .type(ButtonType.Normal)
          .fontSize(11)
          .height(28)
          .padding({ left: 10, right: 10 })
          .backgroundColor('#F8FAFC')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => {
            this.apiTestState = '';
            this.apiDlgOpen = true;
          })
        Blank()
      }
      .width('100%')

      Row({ space: 8 }) {
        Text('工作地').fontSize(11).fontColor('#667085').width(48)
        Text(this.fProvince.length === 0 ? '请选择省份 ▾' : `${this.fProvince} ▾`)
          .fontSize(12)
          .fontColor(this.fProvince.length === 0 ? C_HINT : C_TEXT)
          .padding({ left: 8, right: 8, top: 5, bottom: 5 })
          .layoutWeight(1)
          .borderRadius(8)
          .backgroundColor('#FFFFFF')
          .border({ width: 1, color: '#E6E8F0' })
          .bindMenu(this.provinceMenu())
        Text(this.fRegion.length === 0 ? '请选择地区 ▾' : `${this.fRegion} ▾`)
          .fontSize(12)
          .fontColor(this.fRegion.length === 0 ? C_HINT : C_TEXT)
          .padding({ left: 8, right: 8, top: 5, bottom: 5 })
          .layoutWeight(1)
          .borderRadius(8)
          .backgroundColor('#FFFFFF')
          .border({ width: 1, color: '#E6E8F0' })
          .bindMenu(this.regionMenu())
      }
      .width('100%')

      Row({ space: 8 }) {
        Button('📋 用本地表')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .layoutWeight(1)
          .enabled(!this.isLocked)
          .backgroundColor('#F5F3FF')
          .fontColor('#5B21B6')
          .borderRadius(8)
          .onClick(() => this.useLocalWageTable())
        Button('🌐 联网查询（API）')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .layoutWeight(1)
          .enabled(!this.isLocked)
          .backgroundColor('#ECFDF5')
          .fontColor('#065F46')
          .borderRadius(8)
          .onClick(() => this.fetchWageFromApi())
      }
      .width('100%')
      if (this.wageHint.length > 0) {
        Text(this.wageHint).fontSize(10).fontColor(C_HINT).width('100%')
      }

      FieldRow({
        label: '月最低工资', value: this.fMinWage, unit: '元',
        locked: this.fWageLocked,
        lockable: true,
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fMinWage = v;
          this.applyParam('min_wage', v);
        },
        onToggleLock: () => this.toggleWageLock()
      })
      FieldRow({
        label: '非全日制小时最低工资', value: this.fParttimeMin, unit: '元/时',
        locked: this.fWageLocked,
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fParttimeMin = v;
          this.applyParam('parttime_min', v);
        }
      })
      FieldRow({
        label: '加班费计算基数', value: this.fOvertimeBase, unit: '元',
        tip: '默认与本地月最低工资同步；如需特殊基数，请点击右侧「🔒」解锁后修改',
        locked: this.otBaseLocked,
        lockable: true,
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fOvertimeBase = v;
          this.applyParam('overtime_base', v);
        },
        onToggleLock: () => this.toggleOtBaseLock()
      })
      FieldRow({
        label: '24小时内工时', value: this.fHoursPerDay, unit: '小时',
        disabled: this.isLocked,
        tip: '第 N 次下班 → 第 N+1 次上班结束的 24 小时（正常一个周期应为 24 小时；不是 24 小时说明排班有问题）',
        onEdit: (v: string) => {
          this.fHoursPerDay = v;
          this.applyParam('hours_per_day', v);
        }
      })
    }
    .width('48%')
    .constraintSize({ minWidth: 360 })
    .padding(16)
    .margin({ bottom: 12 })
    .alignItems(HorizontalAlign.Start)
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }

  @Builder
  leaveCard() {
    Column({ space: 10 }) {
      Text('计薪与请假').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text('月计薪天数按国家规定固定 21.75 天；缺勤扣款基准：约定工作天数 − 提供正常劳动天数')
        .fontSize(10)
        .fontColor(C_HINT)
        .width('100%')
      FieldRow({
        label: '约定工作天数', value: this.fAgreedDays, unit: '天',
        disabled: this.isLocked,
        onEdit: (v: string) => {
          this.fAgreedDays = v;
          this.applyParam('agreed_work_days', v);
        }
      })
      Button('一键填入提供正常劳动天数')
        .type(ButtonType.Normal)
        .fontSize(12)
        .height(30)
        .width('100%')
        .enabled(!this.isLocked)
        .backgroundColor('#F8FAFC')
        .fontColor('#475467')
        .border({ width: 1, color: '#E6E8F0' })
        .borderRadius(8)
        .onClick(() => this.fillAgreedDays())
    }
    .width('48%')
    .constraintSize({ minWidth: 360 })
    .padding(16)
    .margin({ bottom: 12 })
    .alignItems(HorizontalAlign.Start)
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }

  @Builder
  noteCard() {
    Column({ space: 10 }) {
      Text('备注 / 姓名').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text('用于区分历史月份').fontSize(10).fontColor(C_HINT).width('100%')
      TextInput({ text: this.fNote, placeholder: '例如：张三 · 工资核算' })
        .height(34)
        .fontSize(13)
        .width('100%')
        .enabled(!this.isLocked)
        .onChange((v: string) => {
          this.fNote = v;
          this.book.note = v;
          this.refresh();
        })
    }
    .width('48%')
    .constraintSize({ minWidth: 360 })
    .padding(16)
    .margin({ bottom: 12 })
    .alignItems(HorizontalAlign.Start)
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }

  @Builder
  tplDialog() {
    Column({ space: 12 }) {
      Text(this.tplDlgTitle).fontSize(15).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      if (this.tplDlgMode === 'delete') {
        Text(`确定要删除模板「${this.tplSel}」吗？删除后无法恢复。`)
          .fontSize(12)
          .fontColor(C_SUB)
          .width('100%')
      } else {
        TextInput({ text: this.tplDlgText, placeholder: '模板名称' })
          .height(34)
          .fontSize(13)
          .width('100%')
          .onChange((v: string) => {
            this.tplDlgText = v;
          })
      }
      Row({ space: 10 }) {
        Blank()
        Button('取消')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => {
            this.tplDlgOpen = false;
          })
        Button('确定')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor(this.tplDlgMode === 'delete' ? '#D92D20' : C_ACCENT)
          .fontColor('#FFFFFF')
          .borderRadius(8)
          .onClick(() => this.confirmTplDialog())
      }
      .width('100%')
    }
    .width(380)
    .padding(18)
    .backgroundColor('#FFFFFF')
    .borderRadius(14)
    .shadow({ radius: 24, color: '#33000000', offsetY: 6 })
  }

  // ================= 报表 =================
  @Builder
  reportPage() {
    Row({ space: 12 }) {
      Scroll() {
        Column({ space: 10 }) {
          ForEach(this.snap.groups, (g: RecGroup, gi: number) => {
            Column({ space: 6 }) {
              Row() {
                Text(`${this.groupOpen[gi] ? '▾' : '▸'} ${g.title}`)
                  .fontSize(13.5)
                  .fontWeight(FontWeight.Bold)
                  .fontColor('#0F172A')
                  .layoutWeight(1)
              }
              .width('100%')
              .padding({ top: 2, bottom: 2 })
              .onClick(() => {
                const next: boolean[] = this.groupOpen.slice();
                next[gi] = !next[gi];
                this.groupOpen = next;
              })

              if (this.groupOpen[gi]) {
                Column({ space: 4 }) {
                  ForEach(g.lines, (ln: RecLine, li: number) => {
                    Row({ space: 16 }) {
                      Text(ln.label)
                        .fontSize(12)
                        .fontColor(ln.kind === 'sec' ? '#7C8AA5' : '#475569')
                        .fontWeight(ln.kind === 'sec' ? FontWeight.Bold : FontWeight.Normal)
                        .layoutWeight(1)
                      Text(ln.value)
                        .fontSize(12)
                        .fontColor(this.lineColor(ln.kind, ln.bold))
                        .fontWeight(this.lineBold(ln.kind, ln.bold))
                        .textAlign(TextAlign.End)
                    }
                    .width('100%')
                    .alignItems(VerticalAlign.Top)
                  }, (ln: RecLine, li: number) => `${gi}-${li}-${ln.label}-${ln.value}-${ln.kind}-${ln.bold}`)
                }
                .width('100%')
                .alignItems(HorizontalAlign.Start)
              }
            }
            .width('100%')
            .padding({ left: 14, right: 14, top: 8, bottom: 12 })
            .alignItems(HorizontalAlign.Start)
            .backgroundColor(BG_CARD)
            .borderRadius(12)
          }, (g: RecGroup, gi: number) => `${gi}-${g.title}-${this.groupOpen[gi]}`)
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
      }
      .layoutWeight(1)
      .height('100%')
      .align(Alignment.Top)
      .scrollBar(BarState.Auto)

      // ---------- 右侧常驻汇总卡 ----------
      Column({ space: 5 }) {
        Text('应发工资').fontSize(12).fontColor('#667085').width('100%')
        Text(`¥ ${this.snap.gross}`)
          .fontSize(26)
          .fontWeight(FontWeight.Bold)
          .fontColor('#4F46E5')
          .width('100%')

        Row() {
          Text('个人扣除').fontSize(12).fontColor('#667085').layoutWeight(1)
          Text(`- ¥ ${this.snap.deductTotal}`).fontSize(12).fontWeight(FontWeight.Bold).fontColor('#F04438')
        }
        .width('100%')
        Row() {
          Text('请假扣款').fontSize(12).fontColor('#667085').layoutWeight(1)
          Text(`- ¥ ${this.snap.leaveDeductionTotal}`)
            .fontSize(12)
            .fontWeight(FontWeight.Bold)
            .fontColor('#F04438')
        }
        .width('100%')

        Divider().color('#E6E8F0')
        Text('实际到手').fontSize(12).fontColor('#667085').width('100%')
        Text(`¥ ${this.snap.takeHome}`)
          .fontSize(30)
          .fontWeight(FontWeight.Bold)
          .fontColor('#4F46E5')
          .width('100%')
        Divider().color('#E6E8F0')

        Row() {
          Text('到手小时工资').fontSize(12).fontColor('#667085').layoutWeight(1)
          Text(`¥ ${this.snap.takeHomeHourly} / h`).fontSize(12).fontWeight(FontWeight.Bold).fontColor('#0F172A')
        }
        .width('100%')
        Row() {
          Text('提供正常劳动').fontSize(12).fontColor('#667085').layoutWeight(1)
          Text(this.snap.normalLaborText).fontSize(12).fontWeight(FontWeight.Bold).fontColor('#0F172A')
        }
        .width('100%')
        Row() {
          Text('公司总成本').fontSize(12).fontColor('#667085').layoutWeight(1)
          Text(`¥ ${this.snap.companyCost}`).fontSize(12).fontWeight(FontWeight.Bold).fontColor('#0F172A')
        }
        .width('100%')

        Text('工作日加班 ×1.5 · 休息日 ×2 · 法定节假日 ×3 · 请假 / 缺勤扣款：先按「(应发工资 − 个人扣除) ÷ 约定工作天数」算出「请假一天扣除的工资」，缺勤按天扣、请假不足一天按小时（再 ÷ 8）扣')
          .fontSize(11)
          .fontColor('#98A2B3')
          .width('100%')
          .margin({ top: 6 })

        Blank()
        Button('📄 导出 CSV')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(32)
          .width('100%')
          .backgroundColor(C_ACCENT)
          .fontColor('#FFFFFF')
          .borderRadius(9)
          .onClick(() => this.exportReport())
        if (this.exportState.length > 0) {
          Text(this.exportState).fontSize(10).fontColor(C_HINT).width('100%').maxLines(4)
        }
      }
      .width(300)
      .padding({ left: 16, right: 16, top: 14, bottom: 14 })
      .alignItems(HorizontalAlign.Start)
      .backgroundColor(BG_CARD)
      .borderRadius(12)
    }
    .width('100%')
    .height('100%')
    .alignItems(VerticalAlign.Top)
  }

  // ================= 薪酬页 =================
  /** 「添加工资项」菜单：按类型分组，已添加的标 ✓，底部可自定义。 */
  @Builder
  addPayMenu() {
    Menu() {
      ForEach(PAYITEM_GROUPS, (g: PayCatalogGroup) => {
        MenuItemGroup({ header: `${g.title} · 可选 ${this.catalogLeft(g.type)} 项` }) {
          ForEach(g.items, (n: string) => {
            MenuItem({ content: this.payItemMenuText(n) })
              .onClick(() => {
                this.addPayItemNamed(n, g.type);
              })
          }, (n: string) => `${g.type}-${n}-${this.hasPayItem(n)}`)
        }
      }, (g: PayCatalogGroup) => `${g.type}-${this.catalogLeft(g.type)}`)
      MenuItem({ content: '＋ 输入自定义名称…' })
        .onClick(() => {
          this.addPayItem();
        })
    }
  }

  @Builder
  salaryPage() {
    Column({ space: 12 }) {
      // 桌面版 SalaryStripWidget 只属于薪酬页（不是全局顶栏）
      this.strip()
      // 桌面版用 ResponsiveColumns：左栏弹性、右栏固定 300（min300/max520），宽屏并排。
      // ⚠ 不能用 Flex(wrap)：左栏 flexGrow(1) 会先占满整行，把右栏挤到下一行（看不见）。
      Row({ space: 14 }) {
      Column({ space: 8 }) {
        Row({ space: 8 }) {
          Text('工资项').fontSize(14).fontWeight(FontWeight.Bold).fontColor('#334155')
          Blank()
          Button('📋 复制工资项')
            .type(ButtonType.Normal)
            .fontSize(12)
            .height(30)
            .width(124)
            .enabled(!this.isLocked)
            .backgroundColor('#F8FAFC')
            .fontColor('#475467')
            .border({ width: 1, color: '#E6E8F0' })
            .borderRadius(8)
            .onClick(() => this.openCopyDialog())
          Button('＋ 添加工资项')
            .type(ButtonType.Normal)
            .fontSize(12)
            .height(30)
            .width(124)
            .enabled(!this.isLocked)
            .backgroundColor(C_ACCENT)
            .fontColor('#FFFFFF')
            .bindMenu(this.addPayMenu)
        }
        .width('100%')

        Row({ space: 8 }) {
          Text('类型').fontSize(11).fontColor(C_HINT).width(PI_COL_TYPE)
          Text('名称').fontSize(11).fontColor(C_HINT).layoutWeight(1)
          Text('标准').fontSize(11).fontColor(C_HINT).width(PI_COL_STD)
          Text('月小计').fontSize(11).fontColor(C_HINT).width(PI_COL_SUB).textAlign(TextAlign.End)
          Text('').width(PI_COL_OP)
        }
        .width('100%')
        .padding({ left: 10, right: 10 })

        if (this.snap.payRows.length === 0) {
          Text('本月还没有工资项：点「＋ 添加工资项」开始录入。')
            .fontSize(12)
            .fontColor(C_HINT)
            .padding({ top: 16, bottom: 16 })
        } else {
          // ⚠ 整行直接写在父组件里，不拆子组件：
          //   @Param 只能观察到「@Local/@Param 变量」的变化，观察不到数组元素的成员属性；
          //   @Event 回写父组件后向子组件同步是异步的。行内控件放父级最稳。
          ForEach(this.snap.payRows, (p: PayRow) => {
            Row({ space: 8 }) {
              Button(`${this.chipOf(p.type).short}  ▾`)
                .type(ButtonType.Normal)
                .fontSize(11)
                .height(28)
                .width(PI_COL_TYPE)
                .padding({ left: 2, right: 2 })
                .enabled(!this.isLocked)
                .fontColor(this.chipOf(p.type).fg)
                .backgroundColor(this.chipOf(p.type).bg)
                .border({ width: 1, color: this.chipOf(p.type).border })
                .borderRadius(6)
                .bindMenu(this.rowTypeMenu(p))

              TextInput({ text: p.name, placeholder: '名称' })
                .height(30)
                .fontSize(12)
                .layoutWeight(1)
                .enabled(!this.isLocked)
                .onChange((v: string) => this.renamePayItem(p.index, v))
              TextInput({ text: p.amountText })
                .type(InputType.NUMBER_DECIMAL)
                .height(30)
                .fontSize(12)
                .width(PI_COL_STD)
                .enabled(!this.isLocked)
                .onChange((v: string) => this.setPayAmount(p.index, v))
              Text(`¥ ${p.subText}`)
                .fontSize(12)
                .fontColor(C_TEXT)
                .width(PI_COL_SUB)
                .textAlign(TextAlign.End)
              Text('✕')
                .fontSize(13)
                .fontColor(C_BAD)
                .width(PI_COL_OP)
                .textAlign(TextAlign.Center)
                .enabled(!this.isLocked)
                .onClick(() => this.removePayItem(p.index))
            }
            .width('100%')
            .padding({ left: 10, right: 10, top: 2, bottom: 2 })
            // key 只含「行号 + 类型」：
            //   类型变 → 重建 chip；名称/金额变 → 不重建，否则输入框会因重建而失焦
          }, (p: PayRow) => `${p.index}-${p.type}`)
        }
      }
      // 与桌面版 ResponsiveColumns 一致：主栏吃满剩余宽度（不设上限）
      .layoutWeight(1)
      .constraintSize({ minWidth: 460 })
      .margin({ bottom: 14 })
      .padding(16)
      .alignItems(HorizontalAlign.Start)
      .backgroundColor(BG_CARD)
      .borderRadius(12)

      Column({ space: 12 }) {
        // 加班工资
        Column({ space: 6 }) {
          Text('加班工资').fontSize(14).fontWeight(FontWeight.Bold).fontColor('#334155')
          Text(`${overtimeHourlyTip()}；工作日 ×1.5 · 休息日 ×2 · 法定节假日 ×3`)
            .fontSize(10)
            .fontColor(C_HINT)
          Row({ space: 8 }) {
            Text('固定加班工资').fontSize(12).fontColor(C_SUB).width(76)
            TextInput({ text: this.snap.fixedOt })
              .type(InputType.NUMBER_DECIMAL)
              .height(30)
              .fontSize(12)
              .width(84)
              .onChange((v: string) => this.setFixedOt(v))
            Text('元').fontSize(11).fontColor(C_HINT).layoutWeight(1)
          }
          .width('100%')
          OtRow({
            label: '工作日加班',
            hours: this.snap.otHoursWorkday,
            wage: this.snap.otWageWorkday,
            badge: '×1.5',
            badgeFg: '#15803D',
            badgeBg: '#DCFCE7',
            onEdit: (v: string) => this.setOtHours('workday', v)
          })
          OtRow({
            label: '休息日加班',
            hours: this.snap.otHoursRestday,
            wage: this.snap.otWageRestday,
            badge: '×2.0',
            badgeFg: '#C2410C',
            badgeBg: '#FFEDD5',
            onEdit: (v: string) => this.setOtHours('restday', v)
          })
          OtRow({
            label: '法定节假日加班',
            hours: this.snap.otHoursHoliday,
            wage: this.snap.otWageHoliday,
            badge: '×3.0',
            badgeFg: '#B91C1C',
            badgeBg: '#FEE2E2',
            onEdit: (v: string) => this.setOtHours('holiday', v)
          })
          Row({ space: 8 }) {
            Text('加班费基数（月）').fontSize(12).fontColor(C_SUB).width(104)
            TextInput({ text: this.snap.otBaseText })
              .type(InputType.NUMBER_DECIMAL)
              .height(30)
              .fontSize(12)
              .width(84)
              .enabled(!this.otBaseLocked)
              .onChange((v: string) => this.setOtBase(v))
            Text(this.otBaseLocked ? '🔒' : '🔓')
              .fontSize(14)
              .layoutWeight(1)
              .textAlign(TextAlign.End)
              .onClick(() => this.toggleOtBaseLock())
          }
          .width('100%')
          Text('默认与月最低工资标准同步；如需特殊基数，请点右侧「🔒」解锁后修改')
            .fontSize(10)
            .fontColor(C_HINT)
          Divider().color('#EEF0F6')
          Row() {
            Text('加班工资合计').fontSize(12).fontColor(C_SUB).layoutWeight(1)
            Text(`¥ ${this.snap.otSubtotal}`).fontSize(15).fontWeight(FontWeight.Bold).fontColor('#1D4ED8')
          }
          .width('100%')
        }
        .padding(16)
        .alignItems(HorizontalAlign.Start)
        .backgroundColor(BG_CARD)
        .borderRadius(12)

        // 个人扣除
        Column({ space: 6 }) {
          Text('个人扣除').fontSize(14).fontWeight(FontWeight.Bold).fontColor('#334155')
          Text('社保 / 公积金 = 基数 × 比例（自动）；基数与比例在「参数」页设置')
            .fontSize(10)
            .fontColor(C_HINT)
          Row({ space: 6 }) {
            Checkbox({ name: 'taxAuto', group: 'ded' })
              .select(this.snap.incomeTaxAuto)
              .enabled(!this.isLocked)
              .onChange((on: boolean) => this.toggleTaxAuto(on))
            Text('自动计算个税（月度预扣率表）')
              .fontSize(12)
              .fontColor(this.isLocked ? '#98A2B3' : C_SUB)
          }
          .width('100%')
          RoRow({ label: '个人社保（自动）', value: this.snap.personalSocialDetail })
          RoRow({ label: '个人公积金（自动）', value: this.snap.personalFundDetail })
          Row({ space: 8 }) {
            Text('大病医疗补助（元）').fontSize(12).fontColor(C_SUB).layoutWeight(1)
            TextInput({ text: this.snap.bigDisease })
              .type(InputType.NUMBER_DECIMAL)
              .height(30)
              .fontSize(12)
              .width(84)
              .fontColor(this.isLocked ? '#98A2B3' : '#0F172A')
              .backgroundColor(this.isLocked ? '#F5F7FA' : '#FFFFFF')
              .onChange((v: string) => this.setBigDisease(v))
          }
          .width('100%')
          if (this.snap.incomeTaxAuto) {
            RoRow({ label: '个人所得税（自动）', value: this.snap.incomeTax })
          } else {
            Row({ space: 8 }) {
              Text('个人所得税').fontSize(12).fontColor(C_SUB).layoutWeight(1)
              TextInput({ text: this.snap.incomeTax })
                .type(InputType.NUMBER_DECIMAL)
                .height(30)
                .fontSize(12)
                .width(84)
                .fontColor(this.isLocked ? '#98A2B3' : '#0F172A')
                .backgroundColor(this.isLocked ? '#F5F7FA' : '#FFFFFF')
                .onChange((v: string) => this.setIncomeTax(v))
            }
            .width('100%')
          }
          Divider().color('#EEF0F6')
          Row() {
            Text('个人扣除合计').fontSize(12).fontColor(C_SUB).layoutWeight(1)
            Text(`- ¥ ${this.snap.deductTotal}`).fontSize(15).fontWeight(FontWeight.Bold).fontColor(C_BAD)
          }
          .width('100%')
        }
        .padding(16)
        .alignItems(HorizontalAlign.Start)
        .backgroundColor(BG_CARD)
        .borderRadius(12)
      }
      // 侧栏：桌面版 setMinimumWidth(300) / setMaximumWidth(520)，实际取 300
      .width(300)
      .margin({ bottom: 14 })
      }
      .width('100%')
      .alignItems(VerticalAlign.Top)
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  // ================= 年度汇总（界面）=================
  @Builder
  annualPage() {
    Column({ space: 10 }) {
      // ---------- 顶栏：年份切换 + 导出 ----------
      Row({ space: 8 }) {
        Button('‹ 上一年')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => this.annualShift(-1))
        Text(`${this.annualYear} 年 · 12 个月一览`)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor(C_TEXT)
        Button('下一年 ›')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => this.annualShift(1))
        Blank()
        Text(`应发合计 ¥ ${this.annualGross} · 到手合计 ¥ ${this.annualTakeHome}`)
          .fontSize(11)
          .fontColor(C_HINT)
        Button('📄 导出 CSV')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .padding({ left: 12, right: 12 })
          .backgroundColor('#F8FAFC')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => this.exportAnnual())
      }
      .width('100%')

      if (this.annualState.length > 0) {
        Text(this.annualState).fontSize(10).fontColor(C_HINT).width('100%').maxLines(3)
      }

      // ---------- 12 个月一览表（10 列，窄屏横向滚动） ----------
      Scroll() {
        Column({ space: 0 }) {
          Text('数据读取自已保存的月份；未保存的月份显示 “—”。公司成本 = 应发 + 公司社保 + 公司公积金。')
            .fontSize(10)
            .fontColor(C_HINT)
            .width(900)
            .padding({ bottom: 6 })

          Row() {
            Text('月份').fontSize(10).fontColor('#98A2B3').width(60).textAlign(TextAlign.Center)
            Text('出勤(天)').fontSize(10).fontColor('#98A2B3').width(64).textAlign(TextAlign.End)
            Text('加班(小时)').fontSize(10).fontColor('#98A2B3').width(72).textAlign(TextAlign.End)
            Text('请假(小时)').fontSize(10).fontColor('#98A2B3').width(72).textAlign(TextAlign.End)
            Text('应发工资').fontSize(10).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('个人扣除').fontSize(10).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('请假扣款').fontSize(10).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('实发工资').fontSize(10).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('公司成本').fontSize(10).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('工时合规').fontSize(10).fontColor('#98A2B3').width(72).textAlign(TextAlign.Center)
          }
          .width(900)
          .padding({ top: 2, bottom: 6 })
          .border({ width: { bottom: 1 }, color: '#E6E8F0' })

          ForEach(this.annualRows, (row: AnnualRow, ri: number) => {
            AnnualRowView({
              month: row.month,
              hasData: row.hasData,
              isTotal: row.isTotal,
              workText: row.workText,
              otText: row.otText,
              leaveText: row.leaveText,
              gross: row.gross,
              deduct: row.deduct,
              leaveDeduct: row.leaveDeduct,
              takeHome: row.takeHome,
              companyCost: row.companyCost,
              legal: row.legal
            })
          }, (row: AnnualRow, ri: number) =>
          `${ri}-${row.month}-${row.hasData}-${row.isTotal}-${row.gross}-${row.takeHome}-${row.legal}`)
        }
        .width(900)
      }
      .width('100%')
      .scrollBar(BarState.Auto)
      .scrollable(ScrollDirection.Horizontal)
      .padding(16)
      .align(Alignment.TopStart)
      .backgroundColor(BG_CARD)
      .borderRadius(12)
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  // ================= 相关单位（界面）=================
  @Builder
  unitsPage() {
    Column({ space: 10 }) {
      // ---------- 卡片头：标题 + hint + 本页锁 ----------
      Row({ space: 8 }) {
        Text('单位登记表').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
        Blank()
        Text(this.unitsState).fontSize(10).fontColor(C_HINT).maxLines(2).layoutWeight(1)
        Button(this.unitsLocked ? '🔒 已锁定' : '🔓 已解锁')
          .type(ButtonType.Normal)
          .fontSize(11)
          .height(28)
          .padding({ left: 10, right: 10 })
          .backgroundColor(this.unitsLocked ? '#F5F7FA' : '#EEF2FF')
          .fontColor(this.unitsLocked ? '#667085' : '#4F46E5')
          .border({ width: 1, color: this.unitsLocked ? '#E6E8F0' : '#C7D2FE' })
          .borderRadius(8)
          .onClick(() => this.toggleUnitsLock())
      }
      .width('100%')

      Text('已按内置类型各列一行，空的直接填；同一类型可以有多家时点「＋ 添加单位」（例如先后 / 同时签过多份劳动合同）；列表里没有的类型选「其他相关单位」，具体是什么写在「单位名称」栏')
        .fontSize(10)
        .fontColor(C_HINT)
        .width('100%')

      if (this.unitsLocked) {
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
        Text('类型').fontSize(10).fontColor('#98A2B3').width(134)
        Text('单位名称').fontSize(10).fontColor('#98A2B3').layoutWeight(1)
        Text('编号').fontSize(10).fontColor('#98A2B3').layoutWeight(1)
        Text('').width(34)
        Text('').width(24)
      }
      .width('100%')
      .padding({ top: 2, bottom: 4 })
      .border({ width: { bottom: 1 }, color: '#E6E8F0' })

      // ---------- 数据行 ----------
      if (this.unitRows.length === 0) {
        Text('单位表是空的 —— 点下面「＋ 添加单位」选一个类型')
          .fontSize(11)
          .fontColor(C_HINT)
          .padding({ top: 16, bottom: 16 })
      } else {
        ForEach(this.unitRows, (u: UnitRow) => {
          UnitRowView({
            role: u.role,
            roleLabel: u.roleLabel,
            codeLabel: u.codeLabel,
            name: u.name,
            code: u.code,
            locked: this.unitsLocked,
            onRename: (v: string) => this.setUnitName(u.index, v),
            onCode: (v: string) => this.setUnitCode(u.index, v),
            onType: (k: string) => this.setUnitType(u.index, k),
            onAction: (s: string) => this.unitAction(u, s),
            onDelete: () => this.removeUnit(u.index)
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
          .backgroundColor(this.unitsLocked ? '#F5F7FA' : C_ACCENT)
          .fontColor(this.unitsLocked ? '#98A2B3' : '#FFFFFF')
          .borderRadius(8)
          .enabled(!this.unitsLocked)
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

  @Builder
  placeholder() {
    Column() {
      Text(`${this.pageTitle()}　（待实现）`).fontSize(14).fontColor(C_HINT)
    }
    .width('100%')
    .height(220)
    .justifyContent(FlexAlign.Center)
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }

  // ================= 内容区 =================
  @Builder
  content() {
    Scroll() {
      Column() {
        if (this.pageKey === 'overview') {
          this.overviewPage()
        } else if (this.pageKey === 'units') {
          this.unitsPage()
        } else if (this.pageKey === 'calendar') {
          this.calendarPage()
        } else if (this.pageKey === 'params') {
          this.paramsPage()
        } else if (this.pageKey === 'salary') {
          this.salaryPage()
        } else if (this.pageKey === 'report') {
          this.reportPage()
        } else if (this.pageKey === 'annual') {
          this.annualPage()
        } else {
          this.placeholder()
        }
      }
      .width('100%')
      .padding(20)
      .alignItems(HorizontalAlign.Start)
    }
    .layoutWeight(1)
    .width('100%')
    .align(Alignment.Top)
  }

  build() {
    Stack() {
      Row() {
        this.sidebar()
        Column() {
          this.topBar()
          if (this.pageKey !== 'units') {
            this.monthBar()
          }
          this.content()
        }
        .layoutWeight(1)
        .height('100%')
      }
      .width('100%')
      .height('100%')
      .backgroundColor(BG_PAGE)

      if (this.copyDlgOpen) {
        this.copyDlg()
      }
      if (this.aboutOpen) {
        this.aboutDialog()
      }
      if (this.apiDlgOpen) {
        this.apiDialog()
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  apiDialog() {
    Column({ space: 10 }) {
      Text('最低工资 / 节假日 API 设置').fontSize(15).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text('OpenAI 兼容接口（https）。配置后「🌐 联网查询」「🌐 API 一键铺」使用它。')
        .fontSize(10)
        .fontColor(C_HINT)
        .width('100%')

      Row({ space: 8 }) {
        Text('服务商').fontSize(11).fontColor('#667085').width(64)
        Text('选择服务商模板 ▾')
          .fontSize(12)
          .fontColor('#4F46E5')
          .padding({ left: 10, right: 10, top: 5, bottom: 5 })
          .layoutWeight(1)
          .backgroundColor('#FFFFFF')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .bindMenu(this.apiProviderMenu())
      }
      .width('100%')

      Row({ space: 8 }) {
        Text('API 地址').fontSize(11).fontColor('#667085').width(64)
        TextInput({ text: this.apiUrl, placeholder: 'https://api.deepseek.com/v1' })
          .height(32)
          .fontSize(12)
          .layoutWeight(1)
          .onChange((v: string) => {
            this.apiUrl = v;
          })
      }
      .width('100%')

      Row({ space: 8 }) {
        Text('模型名').fontSize(11).fontColor('#667085').width(64)
        TextInput({ text: this.apiModel, placeholder: '如 deepseek-chat / qwen-max / glm-4-plus' })
          .height(32)
          .fontSize(12)
          .layoutWeight(1)
          .onChange((v: string) => {
            this.apiModel = v;
          })
      }
      .width('100%')

      Row({ space: 8 }) {
        Text('API Key').fontSize(11).fontColor('#667085').width(64)
        TextInput({ text: this.apiKey, placeholder: '可选（云端服务需填 Key）' })
          .type(InputType.Password)
          .height(32)
          .fontSize(12)
          .layoutWeight(1)
          .onChange((v: string) => {
            this.apiKey = v;
          })
      }
      .width('100%')

      Row({ space: 10 }) {
        Button(this.apiBusy ? '⏳ 测试中…' : '测试连接')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .padding({ left: 12, right: 12 })
          .enabled(!this.apiBusy)
          .backgroundColor('#F8FAFC')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => this.runApiTest())
        Text(this.apiTestState)
          .fontSize(10)
          .fontColor(this.apiTestState.startsWith('✅') ? '#0B7A3B' : C_BAD)
          .layoutWeight(1)
          .maxLines(3)
      }
      .width('100%')

      Row({ space: 10 }) {
        Blank()
        Button('取消')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => {
            this.apiDlgOpen = false;
          })
        Button('保存')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .padding({ left: 14, right: 14 })
          .backgroundColor(C_ACCENT)
          .fontColor('#FFFFFF')
          .borderRadius(8)
          .onClick(() => this.confirmApiDialog())
      }
      .width('100%')
    }
    .width(520)
    .padding(18)
    .alignItems(HorizontalAlign.Start)
    .backgroundColor('#FFFFFF')
    .borderRadius(14)
    .shadow({ radius: 24, color: '#33000000', offsetY: 6 })
  }

  @Builder
  copyDlg() {    Column({ space: 12 }) {
      Text('复制工资项').fontSize(15).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text(`将 ${this.book.year} 年 ${this.book.month} 月的「工资项 + 固定加班工资 + 大病医疗补助」复制到：`)
        .fontSize(11)
        .fontColor(C_SUB)
        .width('100%')
      Row({ space: 8 }) {
        Button('‹')
          .type(ButtonType.Normal)
          .fontSize(13)
          .height(30)
          .width(32)
          .backgroundColor('#F8FAFC')
          .fontColor('#475467')
          .borderRadius(8)
          .onClick(() => this.shiftCopyMonth(-1))
        Text(`${this.copyYear} 年 ${this.copyMonth} 月`)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor(C_TEXT)
          .layoutWeight(1)
          .textAlign(TextAlign.Center)
        Button('›')
          .type(ButtonType.Normal)
          .fontSize(13)
          .height(30)
          .width(32)
          .backgroundColor('#F8FAFC')
          .fontColor('#475467')
          .borderRadius(8)
          .onClick(() => this.shiftCopyMonth(1))
      }
      .width('100%')

      Text('目标月已有工资项时会被覆盖；按出勤津贴会按目标月实际上班天数自动重算。')
        .fontSize(10)
        .fontColor(C_HINT)
        .width('100%')
      if (this.copyHint.length > 0) {
        Text(this.copyHint).fontSize(11).fontColor(C_BAD).width('100%')
      }
      Row({ space: 10 }) {
        Blank()
        Button('取消')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: '#E6E8F0' })
          .borderRadius(8)
          .onClick(() => {
            this.copyDlgOpen = false;
          })
        Button('复制')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor(C_ACCENT)
          .fontColor('#FFFFFF')
          .borderRadius(8)
          .onClick(() => this.doCopyPayItems())
      }
      .width('100%')
    }
    .width(400)
    .padding(18)
    .backgroundColor('#FFFFFF')
    .borderRadius(14)
    .shadow({ radius: 24, color: '#33000000', offsetY: 6 })
  }

  /** 当前数据加密方式的简短描述（只读状态，不含任何密钥材料）。 */
  private cryptoSummary(): string {
    const st = this.store;
    if (st === null) {
      return '检测失败：存储未初始化';
    }
    if (!st.cryptoOk()) {
      const err: string = st.cryptoError();
      return err.length > 0 ? `未加密（明文存储）：${err}` : '未加密（明文存储）';
    }
    return 'HUKS AES-256-GCM · 密钥由系统密钥库托管（无密钥文件）';
  }

  @Builder
  aboutDialog() {
    Column({ space: 10 }) {
      Text('关于 · 工作考勤表').fontSize(15).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text('工作考勤表（Attendance HarmonyOS）').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text('本地离线 · 月度考勤与工资核算工具（HarmonyOS / ArkTS）').fontSize(11).fontColor(C_SUB)
      Row({ space: 4 }) {
        Text('开源许可：').fontSize(11).fontColor(C_SUB)
        Text('GNU General Public License v3.0').fontSize(11).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      }
      Row({ space: 4 }) {
        Text('数据加密：').fontSize(11).fontColor(C_SUB)
        Text(this.cryptoSummary())
          .fontSize(11)
          .fontWeight(FontWeight.Bold)
          .fontColor(this.store !== null && this.store.cryptoOk() ? '#0B7A3B' : '#C00000')
          .layoutWeight(1)
      }
      .width('100%')
      .alignItems(VerticalAlign.Top)

      Divider().color('#E6E8F0')

      Text('免责声明').fontSize(12).fontWeight(FontWeight.Bold).fontColor(C_TEXT).width('100%')
      Text('本软件为免费开源工具，仅作工资核算参考，不构成法律 / 税务 / 财务意见。\n' +
        '内置的节假日、最低工资等数据请以官方最新发布为准；社保 / 公积金 / 个税等参数需按当地政策自行核对。')
        .fontSize(11)
        .fontColor(C_SUB)
        .width('100%')
      Text('用于正式发薪前请务必人工复核。').fontSize(11).fontWeight(FontWeight.Bold).fontColor('#B54708').width('100%')

      Divider().color('#E6E8F0')
      Text('数据位置（按月加密存档）：').fontSize(11).fontColor(C_SUB).width('100%')
      Text(this.store === null ? '—' : this.store.location())
        .fontSize(10)
        .fontColor(C_HINT)
        .width('100%')

      Row({ space: 10 }) {
        Blank()
        Button('确定')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor(C_ACCENT)
          .fontColor('#FFFFFF')
          .borderRadius(8)
          .onClick(() => {
            this.aboutOpen = false;
          })
      }
      .width('100%')
    }
    .width(460)
    .padding(18)
    .alignItems(HorizontalAlign.Start)
    .backgroundColor('#FFFFFF')
    .borderRadius(14)
    .shadow({ radius: 24, color: '#33000000', offsetY: 6 })
  }
}
