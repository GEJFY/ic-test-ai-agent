#!/usr/bin/env python3
"""
Lint エラー自動修正スクリプト
"""

import re
import sys
from pathlib import Path


def fix_unused_imports(file_path: Path) -> int:
    """未使用importを削除"""
    content = file_path.read_text(encoding="utf-8")
    original_lines = content.splitlines()
    fixed_lines = []
    removed_count = 0

    # 削除する未使用importのパターン
    unused_patterns = [
        r"^from typing import Dict$",
        r"^from typing import Any$",
        r"^from typing import Dict, Any$",
        r"^import os$",
    ]

    for line in original_lines:
        should_remove = False
        for pattern in unused_patterns:
            if re.match(pattern, line.strip()):
                # 実際に使用されているか確認
                if "Dict" in line and "Dict[" not in content:
                    should_remove = True
                elif "Any" in line and ": Any" not in content:
                    should_remove = True
                elif line.strip() == "import os" and "os." not in content:
                    should_remove = True

        if not should_remove:
            fixed_lines.append(line)
        else:
            removed_count += 1

    if removed_count > 0:
        file_path.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")
        print(f"  ✅ {file_path.name}: {removed_count}個の未使用importを削除")

    return removed_count


def fix_blank_lines(file_path: Path) -> int:
    """空行の問題を修正"""
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    fixed_lines = []
    fixed_count = 0

    for i, line in enumerate(lines):
        # 関数・メソッド定義の前に空行がない場合
        if line.strip().startswith("def ") and i > 0:
            prev_line = lines[i - 1].strip()
            if prev_line and not prev_line.startswith("#"):
                # クラス内のメソッドなら1行、それ以外なら2行
                if any(lines[j].strip().startswith("class ") for j in range(max(0, i - 10), i)):
                    fixed_lines.append("")
                    fixed_count += 1
                else:
                    fixed_lines.append("")
                    fixed_lines.append("")
                    fixed_count += 1

        fixed_lines.append(line)

    if fixed_count > 0:
        file_path.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")
        print(f"  ✅ {file_path.name}: {fixed_count}個の空行問題を修正")

    return fixed_count


def main():
    """メイン処理"""
    print("\n📋 Lintエラー自動修正開始\n")

    # 修正対象ファイル
    target_files = [
        "src/infrastructure/monitoring/__init__.py",
        "src/infrastructure/secrets/secrets_provider.py",
    ]

    total_fixes = 0

    for file_path_str in target_files:
        file_path = Path(file_path_str)
        if not file_path.exists():
            print(f"  ⚠️  {file_path}: ファイルが見つかりません")
            continue

        print(f"\n処理中: {file_path}")
        fixes = 0
        fixes += fix_unused_imports(file_path)
        # fixes += fix_blank_lines(file_path)  # 空行修正は手動で行う
        total_fixes += fixes

    print(f"\n\n合計 {total_fixes} 個のエラーを修正しました。\n")

    return 0 if total_fixes > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
