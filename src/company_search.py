"""A股上市公司搜索：按简称或代码查找"""

import difflib
import json
from pathlib import Path

import pandas as pd

_stock_list_cache: pd.DataFrame | None = None
_STOCK_LIST_FILE = Path(__file__).parent / "stock_list.json"


def get_stock_list() -> pd.DataFrame:
    """获取A股全量列表。优先本地缓存，失败时尝试在线获取。"""
    global _stock_list_cache
    if _stock_list_cache is not None:
        return _stock_list_cache

    # 1. 优先从本地JSON加载（最可靠）
    try:
        df = _load_from_json()
        if df is not None and len(df) > 1000:
            _stock_list_cache = df
            return df
    except Exception:
        pass

    # 2. 尝试在线获取
    try:
        df = _fetch_online()
        if df is not None and len(df) > 1000:
            _stock_list_cache = df
            return df
    except Exception:
        pass

    # 3. 如果在线获取也失败，再试一次JSON
    try:
        df = _load_from_json()
        if df is not None:
            _stock_list_cache = df
            return df
    except Exception:
        pass

    raise RuntimeError(
        "无法获取A股股票列表。请确保 src/stock_list.json 文件存在，"
        "或网络可访问东方财富/巨潮资讯网。"
    )


def _load_from_json() -> pd.DataFrame | None:
    """从本地JSON文件加载股票列表"""
    if not _STOCK_LIST_FILE.exists():
        return None
    with open(_STOCK_LIST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df["code"] = df["code"].astype(str).str.zfill(6)
    df["market"] = df["code"].apply(_code_to_market)
    return df


def _fetch_online() -> pd.DataFrame | None:
    """在线获取股票列表"""
    import akshare as ak

    # 尝试 stock_zh_a_spot_em（东方财富，海外可访问）
    try:
        df = ak.stock_zh_a_spot_em()
        if "代码" in df.columns and "名称" in df.columns:
            df = df[["代码", "名称"]].copy()
            df.columns = ["code", "name"]
            df["code"] = df["code"].astype(str).str.zfill(6)
            df["market"] = df["code"].apply(_code_to_market)
            if len(df) > 1000:
                return df
    except Exception:
        pass

    # 尝试 stock_info_a_code_name
    try:
        df = ak.stock_info_a_code_name()
        if "code" in df.columns and "name" in df.columns:
            df = df[["code", "name"]].copy()
            df["code"] = df["code"].astype(str).str.zfill(6)
            df["market"] = df["code"].apply(_code_to_market)
            if len(df) > 1000:
                return df
    except Exception:
        pass

    return None


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
        mask = df["code"].str.startswith(query)
        results = df[mask].copy()
    else:
        exact = df[df["name"] == query]
        if not exact.empty:
            results = exact.copy()
        else:
            substring = df[df["name"].str.contains(query, case=False, na=False)]
            if not substring.empty:
                results = substring.copy()
            else:
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
