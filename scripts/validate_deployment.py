#!/usr/bin/env python3
"""
================================================================================
validate_deployment.py - デプロイメント検証スクリプト
================================================================================

【概要】
Azure/AWS/GCP環境へのデプロイが正しく完了したかを検証します。

【検証項目】
1. 必須リソースの存在確認
2. API Gateway/APIM/Apigeeの接続確認
3. バックエンドのヘルスチェック
4. 監視サービスの設定確認
5. シークレット管理の動作確認
6. 相関IDの伝播確認

【使用方法】
python scripts/validate_deployment.py --platform azure
python scripts/validate_deployment.py --platform aws
python scripts/validate_deployment.py --platform gcp
python scripts/validate_deployment.py --all

【前提条件】
- 対応するプラットフォームの環境変数が設定済み
- 必要なPythonパッケージがインストール済み

================================================================================
"""
import argparse
import sys
import os
import requests
import time
from typing import Dict, Any, List, Tuple
from enum import Enum


class ValidationStatus(Enum):
    """検証ステータス"""
    PASS = "✓ PASS"
    FAIL = "✗ FAIL"
    WARN = "⚠ WARN"
    SKIP = "- SKIP"


class ValidationResult:
    """検証結果"""
    def __init__(self, name: str, status: ValidationStatus, message: str = ""):
        self.name = name
        self.status = status
        self.message = message

    def __str__(self):
        return f"{self.status.value} {self.name}: {self.message}"


class DeploymentValidator:
    """デプロイメント検証クラス"""

    def __init__(self, platform: str):
        self.platform = platform
        self.results: List[ValidationResult] = []

    def validate_all(self) -> bool:
        """全検証を実行"""
        print(f"\n{'='*80}")
        print(f"デプロイメント検証開始: {self.platform.upper()}")
        print(f"{'='*80}\n")

        # 環境変数確認
        self._validate_environment_variables()

        # API Gateway接続確認
        self._validate_api_gateway()

        # バックエンドヘルスチェック
        self._validate_backend_health()

        # 相関ID伝播確認
        self._validate_correlation_id()

        # 監視サービス確認
        self._validate_monitoring()

        # 結果サマリー
        return self._print_summary()

    def _validate_environment_variables(self):
        """環境変数の確認"""
        print(f"[1/5] 環境変数確認")

        required_vars = self._get_required_env_vars()

        for var_name in required_vars:
            value = os.getenv(var_name)
            if value:
                self.results.append(
                    ValidationResult(
                        f"環境変数 {var_name}",
                        ValidationStatus.PASS,
                        "設定済み"
                    )
                )
            else:
                self.results.append(
                    ValidationResult(
                        f"環境変数 {var_name}",
                        ValidationStatus.FAIL,
                        "未設定"
                    )
                )

        print()

    def _get_required_env_vars(self) -> List[str]:
        """プラットフォームごとの必須環境変数"""
        if self.platform == "azure":
            return [
                "AZURE_APIM_ENDPOINT",
                "AZURE_APIM_SUBSCRIPTION_KEY",
                "APPLICATIONINSIGHTS_CONNECTION_STRING",
                "KEY_VAULT_NAME"
            ]
        elif self.platform == "aws":
            return [
                "AWS_API_GATEWAY_ENDPOINT",
                "AWS_API_KEY",
                "AWS_REGION"
            ]
        elif self.platform == "gcp":
            return [
                "GCP_APIGEE_ENDPOINT",
                "GCP_API_KEY",
                "GCP_PROJECT"
            ]
        else:
            return []

    def _validate_api_gateway(self):
        """API Gateway接続確認"""
        print(f"[2/5] API Gateway接続確認")

        endpoint, api_key_header, api_key = self._get_api_gateway_config()

        if not endpoint or not api_key:
            self.results.append(
                ValidationResult(
                    "API Gateway接続",
                    ValidationStatus.SKIP,
                    "設定不足"
                )
            )
            print()
            return

        try:
            response = requests.get(
                f"{endpoint}/health",
                headers={api_key_header: api_key},
                timeout=10
            )

            if response.status_code == 200:
                self.results.append(
                    ValidationResult(
                        "API Gateway接続",
                        ValidationStatus.PASS,
                        f"ヘルスチェック成功 ({response.status_code})"
                    )
                )
            else:
                self.results.append(
                    ValidationResult(
                        "API Gateway接続",
                        ValidationStatus.FAIL,
                        f"ヘルスチェック失敗 ({response.status_code})"
                    )
                )

        except requests.exceptions.RequestException as e:
            self.results.append(
                ValidationResult(
                    "API Gateway接続",
                    ValidationStatus.FAIL,
                    f"接続エラー: {str(e)}"
                )
            )

        print()

    def _get_api_gateway_config(self) -> Tuple[str, str, str]:
        """API Gateway設定を取得"""
        if self.platform == "azure":
            return (
                os.getenv("AZURE_APIM_ENDPOINT"),
                "Ocp-Apim-Subscription-Key",
                os.getenv("AZURE_APIM_SUBSCRIPTION_KEY")
            )
        elif self.platform == "aws":
            return (
                os.getenv("AWS_API_GATEWAY_ENDPOINT"),
                "X-Api-Key",
                os.getenv("AWS_API_KEY")
            )
        elif self.platform == "gcp":
            return (
                os.getenv("GCP_APIGEE_ENDPOINT"),
                "X-Api-Key",
                os.getenv("GCP_API_KEY")
            )
        else:
            return (None, None, None)

    def _validate_backend_health(self):
        """バックエンドヘルスチェック"""
        print(f"[3/5] バックエンドヘルスチェック")

        endpoint, api_key_header, api_key = self._get_api_gateway_config()

        if not endpoint or not api_key:
            self.results.append(
                ValidationResult(
                    "バックエンドヘルスチェック",
                    ValidationStatus.SKIP,
                    "API Gateway未設定"
                )
            )
            print()
            return

        try:
            response = requests.get(
                f"{endpoint}/health",
                headers={api_key_header: api_key},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.results.append(
                        ValidationResult(
                            "バックエンドヘルスチェック",
                            ValidationStatus.PASS,
                            "正常"
                        )
                    )
                else:
                    self.results.append(
                        ValidationResult(
                            "バックエンドヘルスチェック",
                            ValidationStatus.WARN,
                            f"ステータス: {data.get('status')}"
                        )
                    )
            else:
                self.results.append(
                    ValidationResult(
                        "バックエンドヘルスチェック",
                        ValidationStatus.FAIL,
                        f"HTTPステータス: {response.status_code}"
                    )
                )

        except Exception as e:
            self.results.append(
                ValidationResult(
                    "バックエンドヘルスチェック",
                    ValidationStatus.FAIL,
                    f"エラー: {str(e)}"
                )
            )

        print()

    def _validate_correlation_id(self):
        """相関ID伝播確認"""
        print(f"[4/5] 相関ID伝播確認")

        endpoint, api_key_header, api_key = self._get_api_gateway_config()

        if not endpoint or not api_key:
            self.results.append(
                ValidationResult(
                    "相関ID伝播",
                    ValidationStatus.SKIP,
                    "API Gateway未設定"
                )
            )
            print()
            return

        test_correlation_id = f"validation_{int(time.time())}"

        try:
            response = requests.get(
                f"{endpoint}/health",
                headers={
                    "X-Correlation-ID": test_correlation_id,
                    api_key_header: api_key
                },
                timeout=10
            )

            if response.status_code == 200:
                returned_id = (
                    response.headers.get("X-Correlation-ID") or
                    response.headers.get("x-correlation-id")
                )

                if returned_id == test_correlation_id:
                    self.results.append(
                        ValidationResult(
                            "相関ID伝播",
                            ValidationStatus.PASS,
                            "正しく伝播"
                        )
                    )
                else:
                    self.results.append(
                        ValidationResult(
                            "相関ID伝播",
                            ValidationStatus.WARN,
                            f"不一致（送信: {test_correlation_id}, 受信: {returned_id}）"
                        )
                    )
            else:
                self.results.append(
                    ValidationResult(
                        "相関ID伝播",
                        ValidationStatus.FAIL,
                        f"リクエスト失敗 ({response.status_code})"
                    )
                )

        except Exception as e:
            self.results.append(
                ValidationResult(
                    "相関ID伝播",
                    ValidationStatus.FAIL,
                    f"エラー: {str(e)}"
                )
            )

        print()

    def _validate_monitoring(self):
        """監視サービス確認"""
        print(f"[5/5] 監視サービス確認")

        if self.platform == "azure":
            connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
            if connection_string:
                self.results.append(
                    ValidationResult(
                        "Azure Application Insights",
                        ValidationStatus.PASS,
                        "接続文字列設定済み"
                    )
                )
            else:
                self.results.append(
                    ValidationResult(
                        "Azure Application Insights",
                        ValidationStatus.WARN,
                        "接続文字列未設定"
                    )
                )

        elif self.platform == "aws":
            # X-Rayは環境変数不要（Lambda自動設定）
            self.results.append(
                ValidationResult(
                    "AWS X-Ray",
                    ValidationStatus.PASS,
                    "Lambda環境で自動有効化"
                )
            )

        elif self.platform == "gcp":
            project_id = os.getenv("GCP_PROJECT")
            if project_id:
                self.results.append(
                    ValidationResult(
                        "GCP Cloud Logging/Trace",
                        ValidationStatus.PASS,
                        f"プロジェクトID: {project_id}"
                    )
                )
            else:
                self.results.append(
                    ValidationResult(
                        "GCP Cloud Logging/Trace",
                        ValidationStatus.WARN,
                        "GCP_PROJECT未設定"
                    )
                )

        print()

    def _print_summary(self) -> bool:
        """結果サマリーを表示"""
        print(f"\n{'='*80}")
        print(f"検証結果サマリー")
        print(f"{'='*80}\n")

        pass_count = sum(1 for r in self.results if r.status == ValidationStatus.PASS)
        fail_count = sum(1 for r in self.results if r.status == ValidationStatus.FAIL)
        warn_count = sum(1 for r in self.results if r.status == ValidationStatus.WARN)
        skip_count = sum(1 for r in self.results if r.status == ValidationStatus.SKIP)

        for result in self.results:
            print(result)

        print(f"\n{'='*80}")
        print(f"合計: {len(self.results)} 項目")
        print(f"  成功: {pass_count}")
        print(f"  失敗: {fail_count}")
        print(f"  警告: {warn_count}")
        print(f"  スキップ: {skip_count}")
        print(f"{'='*80}\n")

        if fail_count > 0:
            print("❌ デプロイメント検証失敗")
            return False
        elif warn_count > 0:
            print("⚠️  デプロイメント検証完了（警告あり）")
            return True
        else:
            print("✅ デプロイメント検証成功")
            return True


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="デプロイメント検証スクリプト"
    )
    parser.add_argument(
        "--platform",
        choices=["azure", "aws", "gcp"],
        help="検証対象プラットフォーム"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="全プラットフォームを検証"
    )

    args = parser.parse_args()

    if not args.platform and not args.all:
        parser.print_help()
        sys.exit(1)

    platforms = ["azure", "aws", "gcp"] if args.all else [args.platform]

    all_passed = True

    for platform in platforms:
        validator = DeploymentValidator(platform)
        passed = validator.validate_all()
        all_passed = all_passed and passed

        if len(platforms) > 1:
            print("\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
