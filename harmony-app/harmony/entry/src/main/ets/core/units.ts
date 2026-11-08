/**
 * 相关单位（全局数据，与月份无关）。对应桌面版 `app/model.py` 的 UNIT_ROLES / RelatedUnit。
 *
 * 现实中「签合同的公司」「缴社保的公司」「发工资的公司」「实际干活的单位」经常不是同一个
 * （集团 / 分公司 / 劳务派遣 / 社保代缴 / 工资代发），分开登记便于核对。
 *
 * ⚠ key 一旦发布不要改（影响存档兼容）。
 */

export class UnitRole {
  key: string = '';
  label: string = '';
  codeLabel: string = '';
  hint: string = '';

  constructor(key: string, label: string, codeLabel: string, hint: string) {
    this.key = key;
    this.label = label;
    this.codeLabel = codeLabel;
    this.hint = hint;
  }
}

const CODE_USCC: string = '统一社会信用代码';

export const UNIT_ROLES: UnitRole[] = [
  new UnitRole('contract', '劳动合同签订单位', CODE_USCC, '劳动合同上的用人单位（甲方）'),
  new UnitRole('social', '社保缴纳单位', CODE_USCC, '实际缴纳社会保险的参保单位（代缴时可能与签订单位不同）'),
  new UnitRole('fund', '公积金缴纳单位', CODE_USCC, '住房公积金缴存单位'),
  new UnitRole('wage', '工资发放单位', CODE_USCC, '实际发放工资的主体（委托代发 / 集团统一发放时不同）'),
  new UnitRole('tax', '个税扣缴单位', CODE_USCC, '个人所得税代扣代缴义务人'),
  new UnitRole('work', '实际用工单位', CODE_USCC, '员工实际工作 / 被派驻的单位'),
  new UnitRole('dispatch', '劳务派遣单位', CODE_USCC, '派遣方（非劳务派遣时不用添加）'),
  new UnitRole('outsourcing', '外包单位', CODE_USCC, '业务外包的承包方（非外包时不用添加）'),
  new UnitRole('superior', '上级单位', CODE_USCC, '上级主管单位（选填）'),
  new UnitRole('group', '集团单位', CODE_USCC, '母公司 / 集团总部（选填）'),
  new UnitRole('bank', '工资代发银行', '联行号／账号', '代发工资的开户银行或支行（选填）')
];

export const UNIT_ROLE_KEYS: string[] = UNIT_ROLES.map((r: UnitRole): string => r.key);

export const UNIT_ROLE_LABELS: Map<string, string> = new Map<string, string>();
export const UNIT_ROLE_CODE_LABELS: Map<string, string> = new Map<string, string>();
export const UNIT_ROLE_HINTS: Map<string, string> = new Map<string, string>();
for (const r of UNIT_ROLES) {
  UNIT_ROLE_LABELS.set(r.key, r.label);
  UNIT_ROLE_CODE_LABELS.set(r.key, r.codeLabel);
  UNIT_ROLE_HINTS.set(r.key, r.hint);
}

export const UNIT_ROLE_DEFAULT: string = 'contract';
export const UNIT_ROLE_BANK: string = 'bank';
/** 其他相关单位 = 非内置类型的落点（具体内容写在名称栏）。 */
export const UNIT_ROLE_OTHER: string = 'other';
UNIT_ROLE_LABELS.set(UNIT_ROLE_OTHER, '其他相关单位');
UNIT_ROLE_CODE_LABELS.set(UNIT_ROLE_OTHER, CODE_USCC);
UNIT_ROLE_HINTS.set(UNIT_ROLE_OTHER, '其它单位：具体是什么写在「单位名称」栏');

/** 类型下拉用的全部可选类型（11 内置 + 其他）。 */
export const UNIT_SELECTABLE_KEYS: string[] = UNIT_ROLE_KEYS.concat([UNIT_ROLE_OTHER]);

/** 把类型文字解析成 key（不认识的一律归 other）。 */
export function resolveUnitRole(text: string): string {
  const t: string = (text ?? '').trim();
  for (const r of UNIT_ROLES) {
    if (t === r.label) {
      return r.key;
    }
  }
  return UNIT_ROLE_OTHER;
}

export interface UnitDict {
  role?: string | null;
  name?: string | null;
  code?: string | null;
}

export class RelatedUnit {
  role: string = UNIT_ROLE_DEFAULT;
  name: string = '';
  code: string = '';

  constructor(role: string = UNIT_ROLE_DEFAULT, name: string = '', code: string = '') {
    this.role = role;
    this.name = name;
    this.code = code;
  }

  typeName(): string {
    const s: string | undefined = UNIT_ROLE_LABELS.get(this.role);
    return s === undefined ? (UNIT_ROLE_LABELS.get(UNIT_ROLE_OTHER) ?? '') : s;
  }

  codeLabel(): string {
    const s: string | undefined = UNIT_ROLE_CODE_LABELS.get(this.role);
    return s === undefined ? CODE_USCC : s;
  }

  toDict(): UnitDict {
    return { role: this.role, name: this.name, code: this.code };
  }

  static fromDict(raw: UnitDict): RelatedUnit {
    let role: string = typeof raw.role === 'string' && raw.role !== '' ? raw.role : UNIT_ROLE_OTHER;
    if (UNIT_ROLE_LABELS.get(role) === undefined) {
      role = UNIT_ROLE_OTHER;
    }
    const name: string = typeof raw.name === 'string' ? raw.name.trim() : '';
    const code: string = typeof raw.code === 'string' ? raw.code.trim() : '';
    return new RelatedUnit(role, name, code);
  }
}

/** 默认单位表：内置 11 类各一行（名称留空，等用户填）。 */
export function defaultUnits(): RelatedUnit[] {
  const out: RelatedUnit[] = [];
  for (const k of UNIT_ROLE_KEYS) {
    out.push(new RelatedUnit(k, '', ''));
  }
  return out;
}

/** 从 JSON 数组还原（保留顺序与重复类型；老数据里的未知 role 归 other）。 */
export function unitsFromJson(raw: UnitDict[]): RelatedUnit[] {
  const out: RelatedUnit[] = [];
  for (const x of raw) {
    if (typeof x === 'object' && x !== null) {
      out.push(RelatedUnit.fromDict(x));
    }
  }
  return out;
}
