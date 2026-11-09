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

import { MonthBook, MonthBookDict, PayItem, createBook } from '../core/model';
import { HolidaySets, classifyDay, yearSets } from '../core/holidays';
import { CalCell, AnnualRow, Snap, UnitRow } from '../model/Snap';
import { ApiStored, MonthStorage, SettingsStorage } from '../model/Storage';
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
  RelatedUnit, UnitDict, UNIT_SELECTABLE_KEYS,
  defaultUnits, unitsFromJson
} from '../core/units';
import { common } from '@kit.AbilityKit';
import { pasteboard } from '@kit.BasicServicesKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { util } from '@kit.ArkTS';
import { compute, countAttendance, Result } from '../core/calc';
import { pyGroupedFixed, pyGeneral } from '../core/num';
import { MinWageRow, minWageOf, minWageRegions } from '../core/minwage.data';
import { PAYITEM_DEFAULT_NAME } from '../core/paycatalog';
import { reportCsv, reportFileName, csvRow } from '../core/csv';
import { ExportResult, Exporter } from '../model/Exporter';
import { BookCache } from '../model/BookCache';
import {
  StatCard, UnitRowView
} from './components';
import { AnnualPage } from './AnnualPage';
import { CalendarPage } from './CalendarPage';
import { OverviewPage } from './OverviewPage';
import { ParamsPage } from './ParamsPage';
import { ReportPage } from './ReportPage';
import { SalaryPage } from './SalaryPage';
import { UnitsPage } from './UnitsPage';
import {
  BG_CARD,
  BG_PAGE,
  C_ACCENT,
  C_BAD,
  C_HINT,
  C_LABEL,
  C_LINE,
  C_OK,
  C_ROW_BG,
  C_SEL_BG,
  C_SUB,
  C_TEXT
} from './theme';

// ================= 常量 =================
/** 月份存档写盘防抖（毫秒）：连续输入合并成一次写盘。 */
const SAVE_DEBOUNCE_MS: number = 400;
/** 首次安装（从未选过）时的默认工作地：与桌面版 `pages_params` 的兜底完全一致。 */
const DEFAULT_PROVINCE: string = '安徽';
const DEFAULT_REGION: string = '池州';

function pad2(n: number): string {
  return (n < 10 ? '0' : '') + n.toString();
}

// ================= 可复用组件见 ./components.ets =================
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
  /** 清空考勤确认弹窗（桌面版 _clear_days 的确认框） */
  @Local clearDlgOpen: boolean = false;
  /** 关于 / 免责声明对话框 */
  @Local aboutOpen: boolean = false;
  /** 当前月份是否锁定（= book.locked，只读） */
  @Local isLocked: boolean = false;
  /** 历史月份列表（侧栏） */
  @Local historyRows: HistRow[] = [];
  /** Preferences 的真实沙箱目录（关于对话框展示用） */
  @Local dataPath: string = '';
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
  private cache: BookCache = new BookCache(12);
  /** 读取失败（JSON 损坏等）的月份：禁止写回，避免覆盖原数据。 */
  private corruptMonths: Set<string> = new Set<string>();
  /** 已锁定月份（与月份正文分开存，历史列表不再需要读每个月）。 */
  private lockedMonths: Set<string> = new Set<string>();
  /** API 配置读取失败原因（解密/解析），空表示正常。 */
  @Local apiKeyError: string = '';

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

  /** 启动加载。Preferences 读写都是异步的。 */
  private async initData(): Promise<void> {
    const ctx = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.dataPath = ctx.preferencesDir;
    this.store = new MonthStorage(ctx);
    this.settings = new SettingsStorage(ctx);
    this.exporter = new Exporter(ctx);
    const keyOk: boolean = await this.settings.warmUp();
    hilog.info(0x0000, 'ATTD', 'api key crypto ready=%{public}s err=%{public}s',
      String(keyOk), this.settings.cryptoError());
    const lockedTxt: string = await this.settings.loadLockedMonths();
    if (lockedTxt.length > 0) {
      for (const k of lockedTxt.split(',')) {
        if (k.length > 0) {
          this.lockedMonths.add(k);
        }
      }
    }
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
      this.corruptMonths.delete(key);
      this.saveState = `已读取 ${key}`;
    } else if (st.hasMonth(y, m)) {
      // 存档解析失败：当成新月份显示，但**禁止写回**，避免覆盖原数据
      this.book = createBook(y, m, '', true);
      this.corruptMonths.add(key);
      this.saveState = `⚠ ${key} 读取失败（${st.lastError || '格式异常'}），已保护原数据不被覆盖`;
    } else {
      // 新建月份带常用工资项（金额 0），与桌面版从 UI 新建月一致；不自动落盘
      this.book = createBook(y, m, '', true);
      this.saveState = `新月份 ${key}（未保存）`;
    }
    this.cache.set(this.monthKey(this.book.year, this.book.month), this.book);
    this.isLocked = this.book.locked;
    if (this.isLocked) {
      // 账本里的锁是权威值（老存档里可能只有账本记了锁）
      this.lockedMonths.add(key);
      this.saveLockedState();
    }
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
   * ⚠ 不能在这里直接写盘：Preferences 的落盘是异步的，连续输入会并发多个 saveMonth，
   * 完成顺序不定 → 后完成的「旧快照」可能覆盖「新快照」（数据丢失）。
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
    if (this.corruptMonths.has(key)) {
      this.saving = false;
      this.savePending = false;
      this.saveState = `⚠ ${key} 读取失败，已跳过保存（不覆盖原数据）`;
      return;
    }
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
        this.saveState = ok ? `已保存 ${key}` : `仅内存（${st.lastError}）`;
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
      this.corruptMonths.delete(key);
      this.saveState = `已读取 ${key}`;
    } else if (st !== null && st.hasMonth(y, m)) {
      this.book = createBook(y, m, '', true);
      this.corruptMonths.add(key);
      this.saveState = `⚠ ${key} 读取失败（${st.lastError || '格式异常'}），已保护原数据不被覆盖`;
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
    // 月份锁定：日期格不可点（桌面版 _set_calendar_locked 把每个格子 setEnabled(False)）
    if (this.isLocked) {
      return;
    }
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

  /** 「清空考勤」入口：锁定时只提示不执行，未锁定先弹确认（桌面版 `_clear_days`）。 */
  private clearAttendance(): void {
    if (this.isLocked) {
      this.setBusinessState(`月份已锁定，无法清空考勤（先点 🔓 解锁 ${this.book.year} 年 ${this.book.month} 月）`);
      return;
    }
    this.clearDlgOpen = true;
  }

  /** 确认后真正清空：状态 / 标记 / 加班 / 请假全部归零。 */
  private doClearAttendance(): void {
    for (const d of this.book.days) {
      d.status = '';
      d.mark = 0;
      d.overtime_hours = 0;
      d.leave_hours = 0;
    }
    this.selOt = '0';
    this.selLeave = '0';
    this.clearDlgOpen = false;
    this.refresh();
    this.setBusinessState('已清空本月考勤（状态 / 标记 / 加班 / 请假）');
  }

  // ================= 参数页：输入 → 模型 =================
  /** 参数页任一字段输入：先同步表单字符串（输入框不回跳），再写模型（applyParam 内含锁定守卫）。 */
  private onParamEdit(key: string, v: string): void {
    switch (key) {
      case 'social_base':
        this.fSocialBase = v;
        break;
      case 'personal_social_rate':
        this.fPersonalSocialRate = v;
        break;
      case 'company_social_rate':
        this.fCompanySocialRate = v;
        break;
      case 'personal_fund_rate':
        this.fPersonalFundRate = v;
        break;
      case 'company_fund_rate':
        this.fCompanyFundRate = v;
        break;
      case 'fund_base':
        this.fFundBase = v;
        break;
      case 'min_wage':
        this.fMinWage = v;
        break;
      case 'parttime_min':
        this.fParttimeMin = v;
        break;
      case 'overtime_base':
        this.fOvertimeBase = v;
        break;
      case 'hours_per_day':
        this.fHoursPerDay = v;
        break;
      case 'agreed_work_days':
        this.fAgreedDays = v;
        break;
      default:
        break;
    }
    this.applyParam(key, v);
  }

  /** 备注 / 姓名输入（直接写 book.note）。 */
  private onNoteEdit(v: string): void {
    if (this.isLocked) {
      return;
    }
    this.fNote = v;
    this.book.note = v;
    this.refresh();
  }

  private applyParam(key: string, text: string): void {
    if (this.isLocked) {
      return;
    }
    const v: number = parseFloat(text);
    if (isNaN(v)) {
      return;
    }
    this.setParamNum(key, v);
    if (key === 'min_wage') {
      // 桌面版：min_wage 变化 → 同步「加班费计算基数 / 公积金缴费基数」（仅限各自处于锁定态时）
      this.syncDerivedFromMinWage();
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
    const v: number = countAttendance(this.book).normal_labor_days;
    this.book.agreed_work_days = v;
    this.fAgreedDays = `${v}`;
    this.refresh();
    this.tplHint = `已按考勤填入约定工作天数：${v} 天`;
  }

  private paramNum(key: string): number {
    const b: MonthBook = this.book;
    switch (key) {
      case 'social_base': return b.social_base;
      case 'personal_social_rate': return b.personal_social_rate;
      case 'company_social_rate': return b.company_social_rate;
      case 'personal_fund_rate': return b.personal_fund_rate;
      case 'company_fund_rate': return b.company_fund_rate;
      case 'fund_base': return b.fund_base;
      case 'min_wage': return b.min_wage;
      case 'parttime_min': return b.parttime_min;
      case 'overtime_base': return b.overtime_base;
      case 'hours_per_day': return b.hours_per_day;
      case 'agreed_work_days': return b.agreed_work_days;
      default: return 0;
    }
  }

  private setParamNum(key: string, v: number): void {
    const b: MonthBook = this.book;
    switch (key) {
      case 'social_base':
        b.social_base = v;
        break;
      case 'personal_social_rate':
        b.personal_social_rate = v;
        break;
      case 'company_social_rate':
        b.company_social_rate = v;
        break;
      case 'personal_fund_rate':
        b.personal_fund_rate = v;
        break;
      case 'company_fund_rate':
        b.company_fund_rate = v;
        break;
      case 'fund_base':
        b.fund_base = v;
        break;
      case 'min_wage':
        b.min_wage = v;
        break;
      case 'parttime_min':
        b.parttime_min = v;
        break;
      case 'overtime_base':
        b.overtime_base = v;
        break;
      case 'hours_per_day':
        b.hours_per_day = v;
        break;
      case 'agreed_work_days':
        b.agreed_work_days = v;
        break;
      default:
        break;
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
    // 没有模板时**不弹对话框**，直接提示（桌面版 _rename_template / _delete_template 同口径）
    if (mode !== 'save' && this.tplSel.length === 0) {
      this.tplHint = mode === 'delete' ? '还没有可删除的模板' : '还没有可重命名的模板';
      return;
    }
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
    // 月份锁定时静默返回：锁定时参数页本就不允许改数，弹提示反而是噪音
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

  // ---- 最低工资：按省 / 地区选（菜单在 ParamsPage 里，这里只管数据与落盘） ----

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

  /** 某一类目下还没添加的可选项数量（已搬到 SalaryPage，外壳只保留数据操作）。 */
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

  /** 工资项类型下拉菜单在 SalaryPage 里生成（这里只管改类型）。 */
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
      if (st === null) {
        rows.push(row);
        continue;
      }
      // 未存档月份 loadMonth 直接返回 null（不再先 hasMonth 多读一次）：
      // 只统计「真的已存档」的月份，否则未保存的新月份会用演示数据污染年度汇总
      const key: string = this.monthKey(year, m);
      let b: MonthBook | null = this.cache.get(key) ?? null;
      if (b === null) {
        b = await st.loadMonth(year, m);
        if (b !== null) {
          this.cache.set(key, b);
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
  /** 首次启动把打包的种子月份写入存档（测试用；导入一次后写标记）。 */
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
        // 不覆盖已有月份（旧数据升级时种子文件可能还在）
        if (store.hasMonth(b.year, b.month)) {
          continue;
        }
        await store.saveMonth(b);
      }
      await settings.saveText('seed_imported', '1');
      hilog.info(0x0000, 'ATTD', 'seed imported %{public}d months', items.length);
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
        this.unitsState = `已读取 ${this.units.length} 家`;
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
   * 名称/编号是「每敲一个字」都会触发保存，所以这里做两件事：
   * 输入用防抖（scheduleUnitsSave），写盘串行化（避免并发互相覆盖）。
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
        this.unitsState = '已保存';
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

  /** 输入防抖：停止输入 500ms 后才真正落盘，避免每次按键都写盘。 */
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
      const cfg: ApiStored = await st.loadApiConfig();
      this.apiUrl = cfg.url;
      this.apiModel = cfg.model;
      this.apiKey = cfg.key;
      // key 为空但确实有配置 → 多半是解密/解析失败，把原因留着给用户看
      const failed: boolean = cfg.url.length > 0 && st.lastError.length > 0;
      this.apiKeyError = failed ? st.lastError : '';
    }
    this.refreshApiHint();
  }

  private async saveApiConfig(): Promise<boolean> {
    const st = this.settings;
    if (st === null) {
      return false;
    }
    const ok: boolean = await st.saveApiConfig(this.apiUrl.trim(), this.apiModel.trim(), this.apiKey.trim());
    this.apiKeyError = ok && st.lastError.length > 0 ? st.lastError : '';
    this.refreshApiHint();
    return ok;
  }

  private refreshApiHint(): void {
    const url: string = this.apiUrl.trim();
    if (url.length > 0) {
      const model: string = this.apiModel.trim().length > 0
        ? this.apiModel.trim() : '（未填，联网查询会失败）';
      const keyTag: string = this.apiKey.trim().length > 0
        ? (this.settings !== null && this.settings.cryptoOk()
          ? 'Key 已填（HUKS 加密）' : 'Key 已填（未加密）')
        : '无 Key（供不校验 Key 的网关）';
      let hint: string = `✅ 已配置 API：${url} · 模型 ${model} · ${keyTag}\n` +
        '「🌐 联网查询」「🌐 API 一键铺」会用它；点「📋 用本地表」则完全不联网';
      if (this.apiKeyError.length > 0) {
        hint += `\n⚠ ${this.apiKeyError}`;
      }
      this.apiHint = hint;
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

  private async confirmApiDialog(): Promise<void> {
    if (this.isLocked) {
      // 月份锁定 = 参数页只读：对话框若在锁定前就开着也不许写（静默关闭）
      this.apiDlgOpen = false;
      return;
    }
    const u: string = this.apiUrl.trim();
    if (u.length > 0 && !u.toLowerCase().startsWith('https://')) {
      this.apiTestState = '为保护 API Key 传输安全，API 地址必须以 https:// 开头';
      return;
    }
    this.apiTestState = '';
    const ok: boolean = await this.saveApiConfig();
    if (!ok) {
      // 留在弹窗里显示原因，避免"点了保存却什么都没发生"
      this.apiTestState = `保存失败：${this.apiKeyError.length > 0 ? this.apiKeyError : '未知原因'}`;
      return;
    }
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
  /** 历史列表只读月份键 + 锁定集合，不再为拿 locked 去解析每个月正文。 */
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
        row.current = (y === this.book.year && m === this.book.month);
        row.locked = row.current ? this.book.locked : this.lockedMonths.has(k);
        row.label = `${y} 年 ${m} 月`;
        rows.push(row);
      }
    }
    // 新的月份排在前面（与桌面版侧栏一致）
    rows.sort((a: HistRow, b: HistRow): number => (b.y * 100 + b.m) - (a.y * 100 + a.m));
    this.historyRows = rows;
  }

  /** 把锁定月份集合写回设置（单键）。 */
  private saveLockedState(): void {
    const st = this.settings;
    if (st === null) {
      return;
    }
    const keys: string[] = [];
    this.lockedMonths.forEach((k: string) => keys.push(k));
    keys.sort();
    st.saveLockedMonths(keys.join(','));
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
      this.corruptMonths.delete(key);
      this.saveState = `已读取 ${key}`;
    } else if (st !== null && st.hasMonth(y, m)) {
      this.book = createBook(y, m, '', true);
      this.corruptMonths.add(key);
      this.saveState = `⚠ ${key} 读取失败（${st.lastError || '格式异常'}），已保护原数据不被覆盖`;
    } else {
      this.book = createBook(y, m, '', true);
      this.saveState = '新月份（未保存）';
    }
    this.cache.set(key, this.book);
    this.isLocked = this.book.locked;
    // 账本里的 locked 是权威值：顺手把锁定集合对齐（老存档里可能有锁但集合没记）
    if (this.book.locked !== this.lockedMonths.has(key)) {
      if (this.book.locked) {
        this.lockedMonths.add(key);
      } else {
        this.lockedMonths.delete(key);
      }
      this.saveLockedState();
    }
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
    const key: string = this.monthKey(b.year, b.month);
    b.locked = next;
    this.isLocked = next;
    if (next) {
      this.lockedMonths.add(key);
    } else {
      this.lockedMonths.delete(key);
    }
    this.saveLockedState();
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
      if (st.hasMonth(y, m)) {
        this.corruptMonths.add(key);
        this.saveState = `⚠ ${key} 读取失败，未修改（原数据未动）`;
      }
      return;
    }
    b.locked = locked;
    const ok: boolean = await st.saveMonth(b);
    if (!ok) {
      this.saveState = `切换锁定失败：${st.lastError}`;
      return;
    }
    this.cache.set(key, b);
    if (locked) {
      this.lockedMonths.add(key);
    } else {
      this.lockedMonths.delete(key);
    }
    this.saveLockedState();
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
    this.corruptMonths.delete(this.monthKey(y, m));
    this.lockedMonths.delete(this.monthKey(y, m));
    this.saveLockedState();
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
    if (created) {
      // 目标月是新建的，不可能被锁；顺手清掉遗留的锁记录
      this.lockedMonths.delete(key);
      this.saveLockedState();
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
                Text('🔒').fontSize(11)
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
            .backgroundColor(r.current ? C_SEL_BG : '#00000000')
            .onClick(() => this.goMonth(r.y, r.m))
            .bindContextMenu(this.histMenu(r), ResponseType.RightClick)
          }
        }, (r: HistRow) => `${r.y}-${r.m}-${r.locked}-${r.current}`)
      }
      .layoutWeight(1)
      .width('100%')
      .scrollBar(BarState.Auto)

      // 底部：数据实际存放位置（与桌面版侧栏一致）
      Text(`数据：${this.dataPath.length > 0 ? this.dataPath : '—'}`)
        .fontSize(11)
        .fontColor(C_HINT)
        .width('100%')
        .padding({ left: 12, right: 12, top: 8, bottom: 6 })
        .maxLines(3)
        .wordBreak(WordBreak.BREAK_ALL)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
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
        .fontColor(C_LABEL)
        .border({ width: 1, color: C_LINE })
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
          .border({ width: 1, color: C_LINE })
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
          .border({ width: 1, color: C_LINE })
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
          .border({ width: 1, color: this.isLocked ? '#FEDF89' : C_LINE })
          .borderRadius(8)
          .onClick(() => this.toggleMonthLock())
        Button('下月 ›')
          .type(ButtonType.Normal)
          .fontSize(13)
          .height(32)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: C_LINE })
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
          .border({ width: 1, color: this.isLocked ? C_LINE : '#FCD0CB' })
          .borderRadius(8)
          .enabled(!this.isLocked)
          .onClick(() => this.deleteCurrentMonth())
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 8, bottom: 8 })

      // 工作台 / 报表 / 年度汇总 只读展示，不涉及修改操作，不显示锁定提示条
      if (this.isLocked && this.pageKey !== 'report' && this.pageKey !== 'annual'
        && this.pageKey !== 'overview') {
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

  // ================= 工作台 =================
  @Builder
  overviewPage() {
    OverviewPage({ snap: this.snap })
  }
  @Builder
  calendarPage() {
    CalendarPage({
      snap: this.snap,
      locked: this.isLocked,
      selOt: this.selOt,
      selLeave: this.selLeave,
      onFillApi: () => this.fillOfficialByApi(),
      onFillLocal: () => this.fillOfficial(),
      onFillDefault: () => this.fillDefaultCalendar(),
      onClear: () => this.clearAttendance(),
      onPickDay: (d: number) => this.selectDay(d),
      onStatus: (s: string) => this.setStatus(s),
      onMark: (m: number) => this.setMark(m),
      onOt: (v: string) => this.setOt(v),
      onLeave: (v: string) => this.setLeave(v)
    })
  }
  // ================= 参数页 =================
  @Builder
  paramsPage() {
    Stack() {
      ParamsPage({
      locked: this.isLocked,
      tplNames: this.tplNames,
      tplSel: this.tplSel,
      tplHint: this.tplHint,
      apiHint: this.apiHint,
      apiUrl: this.apiUrl,
      wageHint: this.wageHint,
      province: this.fProvince,
      region: this.fRegion,
      socialBase: this.fSocialBase,
      personalSocialRate: this.fPersonalSocialRate,
      companySocialRate: this.fCompanySocialRate,
      personalFundRate: this.fPersonalFundRate,
      companyFundRate: this.fCompanyFundRate,
      fundBase: this.fFundBase,
      minWage: this.fMinWage,
      parttimeMin: this.fParttimeMin,
      overtimeBase: this.fOvertimeBase,
      hoursPerDay: this.fHoursPerDay,
      agreedDays: this.fAgreedDays,
      note: this.fNote,
      wageLocked: this.fWageLocked,
      otBaseLocked: this.otBaseLocked,
      fundBaseLocked: this.fFundBaseLocked,
      dataPath: this.dataPath,
      onParam: (k: string, v: string) => this.onParamEdit(k, v),
      onNote: (v: string) => this.onNoteEdit(v),
      onToggleFundBaseLock: () => this.toggleFundBaseLock(),
      onToggleWageLock: () => this.toggleWageLock(),
      onToggleOtBaseLock: () => this.toggleOtBaseLock(),
      onFillAgreedDays: () => this.fillAgreedDays(),
      onUseLocalWage: () => this.useLocalWageTable(),
      onFetchWageApi: () => this.fetchWageFromApi(),
      onOpenApiDialog: () => {
        this.apiTestState = '';
        this.apiDlgOpen = true;
      },
      onPickProvince: (p: string) => this.pickProvince(p),
      onPickRegion: (r: string) => this.pickRegion(r),
      onTplSelect: (n: string) => {
        this.tplSel = n;
      },
      onTplSave: () => this.openTplDialog('save'),
      onTplRename: () => this.openTplDialog('rename'),
      onTplDelete: () => this.openTplDialog('delete'),
      onTplApply: () => this.applyTemplate()
    })
      if (this.tplDlgOpen) {
        this.tplDialog()
      }
    }
    .width('100%')
    .height('100%')
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
          .border({ width: 1, color: C_LINE })
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
    ReportPage({
      snap: this.snap,
      exportState: this.exportState,
      onExport: () => this.exportReport()
    })
  }

  // ================= 薪酬页 =================
  @Builder
  salaryPage() {
    SalaryPage({
      snap: this.snap,
      locked: this.isLocked,
      otBaseLocked: this.otBaseLocked,
      onCopy: () => this.openCopyDialog(),
      onAddNamed: (n: string, t: string) => this.addPayItemNamed(n, t),
      onAddCustom: () => this.addPayItem(),
      onRename: (i: number, v: string) => this.renamePayItem(i, v),
      onAmount: (i: number, v: string) => this.setPayAmount(i, v),
      onType: (i: number, k: string) => this.setPayType(i, k),
      onRemove: (i: number) => this.removePayItem(i),
      onFixedOt: (v: string) => this.setFixedOt(v),
      onOtHours: (k: string, v: string) => this.setOtHours(k, v),
      onOtBase: (v: string) => this.setOtBase(v),
      onToggleOtBaseLock: () => this.toggleOtBaseLock(),
      onTaxAuto: (on: boolean) => this.toggleTaxAuto(on),
      onBigDisease: (v: string) => this.setBigDisease(v),
      onIncomeTax: (v: string) => this.setIncomeTax(v)
    })
  }
  // ================= 年度汇总（界面）=================
  @Builder
  annualPage() {
    AnnualPage({
      year: this.annualYear,
      rows: this.annualRows,
      grossText: this.annualGross,
      takeHomeText: this.annualTakeHome,
      stateText: this.annualState,
      onShift: (delta: number) => this.annualShift(delta),
      onExport: () => this.exportAnnual()
    })
  }

  // ================= 相关单位（界面）=================
  @Builder
  unitsPage() {
    UnitsPage({
      rows: this.unitRows,
      locked: this.unitsLocked,
      stateText: this.unitsState,
      rowsKey: this.rowsKey,
      onToggleLock: () => this.toggleUnitsLock(),
      onRename: (i: number, v: string) => this.setUnitName(i, v),
      onCode: (i: number, v: string) => this.setUnitCode(i, v),
      onType: (i: number, k: string) => this.setUnitType(i, k),
      onAction: (row: UnitRow, site: string) => this.unitAction(row, site),
      onEmptyTerm: () => {
        this.unitsState = '请先填写「统一社会信用代码」或「单位名称」，再去搜索';
      },
      onAdd: (role: string) => this.addUnit(role),
      onDelete: (i: number) => this.removeUnit(i)
    })
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
      if (this.clearDlgOpen) {
        this.clearDlg()
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
        .fontSize(11)
        .fontColor(C_HINT)
        .width('100%')

      Row({ space: 8 }) {
        Text('服务商').fontSize(11).fontColor(C_LABEL).width(64)
        Text('选择服务商模板 ▾')
          .fontSize(12)
          .fontColor(C_ACCENT)
          .padding({ left: 10, right: 10, top: 5, bottom: 5 })
          .layoutWeight(1)
          .backgroundColor('#FFFFFF')
          .border({ width: 1, color: C_LINE })
          .borderRadius(8)
          .bindMenu(this.apiProviderMenu())
      }
      .width('100%')

      Row({ space: 8 }) {
        Text('API 地址').fontSize(11).fontColor(C_LABEL).width(64)
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
        Text('模型名').fontSize(11).fontColor(C_LABEL).width(64)
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
        Text('API Key').fontSize(11).fontColor(C_LABEL).width(64)
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
          .backgroundColor(C_ROW_BG)
          .fontColor('#475467')
          .border({ width: 1, color: C_LINE })
          .borderRadius(8)
          .onClick(() => this.runApiTest())
        Text(this.apiTestState)
          .fontSize(11)
          .fontColor(this.apiTestState.startsWith('✅') ? C_OK : C_BAD)
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
          .border({ width: 1, color: C_LINE })
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
          .backgroundColor(C_ROW_BG)
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
          .backgroundColor(C_ROW_BG)
          .fontColor('#475467')
          .borderRadius(8)
          .onClick(() => this.shiftCopyMonth(1))
      }
      .width('100%')

      Text('目标月已有工资项时会被覆盖；按出勤津贴会按目标月实际上班天数自动重算。')
        .fontSize(11)
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
          .border({ width: 1, color: C_LINE })
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

  /** 清空考勤确认（桌面版 QMessageBox.question「确定清空本月所有出勤状态与加班/请假记录吗？」）。 */
  @Builder
  clearDlg() {
    Column({ space: 12 }) {
      Text('清空考勤').fontSize(15).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text(`确定清空 ${this.book.year} 年 ${this.book.month} 月所有出勤状态与加班/请假记录吗？`)
        .fontSize(12)
        .fontColor(C_SUB)
        .width('100%')
      Text('清空后无法撤销（工资项与参数不受影响）。')
        .fontSize(11)
        .fontColor('#B54708')
        .width('100%')
      Row({ space: 10 }) {
        Blank()
        Button('取消')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: C_LINE })
          .borderRadius(8)
          .onClick(() => {
            this.clearDlgOpen = false;
          })
        Button('清空')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor(C_BAD)
          .fontColor('#FFFFFF')
          .borderRadius(8)
          .onClick(() => this.doClearAttendance())
      }
      .width('100%')
    }
    .width(380)
    .padding(18)
    .backgroundColor('#FFFFFF')
    .borderRadius(14)
    .shadow({ radius: 24, color: '#33000000', offsetY: 6 })
  }

  /** 存储 / 加密方式的简短描述（只读状态，不含任何密钥材料）。
   *
   * ⚠ 句式与桌面版 `app/main_window.py::_crypto_summary()` 对齐：
   *   Windows 是「Windows DPAPI（由当前用户账户托管密钥，无密钥文件）」，
   *   鸿蒙对应「HUKS AES-256-GCM（由系统密钥库托管密钥，不可导出，无密钥文件）」。
   */
  private cryptoSummary(): string {
    const st = this.settings;
    if (st === null) {
      return '检测失败：存储未初始化';
    }
    if (!st.cryptoOk()) {
      const err: string = st.cryptoError();
      return err.length > 0 ? `API Key 未加密（明文降级）：${err}` : 'API Key 未加密（明文降级）';
    }
    return 'HUKS AES-256-GCM（由系统密钥库托管密钥，不可导出，无密钥文件）';
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
        Text('数据加密（仅 API Key）：').fontSize(11).fontColor(C_SUB)
        Text(this.cryptoSummary())
          .fontSize(11)
          .fontWeight(FontWeight.Bold)
          .fontColor(this.settings !== null && this.settings.cryptoOk() ? C_OK : C_BAD)
          .layoutWeight(1)
      }
      .width('100%')
      .alignItems(VerticalAlign.Top)

      Divider().color(C_LINE)

      Text('免责声明').fontSize(12).fontWeight(FontWeight.Bold).fontColor(C_TEXT).width('100%')
      Text('本软件为免费开源工具，仅作工资核算参考，不构成法律 / 税务 / 财务意见。\n' +
        '内置的节假日、最低工资等数据请以官方最新发布为准；社保 / 公积金 / 个税等参数需按当地政策自行核对。')
        .fontSize(11)
        .fontColor(C_SUB)
        .width('100%')
      Text('用于正式发薪前请务必人工复核。').fontSize(11).fontWeight(FontWeight.Bold).fontColor('#B54708').width('100%')

      Divider().color(C_LINE)
      Text('数据位置：').fontSize(11).fontColor(C_SUB).width('100%')
      Text(this.dataPath.length > 0 ? this.dataPath : '—')
        .fontSize(11)
        .fontColor(C_HINT)
        .width('100%')
        .wordBreak(WordBreak.BREAK_ALL)

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
