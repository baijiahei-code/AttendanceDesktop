import { describe, it, expect } from 'vitest';
import { csvEscape, csvRow, reportCsv, reportFileName } from '../core/csv';
import { buildCommonPayItems, createBook, MonthBook, PayItem } from '../core/model';
import { compute } from '../core/calc';

function sampleBook(): MonthBook {
  const b: MonthBook = createBook(2026, 11);
  for (const d of b.days) {
    d.status = '上班';
    d.overtime_hours = 0;
  }
  b.pay_items = buildCommonPayItems();
  b.pay_items.push(new PayItem('基本工资', 'wage', 8000));
  b.min_wage = 2000;
  b.social_base = 4000;
  b.personal_social_rate = 0.105;
  b.company_social_rate = 0.26;
  b.fund_base = 2000;
  b.personal_fund_rate = 0.07;
  b.company_fund_rate = 0.07;
  b.overtime_base = 2000;
  b.note = '测试备注';
  return b;
}

describe('csvEscape / csvRow', () => {
  it('普通字段不加引号', () => {
    expect(csvEscape('应发工资')).toBe('应发工资');
  });

  it('含逗号的字段加引号', () => {
    expect(csvEscape('a,b')).toBe('"a,b"');
  });

  it('含引号的字段：加引号且内部引号翻倍', () => {
    expect(csvEscape('他说"好"')).toBe('"他说""好"""');
  });

  it('含换行的字段加引号', () => {
    expect(csvEscape('a\nb')).toBe('"a\nb"');
  });

  it('csvRow 用逗号连接并逐字段转义', () => {
    expect(csvRow(['x', 'a,b', ''])).toBe('x,"a,b",');
  });
});

describe('reportCsv', () => {
  const b: MonthBook = sampleBook();
  const r = compute(b);
  const csv: string = reportCsv(b, r);
  const lines: string[] = csv.split('\r\n');

  it('表头含年月与备注', () => {
    expect(lines[0]).toContain('工作考勤表 · 2026 年 11 月 核算报表');
    expect(lines[1]).toBe('备注：测试备注,,');
  });

  it('缺备注时写（无）', () => {
    const b2: MonthBook = sampleBook();
    b2.note = '   ';
    const csv2: string = reportCsv(b2, compute(b2));
    expect(csv2.split('\r\n')[1]).toBe('备注：（无）,,');
  });

  it('汇总段有 6 个关键数字，金额保留 2 位', () => {
    const idx: number = lines.indexOf('汇总数据,,');
    expect(idx).toBeGreaterThan(0);
    expect(lines[idx + 1]).toMatch(/^应发工资,\d+\.\d{2},元$/);
    expect(lines[idx + 2]).toMatch(/^个人扣除,-\d+\.\d{2},元$/);
    expect(lines[idx + 3]).toMatch(/^请假扣款,-\d+\.\d{2},元$/);
    expect(lines[idx + 4]).toMatch(/^实际到手,\d+\.\d{2},元$/);
    expect(lines[idx + 5]).toMatch(/^到手小时工资,\d+\.\d{2},元 \/ h$/);
    expect(lines[idx + 6]).toMatch(/^公司总成本,\d+\.\d{2},含公司社保 \/ 公积金$/);
  });

  it('包含全部 6 个分组标题（含合规判定）', () => {
    const titles: string[] = r.groups.map((g) => g.title);
    expect(titles.length).toBeGreaterThanOrEqual(6);
    for (const t of titles) {
      expect(lines).toContain(`${t},,`);
    }
    expect(titles).toContain('合规判定');
  });

  it('每行最多 3 个字段（除被引号包裹的情况）', () => {
    for (const line of lines) {
      if (line.length === 0 || line.indexOf('"') >= 0) {
        continue;
      }
      expect(line.split(',').length).toBeLessThanOrEqual(3);
    }
  });

  it('使用 CRLF 换行（Excel 友好）', () => {
    expect(csv.indexOf('\r\n')).toBeGreaterThan(0);
    expect(csv.indexOf('\n') === -1 || csv.indexOf('\r\n') >= 0).toBe(true);
  });

  it('文件名：工资考勤报表_2026年11月.csv', () => {
    expect(reportFileName(b)).toBe('工资考勤报表_2026年11月.csv');
  });
});
