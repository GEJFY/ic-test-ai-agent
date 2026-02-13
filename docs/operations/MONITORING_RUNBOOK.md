# 監視・アラート対応手順書

## 概要

本システムの監視ダッシュボード、ログクエリ、アラート対応手順を説明します。

---

## 監視ダッシュボード

### Azure Application Insights

**アクセス**: Azure Portal → Application Insights → `<リソース名>`

**主要メトリクス**:
- リクエスト数/成功率
- レスポンスタイム（P50/P95/P99）
- 依存関係呼び出し時間（Azure AI Foundry）
- エラー率

**推奨ダッシュボード**:
```kusto
// リクエスト成功率（過去24時間）
requests
| where timestamp > ago(24h)
| summarize
    Total = count(),
    Success = countif(success == true),
    SuccessRate = 100.0 * countif(success == true) / count()
| project SuccessRate, Total, Success
```

### AWS CloudWatch / X-Ray

**アクセス**: AWS Console → CloudWatch → Dashboards

**主要メトリクス**:
- App Runner実行時間/エラー数
- App Runnerリクエスト数/レイテンシ
- Bedrockトークン使用量
- X-Rayサービスマップ

**推奨CloudWatch Insights クエリ**:
```
fields @timestamp, correlation_id, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
```

### GCP Cloud Logging / Trace

**アクセス**: GCP Console → Logging → Logs Explorer

**主要メトリクス**:
- Cloud Runリクエスト数/実行時間
- Vertex AIトークン使用量
- エラーログ数

**推奨クエリ**:
```
severity="ERROR"
timestamp>="2026-02-09T00:00:00Z"
```

---

## ログクエリサンプル

### 相関IDで全ログを追跡

**Azure**:
```kusto
union traces, requests, dependencies, exceptions
| where customDimensions.correlation_id == "20260209_1707484800_0001"
| order by timestamp asc
| project timestamp, itemType, message, customDimensions
```

**AWS**:
```
fields @timestamp, correlation_id, @message
| filter correlation_id = "20260209_1707484800_0001"
| sort @timestamp asc
```

**GCP**:
```
jsonPayload.correlation_id="20260209_1707484800_0001"
```

### エラー率の監視

**Azure**:
```kusto
requests
| where timestamp > ago(1h)
| summarize ErrorRate = 100.0 * countif(success == false) / count() by bin(timestamp, 5m)
| render timechart
```

### LLM API呼び出し回数

**Azure**:
```kusto
dependencies
| where target contains "openai.azure.com"
| where timestamp > ago(24h)
| summarize count() by bin(timestamp, 1h)
```

---

## アラート設定

### 推奨アラートルール

#### 1. エラー率アラート（全プラットフォーム）

**条件**: エラー率 > 5% が 5分間継続
**アクション**: メール通知 + Slackアラート
**対応**: [エラー急増時の対応](#エラー急増時の対応)

#### 2. レイテンシアラート

**条件**: P95レスポンスタイム > 10秒
**アクション**: 監視ダッシュボード確認
**対応**: [パフォーマンス劣化時の対応](#パフォーマンス劣化時の対応)

#### 3. LLM APIエラーアラート

**条件**: LLM API呼び出しエラー率 > 10%
**アクション**: 即時通知
**対応**: [外部API障害時の対応](#外部api障害時の対応)

---

## アラート対応手順

### エラー急増時の対応

**1. 状況確認**
```bash
# 直近のエラーログ取得
python scripts/validate_deployment.py --platform <platform>
```

**2. 原因特定**
- 相関IDで特定リクエストを追跡
- エラーメッセージ・スタックトレース確認
- 外部APIステータス確認

**3. 対応**
- 一時的な障害 → 自動復旧を待つ
- 設定ミス → 修正デプロイ
- 外部API障害 → [外部API障害時の対応](#外部api障害時の対応)

### パフォーマンス劣化時の対応

**1. ボトルネック特定**
- 依存関係マップでLLM/OCR呼び出し時間確認
- データベースクエリ時間確認（該当する場合）

**2. 対応**
- LLMタイムアウト → モデル変更検討
- OCR遅延 → ドキュメントサイズ制限検討
- メモリ不足 → Container Apps/App Runner/Cloud Runメモリ増量

### 外部API障害時の対応

**Azure AI Foundry / Bedrock / Vertex AI障害**

**1. ステータス確認**
- [Azure Status](https://status.azure.com/)
- [AWS Health Dashboard](https://health.aws.amazon.com/)
- [GCP Status Dashboard](https://status.cloud.google.com/)

**2. 対応**
- サービス復旧を待つ
- 代替プラットフォームへの切り替え検討
- ユーザーへの状況通知

---

## 定期メンテナンス

### 週次確認項目

- [ ] エラーログの傾向確認
- [ ] レスポンスタイムの推移確認
- [ ] コスト使用状況確認（予算超過チェック）
- [ ] 不要なログの削除（30日以上経過）

### 月次確認項目

- [ ] セキュリティ監査実行
  ```bash
  python scripts/audit_security.py
  ```
- [ ] コスト見積もり整合性確認
  ```bash
  python scripts/check_cost_estimates.py
  ```
- [ ] ドキュメント更新確認
  ```bash
  python scripts/verify_documentation.py
  ```

---

## エスカレーション

### Level 1（一次対応）
- エラー率 < 10%
- レイテンシ < 30秒
- 運用チーム内で対応

### Level 2（緊急対応）
- エラー率 > 10%
- サービス停止
- 開発チームエスカレーション

### Level 3（重大障害）
- 全プラットフォーム停止
- データ損失の可能性
- マネジメント報告

---

## 参考資料

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Cost Estimation](../CLOUD_COST_ESTIMATION.md)
