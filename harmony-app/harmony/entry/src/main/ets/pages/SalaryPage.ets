/**
 * 薪酬页（对应桌面版 `app/pages_salary.py`）。
 *
 * 顶部数值条 + 左侧工资项表 + 右侧「加班工资 / 个人扣除」两张卡。
 * 与其它页面一致：数据由 `@Param snap` 下传，所有输入通过 `@Event` 上报，
 * 真正的写模型 / 重算 / 落盘都在外壳（`Index.ets`）里。
 */
import { overtimeHourlyTip } from '../core/calc';
import { PAYITEM_GROUPS, PayCatalogGroup } from '../core/paycatalog';
import {
  PI_COL_OP, PI_COL_STD, PI_COL_SUB, PI_COL_TYPE,
  TYPE_CHIPS, TypeChip, typeChipOf
} from '../core/config';
import { PayRow, Snap } from '../model/Snap';
import { MetaItem, OtRow, RoRow, StripItem } from './components';
import {
  BG_CARD, C_ACCENT, C_BAD, C_DARK, C_HINT, C_INPUT_BG, C_LINE, C_OK, C_ROW_BG, C_SUB, C_TEXT
} from './theme';

@ComponentV2
export struct SalaryPage {
  @Param snap: Snap = new Snap();
  @Param locked: boolean = false;
  /** 「加班费基数」字段级锁（跟随月最低工资） */
  @Param otBaseLocked: boolean = true;

  @Event onCopy: () => void = () => {
  };
  @Event onAddNamed: (name: string, type: string) => void = (name: string, type: string) => {
  };
  @Event onAddCustom: () => void = () => {
  };
  @Event onRename: (index: number, v: string) => void = (index: number, v: string) => {
  };
  @Event onAmount: (index: number, v: string) => void = (index: number, v: string) => {
  };
  @Event onType: (index: number, key: string) => void = (index: number, key: string) => {
  };
  @Event onRemove: (index: number) => void = (index: number) => {
  };
  @Event onFixedOt: (v: string) => void = (v: string) => {
  };
  @Event onOtHours: (kind: string, v: string) => void = (kind: string, v: string) => {
  };
  @Event onOtBase: (v: string) => void = (v: string) => {
  };
  @Event onToggleOtBaseLock: () => void = () => {
  };
  @Event onTaxAuto: (on: boolean) => void = (on: boolean) => {
  };
  @Event onBigDisease: (v: string) => void = (v: string) => {
  };
  @Event onIncomeTax: (v: string) => void = (v: string) => {
  };

  /** 本月是否已有同名工资项（菜单里打 ✓ 用） */
  private hasPayItem(name: string): boolean {
    for (const p of this.snap.payRows) {
      if (p.name === name) {
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

  private chipOf(t: string): TypeChip {
    return typeChipOf(t);
  }

  /** 工资项类型下拉菜单（桌面版：单个 chip 按钮带菜单，非 4 个并排）。 */
  private rowTypeMenu(p: PayRow): MenuElement[] {
    const out: MenuElement[] = [];
    for (const c of TYPE_CHIPS) {
      out.push({
        value: p.type === c.key ? `${c.short}  ✓` : c.short,
        action: () => {
          this.onType(p.index, c.key);
        }
      });
    }
    return out;
  }

  /** 「添加工资项」菜单：按类型分组，已添加的标 ✓，底部可自定义。 */
  @Builder
  addPayMenu() {
    Menu() {
      ForEach(PAYITEM_GROUPS, (g: PayCatalogGroup) => {
        MenuItemGroup({ header: `${g.title} · 可选 ${this.catalogLeft(g.type)} 项` }) {
          ForEach(g.items, (n: string) => {
            MenuItem({ content: this.payItemMenuText(n) })
              .onClick(() => this.onAddNamed(n, g.type))
          }, (n: string) => `${g.type}-${n}-${this.hasPayItem(n)}`)
        }
      }, (g: PayCatalogGroup) => `${g.type}-${this.catalogLeft(g.type)}`)
      MenuItem({ content: '＋ 输入自定义名称…' })
        .onClick(() => this.onAddCustom())
    }
  }

  /** 顶部数值条（桌面版 SalaryStripWidget，只属于薪酬页）。 */
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

  build() {
    Column({ space: 12 }) {
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
              .enabled(!this.locked)
              .backgroundColor(C_ROW_BG)
              .fontColor('#475467')
              .border({ width: 1, color: C_LINE })
              .borderRadius(8)
              .onClick(() => this.onCopy())
            Button('＋ 添加工资项')
              .type(ButtonType.Normal)
              .fontSize(12)
              .height(30)
              .width(124)
              .enabled(!this.locked)
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
            // ⚠ 整行直接写在组件里，不再拆更细的子组件：
            //   @Param 只能观察到「@Local/@Param 变量」的变化，观察不到数组元素的成员属性。
            ForEach(this.snap.payRows, (p: PayRow) => {
              Row({ space: 8 }) {
                Button(`${this.chipOf(p.type).short}  ▾`)
                  .type(ButtonType.Normal)
                  .fontSize(11)
                  .height(28)
                  .width(PI_COL_TYPE)
                  .padding({ left: 2, right: 2 })
                  .enabled(!this.locked)
                  .fontColor(this.chipOf(p.type).fg)
                  .backgroundColor(this.chipOf(p.type).bg)
                  .border({ width: 1, color: this.chipOf(p.type).border })
                  .borderRadius(6)
                  .bindMenu(this.rowTypeMenu(p))

                TextInput({ text: p.name, placeholder: '名称' })
                  .height(30)
                  .fontSize(12)
                  .layoutWeight(1)
                  .enabled(!this.locked)
                  .onChange((v: string) => this.onRename(p.index, v))
                TextInput({ text: p.amountText })
                  .type(InputType.NUMBER_DECIMAL)
                  .height(30)
                  .fontSize(12)
                  .width(PI_COL_STD)
                  .enabled(!this.locked)
                  .onChange((v: string) => this.onAmount(p.index, v))
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
                  .enabled(!this.locked)
                  .onClick(() => this.onRemove(p.index))
              }
              .width('100%')
              .padding({ left: 10, right: 10, top: 2, bottom: 2 })
              // key 只含「行号 + 类型」：类型变 → 重建 chip；名称/金额变 → 不重建，否则输入框会失焦
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
          // ---------- 加班工资 ----------
          Column({ space: 6 }) {
            Text('加班工资').fontSize(14).fontWeight(FontWeight.Bold).fontColor('#334155')
            Text(`${overtimeHourlyTip()}；工作日 ×1.5 · 休息日 ×2 · 法定节假日 ×3`)
              .fontSize(11)
              .fontColor(C_HINT)
            Row({ space: 8 }) {
              Text('固定加班工资').fontSize(12).fontColor(C_SUB).width(76)
              TextInput({ text: this.snap.fixedOt })
                .type(InputType.NUMBER_DECIMAL)
                .height(30)
                .fontSize(12)
                .width(84)
                .onChange((v: string) => this.onFixedOt(v))
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
              onEdit: (v: string) => this.onOtHours('workday', v)
            })
            OtRow({
              label: '休息日加班',
              hours: this.snap.otHoursRestday,
              wage: this.snap.otWageRestday,
              badge: '×2.0',
              badgeFg: '#C2410C',
              badgeBg: '#FFEDD5',
              onEdit: (v: string) => this.onOtHours('restday', v)
            })
            OtRow({
              label: '法定节假日加班',
              hours: this.snap.otHoursHoliday,
              wage: this.snap.otWageHoliday,
              badge: '×3.0',
              badgeFg: '#B91C1C',
              badgeBg: '#FEE2E2',
              onEdit: (v: string) => this.onOtHours('holiday', v)
            })
            Row({ space: 8 }) {
              Text('加班费基数（月）').fontSize(12).fontColor(C_SUB).width(104)
              TextInput({ text: this.snap.otBaseText })
                .type(InputType.NUMBER_DECIMAL)
                .height(30)
                .fontSize(12)
                .width(84)
                .enabled(!this.otBaseLocked)
                .onChange((v: string) => this.onOtBase(v))
              Text(this.otBaseLocked ? '🔒' : '🔓')
                .fontSize(14)
                .layoutWeight(1)
                .textAlign(TextAlign.End)
                .onClick(() => this.onToggleOtBaseLock())
            }
            .width('100%')
            Text('默认与月最低工资标准同步；如需特殊基数，请点右侧「🔒」解锁后修改')
              .fontSize(11)
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

          // ---------- 个人扣除 ----------
          Column({ space: 6 }) {
            Text('个人扣除').fontSize(14).fontWeight(FontWeight.Bold).fontColor('#334155')
            Text('社保 / 公积金 = 基数 × 比例（自动）；基数与比例在「参数」页设置')
              .fontSize(11)
              .fontColor(C_HINT)
            Row({ space: 6 }) {
              Checkbox({ name: 'taxAuto', group: 'ded' })
                .select(this.snap.incomeTaxAuto)
                .enabled(!this.locked)
                .onChange((on: boolean) => this.onTaxAuto(on))
              Text('自动计算个税（月度预扣率表）')
                .fontSize(12)
                .fontColor(this.locked ? '#98A2B3' : C_SUB)
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
                .fontColor(this.locked ? '#98A2B3' : C_DARK)
                .backgroundColor(this.locked ? C_INPUT_BG : '#FFFFFF')
                .onChange((v: string) => this.onBigDisease(v))
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
                  .fontColor(this.locked ? '#98A2B3' : C_DARK)
                  .backgroundColor(this.locked ? C_INPUT_BG : '#FFFFFF')
                  .onChange((v: string) => this.onIncomeTax(v))
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
}
