/**
 * 报表页（对应桌面版 `app/pages_report.py`）。
 *
 * 左侧分组明细（可折叠）+ 右侧常驻汇总卡。分组展开状态是**本组件自己的** UI 状态，
 * 不再放回父级；数据全部来自父级传入的快照。
 */
import { RecGroup, RecLine, Snap } from '../model/Snap';
import { BG_CARD, C_ACCENT, C_BAD, C_DARK, C_HINT, C_LABEL, C_LINE, C_OK } from './theme';

@ComponentV2
export struct ReportPage {
  @Param snap: Snap = new Snap();
  /** 导出结果提示（父级负责执行导出） */
  @Param exportState: string = '';
  @Event onExport: () => void = () => {
  };

  /** 分组展开状态（默认展开；快照换月后组数变了也能正确取到）。 */
  @Local groupOpen: boolean[] = [];

  private isOpen(gi: number): boolean {
    return gi < this.groupOpen.length ? this.groupOpen[gi] !== false : true;
  }

  private lineColor(kind: string, bold: boolean): string {
    if (kind === 'ok') {
      return C_OK;
    } else if (kind === 'bad') {
      return C_BAD;
    } else if (kind === 'sec') {
      return '#7C8AA5';
    } else if (bold) {
      return '#1D4ED8';
    }
    return C_DARK;
  }

  private lineBold(kind: string, bold: boolean): FontWeight {
    if (kind === 'ok' || kind === 'bad' || kind === 'sec' || bold) {
      return FontWeight.Bold;
    }
    return FontWeight.Normal;
  }

  private toggleGroup(gi: number): void {
    const n: number = this.snap.groups.length;
    const next: boolean[] = [];
    for (let i = 0; i < n; i++) {
      next.push(this.isOpen(i));
    }
    next[gi] = !this.isOpen(gi);
    this.groupOpen = next;
  }

  build() {
    Row({ space: 12 }) {
      Scroll() {
        Column({ space: 10 }) {
          ForEach(this.snap.groups, (g: RecGroup, gi: number) => {
            Column({ space: 6 }) {
              Row() {
                Text(`${this.isOpen(gi) ? '▾' : '▸'} ${g.title}`)
                  .fontSize(13.5)
                  .fontWeight(FontWeight.Bold)
                  .fontColor(C_DARK)
                  .layoutWeight(1)
              }
              .width('100%')
              .padding({ top: 2, bottom: 2 })
              .onClick(() => this.toggleGroup(gi))

              if (this.isOpen(gi)) {
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
          }, (g: RecGroup, gi: number) => `${gi}-${g.title}-${this.isOpen(gi)}`)
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
        Text('应发工资').fontSize(12).fontColor(C_LABEL).width('100%')
        Text(`¥ ${this.snap.gross}`)
          .fontSize(26)
          .fontWeight(FontWeight.Bold)
          .fontColor(C_ACCENT)
          .width('100%')

        Row() {
          Text('个人扣除').fontSize(12).fontColor(C_LABEL).layoutWeight(1)
          Text(`- ¥ ${this.snap.deductTotal}`).fontSize(12).fontWeight(FontWeight.Bold).fontColor('#F04438')
        }
        .width('100%')
        Row() {
          Text('请假扣款').fontSize(12).fontColor(C_LABEL).layoutWeight(1)
          Text(`- ¥ ${this.snap.leaveDeductionTotal}`)
            .fontSize(12)
            .fontWeight(FontWeight.Bold)
            .fontColor('#F04438')
        }
        .width('100%')

        Divider().color(C_LINE)
        Text('实际到手').fontSize(12).fontColor(C_LABEL).width('100%')
        Text(`¥ ${this.snap.takeHome}`)
          .fontSize(30)
          .fontWeight(FontWeight.Bold)
          .fontColor(C_ACCENT)
          .width('100%')
        Divider().color(C_LINE)

        Row() {
          Text('到手小时工资').fontSize(12).fontColor(C_LABEL).layoutWeight(1)
          Text(`¥ ${this.snap.takeHomeHourly} / h`).fontSize(12).fontWeight(FontWeight.Bold).fontColor(C_DARK)
        }
        .width('100%')
        Row() {
          Text('提供正常劳动').fontSize(12).fontColor(C_LABEL).layoutWeight(1)
          Text(this.snap.normalLaborText).fontSize(12).fontWeight(FontWeight.Bold).fontColor(C_DARK)
        }
        .width('100%')
        Row() {
          Text('公司总成本').fontSize(12).fontColor(C_LABEL).layoutWeight(1)
          Text(`¥ ${this.snap.companyCost}`).fontSize(12).fontWeight(FontWeight.Bold).fontColor(C_DARK)
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
          .onClick(() => this.onExport())
        if (this.exportState.length > 0) {
          Text(this.exportState).fontSize(11).fontColor(C_HINT).width('100%').maxLines(4)
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
}
