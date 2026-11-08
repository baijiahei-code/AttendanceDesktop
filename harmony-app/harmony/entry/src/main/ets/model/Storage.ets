/**
 * 存档（鸿蒙侧）：Preferences + HUKS 加密。
 *
 * 存储选型依据官方文档「通过用户首选项实现数据持久化」：
 *   轻量键值数据用 Preferences（同步 API：getPreferencesSync / putSync / getSync / flushSync）。
 * 加密选型：HUKS（系统密钥库，密钥不可导出）—— 见 Crypto.ets。
 *
 * 落盘格式：`h1:<base64(nonce||ciphertext)>`（AES-256-GCM）。
 * HUKS 不可用时降级为 `h0:<base64(明文)>` 并置 cryptoAvailable=false（界面会提示未加密）。
 *
 * 业务数据仍是 `MonthBook.to_dict()` 的 JSON —— 与桌面版同构，将来可导出。
 *
 * ⚠ HUKS 只有异步接口，所以本类的读写都是 Promise。
 */

import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { MonthBook, MonthBookDict } from '../core/model';
import { Crypter } from './Crypto';

function pad2(n: number): string {
  return (n < 10 ? '0' : '') + n.toString();
}

export class MonthStorage {
  private pref: preferences.Preferences | null = null;
  private storeName: string = 'attendance_months';
  private crypter: Crypter = new Crypter();
  lastError: string = '';

  constructor(ctx: common.UIAbilityContext) {
    try {
      const options: preferences.Options = { name: this.storeName };
      this.pref = preferences.getPreferencesSync(ctx, options);
    } catch (e) {
      this.lastError = `初始化首选项失败：${e}`;
    }
  }

  location(): string {
    return `用户首选项「${this.storeName}」+ HUKS 加密`;
  }

  cryptoOk(): boolean {
    return this.crypter.available;
  }

  /** 加密失败的阶段与错误码（界面要显示，方便定位）。 */
  cryptoError(): string {
    return this.crypter.lastError;
  }

  private key(year: number, month: number): string {
    return `${year}-${pad2(month)}`;
  }

  hasMonth(year: number, month: number): boolean {
    if (this.pref === null) {
      return false;
    }
    try {
      return this.pref.hasSync(this.key(year, month));
    } catch (e) {
      return false;
    }
  }

  /** 读一个月；键不存在返回 null。解密失败返回 null 并记错误（不静默给空账本）。 */
  async loadMonth(year: number, month: number): Promise<MonthBook | null> {
    if (this.pref === null) {
      this.lastError = '首选项未初始化';
      return null;
    }
    const k: string = this.key(year, month);
    try {
      if (!this.pref.hasSync(k)) {
        return null;
      }
      const stored = this.pref.getSync(k, '') as string;
      if (stored.length === 0) {
        return null;
      }
      const text: string = await this.crypter.decrypt(stored);
      const book: MonthBook = MonthBook.fromDict(JSON.parse(text) as MonthBookDict);
      if (book.year !== year || book.month !== month) {
        this.lastError = `${k} 年月不符（读到 ${book.year}-${pad2(book.month)}）`;
        return null;
      }
      if (book.days.length === 0) {
        this.lastError = `${k} 没有考勤日`;
        return null;
      }
      return book;
    } catch (e) {
      this.lastError = `读取 ${k} 失败：${e}`;
      return null;
    }
  }

  /** 保存一个月：加密 → putSync → flushSync → 回读校验。 */
  async saveMonth(book: MonthBook): Promise<boolean> {
    if (this.pref === null) {
      this.lastError = '首选项未初始化';
      return false;
    }
    const k: string = this.key(book.year, book.month);
    try {
      const json: string = JSON.stringify(book.toDict());
      const stored: string = await this.crypter.encrypt(json);
      this.pref.putSync(k, stored);
      this.pref.flushSync();
      const back = this.pref.getSync(k, '') as string;
      if (back !== stored) {
        this.lastError = `回读不一致（写 ${stored.length} / 读 ${back.length}）`;
        return false;
      }
      if (!this.crypter.available) {
        this.lastError = this.crypter.lastError;
      }
      return true;
    } catch (e) {
      this.lastError = `保存 ${k} 失败：${e}`;
      return false;
    }
  }

  /** 已存档的月份列表（"YYYY-MM"，升序）。 */
  listMonths(): string[] {
    const out: string[] = [];
    if (this.pref === null) {
      return out;
    }
    const year: number = new Date().getFullYear();
    try {
      for (let y = year - 3; y <= year + 1; y++) {
        for (let m = 1; m <= 12; m++) {
          if (this.pref.hasSync(this.key(y, m))) {
            out.push(this.key(y, m));
          }
        }
      }
    } catch (e) {
      this.lastError = `列月份失败：${e}`;
    }
    return out;
  }

  /** 删除某个月的存档（不可恢复）。 */
  deleteMonth(year: number, month: number): boolean {
    if (this.pref === null) {
      this.lastError = '首选项未初始化';
      return false;
    }
    const k: string = this.key(year, month);
    try {
      this.pref.deleteSync(k);
      this.pref.flushSync();
      return !this.pref.hasSync(k);
    } catch (e) {
      this.lastError = `删除 ${k} 失败：${e}`;
      return false;
    }
  }
}

/** 全局设置（相关单位等，与月份无关）。 */
export class SettingsStorage {
  private pref: preferences.Preferences | null = null;
  private storeName: string = 'attendance_settings';
  private crypter: Crypter = new Crypter();
  lastError: string = '';

  constructor(ctx: common.UIAbilityContext) {
    try {
      const options: preferences.Options = { name: this.storeName };
      this.pref = preferences.getPreferencesSync(ctx, options);
    } catch (e) {
      this.lastError = `初始化设置失败：${e}`;
    }
  }

  location(): string {
    return `用户首选项「${this.storeName}」+ HUKS 加密`;
  }

  cryptoOk(): boolean {
    return this.crypter.available;
  }

  cryptoError(): string {
    return this.crypter.lastError;
  }

  /** 启动预热：确保当前密钥就绪。 */
  async warmUp(): Promise<boolean> {
    return await this.crypter.ready();
  }

  hasUnits(): boolean {
    if (this.pref === null) {
      return false;
    }
    try {
      return this.pref.hasSync('units');
    } catch (e) {
      return false;
    }
  }

  async loadUnitsText(): Promise<string | null> {
    if (this.pref === null) {
      this.lastError = '设置首选项未初始化';
      return null;
    }
    try {
      if (!this.pref.hasSync('units')) {
        return null;
      }
      const stored = this.pref.getSync('units', '') as string;
      if (stored.length === 0) {
        return null;
      }
      return await this.crypter.decrypt(stored);
    } catch (e) {
      this.lastError = `读取相关单位失败：${e}`;
      return null;
    }
  }

  async saveUnitsText(text: string): Promise<boolean> {
    if (this.pref === null) {
      this.lastError = '设置首选项未初始化';
      return false;
    }
    try {
      const stored: string = await this.crypter.encrypt(text);
      this.pref.putSync('units', stored);
      this.pref.flushSync();
      const back = this.pref.getSync('units', '') as string;
      if (back !== stored) {
        this.lastError = `相关单位回读不一致（写 ${stored.length} / 读 ${back.length}）`;
        return false;
      }
      if (!this.crypter.available) {
        this.lastError = this.crypter.lastError;
      }
      return true;
    } catch (e) {
      this.lastError = `保存相关单位失败：${e}`;
      return false;
    }
  }

  /** 通用读取（加密存档）。键不存在返回 null。 */
  async loadText(key: string): Promise<string | null> {
    if (this.pref === null) {
      this.lastError = '设置首选项未初始化';
      return null;
    }
    try {
      if (!this.pref.hasSync(key)) {
        return null;
      }
      const stored = this.pref.getSync(key, '') as string;
      if (stored.length === 0) {
        return null;
      }
      return await this.crypter.decrypt(stored);
    } catch (e) {
      this.lastError = `读取 ${key} 失败：${e}`;
      return null;
    }
  }

  /** 通用写入（加密存档 + 回读校验）。 */
  async saveText(key: string, text: string): Promise<boolean> {
    if (this.pref === null) {
      this.lastError = '设置首选项未初始化';
      return false;
    }
    try {
      const stored: string = await this.crypter.encrypt(text);
      this.pref.putSync(key, stored);
      this.pref.flushSync();
      const back = this.pref.getSync(key, '') as string;
      if (back !== stored) {
        this.lastError = `回读不一致（${key}）`;
        return false;
      }
      if (!this.crypter.available) {
        this.lastError = this.crypter.lastError;
      }
      return true;
    } catch (e) {
      this.lastError = `保存 ${key} 失败：${e}`;
      return false;
    }
  }
}
