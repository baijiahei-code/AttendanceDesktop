/**
 * 报表 CSV 生成（纯字符串，无 IO，便于测试）。
 *
 * 格式：纵向排版，3 列（标签 / 数值或文本 / 单位），与桌面版 xlsx 的结构一致
 * （标题 → 备注 → 各分组 → 合规判定）。合规判定本身就是 `Result.groups` 里的一组，
 * 因此这里不需要单独拼。
 *
 * 数值格式：
 *   - 单位是「元」→ 固定 2 位小数（与界面一致）
 *   - 整数 → 原样（天数、工时）
 *   - 其它小数 → 固定 2 位
 */

import { MonthBook } from './model';
import { ReportGroup, ReportLine, Result } from './calc';
import { pyFixed } from './num';

/** CSV 字段转义：含逗号/引号/换行时用双引号包裹，内部引号翻倍。 */
export function csvEscape(field: string): string {
  const needQuote: boolean =
    field.indexOf(',') >= 0 || field.indexOf('"') >= 0 ||
      field.indexOf('\n') >= 0 || field.indexOf('\r') >= 0;
  if (!needQuote) {
    return field;
  }
  return '"' + field.split('"').join('""') + '"';
}

/** 一行 CSV（字段数组 → 逗号分隔，行尾不带换行）。 */
export function csvRow(fields: string[]): string {
  const out: string[] = [];
  for (const f of fields) {
    out.push(csvEscape(f));
  }
  return out.join(',');
}

function fmtNumber(v: number, unit: string): string {
  if (!isFinite(v)) {
    return '';
  }
  if (Number.isInteger(v)) {
    return v.toString();
  }
  return pyFixed(v, 2);
}

function lineFields(line: ReportLine): string[] {
  // 组内小标题：只有标签，占满第一列
  if (line.kind === 'sec') {
    return [line.label, '', ''];
  }
  if (line.text !== null && line.text.length > 0) {
    return [line.label, line.text, ''];
  }
  if (line.value === null) {
    return [line.label, '', line.unit];
  }
  return [line.label, fmtNumber(line.value, line.unit), line.unit];
}

/** 生成整份报表 CSV（不含 BOM；写文件时由调用方补 \uFEFF）。 */
export function reportCsv(book: MonthBook, r: Result): string {
  const rows: string[] = [];
  const title: string = `工作考勤表 · ${book.year} 年 ${book.month} 月 核算报表`;
  rows.push(csvRow([title, '', '']));

  const note: string = book.note.trim();
  rows.push(csvRow([`备注：${note.length === 0 ? '（无）' : note}`, '', '']));
  rows.push('');

  // 汇总（与桌面版一致的 6 个关键数字）
  rows.push(csvRow(['汇总数据', '', '']));
  const companyCost: number = r.gross_wage + r.company_social + r.company_fund;
  rows.push(csvRow(['应发工资', pyFixed(r.gross_wage, 2), '元']));
  rows.push(csvRow(['个人扣除', pyFixed(-r.personal_deductions_total, 2), '元']));
  rows.push(csvRow(['请假扣款', pyFixed(-r.leave_deduction_total, 2), '元']));
  rows.push(csvRow(['实际到手', pyFixed(r.take_home, 2), '元']));
  rows.push(csvRow(['到手小时工资', pyFixed(r.take_home_hourly, 2), '元 / h']));
  rows.push(csvRow(['公司总成本', pyFixed(companyCost, 2), '含公司社保 / 公积金']));
  rows.push('');

  // 各分组（含合规判定）
  for (const g of r.groups) {
    const group: ReportGroup = g;
    rows.push(csvRow([group.title, '', '']));
    for (const line of group.lines) {
      rows.push(csvRow(lineFields(line)));
    }
    rows.push('');
  }

  return rows.join('\r\n');
}

/** 建议的文件名（与桌面版一致的中文命名）。 */
export function reportFileName(book: MonthBook): string {
  return `工资考勤报表_${book.year}年${book.month}月.csv`;
}
