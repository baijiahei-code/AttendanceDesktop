import { MonthBook } from '../core/model';

/**
 * 内存中的月份账本缓存（LRU）。
 *
 * 只保留最近使用的 N 个月：连续切月/年度汇总不会让内存无限增长。
 * 对外接口与 `Map<string, MonthBook>` 的 get/set/has/delete 一致，调用方无需改动。
 */
export class BookCache {
  private readonly limit: number;
  private readonly map: Map<string, MonthBook> = new Map<string, MonthBook>();

  constructor(limit: number) {
    this.limit = limit;
  }

  get(key: string): MonthBook | undefined {
    const v: MonthBook | undefined = this.map.get(key);
    if (v !== undefined) {
      // 命中后移到队尾（最近使用）
      this.map.delete(key);
      this.map.set(key, v);
    }
    return v;
  }

  set(key: string, value: MonthBook): void {
    this.map.delete(key);
    this.map.set(key, value);
    while (this.map.size > this.limit) {
      let oldest: string = '';
      let first: boolean = true;
      this.map.forEach((v: MonthBook, k: string) => {
        if (first) {
          oldest = k;
          first = false;
        }
      });
      if (oldest.length === 0) {
        break;
      }
      this.map.delete(oldest);
    }
  }

  has(key: string): boolean {
    return this.map.has(key);
  }

  delete(key: string): boolean {
    return this.map.delete(key);
  }
}
