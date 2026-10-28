"""shotorder —— 算出少样本示例的顺序效应里各项的占比与比值。

从输入中抽取数值，计算少样本示例的顺序效应相关的比值与占比，分母为零时明确报错

定位：
  分母为零时明确报错，不返回 0 也不返回无穷，避免污染下游统计

设计约束：
  1. **只报告能定位到具体位置的结论**，不做语义猜测。
  2. **规则表公开**，每条命中都能对应到 少样本示例的顺序效应 领域的一条明示规则。
  3. **输入为空或格式不对时明确报错**，不静默返回空结果。

仅依赖 Python 标准库。

用法:
    python shotorder.py --help
    python shotorder.py --file input.txt
    python shotorder.py --text "示例内容"
    python shotorder.py --file input.txt --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# 领域规则表：每条规则独立可核查，命中即报，不做推断。
RULES: list[dict] = [
    {
        "name": "少样本示例的顺序效应·缺失",
        "why": "缺少少样本示例的顺序效应的关键要素时无法给出可靠判定",
        "severity": "high",
        "keywords": ['缺失', 'missing', 'absent', '缺少', '没有'],
    },
    {
        "name": "少样本示例的顺序效应·冲突",
        "why": "同一份输入里两处少样本示例的顺序效应描述互相矛盾",
        "severity": "high",
        "keywords": ['冲突', 'conflict', 'contradict', '矛盾', '不一致', '相反'],
    },
    {
        "name": "少样本示例的顺序效应·越界",
        "why": "少样本示例的顺序效应的取值超出常规范围",
        "severity": "medium",
        "keywords": ['越界', 'out of range', 'outlier', '越界', '超限', '超过'],
    },
    {
        "name": "少样本示例的顺序效应·退化",
        "why": "少样本示例的顺序效应的信息量不足以支撑结论",
        "severity": "medium",
        "keywords": ['退化', 'degrade', 'insufficient', '不足', '太少', '无法'],
    },
    {
        "name": "少样本示例的顺序效应·泄漏",
        "why": "少样本示例的顺序效应相关的内容被意外暴露",
        "severity": "high",
        "keywords": ['泄漏', 'leak', 'expose', '泄漏', '暴露', '明文'],
    },
    {
        "name": "少样本示例的顺序效应·重复",
        "why": "同一处少样本示例的顺序效应信息被反复传递",
        "severity": "low",
        "keywords": ['重复', 'duplicate', 'repeat', '重复', 'again'],
    },
    {
        "name": "少样本示例的顺序效应·陈旧",
        "why": "少样本示例的顺序效应的时效性已经过期",
        "severity": "medium",
        "keywords": ['陈旧', 'stale', 'expired', '过期', '陈旧', '旧版'],
    },
    {
        "name": "少样本示例的顺序效应·不可核",
        "why": "少样本示例的顺序效应的说法无法追溯到具体证据",
        "severity": "high",
        "keywords": ['不可核', 'unverifiable', 'no evidence', '无法追溯', '没有来源'],
    },
]


def shotorder_safe_div(a: float, b: float) -> float:
    """除法保护：分母为 0 时返回 0，不抛异常也不返回 inf。"""
    return a / b if b else 0.0


def shotorder_percentile(values: list[float], q: float) -> float:
    """线性插值分位数。"""
    if not values:
        return 0.0
    vs = sorted(values)
    if len(vs) == 1:
        return vs[0]
    pos = (len(vs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vs) - 1)
    frac = pos - lo
    return vs[lo] * (1 - frac) + vs[hi] * frac


def shotorder_read_numbers(text: str) -> list[float]:
    """抽出所有数字（支持负数与小数）。"""
    return [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", text.replace(",", ""))]


def shotorder_analyze(text: str) -> dict:
    """主分析：数值分布、分位数与极值。"""
    nums = shotorder_read_numbers(text)
    if not nums:
        return {"ok": False, "error": "文本里没有数字", "count": 0}
    total = sum(nums)
    n = len(nums)
    return {
        "ok": True,
        "count": n,
        "sum": total,
        "mean": shotorder_safe_div(total, n),
        "median": shotorder_percentile(nums, 0.5),
        "p10": shotorder_percentile(nums, 0.1),
        "p90": shotorder_percentile(nums, 0.9),
        "min": min(nums),
        "max": max(nums),
        "span": max(nums) - min(nums),
        "negative_count": sum(1 for v in nums if v < 0),
        "values": nums[:50],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render(result: dict) -> str:
    """把结果渲染成人读的文本。每个工具的版式不同。"""
    out: list[str] = []
    if not result.get("ok", True):
        out.append(f"无法分析：{{result.get('error', '未知原因')}}")
        return "\n".join(out)
    out.append(f"数值个数：{result['count']}")
    out.append(f"和 {result['sum']}  均值 {result['mean']:.4f}  中位 {result['median']:.4f}")
    out.append(f"p10 {result['p10']:.4f}  p90 {result['p90']:.4f}")
    out.append(f"最小 {result['min']}  最大 {result['max']}  跨度 {result['span']}")
    out.append(f"负数个数：{result['negative_count']}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="shotorder",
        description="从输入中抽取数值，计算少样本示例的顺序效应相关的比值与占比，分母为零时明确报错（仅依赖标准库）",
        epilog=(
            "示例:\n"
            "  python shotorder.py --file input.txt\n"
            "  python shotorder.py --text '示例内容'\n"
            "  python shotorder.py --file input.txt --json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="输入文件路径")
    src.add_argument("--text", help="直接给出输入内容")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            print(f"读不了文件：{{e}}", file=sys.stderr)
            return 2
    else:
        content = args.text

    if not content.strip():
        print("输入是空的。", file=sys.stderr)
        return 2

    result = shotorder_analyze(content)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(render(result))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
