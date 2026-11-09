/**
 * 参数页（对应桌面版 `app/pages_params.py`）。
 *
 * 全是「表单 → 模型」的只读展示 + 回调：字段值由父级 `@Param` 传入，
 * 输入/点击通过 `@Event` 上报（父级负责改模型、重算快照、防抖落盘）。
 * 模板弹窗（保存 / 重命名 / 删除）仍在 `Index.ets` 的浮层里，这里只管模板条。
 */
import { MIN_WAGE_PROVINCES, minWageRegions } from '../core/minwage.data';
import { FieldRow } from './components';
import {
  BG_CARD, C_ACCENT, C_HINT, C_INPUT_BG, C_LABEL, C_LINE, C_OK, C_ROW_BG, C_SUB, C_TEXT
} from './theme';

@ComponentV2
export struct ParamsPage {
  /** 月份锁定 → 整页只读（桌面版 ParamsPage._set_params_locked 的等价物） */
  @Param locked: boolean = false;
  // ---- 参数模板 ----
  @Param tplNames: string[] = [];
  @Param tplSel: string = '';
  @Param tplHint: string = '';
  // ---- API / 工作地 ----
  @Param apiHint: string = '';
  @Param apiUrl: string = '';
  @Param wageHint: string = '';
  @Param province: string = '';
  @Param region: string = '';
  // ---- 表单字段 ----
  @Param socialBase: string = '';
  @Param personalSocialRate: string = '';
  @Param companySocialRate: string = '';
  @Param personalFundRate: string = '';
  @Param companyFundRate: string = '';
  @Param fundBase: string = '';
  @Param minWage: string = '';
  @Param parttimeMin: string = '';
  @Param overtimeBase: string = '';
  @Param hoursPerDay: string = '';
  @Param agreedDays: string = '';
  @Param note: string = '';
  // ---- 字段级锁 ----
  @Param wageLocked: boolean = true;
  @Param otBaseLocked: boolean = true;
  @Param fundBaseLocked: boolean = true;
  /** Preferences 沙箱真实路径（只显示位置） */
  @Param dataPath: string = '';

  /** 任一参数输入：父级按 key 写模型（含 min_wage 的联动） */
  @Event onParam: (key: string, value: string) => void = (key: string, value: string) => {
  };
  @Event onNote: (value: string) => void = (value: string) => {
  };
  @Event onToggleFundBaseLock: () => void = () => {
  };
  @Event onToggleWageLock: () => void = () => {
  };
  @Event onToggleOtBaseLock: () => void = () => {
  };
  @Event onFillAgreedDays: () => void = () => {
  };
  @Event onUseLocalWage: () => void = () => {
  };
  @Event onFetchWageApi: () => void = () => {
  };
  @Event onOpenApiDialog: () => void = () => {
  };
  @Event onPickProvince: (p: string) => void = (p: string) => {
  };
  @Event onPickRegion: (r: string) => void = (r: string) => {
  };
  // ---- 模板条 ----
  @Event onTplSelect: (name: string) => void = (name: string) => {
  };
  @Event onTplSave: () => void = () => {
  };
  @Event onTplRename: () => void = () => {
  };
  @Event onTplDelete: () => void = () => {
  };
  @Event onTplApply: () => void = () => {
  };

  /** 模板下拉：空列表时给一个占位项（点了什么都不做）。 */
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
          this.onTplSelect(n);
        }
      });
    }
    return out;
  }

  /** 省份菜单（桌面版 PROVINCES 顺序）。 */
  private provinceMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    for (const p of MIN_WAGE_PROVINCES) {
      out.push({
        value: p, action: () => {
          this.onPickProvince(p);
        }
      });
    }
    return out;
  }

  /** 地区菜单：未选省时只给提示。 */
  private regionMenu(): MenuElement[] {
    const out: MenuElement[] = [];
    if (this.province.length === 0) {
      out.push({
        value: '请先选择省份', action: () => {
        }
      });
      return out;
    }
    for (const r of minWageRegions(this.province)) {
      out.push({
        value: r, action: () => {
          this.onPickRegion(r);
        }
      });
    }
    return out;
  }

  build() {
    Scroll() {
      Column({ space: 12 }) {
        // ---------- 参数模板条（锁定时整条禁用，与桌面版 Card.set_locked 一致） ----------
        Row({ space: 10 }) {
          Text('参数模板').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
          Text(this.tplNames.length === 0 ? '（暂无已存模板）' : `${this.tplSel} ▾`)
            .fontSize(12)
            .fontColor(this.locked ? C_LABEL
              : (this.tplNames.length === 0 ? C_HINT : C_ACCENT))
            .padding({ left: 10, right: 10, top: 5, bottom: 5 })
            .borderRadius(8)
            .enabled(!this.locked)
            .backgroundColor(this.locked ? C_INPUT_BG : '#FFFFFF')
            .border({ width: 1, color: C_LINE })
            .bindMenu(this.tplMenu())
          Button('存为模板…')
            .type(ButtonType.Normal)
            .fontSize(12)
            .height(30)
            .enabled(!this.locked)
            .backgroundColor(this.locked ? C_INPUT_BG : '#FFFFFF')
            .fontColor(this.locked ? C_HINT : '#475467')
            .border({ width: 1, color: C_LINE })
            .borderRadius(8)
            .onClick(() => this.onTplSave())
          Button('重命名')
            .type(ButtonType.Normal)
            .fontSize(12)
            .height(30)
            .enabled(!this.locked)
            .backgroundColor(this.locked ? C_INPUT_BG : '#FFFFFF')
            .fontColor(this.locked ? C_HINT : '#475467')
            .border({ width: 1, color: C_LINE })
            .borderRadius(8)
            .onClick(() => this.onTplRename())
          Button('删除')
            .type(ButtonType.Normal)
            .fontSize(12)
            .height(30)
            .enabled(!this.locked)
            .backgroundColor(this.locked ? C_INPUT_BG : '#FFFFFF')
            .fontColor(this.locked ? C_HINT : '#D92D20')
            .border({ width: 1, color: this.locked ? C_LINE : '#FCD0CB' })
            .borderRadius(8)
            .onClick(() => this.onTplDelete())
          Button('套用到本月')
            .type(ButtonType.Normal)
            .fontSize(12)
            .height(30)
            .enabled(!this.locked)
            .backgroundColor(this.locked ? C_INPUT_BG : C_ACCENT)
            .fontColor(this.locked ? C_HINT : '#FFFFFF')
            .borderRadius(8)
            .onClick(() => this.onTplApply())
          Blank()
          Text('整组参数存为模板，新建月份 / 换人时一键套用')
            .fontSize(11)
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
        Text(`存档位置：${this.dataPath.length > 0 ? this.dataPath : '—'}`)
          .fontSize(11)
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
  }

  @Builder
  socialCard() {
    Column({ space: 10 }) {
      Text('社保 / 公积金').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C_TEXT)
      Text('五险一金基数与比例（比例填小数，0.105 = 10.5%；公积金基数默认=最低工资，可点 🔓 解锁手动改）')
        .fontSize(11)
        .fontColor(C_HINT)
        .width('100%')
      FieldRow({
        label: '社保缴费基数', value: this.socialBase, unit: '元',
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('social_base', v)
      })
      FieldRow({
        label: '个人社保比例', value: this.personalSocialRate, unit: '', tip: '小数，0.105 = 10.5%',
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('personal_social_rate', v)
      })
      FieldRow({
        label: '公司社保比例', value: this.companySocialRate, unit: '', tip: '小数，0.24 = 24%',
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('company_social_rate', v)
      })
      FieldRow({
        label: '个人公积金比例', value: this.personalFundRate, unit: '', tip: '小数，0.07 = 7%',
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('personal_fund_rate', v)
      })
      FieldRow({
        label: '公司公积金比例', value: this.companyFundRate, unit: '', tip: '小数，0.07 = 7%',
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('company_fund_rate', v)
      })
      FieldRow({
        label: '公积金缴费基数', value: this.fundBase, unit: '元',
        disabled: this.locked,
        tip: '默认与本地月最低工资同步；如需特殊基数，请点击右侧「🔒」解锁后修改',
        locked: this.fundBaseLocked,
        lockable: true,
        onEdit: (v: string) => this.onParam('fund_base', v),
        onToggleLock: () => this.onToggleFundBaseLock()
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
        .fontSize(11)
        .fontColor(this.apiUrl.length > 0 ? C_OK : C_HINT)
        .width('100%')
      Row({ space: 8 }) {
        Button('⚙️ API 设置')
          .type(ButtonType.Normal)
          .fontSize(11)
          .height(28)
          .padding({ left: 10, right: 10 })
          // 月份锁定 = 参数页整页只读（桌面版 Card.set_locked 连着这排一起禁用）
          .enabled(!this.locked)
          .backgroundColor(this.locked ? C_INPUT_BG : C_ROW_BG)
          .fontColor(this.locked ? C_HINT : '#475467')
          .border({ width: 1, color: C_LINE })
          .borderRadius(8)
          .onClick(() => this.onOpenApiDialog())
        Blank()
      }
      .width('100%')

      Row({ space: 8 }) {
        Text('工作地').fontSize(11).fontColor(C_LABEL).width(48)
        Text(this.province.length === 0 ? '请选择省份 ▾' : `${this.province} ▾`)
          .fontSize(12)
          .fontColor(this.locked ? C_LABEL : (this.province.length === 0 ? C_HINT : C_TEXT))
          .padding({ left: 8, right: 8, top: 5, bottom: 5 })
          .layoutWeight(1)
          .borderRadius(8)
          .enabled(!this.locked)
          .backgroundColor(this.locked ? C_INPUT_BG : '#FFFFFF')
          .border({ width: 1, color: C_LINE })
          .bindMenu(this.provinceMenu())
        Text(this.region.length === 0 ? '请选择地区 ▾' : `${this.region} ▾`)
          .fontSize(12)
          .fontColor(this.locked ? C_LABEL : (this.region.length === 0 ? C_HINT : C_TEXT))
          .padding({ left: 8, right: 8, top: 5, bottom: 5 })
          .layoutWeight(1)
          .borderRadius(8)
          .enabled(!this.locked)
          .backgroundColor(this.locked ? C_INPUT_BG : '#FFFFFF')
          .border({ width: 1, color: C_LINE })
          .bindMenu(this.regionMenu())
      }
      .width('100%')

      Row({ space: 8 }) {
        Button('📋 用本地表')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .layoutWeight(1)
          .enabled(!this.locked)
          .backgroundColor('#F5F3FF')
          .fontColor('#5B21B6')
          .borderRadius(8)
          .onClick(() => this.onUseLocalWage())
        Button('🌐 联网查询（API）')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .layoutWeight(1)
          .enabled(!this.locked)
          .backgroundColor('#ECFDF5')
          .fontColor('#065F46')
          .borderRadius(8)
          .onClick(() => this.onFetchWageApi())
      }
      .width('100%')
      if (this.wageHint.length > 0) {
        Text(this.wageHint).fontSize(11).fontColor(C_HINT).width('100%')
      }

      FieldRow({
        label: '月最低工资', value: this.minWage, unit: '元',
        locked: this.wageLocked,
        lockable: true,
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('min_wage', v),
        onToggleLock: () => this.onToggleWageLock()
      })
      FieldRow({
        label: '非全日制小时最低工资', value: this.parttimeMin, unit: '元/时',
        locked: this.wageLocked,
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('parttime_min', v)
      })
      FieldRow({
        label: '加班费计算基数', value: this.overtimeBase, unit: '元',
        tip: '默认与本地月最低工资同步；如需特殊基数，请点击右侧「🔒」解锁后修改',
        locked: this.otBaseLocked,
        lockable: true,
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('overtime_base', v),
        onToggleLock: () => this.onToggleOtBaseLock()
      })
      FieldRow({
        label: '24小时内工时', value: this.hoursPerDay, unit: '小时',
        disabled: this.locked,
        tip: '第 N 次下班 → 第 N+1 次上班结束的 24 小时（正常一个周期应为 24 小时；不是 24 小时说明排班有问题）',
        onEdit: (v: string) => this.onParam('hours_per_day', v)
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
        .fontSize(11)
        .fontColor(C_HINT)
        .width('100%')
      FieldRow({
        label: '约定工作天数', value: this.agreedDays, unit: '天',
        disabled: this.locked,
        onEdit: (v: string) => this.onParam('agreed_work_days', v)
      })
      Button('一键填入提供正常劳动天数')
        .type(ButtonType.Normal)
        .fontSize(12)
        .height(30)
        .width('100%')
        .enabled(!this.locked)
        .backgroundColor(C_ROW_BG)
        .fontColor('#475467')
        .border({ width: 1, color: C_LINE })
        .borderRadius(8)
        .onClick(() => this.onFillAgreedDays())
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
      Text('用于区分历史月份').fontSize(11).fontColor(C_HINT).width('100%')
      TextInput({ text: this.note, placeholder: '例如：张三 · 工资核算' })
        .height(34)
        .fontSize(13)
        .width('100%')
        .enabled(!this.locked)
        .onChange((v: string) => this.onNote(v))
    }
    .width('48%')
    .constraintSize({ minWidth: 360 })
    .padding(16)
    .margin({ bottom: 12 })
    .alignItems(HorizontalAlign.Start)
    .backgroundColor(BG_CARD)
    .borderRadius(12)
  }
}
