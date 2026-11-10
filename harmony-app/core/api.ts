/**
 * OpenAI 兼容 Chat API 的纯逻辑层（对应桌面版 `app/wages.py` 的 API 部分）。
 *
 * 这里只做纯函数：端点拼接、错误码文案、JSON 提取、回复解析与合理性校验。
 * 真正的 HTTP 请求在 ArkTS 侧（`model/ApiClient.ets`），Node 测试可直接测本文件。
 */

/** OpenAI 兼容服务商模板（与桌面版 `pages_params.py` 的 providers 一致）。 */
export class ApiProvider {
  name: string;
  base: string;
  model: string;

  constructor(name: string, base: string, model: string) {
    this.name = name;
    this.base = base;
    this.model = model;
  }
}

export const API_PROVIDERS: ApiProvider[] = [
  new ApiProvider('Agnes', 'https://apihub.agnes-ai.com/v1', 'agnes-2.5-flash'),
  new ApiProvider('DeepSeek', 'https://api.deepseek.com/v1', 'deepseek-chat'),
  new ApiProvider('通义千问', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'qwen-max'),
  new ApiProvider('Kimi (Moonshot)', 'https://api.moonshot.cn/v1', 'moonshot-v1-8k'),
  new ApiProvider('智谱 GLM', 'https://open.bigmodel.cn/api/paas/v4', 'glm-4-plus'),
  new ApiProvider('OpenAI', 'https://api.openai.com/v1', 'gpt-4o-mini'),
  new ApiProvider('硅基流动', 'https://api.siliconflow.cn/v1', 'Qwen2.5-7B-Instruct'),
  new ApiProvider('火山方舟 (豆包)', 'https://ark.cn-beijing.volces.com/api/v3', 'doubao-seed-1-32k'),
  new ApiProvider('腾讯混元', 'https://api.hunyuan.cloud.tencent.com/v1', 'hunyuan-turbos-latest'),
  new ApiProvider('零一万物', 'https://api.lingyiwanwu.com/v1', 'yi-lightning')
];

/** 短回答（最低工资）超时（秒）。 */
export const CHAT_TIMEOUT_SEC = 25;
/** 节假日要吐 30+ 日期，慢模型更久。 */
export const HOLIDAY_TIMEOUT_SEC = 45;
export const CHAT_PATH: string = '/chat/completions';

/** 月最低工资合理区间（元）。模型幻觉不能进账本。 */
export const MIN_WAGE_RANGE: number[] = [500, 20000];
/** 非全日制小时最低工资合理区间（元/时）。 */
export const PARTTIME_RANGE: number[] = [5, 200];
/** 小时标准 ÷ 月标准 的合理区间（全国普遍 ≈1/100）。 */
export const HOURLY_RATIO_RANGE: number[] = [0.005, 0.02];

/**
 * 拼出 `/chat/completions` 端点；非 https 或地址为空返回 null。
 *
 * 容错：
 * * 直接粘贴完整端点 `.../v1/chat/completions` → 不再重复拼一段
 * * 地址带查询串（`...?key=xxx`）→ 在 `?` 之前插入路径
 */
export function chatEndpoint(apiUrl: string): string | null {
  let url: string = (apiUrl === null || apiUrl === undefined) ? '' : apiUrl.trim();
  if (url.length === 0) {
    return null;
  }
  let query: string = '';
  const qPos: number = url.indexOf('?');
  const hPos: number = url.indexOf('#');
  let cut: number = -1;
  if (qPos >= 0 && hPos >= 0) {
    cut = Math.min(qPos, hPos);
  } else if (qPos >= 0) {
    cut = qPos;
  } else if (hPos >= 0) {
    cut = hPos;
  }
  if (cut >= 0) {
    query = url.substring(cut);
    url = url.substring(0, cut);
  }
  // 去掉末尾所有 '/'
  while (url.length > 0 && url.charAt(url.length - 1) === '/') {
    url = url.substring(0, url.length - 1);
  }
  const lower: string = url.toLowerCase();
  const endpoint: string = lower.endsWith(CHAT_PATH) ? url : url + CHAT_PATH;
  const full: string = endpoint + query;
  return full.toLowerCase().startsWith('https://') ? full : null;
}

/** HTTP 状态码 → 用户可读原因（附服务端原始说明，便于自查）。 */
export function httpReason(code: number, detail: string): string {
  let base: string;
  if (code === 400) {
    base = '请求被服务端拒绝（400，常见原因：模型名不受支持 / 参数不被接受）';
  } else if (code === 401) {
    base = 'API Key 无效（401）';
  } else if (code === 403) {
    base = 'API Key 无权访问该模型（403）';
  } else if (code === 404) {
    base = '接口地址或模型名不正确（404），请检查 API 地址与模型名';
  } else if (code === 429) {
    base = '调用频率超限（429），请稍后再试';
  } else if (code >= 500) {
    base = `服务商服务器错误（${code}）`;
  } else {
    base = `HTTP 错误（${code}）`;
  }
  const d: string = (detail === null || detail === undefined) ? '' : detail;
  // 压缩所有空白（换行 / 制表 / 连续空格）并截断
  const flat: string = d.replace(/\s+/g, ' ').trim();
  const cut: string = flat.length > 160 ? flat.substring(0, 160) : flat;
  return cut.length > 0 ? `${base}｜服务端：${cut}` : base;
}

/**
 * 从模型回复里取出 JSON 对象文本（容错 markdown 围栏 / 前后解释）。
 * 从第一个 `{` 起做括号配对（跳过字符串内的括号），返回原始 JSON 字符串。
 */
export function extractJsonObject(text: string): string | null {
  let s: string = (text === null || text === undefined) ? '' : text.trim();
  if (s.startsWith('```')) {
    // 去掉 ```json 开头与结尾的 ```
    s = s.replace(/^```[A-Za-z]*\s*/, '');
    s = s.replace(/\s*```\s*$/, '');
  }
  const start: number = s.indexOf('{');
  if (start < 0) {
    return null;
  }
  let depth: number = 0;
  let inStr: boolean = false;
  let esc: boolean = false;
  for (let i = start; i < s.length; i++) {
    const ch: string = s.charAt(i);
    if (inStr) {
      if (esc) {
        esc = false;
      } else if (ch === '\\') {
        esc = true;
      } else if (ch === '"') {
        inStr = false;
      }
      continue;
    }
    if (ch === '"') {
      inStr = true;
    } else if (ch === '{') {
      depth = depth + 1;
    } else if (ch === '}') {
      depth = depth - 1;
      if (depth === 0) {
        return s.substring(start, i + 1);
      }
    }
  }
  return null;
}

/** 联网查询最低工资的结果。 */
export class WageApiResult {
  ok: boolean = false;
  minWage: number = 0;
  parttimeMin: number = 0;
  error: string = '';
}

/** 内置 JSON 取值（ArkTS 不便直接用 any）。 */
function numField(raw: string, key: string): number {
  const re: RegExp = new RegExp(`"${key}"\\s*:\\s*(-?[0-9]+(?:\\.[0-9]+)?)`);
  const m: RegExpMatchArray | null = raw.match(re);
  if (m === null) {
    return 0;
  }
  const v: number = parseFloat(m[1]);
  return isNaN(v) ? 0 : v;
}

/**
 * 解析「最低工资」类回复。
 * 成功返回 ok=true 与两个数值；失败返回 ok=false 与可展示原因。
 */
export function parseWageReply(text: string): WageApiResult {
  const out: WageApiResult = new WageApiResult();
  const json: string | null = extractJsonObject(text);
  if (json === null) {
    out.error = '模型返回的不是要求的 JSON 格式（可换用更擅长结构化输出的模型，或改用本地表）';
    return out;
  }
  const mw: number = numField(json, 'min_wage');
  const ph: number = numField(json, 'parttime_min');
  if (mw <= 0 || ph <= 0) {
    out.error = '模型未返回有效数额（需同时给出 min_wage 与 parttime_min）';
    return out;
  }
  if (mw < MIN_WAGE_RANGE[0] || mw > MIN_WAGE_RANGE[1]) {
    out.error = `模型给出的月最低工资 ${mw} 元明显不合理（合理区间 ${MIN_WAGE_RANGE[0]}~${MIN_WAGE_RANGE[1]} 元），已忽略`;
    return out;
  }
  if (ph < PARTTIME_RANGE[0] || ph > PARTTIME_RANGE[1]) {
    out.error = `模型给出的非全日制小时工资 ${ph} 元/时明显不合理（合理区间 ${PARTTIME_RANGE[0]}~${PARTTIME_RANGE[1]} 元），已忽略`;
    return out;
  }
  const ratio: number = ph / mw;
  if (ratio < HOURLY_RATIO_RANGE[0] || ratio > HOURLY_RATIO_RANGE[1]) {
    out.error = `模型给出的两个数额不匹配（月 ${mw} 元 / 小时 ${ph} 元，正常应为月标准的约 1/100），已忽略`;
    return out;
  }
  out.ok = true;
  out.minWage = mw;
  out.parttimeMin = ph;
  return out;
}

/** 联网查询节假日的结果（MM-DD 列表）。 */
export class HolidayApiResult {
  ok: boolean = false;
  statutory: string[] = [];
  rest: string[] = [];
  makeup: string[] = [];
  error: string = '';
}

/** 把模型返回的日期数组规范成去重升序的 MM-DD 列表。 */
export function cleanMmdd(arr: string[]): string[] {
  const out: string[] = [];
  for (const raw of arr) {
    const parts: string[] = raw.trim().split('/').join('-').split('-');
    let mm: string = '';
    let dd: string = '';
    if (parts.length === 2) {
      mm = parts[0];
      dd = parts[1];
    } else if (parts.length === 3) {
      mm = parts[1];
      dd = parts[2];
    } else {
      continue;
    }
    const mi: number = parseInt(mm);
    const di: number = parseInt(dd);
    if (isNaN(mi) || isNaN(di)) {
      continue;
    }
    if (mi < 1 || mi > 12 || di < 1 || di > 31) {
      continue;
    }
    const item: string = `${mi < 10 ? '0' : ''}${mi}-${di < 10 ? '0' : ''}${di}`;
    if (out.indexOf(item) < 0) {
      out.push(item);
    }
  }
  out.sort();
  return out;
}

/** 从 JSON 里取一个字符串数组字段（取值失败返回空数组）。 */
function strArrayField(raw: string, key: string): string[] {
  const idx: number = raw.indexOf(`"${key}"`);
  if (idx < 0) {
    return [];
  }
  const lb: number = raw.indexOf('[', idx);
  if (lb < 0) {
    return [];
  }
  const rb: number = raw.indexOf(']', lb);
  if (rb < 0) {
    return [];
  }
  const body: string = raw.substring(lb + 1, rb);
  const out: string[] = [];
  const re: RegExp = /"([^"]*)"/g;
  let m: RegExpExecArray | null = re.exec(body);
  while (m !== null) {
    out.push(m[1]);
    m = re.exec(body);
  }
  return out;
}

/** 解析「节假日」类回复。 */
export function parseHolidayReply(text: string, year: number): HolidayApiResult {
  const out: HolidayApiResult = new HolidayApiResult();
  const json: string | null = extractJsonObject(text);
  if (json === null) {
    out.error = '模型返回的节假日数据不是有效 JSON（可换用更擅长结构化输出的模型）';
    return out;
  }
  out.statutory = cleanMmdd(strArrayField(json, 'statutory'));
  out.rest = cleanMmdd(strArrayField(json, 'rest'));
  out.makeup = cleanMmdd(strArrayField(json, 'makeup'));
  if (out.statutory.length === 0 && out.rest.length === 0 && out.makeup.length === 0) {
    out.error = `模型没有给出任何日期（${year} 年的安排可能尚未公布，或该模型未能给出），请改用本地表`;
    return out;
  }
  out.ok = true;
  return out;
}

/** 最低工资查询用的 prompt（与桌面版逐字一致）。 */
export function wagePrompt(province: string, region: string, year: number, month: number): string {
  return `请查询中国 ${province} ${region} ${year} 年 ${month} 月的最低工资标准。` +
    '返回一个 JSON 对象，只包含两个数值字段：min_wage（月最低工资，单位元）和 parttime_min（非全日制小时最低工资，单位元）。' +
    `如果找不到 ${year} 年 ${month} 月的官方发布标准，就用该地区在 ${year} 年 ${month} 月实际有效的最新标准。` +
    '直接返回 JSON，不要任何解释、不要 markdown、不要代码块。';
}

/** 节假日查询用的 prompt（与桌面版逐字一致）。 */
export function holidayPrompt(year: number): string {
  return `请查询中国国务院办公厅发布的 ${year} 年法定节假日放假安排（含每个节假日的法定日、放假调休区间、调休补班日）。` +
    '返回一个 JSON 对象，只包含三个数组字段：' +
    '1) statutory：数组，每项为 MM-DD 格式的法定节假日日期（×3加班的那一天）。' +
    '2) rest：数组，每项为 MM-DD 格式的放假调休日（包括法定日和拼假休息日）。' +
    '3) makeup：数组，每项为 MM-DD 格式的调休补班日（原本是周末但需要上班的日子）。' +
    '严格基于官方发布的安排，不要臆造。直接返回 JSON，不要任何解释、不要 markdown、不要代码块。';
}
