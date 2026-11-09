/**
 * 工作台页（对应桌面版 `app/pages_overview.py`）。
 *
 * 纯展示：hero 卡（实际到手）+ 4 张 KPI + 合规判定 / 每小时成本。
 * 两卡等高是桌面版 QHBoxLayout 被拉平的效果 —— 这里用 onAreaChange 量左卡高度，
 * 状态（`cmpCardHeight`）就留在本组件里，不必再挂到父级。
 */
import { Snap } from '../model/Snap';
import { StatCard } from './components';
import { BG_CARD, C_ACCENT, C_LABEL, C_SUB, C_TEXT } from './theme';

@ComponentV2
export struct OverviewPage {
  @Param snap: Snap = new Snap();
  /** 左侧「合规判定」卡实测高度：用来把右侧成本卡拉到同高（桌面版行为） */
  @Local cmpCardHeight: number = 0;

  build() {
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
                Text(this.snap.minWageDetail).fontSize(11).fontColor(C_LABEL)
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
                Text(this.snap.workTimeDetail).fontSize(11).fontColor(C_LABEL)
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
}
