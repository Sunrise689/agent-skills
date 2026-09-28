#!/usr/bin/env python3
"""
flash-reason 校验工具包 — 给免费模型装"物理外挂"

4大能力：
1. validate_calculation() — 代码执行校验层：安全执行数学表达式并与模型答案对比
2. extract_anchors() — 上下文锚定层：提取关键实体防丢失
3. check_anchor_coverage() — 锚点覆盖检查
4. analyze_consistency() — 自一致性轻量投票

v6.1 修订（OpenCode 审查）：
- 修复 consensus 子命令 argv 索引错误（[3] -> [2]）
- 修复 validate 清洗正则误删中文导致数字粘连静默算错（改为拒绝非法字符）
- 支持 sum/min/max 传 list/tuple 参数（AST 增加 List/Tuple 节点）
- 幂运算指数设上限，防 bignum DoS
- 修复 \b 词边界在中文语境失效（改用数字负向断言）
- 复数/NaN/inf 结果返回 error 而非崩溃
- json.loads 加保护；单答案不再误报冲突；consensus 纳入数字一致性
"""

import ast
import re
import sys
import json
import math as _math
import operator as _operator
from typing import Optional


# ─── 安全表达式求值（替代 eval） ──────────────────────

# 幂指数硬上限：防止 bignum DoS（如 9**9**9 / pow(10, 10**8)）
_MAX_EXPONENT = 1000

# 允许的数学函数白名单
_SAFE_FUNCS = {
    "abs": abs, "round": round, "int": int, "float": float,
    "min": min, "max": max, "sum": sum, "pow": pow,
    "sqrt": _math.sqrt, "sin": _math.sin, "cos": _math.cos,
    "tan": _math.tan, "log": _math.log, "log10": _math.log10,
}

# 允许的运算符
_SAFE_OPERATORS = {
    ast.Add: _operator.add,
    ast.Sub: _operator.sub,
    ast.Mult: _operator.mul,
    ast.Div: _operator.truediv,
    ast.FloorDiv: _operator.floordiv,
    ast.Mod: _operator.mod,
    ast.Pow: _operator.pow,
    ast.UAdd: _operator.pos,
    ast.USub: _operator.neg,
}


def _safe_eval(expr: str):
    """使用 AST 安全解析并求值数学表达式，完全替代 eval()。"""
    tree = ast.parse(expr.strip(), mode="eval")
    return _eval_node(tree.body)


def _check_exponent(exponent) -> None:
    """校验幂指数大小，超限抛错（防 bignum DoS）。"""
    if isinstance(exponent, (int, float)) and abs(exponent) > _MAX_EXPONENT:
        raise ValueError(f"幂指数过大（上限 {_MAX_EXPONENT}）")


def _eval_node(node):
    """递归求值 AST 节点，只允许白名单操作。"""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"不支持的常量类型: {type(node.value).__name__}")

    elif isinstance(node, ast.Name):
        # 仅允许 pi / e 两个常量
        if node.id == "pi":
            return _math.pi
        elif node.id == "e":
            return _math.e
        raise ValueError(f"不允许的变量: {node.id}")

    elif isinstance(node, (ast.List, ast.Tuple)):
        return [_eval_node(e) for e in node.elts]

    elif isinstance(node, ast.UnaryOp):
        op_cls = type(node.op)
        if op_cls not in _SAFE_OPERATORS:
            raise ValueError(f"不允许的一元运算符: {op_cls.__name__}")
        return _SAFE_OPERATORS[op_cls](_eval_node(node.operand))

    elif isinstance(node, ast.BinOp):
        op_cls = type(node.op)
        if op_cls not in _SAFE_OPERATORS:
            raise ValueError(f"不允许的二元运算符: {op_cls.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_cls == ast.Pow:
            _check_exponent(right)
        return _SAFE_OPERATORS[op_cls](left, right)

    elif isinstance(node, ast.Call):
        if node.keywords:
            raise ValueError("不支持关键字参数")
        if not isinstance(node.func, ast.Name):
            raise ValueError("不支持的调用形式")
        func_name = node.func.id
        if func_name not in _SAFE_FUNCS:
            raise ValueError(f"不允许的函数调用: {func_name}")
        args = [_eval_node(arg) for arg in node.args]
        if func_name == "pow" and len(args) == 2:
            _check_exponent(args[1])
        return _SAFE_FUNCS[func_name](*args)

    raise ValueError(f"不支持的 AST 节点: {type(node).__name__}")


# ─── 第1层：代码执行校验 ─────────────────────────────────


def validate_calculation(expression: str, model_result: Optional[str] = None) -> dict:
    """
    安全执行数学表达式并返回计算结果，可与模型答案对比。
    用于验证模型输出的数字/计算是否正确。

    参数:
        expression: 数学表达式字符串，如 "15 * 3.14 / 2"
        model_result: 模型的输出结果（可选），会做数值对比

    返回:
        {"correct": bool, "computed": float, "model_result": float, "diff": float, "error": str?}
    """
    if not expression or not expression.strip():
        return {"correct": False, "computed": None, "model_result": model_result, "error": "空表达式"}

    cleaned = expression.strip()
    # 拒绝含非数学字符的输入（中文/其他符号直接报错，而不是清洗后静默算错）
    if re.search(r'[^0-9+\-*/().,%\s^a-zA-Z\[\]]', cleaned):
        return {
            "correct": False, "computed": None, "model_result": model_result,
            "error": "表达式包含不支持的字符（仅允许数字、运算符、函数名，如 sqrt/sin/pi）",
        }

    # 支持 ^ 幂运算（Python 的 ** 为右结合，多级幂请用括号明确优先级）
    cleaned = cleaned.replace('^', '**')

    try:
        result = _safe_eval(cleaned)
    except Exception as e:
        return {"correct": False, "computed": None, "model_result": model_result, "error": str(e)}

    # 复数/无穷/NaN 无法参与数值对比与 JSON 序列化
    if isinstance(result, complex):
        return {"correct": False, "computed": None, "model_result": model_result, "error": "结果为复数，无法比较"}
    if isinstance(result, float) and (_math.isnan(result) or _math.isinf(result)):
        return {"correct": False, "computed": None, "model_result": model_result, "error": "结果为无穷或非数字"}

    computed = round(result, 6)

    if model_result is not None:
        model_num = _extract_number(str(model_result))
        if model_num is None:
            return {
                "correct": False, "computed": computed, "model_result": None,
                "diff": None, "error": "无法从模型结果中提取数字",
            }
        diff = abs(computed - model_num)
        # 绝对误差 < 0.01，或相对误差 < 1%（容忍浮点误差）
        correct = diff < 0.01 or (model_num != 0 and diff / abs(model_num) < 0.01)
        return {
            "correct": correct,
            "computed": computed,
            "model_result": model_num,
            "diff": round(diff, 6),
        }

    return {"correct": True, "computed": computed, "model_result": model_result, "diff": None}


def _extract_number(text: str) -> Optional[float]:
    """从文本中提取最可能的数字结果（优先中文结果标记，过滤时间/涨幅噪音）。"""
    # 过滤"增长/同比/环比/下降"后的百分比数字（易被误当结果）
    text = re.sub(
        r'(?:增长|同比|环比|下降|上升|下跌|回落)[了约]?\s*[+-]?\d+(?:\.\d+)?%?',
        '', text,
    )
    patterns = [
        # 中文结果标记优先
        r'(?:共|合计|总计|最终答案为?|答案为?|结果(?:为|是)?|等于|得)\s*[:：]?\s*([+-]?\d+(?:\.\d+)?)',
        # 等号/冒号标记
        r'[=:：]\s*([+-]?\d+(?:\.\d+)?)',
        # 句尾带单位/百分比的数字
        r'([+-]?\d+(?:\.\d+)?)\s*(?:元|美元|欧元|英镑|个|人|次|%|万|亿)?$',
    ]
    for p in patterns:
        matches = re.findall(p, text)
        if matches:
            return float(matches[-1])
    # 兜底：所有数字中的最后一个
    nums = re.findall(r'[+-]?\d+(?:\.\d+)?', text)
    if nums:
        return float(nums[-1])
    return None


# ─── 第2层：上下文锚定 ─────────────────────────────────


# 常见的免费模型容易遗漏的高价值实体模式
_ANCHOR_PATTERNS = [
    # 数字型（金额、百分比、日期、时间）
    (r'\d+\.?\d*%', 'percentage'),
    (r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', 'date'),
    (r'\d{1,2}:\d{2}', 'time'),
    (r'[+-]?\d+\.?\d*\s*(?:万|亿|千|百)', 'large_number'),
    (r'(?:¥|\$|€|£)\s*\d+\.?\d*', 'currency'),
    (r'\d+\.?\d*\s*(?:元|美元|欧元|英镑)', 'currency_cn'),
    # 专有名词（中文，2-8字）
    (r'《[^》]+》', 'book_title'),
    (r'"[^"]{2,20}"', 'quote'),
    # 人名/公司名（简单规则）
    (r'(?:[A-Z][a-z]+)\s(?:[A-Z][a-z]+)', 'person_en'),
]


def extract_anchors(text: str) -> list:
    """
    从文本中提取关键实体作为上下文锚点。

    返回: [{"value": "锚点值", "type": "实体类型", "pos": 位置}, ...]
    每个锚点去重（同值同类型只保留第一个）
    """
    anchors = []
    seen = set()

    # 用正则匹配
    for pattern, atype in _ANCHOR_PATTERNS:
        for match in re.finditer(pattern, text):
            key = f"{match.group()}|{atype}"
            if key not in seen:
                seen.add(key)
                anchors.append({
                    "value": match.group().strip(),
                    "type": atype,
                    "pos": match.start()
                })

    # 提取显式数字（去重后加入）。
    # 注意：不用 \b 词边界（CJK 汉字属于 \w，与数字相邻时 \b 失效），改用数字负向断言；
    # 若数字已被金额/百分比/日期等模式覆盖（位置重叠），不重复提取，避免冗余锚点。
    occupied = [(a["pos"], a["pos"] + len(a["value"]))
                for a in anchors if a.get("pos", -1) >= 0]

    def _overlaps(start: int, end: int) -> bool:
        return any(start < o_end and end > o_start for o_start, o_end in occupied)

    for match in re.finditer(r'(?<!\d)(\d+(?:\.\d+)?)(?!\d)', text):
        start, end = match.span()
        if _overlaps(start, end):
            continue
        n = match.group(1)
        key = f"{n}|number"
        if key not in seen:
            seen.add(key)
            anchors.append({"value": n, "type": "number", "pos": start})

    # 按出现位置排序
    anchors.sort(key=lambda x: x.get("pos", 999))
    return anchors


def check_anchor_coverage(anchors: list, response: str) -> dict:
    """
    检查回复是否覆盖了关键锚点。
    "覆盖"标准：锚点值或其同义表达出现在回复中（覆盖≠正确，需人工复核核心实体用法）。

    返回:
        {
            "missing": [没覆盖的锚点],
            "covered": [已覆盖的锚点],
            "coverage_rate": 0.0~1.0,
            "safe": bool (覆盖率>=0.7)
        }
    """
    if not isinstance(anchors, list):
        return {"missing": [], "covered": [], "coverage_rate": 1.0, "safe": True,
                "error": "anchors 参数应为列表"}
    if not anchors:
        return {"missing": [], "covered": [], "coverage_rate": 1.0, "safe": True}

    # 过滤掉位置/引用类锚点（不算关键信息遗漏；英文人名在中文回复中几乎不会出现）
    critical = [a for a in anchors
                if a.get("type") not in ("book_title", "quote", "person_en")]
    if not critical:
        return {"missing": [], "covered": [], "coverage_rate": 1.0, "safe": True}

    covered = []
    missing = []

    response_lower = response.lower()
    # 数字类锚点必须"数字边界匹配"：防止 "5元" 被 "15元" 的子串误判为已覆盖；
    # 文本类锚点（书名/人名等）用宽松子串包含即可。
    _NUM_TYPES = {"number", "currency", "currency_cn", "percentage", "large_number", "date", "time"}

    for anchor in critical:
        val = anchor["value"].lower()
        if anchor["type"] in _NUM_TYPES:
            covered_flag = re.search(r'(?<!\d)' + re.escape(val) + r'(?!\d)', response_lower) is not None
        else:
            covered_flag = val in response_lower
        if covered_flag:
            covered.append(anchor)
        else:
            missing.append(anchor)

    rate = len(covered) / len(critical)
    return {
        "missing": missing,
        "covered": covered,
        "coverage_rate": round(rate, 2),
        "safe": rate >= 0.7
    }


# ─── 自一致性分析 ──────────────────────────────────


def analyze_consistency(answers: list) -> dict:
    """
    自一致性轻量分析：对多个候选答案做一致性判断。
    用于多次采样后投票确定最可信答案。

    参数:
        answers: [{"id": 序号, "text": "答案文本", "confidence": 0~1}, ...]

    返回:
        {
            "consensus": "多数票答案摘要",
            "agreement_rate": 0.0~1.0,
            "total_count": int,
            "conflict": bool (是否存在明显分歧)
        }
    """
    if not isinstance(answers, list):
        return {"consensus": None, "agreement_rate": 0, "total_count": 0, "conflict": False,
                "error": "answers 参数应为列表"}

    n = len(answers)
    if n == 0:
        return {"consensus": None, "agreement_rate": 0, "total_count": 0, "conflict": False}
    if n == 1:
        # 单答案没有"分歧"可言，不误报冲突
        return {"consensus": str(answers[0].get("text", ""))[:200], "agreement_rate": 1.0,
                "total_count": 1, "conflict": False}

    texts = [a.get("text", "") for a in answers]

    # 关键词集合：2-4字汉字片段 + 提取到的数字（数字一致性对计算类答案至关重要）
    keyword_sets = []
    for t in texts:
        words = set(re.findall(r'[\u4e00-\u9fff]{2,4}', t))
        num = _extract_number(t)
        if num is not None:
            words.add(("number", num))
        keyword_sets.append(words)

    # 两两计算 Jaccard 相似度
    similarities = []
    for i in range(n):
        for j in range(i + 1, n):
            if not keyword_sets[i] or not keyword_sets[j]:
                continue
            inter = len(keyword_sets[i] & keyword_sets[j])
            union = len(keyword_sets[i] | keyword_sets[j])
            if union > 0:
                similarities.append(inter / union)

    agreement = sum(similarities) / len(similarities) if similarities else 0

    # 找与其他答案最相似的作为 consensus
    best_idx = 0
    best_score = -1.0
    for i in range(n):
        score = 0.0
        cnt = 0
        for j in range(n):
            if i == j or not keyword_sets[i] or not keyword_sets[j]:
                continue
            union = keyword_sets[i] | keyword_sets[j]
            if union:
                score += len(keyword_sets[i] & keyword_sets[j]) / len(union)
                cnt += 1
        if cnt > 0 and score > best_score:
            best_score = score
            best_idx = i

    consensus = texts[best_idx][:200]
    return {
        "consensus": consensus,
        "agreement_rate": round(agreement, 2),
        "total_count": n,
        "conflict": agreement < 0.4
    }


# ─── CLI 入口 ──────────────────────────────────────


def _fail(msg: str):
    """输出错误 JSON 并以退出码 2 退出（让模型可用退出码判断成败）。"""
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(2)


def _load_json_list(raw: str, label: str) -> list:
    """安全解析 JSON 列表参数，失败时友好退出。"""
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("应为 JSON 列表")
        return data
    except Exception as e:
        _fail(f"{label}格式错误: {e}")


def main():
    if len(sys.argv) < 2:
        print("用法: python checks.py <command> [args...]")
        print("命令: validate, anchors, coverage, consensus")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "validate":
        if len(sys.argv) < 3:
            _fail("缺少表达式参数：validate \"<表达式>\" [\"<模型答案>\"]")
        expr = sys.argv[2]
        model_result = sys.argv[3] if len(sys.argv) > 3 else None
        out = validate_calculation(expr, model_result)
        print(json.dumps(out, ensure_ascii=False))
        if "error" in out:
            sys.exit(2)
        if out.get("correct") is False:
            sys.exit(1)

    elif cmd == "anchors":
        if len(sys.argv) < 3:
            _fail("缺少文本参数：anchors \"<文本>\"")
        out = extract_anchors(sys.argv[2])
        print(json.dumps(out, ensure_ascii=False))

    elif cmd == "coverage":
        if len(sys.argv) < 4:
            _fail("缺少参数：coverage \"<锚点JSON>\" \"<回复>\"")
        anchors = _load_json_list(sys.argv[2], "锚点JSON")
        out = check_anchor_coverage(anchors, sys.argv[3])
        print(json.dumps(out, ensure_ascii=False))

    elif cmd == "consensus":
        if len(sys.argv) < 3:
            _fail("缺少答案JSON参数：consensus \"<答案JSON>\"")
        answers = _load_json_list(sys.argv[2], "答案JSON")
        out = analyze_consistency(answers)
        print(json.dumps(out, ensure_ascii=False))

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
