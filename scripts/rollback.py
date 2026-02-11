#!/usr/bin/env python3
"""
ロールバックスクリプト

デプロイメントを以前の状態に戻します。
"""

import argparse
import sys
import subprocess
from pathlib import Path


class Rollback:
    """ロールバック実行クラス"""

    def __init__(self, platform: str, environment: str = "staging", dry_run: bool = False):
        self.platform = platform.lower()
        self.environment = environment
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent

    def rollback(self) -> bool:
        """ロールバック実行"""
        print(f"\n{'='*70}")
        print(f"  ロールバック開始: {self.platform.upper()} ({self.environment})")
        if self.dry_run:
            print(f"  モード: DRY RUN")
        print(f"{'='*70}\n")

        if not self._confirm_rollback():
            return False

        try:
            if self.platform == "azure":
                return self._rollback_azure()
            elif self.platform == "aws":
                return self._rollback_aws()
            elif self.platform == "gcp":
                return self._rollback_gcp()
            else:
                print(f"  ❌ 不明なプラットフォーム: {self.platform}")
                return False

        except Exception as e:
            print(f"\n  ❌ ロールバック失敗: {e}\n")
            return False

    def _confirm_rollback(self) -> bool:
        """ロールバック確認"""
        if self.dry_run:
            return True

        print("  ⚠️  ロールバックを実行すると、以下のリソースが削除されます:")
        print(f"     - {self.platform.upper()} {self.environment}環境の全リソース")
        print()

        response = input("  本当にロールバックしますか? (yes/no): ")
        if response.lower() != 'yes':
            print("  ❌ ロールバックをキャンセルしました")
            return False

        return True

    def _rollback_azure(self) -> bool:
        """Azureロールバック"""
        if self.dry_run:
            print("  [DRY RUN] Azureロールバックをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    az group delete --name ic-test-{self.environment}-rg --yes --no-wait")
            print()
            return True

        print("  Azureリソースグループ削除中...")
        result = subprocess.run(
            [
                "az", "group", "delete",
                "--name", f"ic-test-{self.environment}-rg",
                "--yes",
                "--no-wait",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ リソースグループ削除失敗: {result.stderr}")
            return False

        print("  ✅ Azureロールバック完了（非同期削除中）\n")
        return True

    def _rollback_aws(self) -> bool:
        """AWSロールバック"""
        tf_dir = self.project_root / "infrastructure" / "aws" / "terraform"

        if self.dry_run:
            print("  [DRY RUN] AWSロールバックをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    cd {tf_dir}")
            print(f"    terraform destroy -auto-approve")
            print()
            return True

        print("  AWS Terraform destroy実行中...")
        result = subprocess.run(
            ["terraform", "destroy", "-auto-approve"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Terraform destroy失敗: {result.stderr}")
            return False

        print("  ✅ AWSロールバック完了\n")
        return True

    def _rollback_gcp(self) -> bool:
        """GCPロールバック"""
        tf_dir = self.project_root / "infrastructure" / "gcp" / "terraform"

        if self.dry_run:
            print("  [DRY RUN] GCPロールバックをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    cd {tf_dir}")
            print(f"    terraform destroy -auto-approve")
            print()
            return True

        print("  GCP Terraform destroy実行中...")
        result = subprocess.run(
            ["terraform", "destroy", "-auto-approve"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Terraform destroy失敗: {result.stderr}")
            return False

        print("  ✅ GCPロールバック完了\n")
        return True


def main():
    parser = argparse.ArgumentParser(description="ロールバックスクリプト")
    parser.add_argument(
        "--platform",
        required=True,
        choices=["azure", "aws", "gcp"],
        help="ロールバック対象プラットフォーム",
    )
    parser.add_argument(
        "--environment",
        default="staging",
        choices=["staging", "production"],
        help="ロールバック対象環境",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ドライラン",
    )

    args = parser.parse_args()

    rollback = Rollback(args.platform, args.environment, args.dry_run)
    success = rollback.rollback()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
