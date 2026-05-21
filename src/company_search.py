"""A股上市公司搜索：按简称或代码查找"""

import difflib
import pandas as pd
import akshare as ak

_stock_list_cache: pd.DataFrame | None = None


def get_stock_list() -> pd.DataFrame:
    """获取A股全量列表，带缓存。返回 DataFrame: code, name, market"""
    global _stock_list_cache
    if _stock_list_cache is not None:
        return _stock_list_cache

    # 优先用 stock_info_a_code_name
    try:
        df = ak.stock_info_a_code_name()
        if "code" in df.columns and "name" in df.columns:
            df = df[["code", "name"]].copy()
        else:
            raise ValueError("列名不匹配")
    except Exception:
        # 回退：使用 stock_zh_a_spot_em
        try:
            df = ak.stock_zh_a_spot_em()
            df = df[["代码", "名称"]].copy()
            df.columns = ["code", "name"]
        except Exception as e:
            raise RuntimeError(f"无法获取A股股票列表，请检查 akshare 安装和网络连接。错误：{e}")

    df["code"] = df["code"].astype(str).str.zfill(6)
    df["market"] = df["code"].apply(_code_to_market)
    _stock_list_cache = df
    return df


def _code_to_market(code: str) -> str:
    """根据股票代码判断所属市场"""
    if code.startswith("6"):
        return "上海主板"
    elif code.startswith(("0", "3")):
        return "深圳"
    elif code.startswith(("4", "8", "9")):
        return "北京"
    else:
        return "其他"


def search_company(query: str, limit: int = 20) -> list[dict]:
    """按简称或代码搜索公司，返回匹配列表"""
    if not query or not query.strip():
        return []

    query = query.strip()
    df = get_stock_list()

    if query.isdigit():
        # 按代码搜索
        mask = df["code"].str.startswith(query)
        results = df[mask].copy()
    else:
        # 按名称搜索
        exact = df[df["name"] == query]
        if not exact.empty:
            results = exact.copy()
        else:
            substring = df[df["name"].str.contains(query, case=False, na=False)]
            if not substring.empty:
                results = substring.copy()
            else:
                # 模糊匹配
                all_names = df["name"].tolist()
                close = difflib.get_close_matches(query, all_names, n=limit, cutoff=0.5)
                results = df[df["name"].isin(close)].copy()

    results = results.sort_values("code").head(limit)
    return results[["code", "name", "market"]].to_dict(orient="records")


def validate_stock_code(code: str) -> bool:
    """验证股票代码是否存在于A股"""
    try:
        df = get_stock_list()
        return (df["code"] == str(code).zfill(6)).any()
    except Exception:
        return False
