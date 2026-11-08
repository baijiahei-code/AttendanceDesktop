/**
 * 「添加工资项」预设目录（按工资项类型分组）。
 *
 * ⚠ 由 scripts/export_paycatalog.py 从桌面版 app/model.py 自动生成，**不要手改**。
 */

/** 计入最低工资标准的工资（11 项） */
export const PAYITEM_CATALOG_WAGE: string[] = [
  '基本工资',
  '岗位工资',
  '绩效工资',
  '奖金',
  '工龄工资',
  '全勤奖',
  '职级工资',
  '学历工资',
  '生活补贴',
  '技能津贴',
  '子女教育补贴',
];

/** 公司补贴（3 项） */
export const PAYITEM_CATALOG_SUBSIDY: string[] = [
  '竞业限制补偿',
  '保密费',
  '公司社保补贴',
];

/** 固定津贴（14 项） */
export const PAYITEM_CATALOG_FIXED: string[] = [
  '一次性奖励',
  '官方社保补贴',
  '伙食补贴（固定）',
  '交通补贴（固定）',
  '通讯补贴（固定）',
  '住房补贴（固定）',
  '中班津贴（固定）',
  '夜班津贴（固定）',
  '高温津贴（固定）',
  '低温津贴（固定）',
  '井下津贴（固定）',
  '有毒有害津贴（固定）',
  '特殊环境津贴（固定）',
  '培训补贴（固定）',
];

/** 按出勤津贴（12 项） */
export const PAYITEM_CATALOG_PERDAY: string[] = [
  '伙食补贴',
  '交通补贴',
  '通讯补贴',
  '高温津贴',
  '住房补贴',
  '中班津贴',
  '夜班津贴',
  '低温津贴',
  '井下津贴',
  '有毒有害津贴',
  '特殊环境津贴',
  '培训补贴',
];

export class PayCatalogGroup {
  type: string;
  title: string;
  items: string[];

  constructor(type: string, title: string, items: string[]) {
    this.type = type;
    this.title = title;
    this.items = items;
  }
}

/** 菜单分组（顺序与桌面版一致）。 */
export const PAYITEM_GROUPS: PayCatalogGroup[] = [
  new PayCatalogGroup('wage', '计入最低工资标准的工资', PAYITEM_CATALOG_WAGE),
  new PayCatalogGroup('subsidy', '公司补贴', PAYITEM_CATALOG_SUBSIDY),
  new PayCatalogGroup('fixed_allow', '固定津贴', PAYITEM_CATALOG_FIXED),
  new PayCatalogGroup('perday_allow', '按出勤津贴', PAYITEM_CATALOG_PERDAY),
];

/** 新增项时各类的默认名称（桌面版同源）。 */
export const PAYITEM_DEFAULT_NAME: Map<string, string> = new Map<string, string>([
  ['wage', '基本工资'],
  ['subsidy', '竞业限制补偿'],
  ['fixed_allow', '一次性奖励'],
  ['perday_allow', '伙食补贴'],
]);
