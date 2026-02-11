#!/usr/bin/env python3
"""
================================================================================
verify_documentation.py - ドキュメント整合性検証スクリプト
================================================================================

【概要】
ドキュメントが実装コードと整合していることを確認します。

【検証項目】
1. README.mdが最新のアーキテクチャを反映しているか
2. SYSTEM_SPECIFICATION.mdと実装の整合性
3. 各プラットフォームのREADME.mdの完全性
4. API仕様とエンドポイント実装の整合性
5. ドキュメント間のリンク切れチェック

【使用方法】
python scripts/verify_documentation.py

【出力】
- ドキュメント整合性レポート
- 不整合箇所のリスト
- リンク切れの一覧

================================================================================
"""
import re
import sys
from typing import List, Dict, Set
from pathlib import Path


class DocumentationVerifier:
    """ドキュメント整合性検証クラス"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.issues: List[str] = []
        self.warnings: List[str] = []

    def verify_all(self) -> bool:
        """全検証を実行"""
        print(f"\n{'='*80}")
        print(f"ドキュメント整合性検証開始")
        print(f"{'='*80}\n")

        # 必須ドキュメント存在確認
        self._check_required_documents()

        # README.md整合性チェック
        self._verify_readme()

        # SYSTEM_SPECIFICATION.md整合性チェック
        self._verify_system_specification()

        # プラットフォーム別README整合性チェック
        self._verify_platform_readmes()

        # ドキュメント間リンクチェック
        self._check_document_links()

        # 結果サマリー
        return self._print_summary()

    def _check_required_documents(self):
        """必須ドキュメント存在確認"""
        print(f"[1/5] 必須ドキュメント存在確認")

        required_docs = [
            "README.md",
            "SYSTEM_SPECIFICATION.md",
            "docs/CLOUD_COST_ESTIMATION.md",
            "platforms/azure/README.md",
            "platforms/aws/README.md",
            "platforms/gcp/README.md",
        ]

        for doc_path in required_docs:
            full_path = self.root_dir / doc_path
            if full_path.exists():
                print(f"  ✓ {doc_path}")
            else:
                self.issues.append(f"❌ 必須ドキュメント不在: {doc_path}")
                print(f"  ❌ {doc_path}")

        print()

    def _verify_readme(self):
        """README.md整合性チェック"""
        print(f"[2/5] README.md整合性チェック")

        readme_path = self.root_dir / "README.md"
        if not readme_path.exists():
            self.issues.append("❌ README.mdが見つかりません")
            print(f"  ❌ ファイル不在\n")
            return

        content = readme_path.read_text(encoding="utf-8")

        # アーキテクチャ関連キーワードのチェック
        required_keywords = [
            "API Gateway",
            "APIM",
            "相関ID",
            "監視",
            "Application Insights",
            "X-Ray",
            "Cloud Logging"
        ]

        for keyword in required_keywords:
            if keyword in content:
                print(f"  ✓ キーワード存在: {keyword}")
            else:
                self.warnings.append(
                    f"⚠️  README.mdに'{keyword}'の記載がありません"
                )

        # プラットフォーム情報のチェック
        platforms = ["Azure", "AWS", "GCP"]
        for platform in platforms:
            if platform in content:
                print(f"  ✓ プラットフォーム記載: {platform}")
            else:
                self.warnings.append(
                    f"⚠️  README.mdに'{platform}'の記載がありません"
                )

        print()

    def _verify_system_specification(self):
        """SYSTEM_SPECIFICATION.md整合性チェック"""
        print(f"[3/5] SYSTEM_SPECIFICATION.md整合性チェック")

        spec_path = self.root_dir / "SYSTEM_SPECIFICATION.md"
        if not spec_path.exists():
            self.issues.append("❌ SYSTEM_SPECIFICATION.mdが見つかりません")
            print(f"  ❌ ファイル不在\n")
            return

        content = spec_path.read_text(encoding="utf-8")

        # アーキテクチャ図の記載チェック
        if "```mermaid" in content or "```" in content:
            print(f"  ✓ アーキテクチャ図記載あり")
        else:
            self.warnings.append(
                "⚠️  SYSTEM_SPECIFICATION.mdにアーキテクチャ図がありません"
            )

        # エンドポイント定義チェック
        endpoints = [
            "/api/evaluate",
            "/api/health",
            "/api/config",
            "/api/evaluate/submit",
            "/api/evaluate/status"
        ]

        for endpoint in endpoints:
            if endpoint in content:
                print(f"  ✓ エンドポイント記載: {endpoint}")
            else:
                self.warnings.append(
                    f"⚠️  SYSTEM_SPECIFICATION.mdに'{endpoint}'の記載がありません"
                )

        # 実装エンドポイントとの整合性チェック
        self._check_endpoint_consistency(endpoints)

        print()

    def _check_endpoint_consistency(self, documented_endpoints: List[str]):
        """ドキュメントと実装のエンドポイント整合性チェック"""
        # Azure Functions
        azure_function_app = self.root_dir / "platforms" / "azure" / "function_app.py"
        if azure_function_app.exists():
            content = azure_function_app.read_text(encoding="utf-8")
            # @app.route() デコレータからエンドポイントを抽出
            implemented_endpoints = re.findall(r'@app\.route\(["\']([^"\']+)["\']', content)

            for endpoint in documented_endpoints:
                # /api プレフィックスを除去して比較
                endpoint_path = endpoint.replace("/api", "")
                if any(endpoint_path in impl for impl in implemented_endpoints):
                    print(f"  ✓ Azure実装確認: {endpoint}")
                else:
                    self.warnings.append(
                        f"⚠️  Azureに'{endpoint}'の実装が見つかりません"
                    )

    def _verify_platform_readmes(self):
        """プラットフォーム別README整合性チェック"""
        print(f"[4/5] プラットフォーム別README整合性チェック")

        platforms = ["azure", "aws", "gcp"]

        for platform in platforms:
            readme_path = self.root_dir / "platforms" / platform / "README.md"

            if not readme_path.exists():
                self.warnings.append(
                    f"⚠️  {platform.upper()} README.mdが見つかりません"
                )
                continue

            content = readme_path.read_text(encoding="utf-8")

            # 必須セクションのチェック
            required_sections = [
                "前提条件",
                "デプロイ",
                "環境変数",
                "テスト"
            ]

            for section in required_sections:
                if section in content:
                    print(f"  ✓ {platform.upper()}: {section}セクション存在")
                else:
                    self.warnings.append(
                        f"⚠️  {platform.upper()} README.mdに'{section}'セクションがありません"
                    )

            # API Gateway/APIM/Apigee設定の記載チェック
            if platform == "azure" and "APIM" in content:
                print(f"  ✓ {platform.upper()}: APIM設定記載あり")
            elif platform == "aws" and "API Gateway" in content:
                print(f"  ✓ {platform.upper()}: API Gateway設定記載あり")
            elif platform == "gcp" and "Apigee" in content:
                print(f"  ✓ {platform.upper()}: Apigee設定記載あり")
            else:
                self.warnings.append(
                    f"⚠️  {platform.upper()} README.mdにAPI Gateway層の記載がありません"
                )

        print()

    def _check_document_links(self):
        """ドキュメント間リンクチェック"""
        print(f"[5/5] ドキュメント間リンクチェック")

        # 全markdownファイルを取得
        markdown_files = list(self.root_dir.glob("**/*.md"))

        broken_links_count = 0

        for md_file in markdown_files:
            # .venv, node_modules等を除外
            if any(exclude in str(md_file) for exclude in [".venv", "node_modules", ".git"]):
                continue

            content = md_file.read_text(encoding="utf-8")

            # Markdownリンク [text](path) を抽出
            links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', content)

            for link_text, link_path in links:
                # 外部URLはスキップ
                if link_path.startswith(("http://", "https://", "#")):
                    continue

                # 相対パスを解決
                target_path = (md_file.parent / link_path).resolve()

                if not target_path.exists():
                    self.warnings.append(
                        f"⚠️  リンク切れ: {md_file.name} -> {link_path}"
                    )
                    broken_links_count += 1

        if broken_links_count == 0:
            print(f"  ✓ リンク切れなし")
        else:
            print(f"  ⚠️  リンク切れ: {broken_links_count}件")

        print()

    def _print_summary(self) -> bool:
        """結果サマリーを表示"""
        print(f"\n{'='*80}")
        print(f"検証結果サマリー")
        print(f"{'='*80}\n")

        if self.issues:
            print("【問題】")
            for issue in self.issues:
                print(f"  {issue}")
            print()

        if self.warnings:
            print("【警告】")
            for warning in self.warnings:
                print(f"  {warning}")
            print()

        if not self.issues and not self.warnings:
            print("  ✅ 全てのチェックが成功しました\n")

        print(f"{'='*80}")
        print(f"合計: 問題 {len(self.issues)} 件, 警告 {len(self.warnings)} 件")
        print(f"{'='*80}\n")

        if self.issues:
            print("❌ ドキュメント整合性検証失敗")
            return False
        elif self.warnings:
            print("⚠️  ドキュメント整合性検証完了（警告あり）")
            return True
        else:
            print("✅ ドキュメント整合性検証成功")
            return True


def main():
    """メイン処理"""
    verifier = DocumentationVerifier()
    success = verifier.verify_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
