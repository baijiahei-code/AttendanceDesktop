import { describe, it, expect } from 'vitest';
import {
  MIN_WAGE_PROVINCES,
  MIN_WAGE_ROWS,
  minWageRegions,
  minWageOf,
  minWageFirst,
  MinWageRow
} from '../core/minwage.data';

/**
 * 最低工资表来自桌面版 `app/wages.py`（scripts/export_minwage.py 导出）。
 * 这里锁住规模与几个公开可查的值，防止导出脚本出错或数据被手改。
 */
describe('minwage.data（与桌面版一致）', () => {
  it('省份 31 个', () => {
    expect(MIN_WAGE_PROVINCES.length).toBe(31);
  });

  it('地区 394 条', () => {
    expect(MIN_WAGE_ROWS.length).toBe(394);
  });

  it('省份顺序：常用省在前（北京、上海、广东…）', () => {
    expect(MIN_WAGE_PROVINCES.slice(0, 3)).toEqual(['北京', '上海', '广东']);
    expect(MIN_WAGE_PROVINCES).toContain('黑龙江');
  });

  it('上海：2740 / 25.0', () => {
    const r = minWageOf('上海', '全市统一');
    expect(r).not.toBeNull();
    expect(r?.month).toBe(2740);
    expect(r?.hour).toBe(25);
  });

  it('北京：2540 / 27.7', () => {
    const r = minWageOf('北京', '全市统一');
    expect(r?.month).toBe(2540);
    expect(r?.hour).toBe(27.7);
  });

  it('广州 2500 / 深圳 2520（同省不同档）', () => {
    expect(minWageOf('广东', '广州')?.month).toBe(2500);
    expect(minWageOf('广东', '广州')?.hour).toBe(23.7);
    expect(minWageOf('广东', '深圳')?.month).toBe(2520);
    expect(minWageOf('广东', '深圳')?.hour).toBe(23.7);
  });

  it('查不到的地区返回 null（不静默换成别的城市）', () => {
    expect(minWageOf('上海', '不存在的区')).toBeNull();
    expect(minWageOf('不存在的省', '全市统一')).toBeNull();
  });

  it('每个省至少一条，且 minWageRegions 与 minWageFirst 自洽', () => {
    for (const p of MIN_WAGE_PROVINCES) {
      const regions = minWageRegions(p);
      expect(regions.length).toBeGreaterThan(0);
      const first = minWageFirst(p);
      expect(first).not.toBeNull();
      // 「全省未细分」时取第一个地区，与桌面版 get(province) 行为一致
      expect(first?.region).toBe(regions[0]);
    }
  });

  it('每个地区都能按名字查回自己', () => {
    for (const row of MIN_WAGE_ROWS) {
      const found: MinWageRow | null = minWageOf(row.province, row.region);
      expect(found).not.toBeNull();
      expect(found?.month).toBe(row.month);
      expect(found?.hour).toBe(row.hour);
    }
  });

  it('(省, 地区) 无重复', () => {
    const seen = new Set<string>();
    for (const row of MIN_WAGE_ROWS) {
      const key = `${row.province}/${row.region}`;
      expect(seen.has(key)).toBe(false);
      seen.add(key);
    }
  });

  it('数值合理：月 500~20000，时 5~200', () => {
    for (const row of MIN_WAGE_ROWS) {
      expect(row.month).toBeGreaterThanOrEqual(500);
      expect(row.month).toBeLessThanOrEqual(20000);
      expect(row.hour).toBeGreaterThanOrEqual(5);
      expect(row.hour).toBeLessThanOrEqual(200);
    }
  });
});
