#!/usr/bin/env python3
"""
ワンコマンドデプロイメントスクリプト

全プラットフォーム（Azure Container Apps, AWS App Runner, GCP Cloud Run）への
コンテナベースの自動デプロイメントを実行します。
共通のDockerイメージ（FastAPI/Uvicorn）をビルドし、各クラウドのレジストリにプッシュします。
- Azure: ACR (Azure Container Registry) → Container Apps
- AWS: ECR (Elastic Container Registry) → App Runner
- GCP: Artifact Registry → Cloud Run
"""

import argparse
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
import time


class Deployer:
    """デプロイメント実行クラス"""

    def __init__(self, platform: str, environment: str = "staging", dry_run: bool = False):
        self.platform = platform.lower()
        self.environment = environment
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent
        self.deployment_id = f"{platform}-{environment}-{int(time.time())}"

    def deploy(self) -> bool:
        """デプロイメント実行"""
        print(f"\n{'='*70}")
        print(f"  デプロイメント開始: {self.platform.upper()} ({self.environment})")
        print(f"  デプロイメントID: {self.deployment_id}")
        if self.dry_run:
            print(f"  モード: DRY RUN（実際のリソースは作成されません）")
        print(f"{'='*70}\n")

        try:
            # 1. 事前チェック
            if not self._pre_deployment_check():
                return False

            # 2. シークレット設定確認
            if not self._check_secrets():
                return False

            # 3. インフラストラクチャデプロイ
            if not self._deploy_infrastructure():
                return False

            # 4. アプリケーションデプロイ
            if not self._deploy_application():
                return False

            # 5. デプロイメント検証
            if not self.dry_run:
                if not self._validate_deployment():
                    return False

            print(f"\n{'='*70}")
            print(f"  ✅ デプロイメント成功: {self.platform.upper()}")
            print(f"  デプロイメントID: {self.deployment_id}")
            print(f"{'='*70}\n")
            return True

        except Exception as e:
            print(f"\n{'='*70}")
            print(f"  ❌ デプロイメント失敗: {e}")
            print(f"{'='*70}\n")
            return False

    def _pre_deployment_check(self) -> bool:
        """デプロイメント前チェック"""
        print("📋 [1/5] デプロイメント前チェック\n")

        # 準備スクリプト実行
        result = subprocess.run(
            [sys.executable, "scripts/prepare_deployment.py", "--platform", self.platform],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("  ⚠️  デプロイメント前チェックで問題が検出されました")
            print(result.stdout)

            if not self.dry_run:
                response = input("\n続行しますか? (y/N): ")
                if response.lower() != 'y':
                    print("  ❌ デプロイメントを中止しました")
                    return False
        else:
            print("  ✅ デプロイメント前チェック完了\n")

        return True

    def _check_secrets(self) -> bool:
        """シークレット設定確認"""
        print("🔐 [2/5] シークレット設定確認\n")

        if self.platform == "azure":
            required_vars = [
                "AZURE_API_KEY",
                "AZURE_ENDPOINT",
                "AZURE_DOCUMENT_INTELLIGENCE_API_KEY",
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
            ]
        elif self.platform == "aws":
            required_vars = [
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
            ]
        elif self.platform == "gcp":
            required_vars = [
                "GOOGLE_APPLICATION_CREDENTIALS",
                "GCP_PROJECT_ID",
            ]
        else:
            print(f"  ❌ 不明なプラットフォーム: {self.platform}")
            return False

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            print(f"  ⚠️  以下の環境変数が未設定です:")
            for var in missing_vars:
                print(f"     - {var}")

            if not self.dry_run:
                print(f"\n  💡 .env.{self.platform} ファイルを作成してください:")
                print(f"     cp .env.{self.platform}.template .env.{self.platform}")
                return False
            else:
                print(f"  ℹ️  DRY RUNモードのため続行します\n")
        else:
            print("  ✅ シークレット設定確認完了\n")

        return True

    def _deploy_infrastructure(self) -> bool:
        """インフラストラクチャデプロイ"""
        print("🏗️  [3/5] インフラストラクチャデプロイ\n")

        if self.platform == "azure":
            return self._deploy_azure_infrastructure()
        elif self.platform == "aws":
            return self._deploy_aws_infrastructure()
        elif self.platform == "gcp":
            return self._deploy_gcp_infrastructure()

        return False

    def _deploy_azure_infrastructure(self) -> bool:
        """Azure Bicepデプロイ"""
        bicep_dir = self.project_root / "infrastructure" / "azure" / "bicep"

        if self.dry_run:
            print("  [DRY RUN] Azure Bicepデプロイをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    az deployment group create \\")
            print(f"      --resource-group ic-test-{self.environment}-rg \\")
            print(f"      --template-file {bicep_dir}/main.bicep \\")
            print(f"      --parameters {bicep_dir}/parameters.json")
            print()
            return True

        # リソースグループ作成
        print("  リソースグループ作成中...")
        result = subprocess.run(
            [
                "az", "group", "create",
                "--name", f"ic-test-{self.environment}-rg",
                "--location", "japaneast",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ リソースグループ作成失敗: {result.stderr}")
            return False

        # Bicepデプロイ
        print("  Bicepデプロイ実行中...")
        result = subprocess.run(
            [
                "az", "deployment", "group", "create",
                "--resource-group", f"ic-test-{self.environment}-rg",
                "--template-file", str(bicep_dir / "main.bicep"),
                "--parameters", str(bicep_dir / "parameters.json"),
                "--mode", "Incremental",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Bicepデプロイ失敗: {result.stderr}")
            return False

        print("  ✅ Azureインフラストラクチャデプロイ完了\n")
        return True

    def _deploy_aws_infrastructure(self) -> bool:
        """AWS Terraformデプロイ"""
        tf_dir = self.project_root / "infrastructure" / "aws" / "terraform"

        if self.dry_run:
            print("  [DRY RUN] AWS Terraformデプロイをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    cd {tf_dir}")
            print(f"    terraform init")
            print(f"    terraform plan")
            print(f"    terraform apply -auto-approve")
            print()
            return True

        # Terraform init
        print("  Terraform初期化中...")
        result = subprocess.run(
            ["terraform", "init"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Terraform init失敗: {result.stderr}")
            return False

        # Terraform plan
        print("  Terraform plan実行中...")
        result = subprocess.run(
            ["terraform", "plan", "-out=tfplan"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Terraform plan失敗: {result.stderr}")
            return False

        # Terraform apply
        print("  Terraform apply実行中...")
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "tfplan"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Terraform apply失敗: {result.stderr}")
            return False

        print("  ✅ AWSインフラストラクチャデプロイ完了\n")
        return True

    def _deploy_gcp_infrastructure(self) -> bool:
        """GCP Terraformデプロイ"""
        tf_dir = self.project_root / "infrastructure" / "gcp" / "terraform"

        if self.dry_run:
            print("  [DRY RUN] GCP Terraformデプロイをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    cd {tf_dir}")
            print(f"    terraform init")
            print(f"    terraform plan")
            print(f"    terraform apply -auto-approve")
            print()
            return True

        # Terraform init
        print("  Terraform初期化中...")
        result = subprocess.run(
            ["terraform", "init"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Terraform init失敗: {result.stderr}")
            return False

        # Terraform apply
        print("  Terraform apply実行中...")
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Terraform apply失敗: {result.stderr}")
            return False

        print("  ✅ GCPインフラストラクチャデプロイ完了\n")
        return True

    def _deploy_application(self) -> bool:
        """アプリケーションデプロイ（Dockerイメージのビルド・プッシュ・デプロイ）"""
        print("📦 [4/5] アプリケーションデプロイ\n")

        # 共通Dockerイメージのビルド
        if not self._build_docker_image():
            return False

        if self.platform == "azure":
            return self._deploy_azure_container_apps()
        elif self.platform == "aws":
            return self._deploy_aws_app_runner()
        elif self.platform == "gcp":
            return self._deploy_gcp_cloud_run()

        return False

    def _build_docker_image(self) -> bool:
        """共通Dockerイメージのビルド"""
        image_tag = f"ic-test-agent:{self.environment}-{int(time.time())}"
        self._image_tag = image_tag

        if self.dry_run:
            print(f"  [DRY RUN] Dockerイメージビルドをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    docker build -t {image_tag} .")
            print()
            return True

        print(f"  Dockerイメージビルド中: {image_tag}")
        result = subprocess.run(
            ["docker", "build", "-t", image_tag, "."],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ❌ Dockerイメージビルド失敗: {result.stderr}")
            return False

        print(f"  ✅ Dockerイメージビルド完了: {image_tag}\n")
        return True

    def _deploy_azure_container_apps(self) -> bool:
        """Azure Container Apps デプロイ（ACR経由）"""
        acr_name = f"ictestacr{self.environment}"
        acr_image = f"{acr_name}.azurecr.io/ic-test-agent:{self.environment}"
        container_app_name = f"ic-test-{self.environment}-app"
        resource_group = f"ic-test-{self.environment}-rg"

        if self.dry_run:
            print("  [DRY RUN] Azure Container Appsデプロイをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    az acr login --name {acr_name}")
            print(f"    docker tag {self._image_tag} {acr_image}")
            print(f"    docker push {acr_image}")
            print(f"    az containerapp update \\")
            print(f"      --name {container_app_name} \\")
            print(f"      --resource-group {resource_group} \\")
            print(f"      --image {acr_image}")
            print()
            return True

        # ACRログイン
        print(f"  ACRログイン中: {acr_name}")
        result = subprocess.run(
            ["az", "acr", "login", "--name", acr_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ ACRログイン失敗: {result.stderr}")
            return False

        # イメージタグ付け
        print(f"  イメージタグ付け: {acr_image}")
        result = subprocess.run(
            ["docker", "tag", self._image_tag, acr_image],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ イメージタグ付け失敗: {result.stderr}")
            return False

        # イメージプッシュ
        print(f"  イメージプッシュ中: {acr_image}")
        result = subprocess.run(
            ["docker", "push", acr_image],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ イメージプッシュ失敗: {result.stderr}")
            return False

        # Container Appsアップデート
        print(f"  Container Appsアップデート中: {container_app_name}")
        result = subprocess.run(
            [
                "az", "containerapp", "update",
                "--name", container_app_name,
                "--resource-group", resource_group,
                "--image", acr_image,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ Container Appsアップデート失敗: {result.stderr}")
            return False

        print("  ✅ Azure Container Appsデプロイ完了\n")
        return True

    def _deploy_aws_app_runner(self) -> bool:
        """AWS App Runner デプロイ（ECR経由）"""
        aws_region = os.getenv("AWS_REGION", "ap-northeast-1")
        aws_account_id = os.getenv("AWS_ACCOUNT_ID", "")
        ecr_repo = f"{aws_account_id}.dkr.ecr.{aws_region}.amazonaws.com/ic-test-agent"
        ecr_image = f"{ecr_repo}:{self.environment}"
        service_name = f"ic-test-{self.environment}-app"

        if self.dry_run:
            print("  [DRY RUN] AWS App Runnerデプロイをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    aws ecr get-login-password --region {aws_region} | docker login --username AWS --password-stdin {ecr_repo}")
            print(f"    docker tag {self._image_tag} {ecr_image}")
            print(f"    docker push {ecr_image}")
            print(f"    aws apprunner update-service \\")
            print(f"      --service-arn <service-arn> \\")
            print(f"      --source-configuration ImageRepository={{ImageIdentifier={ecr_image}}}")
            print()
            return True

        # ECRログイン
        print(f"  ECRログイン中: {aws_region}")
        login_password = subprocess.run(
            ["aws", "ecr", "get-login-password", "--region", aws_region],
            capture_output=True,
            text=True,
        )
        if login_password.returncode != 0:
            print(f"  ❌ ECRログインパスワード取得失敗: {login_password.stderr}")
            return False

        result = subprocess.run(
            ["docker", "login", "--username", "AWS", "--password-stdin", ecr_repo],
            input=login_password.stdout,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ ECRログイン失敗: {result.stderr}")
            return False

        # イメージタグ付け
        print(f"  イメージタグ付け: {ecr_image}")
        result = subprocess.run(
            ["docker", "tag", self._image_tag, ecr_image],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ イメージタグ付け失敗: {result.stderr}")
            return False

        # イメージプッシュ
        print(f"  イメージプッシュ中: {ecr_image}")
        result = subprocess.run(
            ["docker", "push", ecr_image],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ イメージプッシュ失敗: {result.stderr}")
            return False

        # App Runnerサービスアップデート（デプロイメントはECRトリガーで自動）
        print(f"  App Runnerサービス: {service_name} - ECRプッシュにより自動デプロイ")
        print("  ✅ AWS App Runnerデプロイ完了\n")
        return True

    def _deploy_gcp_cloud_run(self) -> bool:
        """GCP Cloud Run デプロイ（Artifact Registry経由）"""
        gcp_project = os.getenv("GCP_PROJECT_ID", "")
        gcp_region = os.getenv("GCP_REGION", "asia-northeast1")
        ar_image = f"{gcp_region}-docker.pkg.dev/{gcp_project}/ic-test-agent/app:{self.environment}"
        service_name = f"ic-test-{self.environment}-app"

        if self.dry_run:
            print("  [DRY RUN] GCP Cloud Runデプロイをスキップします")
            print(f"  実行予定コマンド:")
            print(f"    gcloud auth configure-docker {gcp_region}-docker.pkg.dev")
            print(f"    docker tag {self._image_tag} {ar_image}")
            print(f"    docker push {ar_image}")
            print(f"    gcloud run deploy {service_name} \\")
            print(f"      --image {ar_image} \\")
            print(f"      --region {gcp_region} \\")
            print(f"      --platform managed")
            print()
            return True

        # Artifact Registry認証設定
        print(f"  Artifact Registry認証設定中: {gcp_region}")
        result = subprocess.run(
            ["gcloud", "auth", "configure-docker", f"{gcp_region}-docker.pkg.dev", "--quiet"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ Artifact Registry認証設定失敗: {result.stderr}")
            return False

        # イメージタグ付け
        print(f"  イメージタグ付け: {ar_image}")
        result = subprocess.run(
            ["docker", "tag", self._image_tag, ar_image],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ イメージタグ付け失敗: {result.stderr}")
            return False

        # イメージプッシュ
        print(f"  イメージプッシュ中: {ar_image}")
        result = subprocess.run(
            ["docker", "push", ar_image],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ イメージプッシュ失敗: {result.stderr}")
            return False

        # Cloud Runデプロイ
        print(f"  Cloud Runデプロイ中: {service_name}")
        result = subprocess.run(
            [
                "gcloud", "run", "deploy", service_name,
                "--image", ar_image,
                "--region", gcp_region,
                "--platform", "managed",
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ❌ Cloud Runデプロイ失敗: {result.stderr}")
            return False

        print("  ✅ GCP Cloud Runデプロイ完了\n")
        return True

    def _validate_deployment(self) -> bool:
        """デプロイメント検証"""
        print("✅ [5/5] デプロイメント検証\n")

        result = subprocess.run(
            [sys.executable, "scripts/validate_deployment.py", "--platform", self.platform],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        print(result.stdout)

        if result.returncode != 0:
            print("  ⚠️  デプロイメント検証で問題が検出されました")
            return False

        print("  ✅ デプロイメント検証完了\n")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="ワンコマンドデプロイメントスクリプト"
    )
    parser.add_argument(
        "--platform",
        required=True,
        choices=["azure", "aws", "gcp", "all"],
        help="デプロイ先プラットフォーム",
    )
    parser.add_argument(
        "--environment",
        default="staging",
        choices=["staging", "production"],
        help="デプロイ環境",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ドライラン（実際のリソースは作成されません）",
    )

    args = parser.parse_args()

    if args.platform == "all":
        platforms = ["azure", "aws", "gcp"]
    else:
        platforms = [args.platform]

    all_success = True

    for platform in platforms:
        deployer = Deployer(platform, args.environment, args.dry_run)
        success = deployer.deploy()

        if not success:
            all_success = False
            if not args.dry_run:
                response = input(f"\n{platform}のデプロイに失敗しました。続行しますか? (y/N): ")
                if response.lower() != 'y':
                    break

    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
