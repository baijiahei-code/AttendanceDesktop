/**
 * 年度汇总页（对应桌面版 `app/pages_annual.py`）。
 *
 * 只做展示 + 两个动作（换年 / 导出），状态全部由父级（Index.ets）通过 @Param 传入，
 * 动作通过 @Event 回调 —— 与桌面版「页面方法读 self._book + 回调 main_window」的分层一致。
 */
import { AnnualRow } from '../model/Snap';
import { AnnualRowView } from './components';
import { BG_CARD, C_HINT, C_LINE, C_ROW_BG, C_TEXT } from './theme';

@ComponentV2
export struct AnnualPage {
  @Param year: number = 0;
  @Param rows: AnnualRow[] = [];
  /** 已格式化的合计（父级算好，避免这边再引入 num 依赖） */
  @Param grossText: string = '0.00';
  @Param takeHomeText: string = '0.00';
  /** 导出结果提示（含失败原因） */
  @Param stateText: string = '';
  @Event onShift: (delta: number) => void = (delta: number) => {
  };
  @Event onExport: () => void = () => {
  };

  build() {
    Column({ space: 10 }) {
      // ---------- 顶栏：年份切换 + 导出 ----------
      Row({ space: 8 }) {
        Button('‹ 上一年')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: C_LINE })
          .borderRadius(8)
          .onClick(() => this.onShift(-1))
        Text(`${this.year} 年 · 12 个月一览`)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor(C_TEXT)
        Button('下一年 ›')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .backgroundColor('#FFFFFF')
          .fontColor('#475467')
          .border({ width: 1, color: C_LINE })
          .borderRadius(8)
          .onClick(() => this.onShift(1))
        Blank()
        Text(`应发合计 ¥ ${this.grossText} · 到手合计 ¥ ${this.takeHomeText}`)
          .fontSize(11)
          .fontColor(C_HINT)
        Button('📄 导出 CSV')
          .type(ButtonType.Normal)
          .fontSize(12)
          .height(30)
          .padding({ left: 12, right: 12 })
          .backgroundColor(C_ROW_BG)
          .fontColor('#475467')
          .border({ width: 1, color: C_LINE })
          .borderRadius(8)
          .onClick(() => this.onExport())
      }
      .width('100%')

      if (this.stateText.length > 0) {
        Text(this.stateText).fontSize(11).fontColor(C_HINT).width('100%').maxLines(3)
      }

      // ---------- 12 个月一览表（10 列，窄屏横向滚动） ----------
      Scroll() {
        Column({ space: 0 }) {
          Text('数据读取自已保存的月份；未保存的月份显示 “—”。公司成本 = 应发 + 公司社保 + 公司公积金。')
            .fontSize(11)
            .fontColor(C_HINT)
            .width(900)
            .padding({ bottom: 6 })

          Row() {
            Text('月份').fontSize(11).fontColor('#98A2B3').width(60).textAlign(TextAlign.Center)
            Text('出勤(天)').fontSize(11).fontColor('#98A2B3').width(64).textAlign(TextAlign.End)
            Text('加班(小时)').fontSize(11).fontColor('#98A2B3').width(72).textAlign(TextAlign.End)
            Text('请假(小时)').fontSize(11).fontColor('#98A2B3').width(72).textAlign(TextAlign.End)
            Text('应发工资').fontSize(11).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('个人扣除').fontSize(11).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('请假扣款').fontSize(11).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('实发工资').fontSize(11).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('公司成本').fontSize(11).fontColor('#98A2B3').width(108).textAlign(TextAlign.End)
            Text('工时合规').fontSize(11).fontColor('#98A2B3').width(72).textAlign(TextAlign.Center)
          }
          .width(900)
          .padding({ top: 2, bottom: 6 })
          .border({ width: { bottom: 1 }, color: C_LINE })

          ForEach(this.rows, (row: AnnualRow, ri: number) => {
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
}
