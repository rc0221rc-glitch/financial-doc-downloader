"""巨潮资讯网公告查询与PDF下载（直接调用CNINFO API）"""

import re
import time
import math
from pathlib import Path
from functools import lru_cache

import requests
import pandas as pd

from config import (
    MARKET,
    DOC_TYPE_CATEGORIES,
    KEYWORD_SEARCH,
    OTHER_IMPORTANT_CATEGORIES,
    CNINFO_CATEGORIES,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
)


session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
})


@lru_cache()
def _get_stock_json(market: str = "沪深京") -> dict:
    """获取股票代码 → orgId 映射"""
    url = "http://www.cninfo.com.cn/new/data/szse_stock.json"
    if market == "港股":
        url = "http://www.cninfo.com.cn/new/data/hke_stock.json"
    elif market in ("三板", "北交所"):
        url = "http://www.cninfo.com.cn/new/data/gfzr_stock.json"
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    data = resp.json()
    stock_list = data.get("stockList", [])
    return {item["code"]: item["orgId"] for item in stock_list}


def _query_cninfo(
    symbol: str,
    market: str,
    keyword: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = "",
    max_pages: int = 10,
) -> pd.DataFrame:
    """直接调用巨潮资讯网 API 查询公告"""
    column_map = {
        "沪深京": "szse", "港股": "hke", "三板": "third",
        "北交所": "third", "基金": "fund", "债券": "bond",
        "监管": "regulator", "预披露": "pre_disclosure",
    }
    stock_id_map = _get_stock_json(market)
    stock_item = ""
    if symbol and symbol in stock_id_map:
        stock_item = f"{symbol},{stock_id_map[symbol]}"

    # 分类参数用内部代码
    category_code = CNINFO_CATEGORIES.get(category, "")

    se_date = ""
    if start_date and end_date:
        sd = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        ed = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        se_date = f"{sd}~{ed}"

    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    payload = {
        "pageNum": 1,
        "pageSize": 30,
        "column": column_map.get(market, "szse"),
        "tabName": "fulltext",
        "plate": "",
        "stock": stock_item,
        "searchkey": keyword,
        "secid": "",
        "category": category_code,
        "trade": "",
        "seDate": se_date,
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }

    all_rows = []
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.post(url, data=payload, timeout=REQUEST_TIMEOUT)
            data = resp.json()
            total = int(data.get("totalAnnouncement", 0))
            if total == 0:
                return pd.DataFrame()
            total_pages = min(math.ceil(total / 30), max_pages)
            break
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
            else:
                return pd.DataFrame()

    for page in range(1, total_pages + 1):
        if page > 1:
            time.sleep(0.3)
        payload["pageNum"] = page
        try:
            resp = session.post(url, data=payload, timeout=REQUEST_TIMEOUT)
            page_data = resp.json()
            announcements = page_data.get("announcements", [])
            all_rows.extend(announcements)
        except Exception:
            continue

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df.rename(columns={
        "secCode": "代码",
        "secName": "简称",
        "announcementTitle": "公告标题",
        "announcementTime": "公告时间",
    }, inplace=True)

    # 转换时间戳
    if "公告时间" in df.columns:
        df["公告时间"] = pd.to_datetime(
            df["公告时间"], unit="ms", utc=True, errors="coerce"
        )
        df["公告时间"] = df["公告时间"].dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
        df["公告时间"] = df["公告时间"].astype(str)

    # 构建详情页URL
    df["公告链接"] = df.apply(
        lambda r: (
            f"http://www.cninfo.com.cn/new/disclosure/detail"
            f"?stockCode={r.get('代码', '')}&announcementId={r.get('announcementId', '')}"
            f"&orgId={r.get('orgId', '')}&announcementTime={r.get('公告时间', '')}"
        ),
        axis=1,
    )

    keep_cols = ["代码", "简称", "公告标题", "公告时间", "公告链接", "adjunctUrl", "announcementId", "orgId"]
    df = df[[c for c in keep_cols if c in df.columns]]
    return df


def fetch_filing_list(
    symbol: str,
    doc_types: list[str],
    start_date: str,
    end_date: str,
    progress_callback=None,
) -> pd.DataFrame:
    """查询指定公司的公告列表"""
    all_frames = []
    total_types = len(doc_types)

    for i, doc_type in enumerate(doc_types):
        if progress_callback:
            progress_callback(i + 1, total_types, f"正在查询：{doc_type}")

        frames = _query_doc_type(symbol, doc_type, start_date, end_date)
        for df in frames:
            if not df.empty:
                df["文档类型"] = doc_type
                all_frames.append(df)
        time.sleep(REQUEST_DELAY)

    if not all_frames:
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    result = result.drop_duplicates(subset=["公告标题", "公告时间"])
    result = result.sort_values("公告时间", ascending=False).reset_index(drop=True)
    return result


def _query_doc_type(
    symbol: str,
    doc_type: str,
    start_date: str,
    end_date: str,
) -> list[pd.DataFrame]:
    """查询单个文件类型对应的公告"""
    frames = []

    # 1. 通过分类查询
    if doc_type in DOC_TYPE_CATEGORIES:
        for cat in DOC_TYPE_CATEGORIES[doc_type]:
            df = _query_cninfo(symbol, MARKET, category=cat, start_date=start_date, end_date=end_date)
            if not df.empty:
                frames.append(df)
            time.sleep(0.5)

    # 2. 通过关键词查询
    if doc_type in KEYWORD_SEARCH:
        for kw in KEYWORD_SEARCH[doc_type]:
            df = _query_cninfo(symbol, MARKET, keyword=kw, start_date=start_date, end_date=end_date)
            if not df.empty:
                frames.append(df)
            time.sleep(0.5)

    # 3. "其他重要公告" — 多分类查询
    if doc_type == "其他重要公告":
        for cat in OTHER_IMPORTANT_CATEGORIES:
            df = _query_cninfo(symbol, MARKET, category=cat, start_date=start_date, end_date=end_date)
            if not df.empty:
                frames.append(df)
            time.sleep(0.5)

    return frames


def download_filings(
    filing_df: pd.DataFrame,
    output_dir: Path,
    progress_callback=None,
) -> list[Path]:
    """下载公告PDF文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    total = len(filing_df)

    for idx, (_, row) in enumerate(filing_df.iterrows()):
        title = str(row.get("公告标题", f"公告_{idx}"))
        date_str = str(row.get("公告时间", ""))[:10]
        safe_title = _sanitize_filename(title)[:80]
        filename = f"[{date_str}] {safe_title}.pdf"
        filepath = output_dir / filename

        if progress_callback:
            progress_callback(idx, total, filename)

        if filepath.exists():
            downloaded.append(filepath)
            continue

        pdf_url = _get_pdf_url(row)
        if not pdf_url:
            continue

        for attempt in range(MAX_RETRIES):
            try:
                resp = session.get(pdf_url, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    filepath.write_bytes(resp.content)
                    downloaded.append(filepath)
                    break
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 * (attempt + 1))

        time.sleep(1.0)  # 礼貌延迟

    return downloaded


def _get_pdf_url(row) -> str | None:
    """获取PDF直链"""
    # 方式一：直接用 adjunctUrl
    adjunct = str(row.get("adjunctUrl", ""))
    if adjunct and adjunct != "nan":
        return f"http://static.cninfo.com.cn/{adjunct}"

    # 方式二：用 announcementId 从详情页提取
    url = str(row.get("公告链接", ""))
    if url:
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            match = re.search(r'href=["\']([^"\']+\.PDF)["\']', resp.text, re.IGNORECASE)
            if match:
                href = match.group(1)
                if href.startswith("/"):
                    return f"http://static.cninfo.com.cn{href}"
                return href
        except Exception:
            pass

    return None


def _sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "", name)
    name = name.strip().strip(".")
    return name
