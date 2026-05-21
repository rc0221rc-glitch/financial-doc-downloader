"""PDF表格提取：多策略级联提取"""

import re
from pathlib import Path
from dataclasses import dataclass

import pdfplumber

from config import TABLE_TITLE_PATTERNS


@dataclass
class ExtractedTable:
    """提取出的表格及其元数据"""
    page_number: int
    table_index_on_page: int
    data: list[list[str]]
    title: str | None = None
    strategy: str = ""


def extract_tables_from_pdf(
    pdf_path: Path,
    progress_callback=None,
) -> list[ExtractedTable]:
    """
    从PDF中提取所有表格。

    Args:
        pdf_path: PDF文件路径
        progress_callback: 可选 (current_page, total_pages)

    Returns:
        ExtractedTable列表
    """
    tables: list[ExtractedTable] = []

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            if progress_callback:
                progress_callback(i + 1, total)

            page_tables = _extract_from_page(page, i + 1)
            tables.extend(page_tables)

    return _deduplicate_tables(tables)


def _extract_from_page(page, page_num: int) -> list[ExtractedTable]:
    """多策略提取单页表格"""
    results = []
    table_idx = 0

    # 策略1: find_tables（pdfplumber 内置检测）
    try:
        found = page.find_tables()
    except Exception:
        found = []

    for table_obj in found:
        try:
            raw = table_obj.extract()
        except Exception:
            continue
        if not raw or len(raw) < 2:
            continue
        clean = clean_table_data(raw)
        if not _is_valid_table(clean):
            continue

        # 获取准确 bbox
        bbox = table_obj.bbox  # (x0, top, x1, bottom)
        title = _detect_title_from_page(page, bbox)

        results.append(ExtractedTable(
            page_number=page_num,
            table_index_on_page=table_idx,
            data=clean,
            title=title,
            strategy="find_tables",
        ))
        table_idx += 1

    # 策略2: 如果 find_tables 没找到，尝试 extract_tables with lines
    if not results:
        try:
            raw_tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            })
        except Exception:
            raw_tables = []

        for raw in raw_tables:
            if not raw or len(raw) < 2:
                continue
            clean = clean_table_data(raw)
            if not _is_valid_table(clean):
                continue
            results.append(ExtractedTable(
                page_number=page_num,
                table_index_on_page=table_idx,
                data=clean,
                title=None,
                strategy="lines",
            ))
            table_idx += 1

    # 策略3: text-based extraction
    if not results:
        try:
            raw_tables = page.extract_tables({
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 3,
                "join_tolerance": 3,
            })
        except Exception:
            raw_tables = []
        for raw in raw_tables:
            if not raw or len(raw) < 2:
                continue
            clean = clean_table_data(raw)
            if not _is_valid_table(clean):
                continue
            results.append(ExtractedTable(
                page_number=page_num,
                table_index_on_page=table_idx,
                data=clean,
                title=None,
                strategy="text",
            ))
            table_idx += 1

    return results


def _detect_title_from_page(page, table_bbox: tuple) -> str | None:
    """
    从表格上方区域检测标题。
    bbox: (x0, top, x1, bottom)
    """
    x0, top, x1, bottom = table_bbox
    # 搜索区域：表格上方 10~100 pt
    title_top = max(0, top - 100)
    title_bottom = max(0, top - 10)

    try:
        # 扩展水平范围搜索
        region = page.within_bbox((0, title_top, page.width, title_bottom))
        if region is None:
            return None
        text = region.extract_text()
        if not text:
            return None
        lines = text.split("\n")
    except Exception:
        return None

    candidates = []
    for line in lines:
        line = line.strip()
        if len(line) < 3 or len(line) > 100:
            continue
        # 过滤纯数字/纯标点
        if re.match(r'^[\d\s\.\,\、\;\:\-\—\(\)\%，；：、]+$', line):
            continue
        score = _score_title(line)
        if score >= 5:
            candidates.append((score, line))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # 回退：返回最接近表格的最后一行非空文本
    if lines:
        for line in reversed(lines):
            line = line.strip()
            if len(line) >= 3:
                return line[:80]
    return None


def _score_title(line: str) -> int:
    """为候选标题行打分"""
    score = 0
    for pattern in TABLE_TITLE_PATTERNS:
        if re.search(pattern, line):
            score += 10
            break
    if re.search(r"[表况细览总明]$", line):
        score += 5
    if re.search(r"^表\s*\d+|^[一二三四五六七八九十]+、", line):
        score += 3
    # 包含"单位"或"金额"可能是表格说明
    if re.search(r"单位[：:]\s*\S|金额单位", line):
        score += 3
    return score


def clean_table_data(raw_data: list[list[str | None]]) -> list[list[str]]:
    """清洗表格数据"""
    result = []
    for row in raw_data:
        clean_row = [str(c).strip() if c is not None else "" for c in row]
        if any(clean_row):
            result.append(clean_row)
    return result


def _is_valid_table(data: list[list[str]]) -> bool:
    """检查表格是否有效（至少2行2列，至少4个非空单元格）"""
    if len(data) < 2:
        return False
    max_cols = max(len(r) for r in data)
    if max_cols < 2:
        return False
    non_empty = sum(1 for r in data for c in r if c)
    return non_empty >= 4


def _deduplicate_tables(tables: list[ExtractedTable]) -> list[ExtractedTable]:
    """去除同一页上高度相似的表格"""
    if len(tables) <= 1:
        return tables
    keep = []
    for i, t in enumerate(tables):
        is_dup = False
        for j in range(i):
            u = tables[j]
            if t.page_number == u.page_number and _table_similarity(t, u) > 0.9:
                is_dup = True
                break
        if not is_dup:
            keep.append(t)
    return keep


def _table_similarity(a: ExtractedTable, b: ExtractedTable) -> float:
    """计算两个表格的简单相似度"""
    a_text = "".join("".join(r) for r in a.data[:3])
    b_text = "".join("".join(r) for r in b.data[:3])
    if not a_text or not b_text:
        return 0.0
    common = sum(1 for c in a_text if c in b_text)
    return common / max(len(a_text), len(b_text))
