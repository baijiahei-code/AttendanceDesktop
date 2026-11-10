/**
 * 存档（鸿蒙侧）：Preferences 明文 + 仅 API Key 用 HUKS 加密。
 *
 * 与桌面版一致：
 *   - 月份账本 / 参数模板 / 相关单位 / 工作地 → 明文（靠应用沙箱隔离，其它应用读不到）；
 *   - 只有 API Key 用 HUKS 加密 —— `HUKS AES-256-GCM（由系统密钥库托管密钥，不可导出，无密钥文件）`
 *     （与桌面版同一句式：Windows 是 `Windows DPAPI（由当前用户账户托管密钥，无密钥文件）`）。
 *
 * 为什么不再整份加密：HUKS 对称密钥不可导出、也没有备份/恢复接口，
 * 而 `backup_config.json` 会把 Preferences 一起备份 —— 换机恢复后密钥没了、密文解不开，
 * 账本会静默丢失。把「可重建的凭据」和「不可重建的账本」分开，是桌面版一直采用的口径。
 */

import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { MonthBook, MonthBookDict } from '../core/model';
import { Crypter } from './Crypto';

function pad2(n: number): string {
  return (n < 10 ? '0' : '') + n.toString();
}

/** API 配置（url / model 明文，key 为加密令牌）。 */
export class ApiStored {
  url: string = '';
  model: string = '';
  key: string = '';
}

/** 存储用记录（字段名短，减少 Preferences 体积）。 */
class ApiRecord {
  u: string = '';
  m: string = '';
  k: string = '';

  constructor(u: string, m: string, k: string) {
    this.u = u;
    this.m = m;
    this.k = k;
  }
}

const API_CONFIG_KEY: string = 'api_config';

export class MonthStorage {
  private pref: preferences.Preferences | null = null;
  private storeName: string = 'attendance_months';
  lastError: string = '';

  constructor(ctx: common.UIAbilityContext) {
    try {
      const options: preferences.Options = { name: this.storeName };
      this.pref = preferences.getPreferencesSync(ctx, options);
    } catch (e) {
      this.lastError = `初始化首选项失败：${e}`;
    }
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

  /** 读一个月；键不存在返回 null。读取失败返回 null 并记 lastError（不静默给空账本）。 */
  async loadMonth(year: number, month: number): Promise<MonthBook | null> {
    if (this.pref === null) {
      this.lastError = '首选项未初始化';
      return null;
    }
    this.lastError = '';
    const k: string = this.key(year, month);
    try {
      const stored = this.pref.getSync(k, '') as string;
      if (stored.length === 0) {
        return null;
      }
      const book: MonthBook = MonthBook.fromDict(JSON.parse(stored) as MonthBookDict);
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

  /** 保存一个月：明文 JSON → putSync → flushSync → 回读校验（与桌面版一致，靠应用沙箱隔离）。 */
  async saveMonth(book: MonthBook): Promise<boolean> {
    if (this.pref === null) {
      this.lastError = '首选项未初始化';
      return false;
    }
    const k: string = this.key(book.year, book.month);
    try {
      const stored: string = JSON.stringify(book.toDict());
      this.pref.putSync(k, stored);
      this.pref.flushSync();
      const back = this.pref.getSync(k, '') as string;
      if (back !== stored) {
        this.lastError = `回读不一致（写 ${stored.length} / 读 ${back.length}）`;
        return false;
      }
      return true;
    } catch (e) {
      this.lastError = `保存 ${k} 失败：${e}`;
      return false;
    }
  }

  /** 已存档的月份列表（"YYYY-MM"，升序）。以实际键为准，不限制年份范围。 */
  listMonths(): string[] {
    const out: string[] = [];
    if (this.pref === null) {
      return out;
    }
    try {
      const all: Object = this.pref.getAllSync();
      const keys: string[] = Object.keys(all);
      for (const k of keys) {
        if (k.length === 7 && k.charAt(4) === '-') {
          out.push(k);
        }
      }
      out.sort((a: string, b: string): number => a < b ? -1 : (a > b ? 1 : 0));
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

  cryptoOk(): boolean {
    return this.crypter.available;
  }

  cryptoError(): string {
    return this.crypter.lastError;
  }

  /** 启动预热：确保 HUKS 密钥就绪（只用于 API Key）。 */
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
      return stored;
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
      const stored: string = text;
      this.pref.putSync('units', stored);
      this.pref.flushSync();
      const back = this.pref.getSync('units', '') as string;
      if (back !== stored) {
        this.lastError = `相关单位回读不一致（写 ${stored.length} / 读 ${back.length}）`;
        return false;
      }
      return true;
    } catch (e) {
      this.lastError = `保存相关单位失败：${e}`;
      return false;
    }
  }

  /** 通用读取（明文）。键不存在返回 null。 */
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
      return stored;
    } catch (e) {
      this.lastError = `读取 ${key} 失败：${e}`;
      return null;
    }
  }

  /** 通用写入（明文 + 回读校验）。 */
  async saveText(key: string, text: string): Promise<boolean> {
    if (this.pref === null) {
      this.lastError = '设置首选项未初始化';
      return false;
    }
    try {
      const stored: string = text;
      this.pref.putSync(key, stored);
      this.pref.flushSync();
      const back = this.pref.getSync(key, '') as string;
      if (back !== stored) {
        this.lastError = `回读不一致（${key}）`;
        return false;
      }
      return true;
    } catch (e) {
      this.lastError = `保存 ${key} 失败：${e}`;
      return false;
    }
  }

  /** 读 API 配置（单键 JSON）。解密失败时 key 为空并把原因写进 lastError。 */
  async loadApiConfig(): Promise<ApiStored> {
    const out: ApiStored = new ApiStored();
    if (this.pref === null) {
      this.lastError = '设置首选项未初始化';
      return out;
    }
    this.lastError = '';
    try {
      const stored = this.pref.getSync(API_CONFIG_KEY, '') as string;
      if (stored.length === 0) {
        return out;
      }
      const rec: ApiRecord = JSON.parse(stored) as ApiRecord;
      out.url = rec.u === undefined ? '' : rec.u;
      out.model = rec.m === undefined ? '' : rec.m;
      const token: string = rec.k === undefined ? '' : rec.k;
      if (token.length > 0) {
        out.key = await this.crypter.decrypt(token);
      }
      return out;
    } catch (e) {
      this.lastError = `读取 API 配置失败：${e}`;
      return out;
    }
  }

  /** 写 API 配置（单键一次写入；key 走 HUKS，失败降级 h0 并记原因）。 */
  async saveApiConfig(url: string, model: string, key: string): Promise<boolean> {
    if (this.pref === null) {
      this.lastError = '设置首选项未初始化';
      return false;
    }
    this.lastError = '';
    try {
      const token: string = key.length > 0 ? await this.crypter.encrypt(key) : '';
      const stored: string = JSON.stringify(new ApiRecord(url, model, token));
      this.pref.putSync(API_CONFIG_KEY, stored);
      this.pref.flushSync();
      const back = this.pref.getSync(API_CONFIG_KEY, '') as string;
      if (back !== stored) {
        this.lastError = '回读不一致（api_config）';
        return false;
      }
      if (!this.crypter.available) {
        this.lastError = this.crypter.lastError;
      }
      // 清掉旧版本拆开存的三个键（本版本不再使用）
      this.pref.deleteSync('api_url');
      this.pref.deleteSync('api_model');
      this.pref.deleteSync('api_key');
      this.pref.flushSync();
      return true;
    } catch (e) {
      this.lastError = `保存 API 配置失败：${e}`;
      return false;
    }
  }

  /** 锁定月份集合（逗号分隔的 "YYYY-MM"）。 */
  async loadLockedMonths(): Promise<string> {
    const txt: string | null = await this.loadText('locked_months');
    return txt === null ? '' : txt;
  }

  async saveLockedMonths(text: string): Promise<boolean> {
    return await this.saveText('locked_months', text);
  }
}
