import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import * as path from 'node:path';

import { compute } from '../core/calc';
import { MonthBook } from '../core/model';
import type { MonthBookDict } from '../core/model';

interface Case {
  name: string;
  input: MonthBookDict;
  expected: unknown;
}

const here: string = path.dirname(fileURLToPath(import.meta.url));
const fixtureFile: string = path.resolve(here, '..', 'fixtures', 'baseline.json');

/** 把 Result / Counts / ReportGroup 实例摊平成与 `dataclasses.asdict` 同构的普通对象。 */
function toPlain(v: unknown): unknown {
  if (v === null || typeof v !== 'object') {
    return v;
  }
  if (Array.isArray(v)) {
    return v.map((x: unknown): unknown => toPlain(x));
  }
  const src = v as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const k of Object.keys(src)) {
    out[k] = toPlain(src[k]);
  }
  return out;
}

/** 递归比较，把差异写进 out（只报路径 + 两个值，够定位就行）。 */
function diffJson(expected: unknown, actual: unknown, at: string, out: string[]): void {
  if (out.length >= 40) {
    return;
  }
  if (typeof expected === 'number' && typeof actual === 'number') {
    if (expected !== actual) {
      out.push(`${at}: py=${expected} ts=${actual}`);
    }
    return;
  }
  if (Array.isArray(expected) || Array.isArray(actual)) {
    const ea: unknown[] = Array.isArray(expected) ? expected : [];
    const aa: unknown[] = Array.isArray(actual) ? actual : [];
    if (ea.length !== aa.length) {
      out.push(`${at}: 长度 py=${ea.length} ts=${aa.length}`);
      return;
    }
    for (let i = 0; i < ea.length; i++) {
      diffJson(ea[i], aa[i], `${at}[${i}]`, out);
    }
    return;
  }
  if (expected !== null && actual !== null
      && typeof expected === 'object' && typeof actual === 'object') {
    const eo = expected as Record<string, unknown>;
    const ao = actual as Record<string, unknown>;
    const keys: string[] = Array.from(new Set<string>([
      ...Object.keys(eo), ...Object.keys(ao)
    ])).sort();
    for (const k of keys) {
      diffJson(eo[k], ao[k], at === '' ? k : `${at}.${k}`, out);
    }
    return;
  }
  if (expected !== actual) {
    out.push(`${at}: py=${JSON.stringify(expected)} ts=${JSON.stringify(actual)}`);
  }
}

const fixture: { cases: Case[] } = { cases: [] };
try {
  const parsed = JSON.parse(readFileSync(fixtureFile, 'utf8')) as { cases: Case[] };
  fixture.cases = parsed.cases;
} catch {
  fixture.cases = [];
}

describe('与桌面版 Python 的数值对拍（fixtures/baseline.json）', () => {
  if (fixture.cases.length === 0) {
    it.skip('缺少 fixtures/baseline.json —— 先跑 scripts/dump_baseline.py', () => {
      // 跳过：基准文件是本机生成物（含真实工资数据），不进 git
    });
    return;
  }

  for (const c of fixture.cases) {
    it(c.name, () => {
      const book = MonthBook.fromDict(c.input);
      const got: unknown = toPlain(compute(book));
      const diffs: string[] = [];
      diffJson(c.expected, got, '', diffs);
      expect(diffs.slice(0, 20).join('\n')).toBe('');
    });
  }
});
