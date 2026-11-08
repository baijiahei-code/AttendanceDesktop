import { describe, expect, it } from 'vitest';
import { pyRound2, pyRound6 } from '../core/num';

/**
 * 基准值全部来自桌面版 Python 实测（`Decimal(str(v)).quantize('0.01', ROUND_HALF_UP)`
 * 与 `round(v, 6)` 的真实输出），不是"我觉得应该等于"。
 */
describe('pyRound2 —— 对应 calc.py::_round2（Decimal(str(v)) + HALF_UP）', () => {
  const cases: Array<[number, number]> = [
    [443.835, 443.84], // 精确值 443.83499…，但 str 是 "443.835" → 进位
    [2.675, 2.68], // Python 内置 round 会给 2.67，此处必须是 2.68
    [1.005, 1.01], // toFixed 会给 1.00，此处必须是 1.01
    [0.125, 0.13], // 银行家舍入会给 0.12
    [0.615, 0.62],
    [0.605, 0.61],
    [12345678.905, 12345678.91],
    [1e-9, 0],
    [-1.005, -1.01],
    [0.1 + 0.2, 0.3], // 0.30000000000000004
    [2 / 3, 0.67],
    [0, 0],
  ];

  for (const c of cases) {
    it(`${c[0]} → ${c[1]}`, () => {
      expect(pyRound2(c[0])).toBe(c[1]);
    });
  }

  it('保留负零（Python 的 -0.004 → -0.0）', () => {
    const got: number = pyRound2(-0.004);
    // 注意：vitest 的 toBe 用 Object.is，-0 与 +0 不相等，所以这里分两步断言
    expect(got === 0).toBe(true);
    expect(Object.is(got, -0)).toBe(true);
  });

  it('null / undefined 按 0 处理（对应 Python 的 `v or 0.0`）', () => {
    expect(pyRound2(null)).toBe(0);
    expect(pyRound2(undefined)).toBe(0);
  });
});

describe('pyRound6 —— 对应 calc.py::_f（Python round(v, 6)，对精确值做 half-even）', () => {
  const cases: Array<[number, number]> = [
    [0.1234565, 0.123456], // 精确值 0.1234564999… → 舍
    [1.0000005, 1.000001], // 精确值 1.00000050000000006… → 入
    [1.2345678901234, 1.234568],
    [5e-7, 0],
    [1.0000004999, 1],
    [2.675, 2.675],
    [0.1 + 0.2, 0.3],
    [2 / 3, 0.666667],
    [443.835, 443.835],
  ];

  for (const c of cases) {
    it(`${c[0]} → ${c[1]}`, () => {
      expect(pyRound6(c[0])).toBe(c[1]);
    });
  }
});
