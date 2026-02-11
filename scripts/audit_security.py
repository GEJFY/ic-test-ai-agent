#!/usr/bin/env python3
"""
================================================================================
audit_security.py - セキュリティ監査スクリプト
================================================================================

【概要】
コードベースのセキュリティ問題を検出します。

【検証項目】
1. ハードコードされたシークレット（APIキー、パスワード等）
2. .gitignoreにシークレットファイルが含まれているか
3. 本番環境でトレースバック非表示設定
4. SQLインジェクション対策（該当する場合）
5. XSS対策（該当する場合）
6. CORS設定の確認

【使用方法】
python scripts/audit_security.py

【出力】
- セキュリティ問題のリスト
- 推奨修正事項

================================================================================
"""
import re
import sys
from typing import List, Dict, Set
from pathlib import Path


class SecurityAuditor:
    """セキュリティ監査クラス"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def audit_all(self) -> bool:
        """全監査を実行"""
        print(f"\n{'='*80}")
        print(f"セキュリティ監査開始")
        print(f"{'='*80}\n")

        # ハードコードされたシークレットチェック
        self._check_hardcoded_secrets()

        # .gitignore設定チェック
        self._check_gitignore()

        # エラーハンドリングチェック
        self._check_error_handling()

        # 環境変数使用チェック
        self._check_environment_variables()

        # CORS設定チェック
        self._check_cors_configuration()

        # 結果サマリー
        return self._print_summary()

    def _check_hardcoded_secrets(self):
        """ハードコードされたシークレットチェック"""
        print(f"[1/5] ハードコードされたシークレットチェック")

        # Pythonファイルのみをスキャン
        python_files = list(self.root_dir.glob("**/*.py"))

        # パターン定義
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "パスワード"),
            (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', "APIキー"),
            (r'secret[_-]?key\s*=\s*["\'][^"\']+["\']', "シークレットキー"),
            (r'token\s*=\s*["\'][^"\']+["\']', "トークン"),
            (r'aws[_-]?access[_-]?key[_-]?id\s*=\s*["\']AKI[A-Z0-9]+["\']', "AWS Access Key"),
            (r'AKIA[A-Z0-9]{16}', "AWS Access Key ID"),
            (r'["\'][0-9a-zA-Z]{32,}["\']', "疑わしい長い文字列")
        ]

        found_secrets = []

        for py_file in python_files:
            # 除外パス
            if any(exclude in str(py_file) for exclude in [".venv", "node_modules", ".git", "tests/"]):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")

                for pattern, secret_type in secret_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # 除外: os.getenv(), os.environ等の環境変数参照
                        if "os.getenv" in match.group(0) or "os.environ" in match.group(0):
                            continue
                        # 除外: テスト用の明示的なダミー値
                        if "test" in match.group(0).lower() or "dummy" in match.group(0).lower():
                            continue
                        # 除外: 例示用のプレースホルダー
                        if "YOUR_" in match.group(0) or "PLACEHOLDER" in match.group(0):
                            continue

                        found_secrets.append((py_file.relative_to(self.root_dir), secret_type, match.group(0)))

            except Exception as e:
                self.warnings.append(f"⚠️  ファイル読み込みエラー: {py_file.name}")

        if found_secrets:
            for file_path, secret_type, matched_text in found_secrets:
                # 長すぎる場合は省略
                display_text = matched_text[:50] + "..." if len(matched_text) > 50 else matched_text
                self.issues.append(
                    f"❌ ハードコードされた{secret_type}の可能性: {file_path} -> {display_text}"
                )
                print(f"  ❌ {file_path}: {secret_type}")
        else:
            print(f"  ✓ ハードコードされたシークレットは検出されませんでした")

        print()

    def _check_gitignore(self):
        """.gitignore設定チェック"""
        print(f"[2/5] .gitignore設定チェック")

        gitignore_path = self.root_dir / ".gitignore"

        if not gitignore_path.exists():
            self.issues.append("❌ .gitignoreファイルが見つかりません")
            print(f"  ❌ .gitignoreファイル不在\n")
            return

        content = gitignore_path.read_text(encoding="utf-8")

        # 必須エントリ
        required_entries = [
            ".env",
            "*.env",
            ".env.local",
            ".venv",
            "venv/",
            "*.key",
            "*.pem",
            "credentials.json",
            ".secrets"
        ]

        for entry in required_entries:
            if entry in content:
                print(f"  ✓ {entry}")
            else:
                self.warnings.append(
                    f"⚠️  .gitignoreに'{entry}'が含まれていません"
                )
                print(f"  ⚠️  {entry}")

        print()

    def _check_error_handling(self):
        """エラーハンドリングチェック"""
        print(f"[3/5] エラーハンドリングチェック")

        # error_handler.pyの存在確認
        error_handler_path = self.root_dir / "src" / "core" / "error_handler.py"

        if error_handler_path.exists():
            content = error_handler_path.read_text(encoding="utf-8")

            # トレースバック非表示機能の確認
            if "include_internal" in content and "to_dict" in content:
                print(f"  ✓ エラーハンドラーにトレースバック制御機能あり")
            else:
                self.warnings.append(
                    "⚠️  エラーハンドラーにトレースバック制御機能が見つかりません"
                )

            # ErrorResponseクラスの確認
            if "class ErrorResponse" in content:
                print(f"  ✓ ErrorResponseクラス実装済み")
            else:
                self.warnings.append(
                    "⚠️  ErrorResponseクラスが見つかりません"
                )

        else:
            self.warnings.append(
                "⚠️  error_handler.pyが見つかりません"
            )

        # プラットフォーム層でのエラーハンドリング確認
        platform_handlers = [
            self.root_dir / "platforms" / "azure" / "function_app.py",
            self.root_dir / "platforms" / "aws" / "lambda_handler.py",
            self.root_dir / "platforms" / "gcp" / "main.py"
        ]

        for handler_path in platform_handlers:
            if handler_path.exists():
                content = handler_path.read_text(encoding="utf-8")

                # try-exceptブロックの存在確認
                if "try:" in content and "except" in content:
                    print(f"  ✓ {handler_path.name}: try-exceptブロックあり")
                else:
                    self.warnings.append(
                        f"⚠️  {handler_path.name}: try-exceptブロックが見つかりません"
                    )

        print()

    def _check_environment_variables(self):
        """環境変数使用チェック"""
        print(f"[4/5] 環境変数使用チェック")

        # secrets_provider.pyの確認
        secrets_provider_path = self.root_dir / "src" / "infrastructure" / "secrets" / "secrets_provider.py"

        if secrets_provider_path.exists():
            print(f"  ✓ secrets_provider.py実装済み")

            content = secrets_provider_path.read_text(encoding="utf-8")

            # Key Vault/Secrets Manager/Secret Manager統合確認
            if "Key Vault" in content or "KeyVault" in content:
                print(f"  ✓ Azure Key Vault統合あり")
            else:
                self.warnings.append(
                    "⚠️  Azure Key Vault統合が見つかりません"
                )

            if "Secrets Manager" in content or "SecretsManager" in content:
                print(f"  ✓ AWS Secrets Manager統合あり")
            else:
                self.warnings.append(
                    "⚠️  AWS Secrets Manager統合が見つかりません"
                )

            if "Secret Manager" in content or "SecretManager" in content:
                print(f"  ✓ GCP Secret Manager統合あり")
            else:
                self.warnings.append(
                    "⚠️  GCP Secret Manager統合が見つかりません"
                )

        else:
            self.issues.append(
                "❌ secrets_provider.pyが見つかりません"
            )

        print()

    def _check_cors_configuration(self):
        """CORS設定チェック"""
        print(f"[5/5] CORS設定チェック")

        # Azure Functions
        azure_function_app = self.root_dir / "platforms" / "azure" / "function_app.py"
        if azure_function_app.exists():
            content = azure_function_app.read_text(encoding="utf-8")

            if "Access-Control-Allow-Origin" in content:
                print(f"  ✓ Azure: CORS設定あり")

                # ワイルドカード使用の警告
                if '"*"' in content or "'*'" in content:
                    self.warnings.append(
                        "⚠️  Azure: CORSでワイルドカード(*)が使用されています（本番環境では制限推奨）"
                    )
            else:
                self.info.append(
                    "ℹ️  Azure: CORS設定が見つかりません（必要に応じて設定）"
                )

        # AWS Lambda
        aws_lambda_handler = self.root_dir / "platforms" / "aws" / "lambda_handler.py"
        if aws_lambda_handler.exists():
            content = aws_lambda_handler.read_text(encoding="utf-8")

            if "Access-Control-Allow-Origin" in content:
                print(f"  ✓ AWS: CORS設定あり")

                if '"*"' in content or "'*'" in content:
                    self.warnings.append(
                        "⚠️  AWS: CORSでワイルドカード(*)が使用されています（本番環境では制限推奨）"
                    )
            else:
                self.info.append(
                    "ℹ️  AWS: CORS設定が見つかりません（必要に応じて設定）"
                )

        # GCP Cloud Functions
        gcp_main = self.root_dir / "platforms" / "gcp" / "main.py"
        if gcp_main.exists():
            content = gcp_main.read_text(encoding="utf-8")

            if "Access-Control-Allow-Origin" in content:
                print(f"  ✓ GCP: CORS設定あり")

                if '"*"' in content or "'*'" in content:
                    self.warnings.append(
                        "⚠️  GCP: CORSでワイルドカード(*)が使用されています（本番環境では制限推奨）"
                    )
            else:
                self.info.append(
                    "ℹ️  GCP: CORS設定が見つかりません（必要に応じて設定）"
                )

        print()

    def _print_summary(self) -> bool:
        """結果サマリーを表示"""
        print(f"\n{'='*80}")
        print(f"監査結果サマリー")
        print(f"{'='*80}\n")

        if self.issues:
            print("【重大な問題】")
            for issue in self.issues:
                print(f"  {issue}")
            print()

        if self.warnings:
            print("【警告】")
            for warning in self.warnings:
                print(f"  {warning}")
            print()

        if self.info:
            print("【情報】")
            for info_item in self.info:
                print(f"  {info_item}")
            print()

        if not self.issues and not self.warnings:
            print("  ✅ 重大なセキュリティ問題は検出されませんでした\n")

        print(f"{'='*80}")
        print(f"合計: 重大な問題 {len(self.issues)} 件, 警告 {len(self.warnings)} 件, 情報 {len(self.info)} 件")
        print(f"{'='*80}\n")

        if self.issues:
            print("❌ セキュリティ監査失敗 - 重大な問題があります")
            return False
        elif self.warnings:
            print("⚠️  セキュリティ監査完了（警告あり）")
            return True
        else:
            print("✅ セキュリティ監査成功")
            return True


def main():
    """メイン処理"""
    auditor = SecurityAuditor()
    success = auditor.audit_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
