"""全局配置、文件类型映射、关键词定义"""

from pathlib import Path

MARKET = "沪深京"

# 巨潮资讯网分类名称 → 内部代码（用于请求）
CNINFO_CATEGORIES = {
    "年报": "category_ndbg_szsh",
    "半年报": "category_bndbg_szsh",
    "一季报": "category_yjdbg_szsh",
    "三季报": "category_sjdbg_szsh",
    "业绩预告": "category_yjygjxz_szsh",
    "权益分派": "category_qyfpxzcs_szsh",
    "董事会": "category_dshgg_szsh",
    "监事会": "category_jshgg_szsh",
    "股东大会": "category_gddh_szsh",
    "日常经营": "category_rcjy_szsh",
    "公司治理": "category_gszl_szsh",
    "中介报告": "category_zj_szsh",
    "首发": "category_sf_szsh",
    "增发": "category_zf_szsh",
    "股权激励": "category_gqjl_szsh",
    "配股": "category_pg_szsh",
    "解禁": "category_jj_szsh",
    "公司债": "category_gszq_szsh",
    "可转债": "category_kzzq_szsh",
    "其他融资": "category_qtrz_szsh",
    "股权变动": "category_gqbd_szsh",
    "补充更正": "category_bcgz_szsh",
    "澄清致歉": "category_cqdq_szsh",
    "风险提示": "category_fxts_szsh",
    "特别处理和退市": "category_tbclts_szsh",
    "退市整理期": "category_tszlq_szsh",
}

# 文件类型 → akshare category 参数用的中文名称
DOC_TYPE_CATEGORIES = {
    "季度报告": ["一季报", "半年报", "三季报"],
    "年度报告": ["年报"],
    "招股说明书": ["首发"],
}

# 没有专属分类的文件类型，通过关键词搜索
KEYWORD_SEARCH = {
    "业绩说明会/投资者关系活动记录表": [
        "业绩说明会",
        "投资者关系活动记录表",
        "业绩交流会",
        "投资者交流",
        "网上业绩说明会",
        "电话会议纪要",
    ],
}

# "其他重要公告" 包含的分类
OTHER_IMPORTANT_CATEGORIES = [
    "业绩预告", "董事会", "监事会", "股东大会", "权益分派",
    "股权激励", "风险提示", "日常经营", "公司治理", "股权变动",
    "增发", "解禁", "可转债", "公司债", "中介报告", "配股",
    "其他融资", "补充更正", "澄清致歉", "特别处理和退市",
]

# 文件类型中文标签
DOC_TYPE_LABELS = {
    "季度报告": "季度报告（含一季报、半年报、三季报）",
    "年度报告": "年度报告",
    "招股说明书": "招股说明书",
    "业绩说明会/投资者关系活动记录表": "业绩说明会/投资者关系活动记录表",
    "其他重要公告": "其他重要公告（业绩预告、董事会、股东大会等）",
}

DEFAULT_YEARS_BACK = 3
DOWNLOAD_DIR = Path(__file__).parent / "downloads"
REQUEST_DELAY = 1.5
REQUEST_TIMEOUT = 60
PDF_CHUNK_SIZE = 8192
MAX_RETRIES = 3

# 表格标题识别模式
TABLE_TITLE_PATTERNS = [
    r"(?:公司|合并|母公司)?\s*资产负债表",
    r"(?:公司|合并|母公司)?\s*利润表",
    r"(?:公司|合并|母公司)?\s*现金流量表",
    r"(?:公司|合并|母公司)?\s*所有者?权益变动表",
    r"主要会计数据.*?财务指标",
    r"主营业务.*?(?:构成|分析|情况)",
    r"(?:前[十\d]+名?|主要).*?(?:股东|客户|供应商)",
    r"(?:董事|监事|高级管理人员).*?(?:情况|报酬|持股)",
    r"(?:募集|发行).*?(?:资金|情况|使用)",
    r"关联.*?(?:交易|往来)",
    r"或有事项|承诺事项|资产负债表日后事项",
    r"(?:营业收入|成本|费用).*?(?:构成|明细|分析)",
    r"(?:应收|应付|存货|固定资产|无形资产).*?(?:情况|明细)",
]
