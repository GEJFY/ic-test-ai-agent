# 監視クエリサンプル集

> **対象システム**: 内部統制テストAIエージェント (ic-test-ai-agent)
> **最終更新**: 2026-02-11
> **対象プラットフォーム**: Azure / AWS / GCP

---

## 目次

1. [概要](#1-概要)
2. [Azure Application Insights（Kusto）](#2-azure-application-insightskusto)
3. [AWS CloudWatch Insights](#3-aws-cloudwatch-insights)
4. [GCP Cloud Logging](#4-gcp-cloud-logging)
5. [ダッシュボード設定例](#5-ダッシュボード設定例)
6. [アラートルール設定](#6-アラートルール設定)

---

## 1. 概要

本ドキュメントは、内部統制テストAIエージェントの運用監視に使用する
クエリのリファレンス集です。3つのクラウドプラットフォームそれぞれについて、
以下のカテゴリのクエリを提供します。

| カテゴリ | 用途 |
|---------|------|
| 相関IDリクエスト追跡 | 個別リクエストの全処理フローを追跡 |
| エラー率監視 | 時系列でのエラー発生率を監視 |
| LLM API呼び出し分析 | LLM APIの使用状況・レスポンスタイム分析 |
| レスポンスタイム分析 | P50/P95/P99パーセンタイル分析 |
| 処理時間の長いリクエスト | ボトルネック特定 |
| エラータイプ別集計 | エラーコード別の発生頻度 |
| 日次/週次サマリー | 定期レポート用集計 |

### 主要メトリクス名一覧

| メトリクス名 | 単位 | 説明 |
|-------------|------|------|
| `document_processing_total` | count | 処理済みドキュメント数 |
| `ocr_duration_ms` | ms | OCR処理時間 |
| `llm_api_calls_total` | count | LLM API呼び出し回数 |
| `llm_duration_ms` | ms | LLM処理時間 |
| `error_total` | count | エラー発生数 |
| `request_duration_ms` | ms | リクエスト全体の処理時間 |

---

## 2. Azure Application Insights（Kusto）

### 2.1 相関IDによるリクエスト追跡

```kusto
// 特定の相関IDに関連するすべてのログを時系列で表示
traces
| where customDimensions.correlation_id == "20260209_1707484800_0001"
| order by timestamp asc
| project
    timestamp,
    message,
    severityLevel,
    customDimensions.correlation_id,
    customDimensions.error_id,
    customDimensions.error_code,
    operation_Name
```

```kusto
// 相関IDに関連する例外を表示
exceptions
| where customDimensions.correlation_id == "20260209_1707484800_0001"
| project
    timestamp,
    type,
    outerMessage,
    innermostMessage,
    details,
    customDimensions.error_id
| order by timestamp asc
```

```kusto
// 相関IDに関連する依存関係呼び出し（LLM API、OCRなど）
dependencies
| where customDimensions.correlation_id == "20260209_1707484800_0001"
| project
    timestamp,
    name,
    type,
    target,
    duration,
    success,
    resultCode
| order by timestamp asc
```

### 2.2 エラー率監視（時系列）

```kusto
// 1時間ごとのエラー率推移
traces
| where timestamp > ago(24h)
| summarize
    total = count(),
    errors = countif(severityLevel >= 3),
    error_rate = round(100.0 * countif(severityLevel >= 3) / count(), 2)
    by bin(timestamp, 1h)
| order by timestamp asc
| render timechart
```

```kusto
// エラーコード別の時系列推移
traces
| where timestamp > ago(24h)
| where isnotempty(customDimensions.error_code)
| summarize error_count = count()
    by bin(timestamp, 1h),
       tostring(customDimensions.error_code)
| order by timestamp asc
| render timechart
```

```kusto
// 直近1時間のエラー率（アラート用）
let time_window = 1h;
traces
| where timestamp > ago(time_window)
| summarize
    total = count(),
    errors = countif(severityLevel >= 3)
| extend error_rate_percent = round(100.0 * errors / total, 2)
| where error_rate_percent > 5
```

### 2.3 LLM API呼び出し分析

```kusto
// LLM API呼び出し回数と成功率（1時間ごと）
customMetrics
| where name == "llm_api_calls_total"
| where timestamp > ago(24h)
| summarize
    total_calls = sum(value),
    success_calls = sumif(value, customDimensions.success == "True"),
    failed_calls = sumif(value, customDimensions.success == "False")
    by bin(timestamp, 1h)
| extend success_rate = round(100.0 * success_calls / total_calls, 2)
| order by timestamp asc
| render timechart
```

```kusto
// LLM処理時間の統計（プロバイダー別）
customMetrics
| where name == "llm_duration_ms"
| where timestamp > ago(24h)
| summarize
    avg_duration = round(avg(value), 1),
    p50 = round(percentile(value, 50), 1),
    p95 = round(percentile(value, 95), 1),
    p99 = round(percentile(value, 99), 1),
    max_duration = round(max(value), 1),
    call_count = count()
    by tostring(customDimensions.dependency_type)
```

```kusto
// LLM APIエラーの詳細分析
traces
| where timestamp > ago(24h)
| where customDimensions.error_code == "LLM_API_ERROR"
| project
    timestamp,
    message,
    customDimensions.correlation_id,
    customDimensions.error_id,
    customDimensions.dependency_type,
    customDimensions.target
| order by timestamp desc
| take 50
```

### 2.4 レスポンスタイム分析（P50/P95/P99）

```kusto
// リクエスト全体の処理時間パーセンタイル（1時間ごと）
customMetrics
| where name == "request_duration_ms"
| where timestamp > ago(24h)
| summarize
    p50 = round(percentile(value, 50), 0),
    p95 = round(percentile(value, 95), 0),
    p99 = round(percentile(value, 99), 0),
    avg_ms = round(avg(value), 0),
    request_count = count()
    by bin(timestamp, 1h)
| order by timestamp asc
| render timechart
```

```kusto
// OCR処理時間の分布
customMetrics
| where name == "ocr_duration_ms"
| where timestamp > ago(24h)
| summarize
    p50 = round(percentile(value, 50), 0),
    p95 = round(percentile(value, 95), 0),
    p99 = round(percentile(value, 99), 0),
    avg_ms = round(avg(value), 0),
    max_ms = round(max(value), 0),
    count = count()
    by bin(timestamp, 1h)
| order by timestamp asc
```

```kusto
// 処理段階別の所要時間内訳
customMetrics
| where timestamp > ago(24h)
| where name in ("ocr_duration_ms", "llm_duration_ms", "request_duration_ms")
| summarize
    avg_ms = round(avg(value), 0),
    p95_ms = round(percentile(value, 95), 0)
    by name
| order by avg_ms desc
```

### 2.5 処理時間の長いリクエスト

```kusto
// P95を超える遅延リクエスト（直近24時間）
let p95_threshold =
    customMetrics
    | where name == "request_duration_ms"
    | where timestamp > ago(24h)
    | summarize threshold = percentile(value, 95);
customMetrics
| where name == "request_duration_ms"
| where timestamp > ago(24h)
| where value > toscalar(p95_threshold)
| project
    timestamp,
    duration_ms = round(value, 0),
    customDimensions.correlation_id,
    customDimensions
| order by duration_ms desc
| take 20
```

```kusto
// 10秒以上かかったリクエストの詳細
customMetrics
| where name == "request_duration_ms"
| where timestamp > ago(24h)
| where value > 10000
| join kind=inner (
    traces
    | where timestamp > ago(24h)
    | where isnotempty(customDimensions.correlation_id)
) on $left.customDimensions.correlation_id == $right.customDimensions.correlation_id
| summarize
    duration_ms = max(value),
    log_count = count(),
    errors = countif(severityLevel >= 3)
    by tostring(customDimensions.correlation_id)
| order by duration_ms desc
```

### 2.6 エラータイプ別集計

```kusto
// エラーコード別の集計（直近24時間）
traces
| where timestamp > ago(24h)
| where isnotempty(customDimensions.error_code)
| summarize
    count = count(),
    latest = max(timestamp),
    affected_requests = dcount(tostring(customDimensions.correlation_id))
    by tostring(customDimensions.error_code)
| order by count desc
```

```kusto
// 例外タイプ別の集計
exceptions
| where timestamp > ago(24h)
| summarize
    count = count(),
    latest = max(timestamp),
    sample_message = take_any(outerMessage)
    by type
| order by count desc
```

```kusto
// エラーコードとHTTPステータスコードのクロス集計
requests
| where timestamp > ago(24h)
| where success == false
| join kind=leftouter (
    traces
    | where isnotempty(customDimensions.error_code)
    | project customDimensions.correlation_id, customDimensions.error_code
) on $left.customDimensions.correlation_id == $right.customDimensions.correlation_id
| summarize count = count()
    by resultCode, tostring(customDimensions.error_code)
| order by count desc
```

### 2.7 日次/週次サマリー

```kusto
// 日次サマリーレポート
let target_date = datetime(2026-02-09);
traces
| where timestamp between (target_date .. target_date + 1d)
| summarize
    total_requests = dcount(tostring(customDimensions.correlation_id)),
    total_logs = count(),
    error_logs = countif(severityLevel >= 3),
    unique_errors = dcount(tostring(customDimensions.error_code)),
    client_requests = dcountif(
        tostring(customDimensions.correlation_id),
        customDimensions.correlation_id matches regex @"^\d{8}_"
    ),
    server_generated = dcountif(
        tostring(customDimensions.correlation_id),
        customDimensions.correlation_id matches regex @"^[0-9a-f]{8}-"
    )
```

```kusto
// 週次トレンドレポート
traces
| where timestamp > ago(7d)
| summarize
    total_requests = dcount(tostring(customDimensions.correlation_id)),
    error_count = countif(severityLevel >= 3),
    error_rate = round(100.0 * countif(severityLevel >= 3) / count(), 2)
    by bin(timestamp, 1d)
| order by timestamp asc
| render columnchart
```

```kusto
// 週次LLM使用量サマリー
customMetrics
| where timestamp > ago(7d)
| where name in ("llm_api_calls_total", "llm_duration_ms")
| summarize
    total_value = sum(value),
    avg_value = round(avg(value), 1)
    by name, bin(timestamp, 1d)
| order by timestamp asc, name
```

---

## 3. AWS CloudWatch Insights

### 3.1 相関IDログ検索

```
# 特定の相関IDに関連するすべてのログ
fields @timestamp, @message, correlation_id, error_id, error_code
| filter correlation_id = "20260209_1707484800_0001"
| sort @timestamp asc
| limit 200
```

```
# 特定日のリクエスト一覧と処理結果
fields @timestamp, correlation_id, @message
| filter correlation_id like /^20260209_/
| stats
    count() as log_count,
    earliest(@timestamp) as first_seen,
    latest(@timestamp) as last_seen
    by correlation_id
| sort first_seen desc
| limit 100
```

```
# UUIDフォールバックが発生したリクエスト（ヘッダー未設定）
fields @timestamp, correlation_id, @message
| filter correlation_id like /^[0-9a-f]{8}-[0-9a-f]{4}-4/
| filter @message like /相関IDが見つからないため新規生成/
| stats count() as fallback_count by bin(@timestamp, 1h)
| sort @timestamp desc
```

### 3.2 App Runner実行分析

```
# App Runnerサービスの実行統計
fields @timestamp, @message
| filter @message like /request_duration_ms/
| parse @message '"metric_value":*,' as duration_ms
| stats
    avg(duration_ms) as avg_ms,
    pct(duration_ms, 50) as p50_ms,
    pct(duration_ms, 95) as p95_ms,
    pct(duration_ms, 99) as p99_ms,
    max(duration_ms) as max_ms,
    count() as request_count
    by bin(@timestamp, 1h)
| sort @timestamp desc
```

```
# 実行時間の長いApp Runnerリクエスト（10秒超）
fields @timestamp, correlation_id, @message
| filter @message like /request_duration_ms/
| parse @message '"metric_value":*,' as duration_ms
| filter duration_ms > 10000
| sort duration_ms desc
| limit 20
```

```
# App Runner Cold Start検出と影響分析
fields @timestamp, @message
| filter @message like /cold_start/
| stats
    count() as cold_starts,
    avg(duration_ms) as avg_duration_ms
    by bin(@timestamp, 1h)
| sort @timestamp desc
```

### 3.3 エラー集計

```
# エラーコード別集計（直近24時間）
fields @timestamp, error_code, correlation_id, @message
| filter ispresent(error_code)
| stats
    count() as error_count,
    earliest(@timestamp) as first_occurrence,
    latest(@timestamp) as last_occurrence
    by error_code
| sort error_count desc
```

```
# 時間帯別エラー率
fields @timestamp, @message
| stats
    count() as total,
    sum(strcontains(@message, "ERROR") or strcontains(@message, "エラー")) as errors
    by bin(@timestamp, 1h)
| display @timestamp, total, errors,
    concat(toString(errors * 100 / total), "%") as error_rate
| sort @timestamp desc
```

```
# LLM APIエラーの詳細
fields @timestamp, correlation_id, error_code, @message
| filter error_code = "LLM_API_ERROR"
| sort @timestamp desc
| limit 50
```

```
# App Runner実行エラー
filter @message like /Task timed out/
    or @message like /HealthCheckFailed/
    or @message like /ContainerError/
| fields @timestamp, correlation_id, @message
| sort @timestamp desc
| limit 20
```

### 3.4 Bedrockトークン使用量

```
# Bedrock API呼び出し統計
fields @timestamp, @message
| filter @message like /metric_name.*llm_api_calls_total/
    or @message like /Bedrock/
| parse @message '"metric_value":*,' as token_count
| stats
    sum(token_count) as total_tokens,
    avg(token_count) as avg_tokens,
    count() as call_count
    by bin(@timestamp, 1h)
| sort @timestamp desc
```

```
# Bedrock処理時間分析
fields @timestamp, @message
| filter @message like /llm_duration_ms/
| parse @message '"metric_value":*,' as duration_ms
| stats
    avg(duration_ms) as avg_ms,
    pct(duration_ms, 50) as p50_ms,
    pct(duration_ms, 95) as p95_ms,
    max(duration_ms) as max_ms,
    count() as call_count
    by bin(@timestamp, 1h)
| sort @timestamp desc
```

```
# Bedrockモデル別使用量
fields @timestamp, @message
| filter @message like /dependency_call/
    and @message like /Bedrock/
| parse @message '"target":"*"' as model_id
| parse @message '"duration_ms":*,' as duration_ms
| parse @message '"success":*}' as success
| stats
    count() as calls,
    avg(duration_ms) as avg_ms,
    sum(success = "true") as success_count,
    sum(success = "false") as failure_count
    by model_id
| sort calls desc
```

---

## 4. GCP Cloud Logging

### 4.1 相関IDフィルタ

```
-- 特定の相関IDでフィルタ（Cloud Logging フィルタ構文）
resource.type="cloud_run_revision"
    OR resource.type="cloud_run_revision"
jsonPayload.correlation_id="20260209_1707484800_0001"
```

```
-- 特定日のリクエスト（正規表現フィルタ）
resource.type="cloud_run_revision"
jsonPayload.correlation_id=~"^20260209_"
severity>=INFO
```

```sql
-- BigQueryエクスポート後: 相関IDの詳細追跡
SELECT
    timestamp,
    severity,
    JSON_VALUE(json_payload, '$.message') AS message,
    JSON_VALUE(json_payload, '$.correlation_id') AS correlation_id,
    JSON_VALUE(json_payload, '$.error_id') AS error_id,
    JSON_VALUE(json_payload, '$.error_code') AS error_code
FROM
    `project.dataset.cloud_run_logs`
WHERE
    JSON_VALUE(json_payload, '$.correlation_id') = '20260209_1707484800_0001'
ORDER BY
    timestamp ASC
```

### 4.2 Cloud Run実行分析

```
-- Cloud Run実行ログ
resource.type="cloud_run_revision"
resource.labels.service_name="ic-test-ai-analyze"
severity>=INFO
```

```sql
-- BigQuery: Cloud Run実行時間統計
SELECT
    DATE(timestamp) AS execution_date,
    APPROX_QUANTILES(
        CAST(JSON_VALUE(json_payload, '$.duration_ms') AS FLOAT64), 100
    )[OFFSET(50)] AS p50_ms,
    APPROX_QUANTILES(
        CAST(JSON_VALUE(json_payload, '$.duration_ms') AS FLOAT64), 100
    )[OFFSET(95)] AS p95_ms,
    APPROX_QUANTILES(
        CAST(JSON_VALUE(json_payload, '$.duration_ms') AS FLOAT64), 100
    )[OFFSET(99)] AS p99_ms,
    AVG(CAST(JSON_VALUE(json_payload, '$.duration_ms') AS FLOAT64)) AS avg_ms,
    COUNT(*) AS execution_count
FROM
    `project.dataset.cloud_run_logs`
WHERE
    DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    AND JSON_VALUE(json_payload, '$.duration_ms') IS NOT NULL
GROUP BY
    execution_date
ORDER BY
    execution_date DESC
```

```sql
-- BigQuery: Cloud Run Cold Start分析
SELECT
    EXTRACT(HOUR FROM timestamp) AS hour_of_day,
    COUNT(*) AS total_invocations,
    COUNTIF(
        JSON_VALUE(json_payload, '$.cold_start') = 'true'
    ) AS cold_starts,
    ROUND(
        100.0 * COUNTIF(JSON_VALUE(json_payload, '$.cold_start') = 'true')
        / COUNT(*), 2
    ) AS cold_start_rate_pct
FROM
    `project.dataset.cloud_run_logs`
WHERE
    DATE(timestamp) = CURRENT_DATE()
GROUP BY
    hour_of_day
ORDER BY
    hour_of_day
```

### 4.3 Vertex AI使用量

```
-- Vertex AI API呼び出しログ
resource.type="cloud_run_revision"
jsonPayload.event="dependency_call"
jsonPayload.dependency_type="Vertex AI"
```

```sql
-- BigQuery: Vertex AI呼び出し統計
SELECT
    DATE(timestamp) AS call_date,
    JSON_VALUE(json_payload, '$.target') AS model_endpoint,
    COUNT(*) AS total_calls,
    AVG(
        CAST(JSON_VALUE(json_payload, '$.duration_ms') AS FLOAT64)
    ) AS avg_duration_ms,
    APPROX_QUANTILES(
        CAST(JSON_VALUE(json_payload, '$.duration_ms') AS FLOAT64), 100
    )[OFFSET(95)] AS p95_duration_ms,
    COUNTIF(
        JSON_VALUE(json_payload, '$.success') = 'true'
    ) AS success_count,
    COUNTIF(
        JSON_VALUE(json_payload, '$.success') = 'false'
    ) AS failure_count,
    ROUND(
        100.0 * COUNTIF(JSON_VALUE(json_payload, '$.success') = 'true')
        / COUNT(*), 2
    ) AS success_rate_pct
FROM
    `project.dataset.cloud_run_logs`
WHERE
    DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    AND JSON_VALUE(json_payload, '$.event') = 'dependency_call'
    AND JSON_VALUE(json_payload, '$.dependency_type') = 'Vertex AI'
GROUP BY
    call_date, model_endpoint
ORDER BY
    call_date DESC, total_calls DESC
```

```sql
-- BigQuery: Vertex AI日次トークン推定使用量
SELECT
    DATE(timestamp) AS usage_date,
    JSON_VALUE(json_payload, '$.target') AS model,
    SUM(
        CAST(JSON_VALUE(json_payload, '$.metric_value') AS FLOAT64)
    ) AS estimated_tokens,
    COUNT(*) AS api_calls
FROM
    `project.dataset.cloud_run_logs`
WHERE
    DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND JSON_VALUE(json_payload, '$.metric_name') = 'llm_api_calls_total'
GROUP BY
    usage_date, model
ORDER BY
    usage_date DESC
```

### 4.4 エラーサマリー

```
-- エラーログフィルタ
resource.type="cloud_run_revision"
severity=ERROR
```

```sql
-- BigQuery: エラーコード別集計
SELECT
    JSON_VALUE(json_payload, '$.error_code') AS error_code,
    COUNT(*) AS error_count,
    COUNT(DISTINCT JSON_VALUE(json_payload, '$.correlation_id')) AS affected_requests,
    MIN(timestamp) AS first_occurrence,
    MAX(timestamp) AS last_occurrence,
    ANY_VALUE(JSON_VALUE(json_payload, '$.message')) AS sample_message
FROM
    `project.dataset.cloud_run_logs`
WHERE
    DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    AND severity = 'ERROR'
    AND JSON_VALUE(json_payload, '$.error_code') IS NOT NULL
GROUP BY
    error_code
ORDER BY
    error_count DESC
```

```sql
-- BigQuery: 時間帯別エラー率
SELECT
    TIMESTAMP_TRUNC(timestamp, HOUR) AS hour_bucket,
    COUNT(*) AS total_logs,
    COUNTIF(severity = 'ERROR') AS error_count,
    ROUND(
        100.0 * COUNTIF(severity = 'ERROR') / COUNT(*), 2
    ) AS error_rate_pct
FROM
    `project.dataset.cloud_run_logs`
WHERE
    DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
GROUP BY
    hour_bucket
ORDER BY
    hour_bucket DESC
```

---

## 5. ダッシュボード設定例

### 5.1 Azure - Application Insights ダッシュボード

推奨ウィジェット構成:

```
+--------------------------------------------------+
| [タイル1] リクエスト概要                              |
| 直近24時間の合計リクエスト数 / 成功率                    |
+--------------------------------------------------+
| [タイル2] エラー率推移        | [タイル3] P95レイテンシ  |
| 1時間ごとの折れ線グラフ       | 1時間ごとの折れ線グラフ    |
+---------------------------+----------------------+
| [タイル4] エラーコード別      | [タイル5] LLM API      |
| 円グラフ                    | 呼び出し回数/処理時間     |
+---------------------------+----------------------+
| [タイル6] 処理時間内訳                                |
| OCR / LLM / 全体 の積み上げ棒グラフ                    |
+--------------------------------------------------+
```

**タイル1: リクエスト概要（KPI）**
```kusto
customMetrics
| where name == "document_processing_total"
| where timestamp > ago(24h)
| summarize total = sum(value)
```

**タイル2: エラー率推移（折れ線グラフ）**
```kusto
traces
| where timestamp > ago(24h)
| summarize error_rate = round(100.0 * countif(severityLevel >= 3) / count(), 2)
    by bin(timestamp, 1h)
| render timechart
```

**タイル3: P95レイテンシ推移（折れ線グラフ）**
```kusto
customMetrics
| where name == "request_duration_ms"
| where timestamp > ago(24h)
| summarize p95 = percentile(value, 95)
    by bin(timestamp, 1h)
| render timechart
```

### 5.2 AWS - CloudWatch ダッシュボード

推奨ウィジェット構成 (JSON定義):

```json
{
    "widgets": [
        {
            "type": "metric",
            "properties": {
                "title": "App Runnerリクエスト数",
                "metrics": [
                    ["AWS/AppRunner", "RequestCount",
                     "ServiceName", "ic-test-ai-analyze"]
                ],
                "period": 3600,
                "stat": "Sum"
            }
        },
        {
            "type": "metric",
            "properties": {
                "title": "App Runner処理時間 (P50/P95/P99)",
                "metrics": [
                    ["AWS/AppRunner", "RequestLatency",
                     "ServiceName", "ic-test-ai-analyze",
                     {"stat": "p50", "label": "P50"}],
                    ["...", {"stat": "p95", "label": "P95"}],
                    ["...", {"stat": "p99", "label": "P99"}]
                ],
                "period": 3600
            }
        },
        {
            "type": "metric",
            "properties": {
                "title": "App Runnerエラー数",
                "metrics": [
                    ["AWS/AppRunner", "4xxStatusResponses",
                     "ServiceName", "ic-test-ai-analyze"]
                ],
                "period": 3600,
                "stat": "Sum"
            }
        },
        {
            "type": "log",
            "properties": {
                "title": "直近エラーログ",
                "query": "fields @timestamp, error_code, correlation_id, @message\n| filter ispresent(error_code)\n| sort @timestamp desc\n| limit 10",
                "region": "ap-northeast-1",
                "stacked": false
            }
        }
    ]
}
```

### 5.3 GCP - Cloud Monitoring ダッシュボード

推奨ウィジェット構成:

| ウィジェット | タイプ | データソース |
|------------|--------|------------|
| Cloud Run実行回数 | 折れ線グラフ | `run.googleapis.com/request_count` |
| 実行時間（P50/P95） | 折れ線グラフ | `run.googleapis.com/request_latencies` |
| エラー数 | 棒グラフ | Log-based Metric: `error_code` カウント |
| メモリ使用量 | 折れ線グラフ | `run.googleapis.com/container/memory/utilizations` |
| Vertex AI呼び出し回数 | 数値 | Log-based Metric: `vertex_ai_calls` |
| 直近エラーログ | テーブル | Cloud Logging: `severity=ERROR` |

**Log-based Metric作成例（Terraformコード）**:

```hcl
resource "google_logging_metric" "error_code_count" {
  name        = "ic-test-ai/error_code_count"
  description = "エラーコード別のエラー発生数"
  filter      = <<-EOT
    resource.type = "cloud_run_revision"
    severity = ERROR
    jsonPayload.error_code != ""
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "error_code"
      value_type  = "STRING"
      description = "エラーコード"
    }
  }

  label_extractors = {
    "error_code" = "EXTRACT(jsonPayload.error_code)"
  }
}
```

---

## 6. アラートルール設定

### 6.1 エラー率アラート（> 5%）

#### Azure Application Insights

```kusto
// アラートクエリ（5分間隔で評価）
traces
| where timestamp > ago(5m)
| summarize
    total = count(),
    errors = countif(severityLevel >= 3)
| extend error_rate = 100.0 * errors / total
| where error_rate > 5
| where total > 10  // 最低サンプル数を保証
```

**Azure Monitorアラートルール設定**:

| 項目 | 設定値 |
|------|--------|
| シグナルの種類 | カスタムログ検索 |
| 評価頻度 | 5分 |
| 集計期間 | 5分 |
| しきい値 | 結果件数 > 0 |
| アクショングループ | 運用チーム通知（メール + Teams） |
| 重大度 | Sev 2 (Warning) |

#### AWS CloudWatch

```json
{
    "MetricName": "ErrorRate",
    "Namespace": "ICTestAI",
    "ComparisonOperator": "GreaterThanThreshold",
    "Threshold": 5,
    "EvaluationPeriods": 3,
    "Period": 300,
    "Statistic": "Average",
    "TreatMissingData": "notBreaching",
    "AlarmActions": [
        "arn:aws:sns:ap-northeast-1:ACCOUNT_ID:ic-test-ai-alerts"
    ]
}
```

#### GCP Cloud Monitoring

```yaml
# アラートポリシー（YAML形式）
displayName: "IC Test AI - エラー率 > 5%"
conditions:
  - displayName: "エラー率しきい値超過"
    conditionThreshold:
      filter: >
        resource.type = "cloud_run_revision"
        AND metric.type = "logging.googleapis.com/user/ic-test-ai/error_code_count"
      comparison: COMPARISON_GT
      thresholdValue: 5
      duration: 300s
      aggregations:
        - alignmentPeriod: 300s
          perSeriesAligner: ALIGN_RATE
notificationChannels:
  - "projects/PROJECT_ID/notificationChannels/CHANNEL_ID"  # pragma: allowlist secret
alertStrategy:
  autoClose: 1800s
```

### 6.2 レイテンシアラート（P95 > 10秒）

#### Azure Application Insights

```kusto
// P95レイテンシ監視（5分間隔）
customMetrics
| where name == "request_duration_ms"
| where timestamp > ago(5m)
| summarize p95 = percentile(value, 95)
| where p95 > 10000
```

**アラートルール設定**:

| 項目 | 設定値 |
|------|--------|
| 評価頻度 | 5分 |
| 集計期間 | 5分 |
| しきい値 | P95 > 10000ms |
| 重大度 | Sev 2 (Warning) |

#### AWS CloudWatch

```json
{
    "MetricName": "RequestLatency",
    "Namespace": "AWS/AppRunner",
    "Dimensions": [
        {"Name": "ServiceName", "Value": "ic-test-ai-analyze"}
    ],
    "ComparisonOperator": "GreaterThanThreshold",
    "Threshold": 10000,
    "EvaluationPeriods": 3,
    "Period": 300,
    "ExtendedStatistic": "p95",
    "TreatMissingData": "notBreaching",
    "AlarmActions": [
        "arn:aws:sns:ap-northeast-1:ACCOUNT_ID:ic-test-ai-alerts"
    ]
}
```

### 6.3 LLM APIエラーアラート（> 10%）

#### Azure Application Insights

```kusto
// LLM APIエラー率監視（15分間隔）
customMetrics
| where timestamp > ago(15m)
| where name == "llm_api_calls_total"
| summarize
    total = sum(value),
    failures = sumif(value, customDimensions.success == "False")
| extend failure_rate = 100.0 * failures / total
| where failure_rate > 10
| where total > 5  // 最低サンプル数
```

**アラートルール設定**:

| 項目 | 設定値 |
|------|--------|
| 評価頻度 | 15分 |
| 集計期間 | 15分 |
| しきい値 | エラー率 > 10% |
| 重大度 | Sev 1 (Error) |
| 自動解決 | 30分後に自動クローズ |

#### AWS CloudWatch

```
# CloudWatch Insights メトリクスフィルタ
fields @timestamp, @message
| filter @message like /LLM_API_ERROR/
| stats count() as error_count by bin(@timestamp, 15m)
```

#### GCP Cloud Monitoring

```yaml
displayName: "IC Test AI - LLM APIエラー率 > 10%"
conditions:
  - displayName: "LLM APIエラー率"
    conditionThreshold:
      filter: >
        resource.type = "cloud_run_revision"
        AND metric.type = "logging.googleapis.com/user/ic-test-ai/error_code_count"
        AND metric.labels.error_code = "LLM_API_ERROR"
      comparison: COMPARISON_GT
      thresholdValue: 10
      duration: 900s
      aggregations:
        - alignmentPeriod: 900s
          perSeriesAligner: ALIGN_RATE
```

### アラート重大度ガイドライン

| 重大度 | 条件 | 通知先 | 対応時間 |
|--------|------|--------|---------|
| **Sev 0 (Critical)** | サービス完全停止 | 全チーム（電話 + メール） | 即時 |
| **Sev 1 (Error)** | LLM APIエラー率 > 10% | 運用チーム（メール + チャット） | 30分以内 |
| **Sev 2 (Warning)** | エラー率 > 5%、P95 > 10秒 | 運用チーム（メール） | 4時間以内 |
| **Sev 3 (Info)** | エラー率 > 2%、異常なパターン | ダッシュボード表示のみ | 翌営業日 |
