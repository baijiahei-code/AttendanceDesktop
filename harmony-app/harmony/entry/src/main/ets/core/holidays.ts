/**
 * 中国法定节假日 / 调休数据表（对应桌面版 `app/holidays.py`）。
 *
 * 数据来源：国务院办公厅历年「部分节假日安排的通知」
 *   2026：国办发明电〔2025〕7号（2025-11-04 发布）
 *   2025：国办发明电〔2024〕7号
 *
 * kind 取值：
 *   statutory  法定节假日当天（加班 ×3，计入「提供正常劳动」）
 *   rest       放假调休区间（含法定日与拼假休息日）
 *   makeup     调休补班日（周末但需上班）
 */

interface YearData {
  readonly statutory: string[];
  readonly ranges: string[][];
  readonly makeup: string[];
}

/** 某年展开后的三组 "MM-DD" 集合。 */
export class HolidaySets {
  statutory: Set<string> = new Set<string>();
  rest: Set<string> = new Set<string>();
  makeup: Set<string> = new Set<string>();
}

const YEAR_DATA: Map<number, YearData> = new Map<number, YearData>([
  [2026, {
    statutory: ['01-01',
      '02-16', '02-17', '02-18', '02-19',
      '04-05',
      '05-01', '05-02',
      '06-19',
      '09-25',
      '10-01', '10-02', '10-03'],
    ranges: [['01-01', '01-03'],
      ['02-15', '02-23'],
      ['04-04', '04-06'],
      ['05-01', '05-05'],
      ['06-19', '06-21'],
      ['09-25', '09-27'],
      ['10-01', '10-07']],
    makeup: ['01-04', '02-14', '02-28', '05-09', '09-20', '10-10'],
  }],
  [2025, {
    statutory: ['01-01',
      '01-28', '01-29', '01-30', '01-31',
      '04-04',
      '05-01', '05-02',
      '05-31',
      '10-01', '10-02', '10-03', '10-06'],
    ranges: [['01-01', '01-01'],
      ['01-28', '02-04'],
      ['04-04', '04-06'],
      ['05-01', '05-05'],
      ['05-31', '06-02'],
      ['10-01', '10-08']],
    makeup: ['01-26', '02-08', '04-27', '09-28', '10-11'],
  }],
]);

const CACHE: Map<number, HolidaySets | null> = new Map<number, HolidaySets | null>();

/** 公历日期 ↔ 自 1970-01-01 的天数（Howard Hinnant 算法，proleptic Gregorian）。 */
function daysFromCivil(y: number, m: number, d: number): number {
  const yy: number = m <= 2 ? y - 1 : y;
  const era: number = Math.floor(yy / 400);
  const yoe: number = yy - era * 400;
  const doy: number = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
  const doe: number = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

interface CivilDate {
  readonly y: number;
  readonly m: number;
  readonly d: number;
}

function civilFromDays(z0: number): CivilDate {
  const z: number = z0 + 719468;
  const era: number = Math.floor(z / 146097);
  const doe: number = z - era * 146097;
  const yoe: number = Math.floor((doe - Math.floor(doe / 1460) + Math.floor(doe / 36524)
    - Math.floor(doe / 146096)) / 365);
  const y: number = yoe + era * 400;
  const doy: number = doe - (365 * yoe + Math.floor(yoe / 4) - Math.floor(yoe / 100));
  const mp: number = Math.floor((5 * doy + 2) / 153);
  const d: number = doy - Math.floor((153 * mp + 2) / 5) + 1;
  const m: number = mp + (mp < 10 ? 3 : -9);
  return { y: y + (m <= 2 ? 1 : 0), m: m, d: d };
}

function pad2(n: number): string {
  return (n < 10 ? '0' : '') + n.toString();
}

/** 展开某年的三组集合；未收录返回 null。 */
export function yearSets(year: number): HolidaySets | null {
  if (CACHE.has(year)) {
    return CACHE.get(year) ?? null;
  }
  const data: YearData | undefined = YEAR_DATA.get(year);
  if (data === undefined) {
    CACHE.set(year, null);
    return null;
  }
  const out: HolidaySets = new HolidaySets();
  for (const s of data.statutory) {
    out.statutory.add(s);
  }
  for (const s of data.makeup) {
    out.makeup.add(s);
  }
  for (const s of data.statutory) {
    out.rest.add(s);
  }
  for (const range of data.ranges) {
    const start: string[] = range[0].split('-');
    const end: string[] = range[1].split('-');
    const from: number = daysFromCivil(year, Number(start[0]), Number(start[1]));
    const to: number = daysFromCivil(year, Number(end[0]), Number(end[1]));
    for (let day = from; day <= to; day++) {
      const c: CivilDate = civilFromDays(day);
      out.rest.add(pad2(c.m) + '-' + pad2(c.d));
    }
  }
  CACHE.set(year, out);
  return out;
}

/** 该年节假日安排是否已收录。 */
export function hasYear(year: number): boolean {
  return YEAR_DATA.has(year);
}

/**
 * 把某个 "MM-DD" 归类为 statutory / rest / makeup；普通日返回 null。
 *
 * ⚠ 优先级全项目只有这一处：法定 → 补班 → 放假。
 *   联网数据真会出现「同一天既在放假区间又在补班日」，两条链路必须给出同一答案。
 */
export function classifyDay(key: string, sets: HolidaySets): string | null {
  if (sets.statutory.has(key)) {
    return 'statutory';
  }
  if (sets.makeup.has(key)) {
    return 'makeup';
  }
  if (sets.rest.has(key)) {
    return 'rest';
  }
  return null;
}

/** 返回某天类型：statutory / rest / makeup；未收录或普通日返回 null。 */
export function dayKind(year: number, month: number, day: number): string | null {
  const sets: HolidaySets | null = yearSets(year);
  if (sets === null) {
    return null;
  }
  return classifyDay(pad2(month) + '-' + pad2(day), sets);
}
