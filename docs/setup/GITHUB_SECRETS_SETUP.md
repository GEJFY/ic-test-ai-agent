# GitHub Secrets セットアップガイド

このドキュメントでは、CI/CDパイプラインに必要なGitHub Secretsの設定手順を説明します。

## アクセス方法

1. GitHubリポジトリページへアクセス
2. **Settings** タブをクリック
3. 左メニューから **Secrets and variables** → **Actions** を選択
4. **New repository secret** をクリック

---

## 必要なSecrets一覧

### Azure環境

| Secret名 | 説明 | 取得方法 |
|---------|------|---------|
| `AZURE_CREDENTIALS` | サービスプリンシパル認証情報（JSON形式） | 下記「Azure認証情報の作成」参照 |
| `AZURE_RESOURCE_GROUP` | リソースグループ名 | 例: `ic-test-rg` |
| `AZURE_FUNCTION_APP_NAME` | Function App名 | 例: `ic-test-functions` |
| `AZURE_APIM_ENDPOINT` | APIM エンドポイント | 例: `https://ic-test-apim.azure-api.net/api` |
| `AZURE_APIM_SUBSCRIPTION_KEY` | APIM サブスクリプションキー | APIMポータルから取得 |

#### Azure認証情報の作成

```bash
# サービスプリンシパル作成
az ad sp create-for-rbac \
  --name "ic-test-github-actions" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/ic-test-rg \
  --sdk-auth

# 出力されたJSON全体をAZURE_CREDENTIALSに設定
```

出力例:
```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

---

### AWS環境

| Secret名 | 説明 | 取得方法 |
|---------|------|---------|
| `AWS_ACCESS_KEY_ID` | アクセスキーID | IAMユーザー作成時に取得 |
| `AWS_SECRET_ACCESS_KEY` | シークレットアクセスキー | IAMユーザー作成時に取得 |
| `AWS_LAMBDA_FUNCTION_NAME` | Lambda関数名 | 例: `ic-test-evaluator` |
| `AWS_API_GATEWAY_ENDPOINT` | API Gateway エンドポイント | 例: `https://xxxxx.execute-api.ap-northeast-1.amazonaws.com/prod` |
| `AWS_API_KEY` | API Key | API Gatewayコンソールから取得 |

#### AWS IAMユーザーの作成

```bash
# IAMユーザー作成
aws iam create-user --user-name ic-test-github-actions

# ポリシーアタッチ
aws iam attach-user-policy \
  --user-name ic-test-github-actions \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# アクセスキー作成
aws iam create-access-key --user-name ic-test-github-actions
```

---

### GCP環境

| Secret名 | 説明 | 取得方法 |
|---------|------|---------|
| `GCP_SERVICE_ACCOUNT_KEY` | サービスアカウントキー（JSON形式） | 下記「GCPサービスアカウントの作成」参照 |
| `GCP_PROJECT_ID` | プロジェクトID | 例: `ic-test-project` |
| `GCP_FUNCTION_SERVICE_ACCOUNT` | Cloud Functions サービスアカウント | 例: `ic-test-sa@ic-test-project.iam.gserviceaccount.com` |
| `GCP_APIGEE_ENDPOINT` | Apigee エンドポイント | 例: `https://xxxxx-eval.apigee.net/evaluate` |
| `GCP_API_KEY` | API Key | Apigeeコンソールから取得 |

#### GCPサービスアカウントの作成

```bash
# サービスアカウント作成
gcloud iam service-accounts create ic-test-github-actions \
  --display-name "IC Test GitHub Actions"

# ロール付与
gcloud projects add-iam-policy-binding ic-test-project \
  --member="serviceAccount:ic-test-github-actions@ic-test-project.iam.gserviceaccount.com" \
  --role="roles/editor"

# キー作成（JSON形式）
gcloud iam service-accounts keys create key.json \
  --iam-account=ic-test-github-actions@ic-test-project.iam.gserviceaccount.com

# key.jsonの内容をGCP_SERVICE_ACCOUNT_KEYに設定
cat key.json
```

---

## 設定完了チェックリスト

### Azure

- [ ] `AZURE_CREDENTIALS` を設定
- [ ] `AZURE_RESOURCE_GROUP` を設定
- [ ] `AZURE_FUNCTION_APP_NAME` を設定
- [ ] `AZURE_APIM_ENDPOINT` を設定
- [ ] `AZURE_APIM_SUBSCRIPTION_KEY` を設定

### AWS

- [ ] `AWS_ACCESS_KEY_ID` を設定
- [ ] `AWS_SECRET_ACCESS_KEY` を設定
- [ ] `AWS_LAMBDA_FUNCTION_NAME` を設定
- [ ] `AWS_API_GATEWAY_ENDPOINT` を設定
- [ ] `AWS_API_KEY` を設定

### GCP

- [ ] `GCP_SERVICE_ACCOUNT_KEY` を設定
- [ ] `GCP_PROJECT_ID` を設定
- [ ] `GCP_FUNCTION_SERVICE_ACCOUNT` を設定
- [ ] `GCP_APIGEE_ENDPOINT` を設定
- [ ] `GCP_API_KEY` を設定

---

## セキュリティのベストプラクティス

### 1. 最小権限の原則

GitHub Actionsには必要最小限の権限のみを付与:
- Azure: Contributorロール（リソースグループスコープ）
- AWS: PowerUserAccessまたはカスタムポリシー
- GCP: Editorロール（プロジェクトスコープ）

### 2. キーのローテーション

定期的にキーをローテーション:
- Azure: サービスプリンシパルシークレットは90日ごと
- AWS: アクセスキーは90日ごと
- GCP: サービスアカウントキーは90日ごと

### 3. アクティビティ監視

認証情報の使用状況を監視:
- Azure: Azure AD監査ログ
- AWS: CloudTrail
- GCP: Cloud Audit Logs

---

## トラブルシューティング

### Azure: "Unauthorized" エラー

**原因**: サービスプリンシパルに権限がない

**解決策**:
```bash
# サブスクリプションスコープでContributorロールを付与
az role assignment create \
  --assignee {clientId} \
  --role Contributor \
  --scope /subscriptions/{subscription-id}
```

### AWS: "Access Denied" エラー

**原因**: IAMユーザーに権限がない

**解決策**:
```bash
# 必要なポリシーを確認して追加
aws iam attach-user-policy \
  --user-name ic-test-github-actions \
  --policy-arn arn:aws:iam::aws:policy/AWSLambdaFullAccess
```

### GCP: "Permission Denied" エラー

**原因**: サービスアカウントに権限がない

**解決策**:
```bash
# 必要なロールを追加
gcloud projects add-iam-policy-binding ic-test-project \
  --member="serviceAccount:ic-test-github-actions@ic-test-project.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.admin"
```

---

## 参考資料

- [Azure - GitHub Actions から Azure へ接続する](https://learn.microsoft.com/ja-jp/azure/developer/github/connect-from-azure)
- [AWS - GitHub Actions による AWS へのデプロイ](https://docs.github.com/ja/actions/deployment/deploying-to-your-cloud-provider/deploying-to-amazon-elastic-container-service)
- [GCP - GitHub Actions からの認証](https://cloud.google.com/blog/ja/products/identity-security/enabling-keyless-authentication-from-github-actions)
