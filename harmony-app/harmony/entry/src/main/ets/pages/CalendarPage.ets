/**
 * 考勤日历页（对应桌面版 `app/pages_calendar.py`）。
 *
 * 版式与桌面版一致：操作条（4 颗按钮）与考勤统计小条都是页面级独立一行/一组，
 * 月历卡里只有「标题 + 星期 + 日期格 + 图例」；右侧是选中日期的编辑面板。
 * 数据来自 `@Param snap`，所有编辑动作通过 `@Event` 回到外壳。
 */
import { DAY_PALETTES, DayPalette, dayPaletteOf } from '../core/config';
import { STATUS_LABELS } from '../core/model';
import { CalCell, CalStat, Snap } from '../model/Snap';
import { Chip, DayCell } from './components';
import { BG_CARD, C_ACCENT, C_BAD, C_HINT, C_LINE, C_ROW_BG, C_SEL_BG, C_SUB, C_TEXT } from './theme';

@ComponentV2
export struct CalendarPage {
  @Param snap: Snap = new Snap();
  @Param locked: boolean = false;
  /** 选中日的两个输入框文本（由外壳持有，避免输入时被重算冲掉） */
  @Param selOt: string = '0';
  @Param selLeave: string = '0';

  @Event onFillApi: () => void = () => {
  };
  @Event onFillLocal: () => void = () => {
  };
  @Event onFillDefault: () => void = () => {
  };
  @Event onClear: () => void = () => {
  };
  @Event onPickDay: (day: number) => void = (day: number) => {
  };
  @Event onStatus: (s: string) => void = (s: string) => {
  };
  @Event onMark: (m: number) => void = (m: number) => {
  };
  @Event onOt: (v: string) => void = (v: string) => {
  };
  @Event onLeave: (v: string) => void = (v: string) => {
  };

  private chipActive(label: string): boolean {
    return this.snap.selStatus === label;
  }

  /** 空格子（day=0）与有内容的格子必须能区分，且选中态要进 key（否则点了不变色）。 */
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

  build() {
    // 与桌面版一致：操作条是页面级独立一行（桌面版是 lay 里的 bar，不在月历卡里）。
    // 放进卡里的话，卡只有左栏那么宽 → 四颗按钮必然溢出到卡片外面。
    Column({ space: 10 }) {
      Flex({ wrap: FlexWrap.Wrap, justifyContent: FlexAlign.End }) {
        Button('🌐 API 一键铺（联网）')
          .type(ButtonType.Normal)
          .fontSize(11)
          .height(30)
          .margin({ left: 8, bottom: 4 })
          .enabled(!this.locked)
          .backgroundColor('#ECFDF5')
          .fontColor('#065F46')
          .onClick(() => this.onFillApi())
        Button('📋 铺本地表（法定节假日/调休）')
          .type(ButtonType.Normal)
          .fontSize(11)
          .height(30)
          .margin({ left: 8, bottom: 4 })
          .enabled(!this.locked)
          .backgroundColor('#F5F3FF')
          .fontColor('#5B21B6')
          .onClick(() => this.onFillLocal())
        Button('✨ 一键铺（周末休/工作日上）')
          .type(ButtonType.Normal)
          .fontSize(11)
          .height(30)
          .margin({ left: 8, bottom: 4 })
          .enabled(!this.locked)
          .backgroundColor(C_SEL_BG)
          .fontColor(C_ACCENT)
          .onClick(() => this.onFillDefault())
        Button('清空考勤')
          .type(ButtonType.Normal)
          .fontSize(11)
          .height(30)
          .margin({ left: 8, bottom: 4 })
          .enabled(!this.locked)
          .backgroundColor('#FEF2F2')
          .fontColor(C_BAD)
          .onClick(() => this.onClear())
      }
      .width('100%')

      Text('「铺本地表 / API 一键铺」只覆盖周末、法定节假日、调休三类日期（并把「法定节假日」标记整月重写）；' +
        '其余普通工作日的状态不动，手填的请假不受影响。')
        .fontSize(11)
        .fontColor(C_HINT)
        .width('100%')

      // 统计小条也是页面级单独一组（桌面版 cg = QGridLayout，5 个一行），不在月历卡里
      Flex({ wrap: FlexWrap.Wrap }) {
        ForEach(this.snap.calStats, (s: CalStat) => {
          Text(`${s.label} ${s.value}`)
            .fontSize(11)
            .fontColor('#475467')
            .backgroundColor(C_ROW_BG)
            .border({ width: 1, color: C_LINE })
            .borderRadius(999)
            .padding({ left: 9, right: 9, top: 4, bottom: 4 })
            .margin({ right: 6, bottom: 6 })
        }, (s: CalStat) => `${s.label}-${s.value}`)
      }
      .width('100%')

      Row({ space: 14 }) {
        Column({ space: 8 }) {
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
                    // 月份锁定：点格子没反应（右侧 chips / 输入框也已禁用）
                    disabled: this.locked,
                    onPick: () => this.onPickDay(c.day)
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
                .fontSize(11)
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

        // ---------- 右侧：当天编辑 ----------
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
                disabled: this.locked,
                onTap: () => this.onStatus(s)
              })
            }, (s: string) => `${s}-${this.chipActive(s)}`)
          }
          .width('100%')

          Row({ space: 6 }) {
            ForEach(STATUS_LABELS.slice(5), (s: string) => {
              Chip({
                label: s,
                active: this.chipActive(s),
                disabled: this.locked,
                onTap: () => this.onStatus(s)
              })
            }, (s: string) => `${s}-${this.chipActive(s)}`)
            Chip({
              label: '未填',
              active: this.snap.selStatus.length === 0,
              disabled: this.locked,
              onTap: () => this.onStatus('')
            })
          }
          .width('100%')

          Text('标记').fontSize(12).fontColor(C_SUB).width('100%')
          Row({ space: 6 }) {
            Chip({ label: '无', active: this.snap.selMark === 0, disabled: this.locked, onTap: () => this.onMark(0) })
            Chip({
              label: '法定节假日', active: this.snap.selMark === 1, disabled: this.locked,
              onTap: () => this.onMark(1)
            })
            Chip({
              label: '视为正常劳动', active: this.snap.selMark === 2, disabled: this.locked,
              onTap: () => this.onMark(2)
            })
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
              .enabled(!this.locked)
              .onChange((v: string) => this.onOt(v))
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
              .enabled(!this.locked)
              .onChange((v: string) => this.onLeave(v))
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
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }
}
