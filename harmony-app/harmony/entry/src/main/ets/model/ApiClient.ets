/**
 * OpenAI 兼容 Chat API 的 ArkTS 客户端（HTTP 部分）。
 *
 * 纯逻辑（端点拼接 / 错误文案 / JSON 提取 / 合理性校验）在 `core/api.ts`，
 * 这里只负责发请求并把结果翻译成「可直接展示」的中文原因。
 */
import { http } from '@kit.NetworkKit';
import { BusinessError } from '@kit.BasicServicesKit';
import {
  API_PROVIDERS,
  CHAT_TIMEOUT_SEC,
  HOLIDAY_TIMEOUT_SEC,
  chatEndpoint,
  extractJsonObject,
  httpReason,
  HolidayApiResult,
  parseHolidayReply,
  parseWageReply,
  WageApiResult,
  holidayPrompt,
  wagePrompt
} from '../core/api';

/** 服务商模板（ArkTS 侧使用的轻量副本）。 */
export class ApiProviderTemplate {
  name: string = '';
  base: string = '';
  model: string = '';

  constructor(name: string, base: string, model: string) {
    this.name = name;
    this.base = base;
    this.model = model;
  }
}

/** API 连接配置（存放在加密的 Preferences 里）。 */
export class ApiConfig {
  url: string = '';
  model: string = '';
  key: string = '';

  get configured(): boolean {
    return this.url.length > 0;
  }
}

/** 一次 Chat 调用的结果。 */
export class ChatResult {
  ok: boolean = false;
  text: string = '';
  error: string = '';
}

/** POST /chat/completions，返回首条回复正文。 */
/** Chat 消息与请求体（ArkTS 要求对象字面量有明确类型）。 */
interface ChatMessage {
  role: string;
  content: string;
}

interface ResponseFormat {
  type: string;
}

export async function chatPost(cfg: ApiConfig, prompt: string, timeoutSec: number,
                               jsonMode: boolean): Promise<ChatResult> {
  const out: ChatResult = new ChatResult();
  const endpoint: string | null = chatEndpoint(cfg.url);
  if (endpoint === null) {
    out.error = 'API 地址无效：必须以 https:// 开头（当前版本不支持 http 本地服务）';
    return out;
  }
  // 桌面版口径：没有默认模型名，空着就一个请求都不发（避免静默用错模型）
  if (cfg.model.length === 0) {
    out.error = '未填写模型名：请在「⚙️ API 设置」里选择服务商或手动填写模型名';
    return out;
  }
  const req: http.HttpRequest = http.createHttp();
  try {
    const msg: ChatMessage = { role: 'user', content: prompt };
    const messages: ChatMessage[] = [msg];
    let body: string = JSON.stringify(messages);
    // 组装请求体（手写 JSON，避开 Record 字面量限制）
    let payload: string = `{"model":${JSON.stringify(cfg.model)},` +
      `"temperature":0,"messages":${body}`;
    if (jsonMode) {
      const rf: ResponseFormat = { type: 'json_object' };
      payload = payload + `,"response_format":${JSON.stringify(rf)}`;
    }
    payload = payload + '}';

    const header: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    header['Accept'] = 'application/json';
    if (cfg.key.length > 0) {
      header['Authorization'] = `Bearer ${cfg.key}`;
    }
    const resp: http.HttpResponse = await req.request(endpoint, {
      method: http.RequestMethod.POST,
      header: header,
      extraData: payload,
      connectTimeout: 15000,
      readTimeout: timeoutSec * 1000,
      expectDataType: http.HttpDataType.STRING
    });
    const code: number = resp.responseCode;
    const respBody: string = typeof resp.result === 'string' ? resp.result as string : '';
    if (code < 200 || code >= 300) {
      out.error = httpReason(code, respBody);
      return out;
    }
    const json: string | null = extractJsonObject(respBody);
    if (json === null && respBody.indexOf('choices') < 0) {
      out.error = '返回内容不是有效 JSON，可能不是 OpenAI 兼容的 /chat/completions 端点';
      return out;
    }
    const content: string = messageContent(respBody);
    if (content.length === 0) {
      out.error = '接口返回内容为空，请检查模型名是否可用（推理型模型请换非推理型）';
      return out;
    }
    out.ok = true;
    out.text = content;
    return out;
  } catch (e) {
    const be: BusinessError = e as BusinessError;
    const msg: string = be !== undefined && be.message !== undefined ? be.message : `${e}`;
    out.error = msg.indexOf('timeout') >= 0 || msg.indexOf('Timeout') >= 0
      ? '连接超时，请检查网络或 API 地址'
      : `网络请求失败：${msg}`;
    return out;
  } finally {
    req.destroy();
  }
}

/**
 * 从 `/chat/completions` 的响应体里取 `choices[0].message.content`。
 * 兼容 content 为字符串 / 多段数组 / 老式 text 字段。
 */
function messageContent(body: string): string {
  const cIdx: number = body.indexOf('"choices"');
  if (cIdx < 0) {
    return '';
  }
  const msgIdx: number = body.indexOf('"message"', cIdx);
  const from: number = msgIdx >= 0 ? msgIdx : cIdx;
  const kIdx: number = body.indexOf('"content"', from);
  if (kIdx < 0) {
    const tIdx: number = body.indexOf('"text"', from);
    if (tIdx < 0) {
      return '';
    }
    return readJsonString(body, tIdx + 6);
  }
  const colon: number = body.indexOf(':', kIdx);
  if (colon < 0) {
    return '';
  }
  let p: number = colon + 1;
  while (p < body.length && (body.charAt(p) === ' ' || body.charAt(p) === '\n' ||
    body.charAt(p) === '\r' || body.charAt(p) === '\t')) {
    p = p + 1;
  }
  if (p >= body.length) {
    return '';
  }
  if (body.charAt(p) === '"') {
    return unescapeJson(body, p);
  }
  if (body.charAt(p) === '[') {
    // 多段数组：[{"type":"text","text":"..."}, ...] → 把所有 text 拼起来
    const rb: number = body.indexOf(']', p);
    const seg: string = rb > p ? body.substring(p, rb) : body.substring(p);
    let acc: string = '';
    let i: number = seg.indexOf('"text"');
    while (i >= 0) {
      const colon: number = seg.indexOf(':', i);
      if (colon < 0) {
        break;
      }
      acc = acc + readJsonString(seg, colon + 1);
      i = seg.indexOf('"text"', i + 6);
    }
    return acc;
  }
  return '';
}

/** 读取 `"` 起始的 JSON 字符串（p 必须指向开引号），返回反转义后的内容。 */
function readJsonString(body: string, quotePos: number): string {
  let p: number = quotePos;
  while (p < body.length && body.charAt(p) !== '"') {
    p = p + 1;
  }
  if (p >= body.length) {
    return '';
  }
  return unescapeJson(body, p);
}

/** 把从 quotePos（开引号）开始的 JSON 字符串反转义。 */
function unescapeJson(body: string, quotePos: number): string {
  let out: string = '';
  let i: number = quotePos + 1;
  while (i < body.length) {
    const ch: string = body.charAt(i);
    if (ch === '"') {
      break;
    }
    if (ch === '\\' && i + 1 < body.length) {
      const n: string = body.charAt(i + 1);
      if (n === 'n') {
        out = out + '\n';
      } else if (n === 't') {
        out = out + '\t';
      } else if (n === 'r') {
        out = out + '\r';
      } else if (n === '"') {
        out = out + '"';
      } else if (n === '\\') {
        out = out + '\\';
      } else if (n === 'u' && i + 5 < body.length) {
        const hex: string = body.substring(i + 2, i + 6);
        const cp: number = parseInt(hex, 16);
        if (!isNaN(cp)) {
          out = out + String.fromCharCode(cp);
        }
        i = i + 4;
      } else {
        out = out + n;
      }
      i = i + 2;
      continue;
    }
    out = out + ch;
    i = i + 1;
  }
  return out;
}

/** 测试连接：发一条极短消息，验证地址 / Key / 模型是否可用。 */
export async function testConnection(cfg: ApiConfig): Promise<ChatResult> {
  return await chatPost(cfg, '请只回复：ok', CHAT_TIMEOUT_SEC, false);
}

/** 联网查询最低工资（只走 API，不回退内置表）。 */
export async function fetchWageApi(cfg: ApiConfig, province: string, region: string,
                                   year: number, month: number): Promise<WageApiResult> {
  const out: WageApiResult = new WageApiResult();
  if (!cfg.configured) {
    out.error = '未配置 API 地址（请先点「⚙️ API 设置」）';
    return out;
  }
  const r: ChatResult = await chatPost(cfg, wagePrompt(province, region, year, month),
    CHAT_TIMEOUT_SEC, true);
  if (!r.ok) {
    out.error = r.error;
    return out;
  }
  return parseWageReply(r.text);
}

/** 联网查询某年节假日安排（只走 API，不回退内置表）。 */
export async function fetchHolidaysApi(cfg: ApiConfig, year: number): Promise<HolidayApiResult> {
  const out: HolidayApiResult = new HolidayApiResult();
  if (!cfg.configured) {
    out.error = '未配置 API 地址（请先点「⚙️ API 设置」）';
    return out;
  }
  const r: ChatResult = await chatPost(cfg, holidayPrompt(year), HOLIDAY_TIMEOUT_SEC, true);
  if (!r.ok) {
    out.error = r.error;
    return out;
  }
  return parseHolidayReply(r.text, year);
}

/** 服务商模板（供设置界面下拉）。 */
export function providers(): ApiProviderTemplate[] {
  const out: ApiProviderTemplate[] = [];
  for (const p of API_PROVIDERS) {
    out.push(new ApiProviderTemplate(p.name, p.base, p.model));
  }
  return out;
}
