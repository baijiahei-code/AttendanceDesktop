/**
 * 常量单一来源（对应桌面版 `app/config.py` 里**参与计算**的那部分）。
 *
 * 纯 UI 常量（chip 配色 / 列宽 / 卡片标题）等做界面时再补，不进 core 逻辑层。
 */

/** 加班三档倍率 —— 唯一出处：算钱与文案都读这里。 */
export const OT_RATE_WORKDAY: number = 1.5;
export const OT_RATE_RESTDAY: number = 2.0;
export const OT_RATE_HOLIDAY: number = 3.0;

/** 合规 / 违规文本色（UI 与导出共用）。 */
export const OK_COLOR: string = '#0B7A3B';
export const BAD_COLOR: string = '#C00000';

/**
 * 工资项类型 chip 的四种配色（桌面版 `config.TYPE_CHIP` 同源）。
 *
 * chip 在界面上的形态与桌面版一致：`{short}  ▾` 的按钮，宽 86，点开是 4 类菜单。
 */
export class TypeChip {
  key: string;
  short: string;
  fg: string;
  bg: string;
  border: string;

  constructor(key: string, short: string, fg: string, bg: string, border: string) {
    this.key = key;
    this.short = short;
    this.fg = fg;
    this.bg = bg;
    this.border = border;
  }
}

export const TYPE_CHIPS: TypeChip[] = [
  new TypeChip('wage', '最低工资', '#4F46E5', '#EEF2FF', '#C7D2FE'),
  new TypeChip('subsidy', '公司补贴', '#0E7490', '#ECFEFF', '#A5F3FC'),
  new TypeChip('fixed_allow', '固定津贴', '#B54708', '#FEF4E6', '#FEDF89'),
  new TypeChip('perday_allow', '按出勤', '#027A48', '#DCFCE7', '#BBF7D0')
];

/** 取某类型的 chip 配色；未知类型回落到「最低工资」。 */
export function typeChipOf(key: string): TypeChip {
  for (const c of TYPE_CHIPS) {
    if (c.key === key) {
      return c;
    }
  }
  return TYPE_CHIPS[0];
}

/** 工资项列宽（对应桌面版 `PAYITEM_COL_WIDTHS`，表头与数据行共用）。 */
export const PI_COL_TYPE: number = 86;
export const PI_COL_STD: number = 150;
export const PI_COL_SUB: number = 110;
export const PI_COL_OP: number = 36;

/** 考勤日历的每日配色（桌面版 `ui.DAY_PALETTE` 同源）。 */
export class DayPalette {
  status: string;
  bg: string;
  fg: string;

  constructor(status: string, bg: string, fg: string) {
    this.status = status;
    this.bg = bg;
    this.fg = fg;
  }
}

export const DAY_PALETTES: DayPalette[] = [
  new DayPalette('上班', '#DCFCE7', '#15803D'),
  new DayPalette('休息', '#F1F5F9', '#475569'),
  new DayPalette('事假', '#FEF3C7', '#B45309'),
  new DayPalette('病假', '#FFE4E6', '#BE123C'),
  new DayPalette('婚假', '#FCE7F3', '#BE185D'),
  new DayPalette('丧假', '#E2E8F0', '#334155'),
  new DayPalette('产假', '#EDE9FE', '#6D28D9'),
  new DayPalette('年假', '#E0F2FE', '#0369A1'),
  new DayPalette('其他', '#CCFBF1', '#0F766E')
];

/** 未填状态时的格子配色。 */
export const DAY_EMPTY_BG: string = '#FCFCFD';
export const DAY_EMPTY_FG: string = '#475569';

export function dayPaletteOf(status: string): DayPalette {
  for (const p of DAY_PALETTES) {
    if (p.status === status) {
      return p;
    }
  }
  return new DayPalette('', DAY_EMPTY_BG, DAY_EMPTY_FG);
}
