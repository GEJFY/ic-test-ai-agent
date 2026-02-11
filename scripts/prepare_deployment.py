#!/usr/bin/env python3
"""
デプロイメント準備スクリプト

環境のチェックとセットアップを自動化します。
"""

import argparse
import os
import sys
from typing import Dict, List, Optional
import subprocess
import json


class DeploymentPreparation:
    """デプロイメント準備クラス"""

    def __init__(self, platform: str):
        self.platform = platform.lower()
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.success_items: List[str] = []

    def run_all_checks(self) -> bool:
        """全チェック実行"""
        print(f"\n{'='*70}")
        print(f"  デプロイメント準備チェック - {self.platform.upper()}")
        print(f"{'='*70}\n")

        # 1. CLIツールの確認
        self._check_cli_tools()

        # 2. 認証情報の確認
        self._check_credentials()

        # 3. 環境変数の確認
        self._check_environment_variables()

        # 4. IaCファイルの確認
        self._check_iac_files()

        # 5. シークレットの確認
        self._check_secrets()

        # 結果サマリー表示
        return self._print_summary()

    def _check_cli_tools(self):
        """CLIツールの確認"""
        print("📋 CLIツールの確認\n")

        if self.platform == "azure":
            tools = {
                "az": "Azure CLI",
                "terraform": "Terraform (optional)",
            }
        elif self.platform == "aws":
            tools = {
                "aws": "AWS CLI",
                "terraform": "Terraform",
            }
        elif self.platform == "gcp":
            tools = {
                "gcloud": "Google Cloud SDK",
                "terraform": "Terraform",
            }
        else:
            self.issues.append(f"不明なプラットフォーム: {self.platform}")
            return

        for cmd, name in tools.items():
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    version = result.stdout.split("\n")[0]
                    print(f"  ✅ {name}: {version}")
                    self.success_items.append(f"{name} インストール済み")
                else:
                    print(f"  ❌ {name}: インストールされていません")
                    self.issues.append(f"{name} がインストールされていません")
            except FileNotFoundError:
                print(f"  ❌ {name}: インストールされていません")
                self.issues.append(f"{name} がインストールされていません")
            except Exception as e:
                print(f"  ⚠️  {name}: チェックエラー ({e})")
                self.warnings.append(f"{name} のチェックに失敗しました")

        print()

    def _check_credentials(self):
        """認証情報の確認"""
        print("🔐 認証情報の確認\n")

        if self.platform == "azure":
            self._check_azure_credentials()
        elif self.platform == "aws":
            self._check_aws_credentials()
        elif self.platform == "gcp":
            self._check_gcp_credentials()

        print()

    def _check_azure_credentials(self):
        """Azure認証情報の確認"""
        try:
            result = subprocess.run(
                ["az", "account", "show"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                account_info = json.loads(result.stdout)
                print(f"  ✅ Azure認証済み")
                print(f"     サブスクリプション: {account_info.get('name')}")
                print(f"     ID: {account_info.get('id')}")
                self.success_items.append("Azure認証済み")
            else:
                print(f"  ❌ Azure認証が必要です")
                print(f"     実行: az login")
                self.issues.append("Azure認証が必要です")
        except Exception as e:
            print(f"  ⚠️  Azure認証確認エラー: {e}")
            self.warnings.append("Azure認証の確認に失敗しました")

    def _check_aws_credentials(self):
        """AWS認証情報の確認"""
        try:
            result = subprocess.run(
                ["aws", "sts", "get-caller-identity"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                identity = json.loads(result.stdout)
                print(f"  ✅ AWS認証済み")
                print(f"     アカウントID: {identity.get('Account')}")
                print(f"     ARN: {identity.get('Arn')}")
                self.success_items.append("AWS認証済み")
            else:
                print(f"  ❌ AWS認証が必要です")
                print(f"     実行: aws configure")
                self.issues.append("AWS認証が必要です")
        except Exception as e:
            print(f"  ⚠️  AWS認証確認エラー: {e}")
            self.warnings.append("AWS認証の確認に失敗しました")

    def _check_gcp_credentials(self):
        """GCP認証情報の確認"""
        try:
            result = subprocess.run(
                ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                accounts = json.loads(result.stdout)
                if accounts:
                    print(f"  ✅ GCP認証済み")
                    print(f"     アカウント: {accounts[0].get('account')}")
                    self.success_items.append("GCP認証済み")
                else:
                    print(f"  ❌ GCP認証が必要です")
                    print(f"     実行: gcloud auth login")
                    self.issues.append("GCP認証が必要です")
            else:
                print(f"  ❌ GCP認証が必要です")
                self.issues.append("GCP認証が必要です")
        except Exception as e:
            print(f"  ⚠️  GCP認証確認エラー: {e}")
            self.warnings.append("GCP認証の確認に失敗しました")

    def _check_environment_variables(self):
        """環境変数の確認"""
        print("🔧 環境変数の確認\n")

        env_file = f".env.{self.platform}"
        if os.path.exists(env_file):
            print(f"  ✅ 環境変数ファイル存在: {env_file}")
            self.success_items.append(f"環境変数ファイル {env_file} 存在")
        else:
            print(f"  ⚠️  環境変数ファイル未作成: {env_file}")
            print(f"     テンプレートからコピー: cp {env_file}.template {env_file}")
            self.warnings.append(f"環境変数ファイル {env_file} が未作成です")

        print()

    def _check_iac_files(self):
        """IaCファイルの確認"""
        print("📂 IaCファイルの確認\n")

        if self.platform == "azure":
            iac_dir = "infrastructure/azure/bicep"
            required_files = ["main.bicep", "parameters.json"]
        else:  # aws or gcp
            iac_dir = f"infrastructure/{self.platform}/terraform"
            required_files = ["backend.tf", "variables.tf"]

        missing_files = []
        for file in required_files:
            file_path = os.path.join(iac_dir, file)
            if os.path.exists(file_path):
                print(f"  ✅ {file_path}")
                self.success_items.append(f"IaCファイル {file} 存在")
            else:
                print(f"  ❌ {file_path} が見つかりません")
                missing_files.append(file_path)

        if missing_files:
            self.issues.append(f"IaCファイルが不足: {', '.join(missing_files)}")

        print()

    def _check_secrets(self):
        """シークレットの確認"""
        print("🔒 シークレット管理の確認\n")

        if self.platform == "azure":
            print("  Azure Key Vaultにシークレットを登録してください:")
            print("    - AZURE-FOUNDRY-API-KEY")
            print("    - AZURE-FOUNDRY-ENDPOINT")
            print("    - AZURE-DOCUMENT-INTELLIGENCE-API-KEY")
            print("    - AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT")
        elif self.platform == "aws":
            print("  AWS Secrets Managerにシークレットを登録してください:")
            print("    - ic-test/bedrock-api-key")
            print("    - ic-test/bedrock-endpoint")
            print("    - ic-test/textract-api-key")
        elif self.platform == "gcp":
            print("  GCP Secret Managerにシークレットを登録してください:")
            print("    - vertexai-api-key")
            print("    - vertexai-endpoint")
            print("    - documentai-api-key")

        self.warnings.append("シークレットの登録を確認してください")
        print()

    def _print_summary(self) -> bool:
        """結果サマリー表示"""
        print(f"\n{'='*70}")
        print("  チェック結果サマリー")
        print(f"{'='*70}\n")

        if self.success_items:
            print("✅ 成功項目:")
            for item in self.success_items:
                print(f"  - {item}")
            print()

        if self.warnings:
            print("⚠️  警告:")
            for warning in self.warnings:
                print(f"  - {warning}")
            print()

        if self.issues:
            print("❌ 問題:")
            for issue in self.issues:
                print(f"  - {issue}")
            print()
            print("デプロイメント前に上記の問題を解決してください。\n")
            return False
        else:
            if self.warnings:
                print("⚠️  警告がありますが、デプロイメント可能です。\n")
            else:
                print("✅ すべてのチェックが成功しました。デプロイメント可能です。\n")
            return True


def main():
    parser = argparse.ArgumentParser(
        description="デプロイメント準備チェックスクリプト"
    )
    parser.add_argument(
        "--platform",
        required=True,
        choices=["azure", "aws", "gcp"],
        help="デプロイ先プラットフォーム",
    )

    args = parser.parse_args()

    prep = DeploymentPreparation(args.platform)
    success = prep.run_all_checks()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
