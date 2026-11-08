import { describe, expect, it } from 'vitest';
import { daysInMonth, weekdayIndex } from '../core/model';

/** 星期几：0=周一 … 6=周日（与 Python `date.weekday()` 同口径）。 */
describe('weekdayIndex（日历排版基础）', () => {
  const cases: Array<[number, number, number, number, string]> = [
    [1970, 1, 1, 3, '周四'],
    [2025, 1, 1, 2, '周三'],
    [2026, 1, 1, 3, '周四'],
    [2026, 2, 1, 6, '周日'],
    [2026, 10, 1, 3, '周四（国庆）'],
    [2026, 11, 1, 6, '周日'],
    [2026, 11, 30, 0, '周一'],
  ];

  for (const c of cases) {
    it(`${c[0]}-${c[1]}-${c[2]} → ${c[4]}`, () => {
      expect(weekdayIndex(c[0], c[1], c[2])).toBe(c[3]);
    });
  }
});

describe('daysInMonth', () => {
  const cases: Array<[number, number, number]> = [
    [2026, 1, 31],
    [2026, 2, 28],
    [2024, 2, 29],
    [2000, 2, 29],
    [1900, 2, 28],
    [2026, 11, 30],
    [2026, 13, 0],
  ];
  for (const c of cases) {
    it(`${c[0]}-${c[1]} → ${c[2]} 天`, () => {
      expect(daysInMonth(c[0], c[1])).toBe(c[2]);
    });
  }
});
