import { describe, expect, it } from 'vitest';
import {
  chatEndpoint,
  cleanMmdd,
  extractJsonObject,
  httpReason,
  parseHolidayReply,
  parseWageReply,
  MIN_WAGE_RANGE,
  PARTTIME_RANGE
} from '../core/api';

describe('chatEndpoint', () => {
  it('空地址返回 null', () => {
    expect(chatEndpoint('')).toBeNull();
    expect(chatEndpoint('   ')).toBeNull();
  });

  it('非 https 返回 null', () => {
    expect(chatEndpoint('http://api.deepseek.com/v1')).toBeNull();
  });

  it('基础地址补 /chat/completions', () => {
    expect(chatEndpoint('https://api.deepseek.com/v1')).toBe('https://api.deepseek.com/v1/chat/completions');
  });

  it('末尾斜杠不会产生双斜杠', () => {
    expect(chatEndpoint('https://api.deepseek.com/v1/'))
      .toBe('https://api.deepseek.com/v1/chat/completions');
  });

  it('已含 /chat/completions 时不重复拼接', () => {
    expect(chatEndpoint('https://x.com/v1/chat/completions'))
      .toBe('https://x.com/v1/chat/completions');
  });

  it('查询串插入在路径之后', () => {
    expect(chatEndpoint('https://x.com/v1?key=abc'))
      .toBe('https://x.com/v1/chat/completions?key=abc');
  });
});

describe('httpReason', () => {
  it('常见状态码有中文说明', () => {
    expect(httpReason(401, '')).toContain('API Key 无效');
    expect(httpReason(404, '')).toContain('接口地址或模型名不正确');
    expect(httpReason(429, '')).toContain('频率超限');
    expect(httpReason(503, '')).toContain('服务器错误');
  });

  it('附带服务端说明并压缩空白', () => {
    const s = httpReason(400, '  model\n not   found  ');
    expect(s).toContain('服务端');
    expect(s).toContain('model not found');
    expect(s).not.toContain('\n');
  });
});

describe('extractJsonObject', () => {
  it('提取纯 JSON', () => {
    expect(extractJsonObject('{"a":1}')).toBe('{"a":1}');
  });

  it('去掉 markdown 围栏', () => {
    expect(extractJsonObject('```json\n{"a":1}\n```')).toBe('{"a":1}');
  });

  it('容忍前后解释', () => {
    expect(extractJsonObject('好的，结果是 {"a":1} 以上')).toBe('{"a":1}');
  });

  it('支持嵌套对象', () => {
    expect(extractJsonObject('{"a":{"b":2}}')).toBe('{"a":{"b":2}}');
  });

  it('字符串里的括号不算配对', () => {
    expect(extractJsonObject('{"a":"}{"}')).toBe('{"a":"}{"}');
  });

  it('无括号返回 null', () => {
    expect(extractJsonObject('没有 JSON')).toBeNull();
  });

  it('括号不配对返回 null', () => {
    expect(extractJsonObject('{"a":1')).toBeNull();
  });
});

describe('parseWageReply', () => {
  it('正常数值通过', () => {
    const r = parseWageReply('{"min_wage": 2520, "parttime_min": 23.7}');
    expect(r.ok).toBe(true);
    expect(r.minWage).toBe(2520);
    expect(r.parttimeMin).toBe(23.7);
  });

  it('缺字段时报错', () => {
    const r = parseWageReply('{"min_wage": 2520}');
    expect(r.ok).toBe(false);
    expect(r.error).toContain('min_wage');
  });

  it('低于合理区间时报错', () => {
    const r = parseWageReply(`{"min_wage": ${MIN_WAGE_RANGE[0] - 1}, "parttime_min": 23.7}`);
    expect(r.ok).toBe(false);
    expect(r.error).toContain('不合理');
  });

  it('小时工资超出区间时报错', () => {
    const r = parseWageReply(`{"min_wage": 2520, "parttime_min": ${PARTTIME_RANGE[1] + 1}}`);
    expect(r.ok).toBe(false);
  });

  it('两个数值比例失常时报错', () => {
    const r = parseWageReply('{"min_wage": 2520, "parttime_min": 150}');
    expect(r.ok).toBe(false);
    expect(r.error).toContain('不匹配');
  });

  it('非 JSON 时报错', () => {
    const r = parseWageReply('我不知道');
    expect(r.ok).toBe(false);
  });
});

describe('cleanMmdd', () => {
  it('规范化并去重排序', () => {
    expect(cleanMmdd(['1-1', '01-01', '10-2'])).toEqual(['01-01', '10-02']);
  });

  it('支持 YYYY-MM-DD', () => {
    expect(cleanMmdd(['2026-10-01'])).toEqual(['10-01']);
  });

  it('丢弃无法识别的项', () => {
    expect(cleanMmdd(['abc', '13-01', '02-32', '05-05'])).toEqual(['05-05']);
  });
});

describe('parseHolidayReply', () => {
  it('解析三类日期', () => {
    const r = parseHolidayReply(
      '{"statutory":["10-01"],"rest":["10-01","10-02"],"makeup":["09-28"]}', 2026);
    expect(r.ok).toBe(true);
    expect(r.statutory).toEqual(['10-01']);
    expect(r.rest).toEqual(['10-01', '10-02']);
    expect(r.makeup).toEqual(['09-28']);
  });

  it('全部为空时报错', () => {
    const r = parseHolidayReply('{"statutory":[],"rest":[],"makeup":[]}', 2026);
    expect(r.ok).toBe(false);
    expect(r.error).toContain('2026');
  });

  it('非 JSON 时报错', () => {
    const r = parseHolidayReply('没有数据', 2026);
    expect(r.ok).toBe(false);
  });
});
