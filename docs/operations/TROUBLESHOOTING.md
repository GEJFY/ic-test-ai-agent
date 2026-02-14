# トラブルシューティングガイド

## 概要

本システムでよくある問題と解決方法を説明します。

---

## デプロイメント関連

### 問題: Terraformデプロイが失敗する

**症状**:
```
Error: Resource already exists
```

**原因**: リソース名が既に使用されている

**解決策**:
```bash
# パラメータファイルでユニークな名前を指定
# Azure
az deployment group create --parameters projectName=ic-test-unique-123

# AWS/GCP
terraform apply -var="project_name=ic-test-unique-123"
```

### 問題: シークレット設定エラー

**症状**:
```
KeyVaultAccessDenied / AccessDenied
```

**原因**: デプロイ実行ユーザーにシークレット管理権限がない

**解決策**:
```bash
# Azure
az keyvault set-policy --name <VAULT_NAME> \
  --upn <USER_EMAIL> \
  --secret-permissions get list set

# AWS
aws secretsmanager put-resource-policy \
  --secret-id <SECRET_NAME> \
  --resource-policy file://policy.json

# GCP
gcloud secrets add-iam-policy-binding <SECRET_NAME> \
  --member="user:<EMAIL>" \
  --role="roles/secretmanager.admin"
```

---

## API実行関連

### 問題: 401 Unauthorized エラー

**症状**:
```json
{
  "error_code": "UNAUTHORIZED",
  "message": "Invalid API key"
}
```

**原因**: API Keyが正しくない、または未設定

**解決策**:
```bash
# API Key確認（Azure）
az apim subscription show --resource-group <RG> \
  --service-name <APIM_NAME> --sid <SUBSCRIPTION_ID>

# API Key確認（AWS）
aws apigateway get-api-keys --include-values

# API Key確認（GCP）
gcloud apigee apps describe <APP_NAME>
```

### 問題: 429 Too Many Requests エラー

**症状**:
```json
{
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded"
}
```

**原因**: レート制限（100 calls/60秒）に到達

**解決策**:
- リクエスト頻度を下げる
- レート制限の緩和を申請（本番環境）
- 複数のAPI Keyを使用して負荷分散

### 問題: 相関IDがレスポンスに含まれない

**症状**: `X-Correlation-ID`ヘッダーがレスポンスにない

**原因**: API Gateway設定ミス、またはバックエンドの実装漏れ

**解決策**:
```bash
# デプロイメント検証を実行
python scripts/validate_deployment.py --platform <platform>

# ログで相関ID伝播を確認
# Azure
az monitor app-insights query --app <APP_NAME> \
  --analytics-query "traces | where customDimensions.correlation_id == '<ID>'"
```

---

## 監視・ログ関連

### 問題: Application Insightsにログが表示されない

**症状**: ログが記録されない

**原因**: 接続文字列未設定、またはサンプリング設定

**解決策**:
```bash
# 接続文字列確認
az monitor app-insights component show \
  --app <APP_NAME> --resource-group <RG> \
  --query "connectionString"

# 環境変数設定確認
az containerapp show \
  --name <CONTAINER_APP_NAME> --resource-group <RG> \
  --query "properties.configuration.secrets"
```

**注意**: 10%サンプリング設定により、全リクエストが記録されるわけではありません。

### 問題: X-Rayトレースが表示されない

**症状**: X-Rayサービスマップが空

**原因**: X-Ray SDKが初期化されていない、または権限不足

**解決策**:
```bash
# App Runnerインスタンスロールにx-Ray権限追加
aws iam attach-role-policy \
  --role-name <APPRUNNER_INSTANCE_ROLE> \
  --policy-arn arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess

# App Runnerサービスの設定確認
aws apprunner describe-service \
  --service-arn <SERVICE_ARN> \
  --query "Service.ObservabilityConfiguration"
```

---

## パフォーマンス関連

### 問題: レスポンスが遅い（10秒以上）

**症状**: `/evaluate`のレスポンスタイムが長い

**原因**: LLM/OCR APIの処理時間

**解決策**:
1. **非同期処理に切り替え**
   ```bash
   # /evaluate/submitを使用
   curl -X POST <ENDPOINT>/evaluate/submit \
     -H "Content-Type: application/json" \
     -d @request.json
   ```

2. **タイムアウト設定の調整**
   ```bash
   # Azure Container Apps
   az containerapp ingress update --name <APP_NAME> \
     --resource-group <RG> --request-timeout 600

   # GCP Cloud Run
   gcloud run deploy <SERVICE_NAME> --timeout=540

   # AWS App Runner
   aws apprunner update-service --service-arn <ARN> \
     --health-check-configuration "Timeout=20"
   ```

3. **ドキュメントサイズの制限**
   - PDFは10ページ以内を推奨
   - 画像は2MB以内を推奨

### 問題: メモリ不足エラー

**症状**:
```
Process out of memory
```

**原因**: コンテナのメモリ設定不足

**解決策**:
```bash
# Azure Container Apps
az containerapp update --name <APP_NAME> \
  --resource-group <RG> --cpu 2.0 --memory 4.0Gi

# AWS App Runner
aws apprunner update-service --service-arn <SERVICE_ARN> \
  --instance-configuration "Cpu=2 vCPU,Memory=4 GB"

# GCP Cloud Run
gcloud run deploy <SERVICE_NAME> --memory=4Gi --cpu=2
```

---

## コスト関連

### 問題: 予想外にコストが高い

**症状**: 月額コストが見積もりの2倍以上

**原因**: LLMトークン使用量、またはログ保持量の増加

**調査方法**:
```bash
# コスト分析
# Azure
az consumption usage list --start-date 2026-02-01 --end-date 2026-02-28

# AWS
aws ce get-cost-and-usage --time-period Start=2026-02-01,End=2026-02-28 \
  --granularity MONTHLY --metrics BlendedCost

# GCP
gcloud billing accounts list
```

**対策**:
- ログ保持期間を30日→7日に短縮
- サンプリング率を10%→5%に削減
- LLMモデルをGPT-5.2→GPT-5 Nanoに変更（コスト削減）

---

## セキュリティ関連

### 問題: シークレットがログに露出

**症状**: CloudWatch/Application Insightsにシークレット文字列が記録

**原因**: ログ出力にシークレットを含めている

**解決策**:
```bash
# セキュリティ監査実行
python scripts/audit_security.py

# 該当箇所を修正
# 例: logger.info(f"API Key: {api_key}")  # ❌ NG
#     logger.info("API Key retrieved")   # ✅ OK
```

### 問題: トレースバックが本番環境で表示される

**症状**: エラーレスポンスにスタックトレースが含まれる

**原因**: `include_internal=True`設定、または環境判定ミス

**解決策**:
```python
# error_handler.pyで環境判定
import os

is_production = os.getenv("ENVIRONMENT") == "production"

error_response = ErrorResponse(...)
return error_response.to_dict(include_internal=not is_production)
```

---

## VBA/PowerShellクライアント関連

### 問題: VBAから接続できない

**症状**:
```
Run-time error '13': Type mismatch
```

**原因**: JSONレスポンスのパースエラー

**解決策**:
```vba
' ExcelToJson.bas
' エラーハンドリング追加
On Error GoTo ErrorHandler

Set httpReq = CreateObject("MSXML2.XMLHTTP")
' ... (省略)

ErrorHandler:
    MsgBox "エラー: " & Err.Description & vbCrLf & _
           "Status: " & httpReq.Status & vbCrLf & _
           "Response: " & httpReq.responseText
```

### 問題: PowerShellで証明書エラー

**症状**:
```
The underlying connection was closed: Could not establish trust relationship
```

**原因**: 自己署名証明書、またはTLS設定

**解決策**:
```powershell
# 一時的に証明書検証を無効化（開発環境のみ）
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {$true}

# または、証明書をインストール
Import-Certificate -FilePath cert.cer -CertStoreLocation Cert:\LocalMachine\Root
```

---

## 緊急時の連絡先

**開発チーム**: dev-team@example.com
**運用チーム**: ops-team@example.com
**エスカレーション**: manager@example.com

---

## 参考資料

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Monitoring Runbook](MONITORING_RUNBOOK.md)
- [Security Audit Script](../../scripts/audit_security.py)
