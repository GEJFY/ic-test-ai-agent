# クライアントセットアップガイド（VBA / PowerShell）

> **対象システム**: 内部統制テストAIエージェント (ic-test-ai-agent)
> **最終更新**: 2026-02-11
> **対象読者**: Excel VBA / PowerShell を使って本システムを利用するユーザー（初心者歓迎）

---

## 目次

1. [はじめに](#1-はじめに)
2. [Excel VBA クライアント（超詳細版）](#2-excel-vba-クライアント超詳細版)
3. [PowerShell クライアント（超詳細版）](#3-powershell-クライアント超詳細版)
4. [相関ID活用ガイド](#4-相関id活用ガイド)
5. [セキュリティ注意事項](#5-セキュリティ注意事項)
6. [まとめ・参考資料](#6-まとめ参考資料)

---

## 1. はじめに

### 1.1 このドキュメントの概要

このドキュメントでは、内部統制テストAIエージェントに **Excel VBA** または **PowerShell** から
アクセスするための設定手順を、初心者の方にもわかるよう詳しく説明します。

本システムは、Excelに入力された内部統制テスト項目をクラウドAI（Azure / AWS / GCP）に送信し、
自動評価の結果を受け取る仕組みです。ユーザーは普段使い慣れたExcelやPowerShellから操作できます。

### 1.2 対象者

- 内部統制テストの担当者（ITに詳しくなくてもOK）
- Excel VBAやPowerShellを初めて使う方
- 既存のExcelテンプレートにデータを入力して評価を実行したい方

### 1.3 前提条件

| 項目 | 必要なもの |
|------|-----------|
| OS | Windows 10 / 11 |
| Excel | Microsoft Excel 2016 以降（マクロ対応版） |
| PowerShell | PowerShell 5.1 以降（Windows に標準搭載） |
| ネットワーク | インターネット接続（クラウドAPIへのアクセス） |
| API Key | 管理者から提供される各プラットフォームのAPIキー |

> **補足**: 前提条件の詳しいインストール手順は [PREREQUISITES.md](./PREREQUISITES.md) を参照してください。

---

## 2. Excel VBA クライアント（超詳細版）

### 2.1 Excel VBA とは（初心者向け概要）

**VBA（Visual Basic for Applications）** とは、Microsoft Office に組み込まれた
プログラミング言語です。Excelの操作を自動化する「マクロ」を作るために使います。

本システムでは、VBAを使って以下のことを自動で行います：

1. Excelに入力されたテスト項目データを **JSON形式**（コンピューターが読みやすい形式）に変換
2. 変換したデータをクラウドの **AI評価API** に送信
3. AIが返してきた評価結果をExcelに書き戻す

つまり、ユーザーは **Excelにデータを入力してボタンを押すだけ** で、AIによる内部統制の評価結果を
得られるということです。

> **用語解説**:
> - **マクロ**: Excelの操作を自動化するプログラムのこと
> - **JSON**: データをやり取りするための標準的なテキスト形式（JavaScriptで使われる記法）
> - **API**: アプリケーション同士がデータをやり取りする仕組み（Application Programming Interface）

### 2.2 マクロのセキュリティ設定

Excelは初期状態ではマクロの実行がブロックされています。
本システムのVBAマクロを使うために、セキュリティ設定を変更する必要があります。

#### 手順: マクロを有効にする

1. **Excelを開く**
   - 普段通りExcelを起動します（どのファイルでも構いません）

2. **ファイル タブをクリック**
   - 画面左上の「ファイル」をクリックします

3. **オプション を開く**
   - 左側メニューの一番下にある「オプション」をクリックします
   - 「Excelのオプション」ウィンドウが表示されます

4. **トラストセンター を開く**
   - 左側メニューから「トラストセンター」をクリックします
   - 右側に表示される「トラストセンターの設定」ボタンをクリックします

5. **マクロの設定を変更する**
   - 左側メニューから「マクロの設定」をクリックします
   - 以下のいずれかを選択します：
     - **「警告を表示してすべてのマクロを無効にする」（推奨）**
       - マクロ実行時に確認ダイアログが表示されます
       - セキュリティと利便性のバランスが最も良い設定です
     - 「すべてのマクロを有効にする」
       - 確認なしでマクロが実行されます（セキュリティリスクあり）
   - 「OK」をクリックして設定を保存します

6. **Excelを再起動する**
   - 設定を反映するため、一度Excelを閉じてから再度開いてください

> **注意**: 「すべてのマクロを有効にする」は便利ですが、悪意のあるマクロも実行されてしまう
> リスクがあります。特に社外からもらったExcelファイルを開くことがある場合は、
> 「警告を表示してすべてのマクロを無効にする」を選ぶことを強く推奨します。

### 2.3 VBAエディタの開き方

VBAエディタとは、VBAコードを書いたり編集したりするための画面です。
ExcelToJson.basファイルをインポートするために使います。

#### VBAエディタを開く方法

**方法1: キーボードショートカット（推奨）**

```
Alt + F11
```

Excelを開いた状態で、キーボードの `Alt` キーを押しながら `F11` キーを押します。

**方法2: メニューから開く**

1. 「開発」タブをクリックします
2. 「Visual Basic」ボタンをクリックします

> **「開発」タブが表示されていない場合**:
> 1. 「ファイル」→「オプション」→「リボンのユーザー設定」を開く
> 2. 右側の「メインタブ」一覧で「開発」にチェックを入れる
> 3. 「OK」をクリックする

#### VBAエディタの画面構成

VBAエディタには主に3つのペイン（区画）があります：

```
+-------------------------------------------+
| メニューバー / ツールバー                    |
+----------------+--------------------------+
| プロジェクト   |                           |
| エクスプローラー |    コードウィンドウ        |
|（左上）        |   （右側の広いエリア）      |
|                |                           |
+----------------+                           |
| プロパティ     |  ← ここにVBAコードが       |
| ウィンドウ     |     表示されます            |
|（左下）        |                           |
+----------------+--------------------------+
```

- **プロジェクトエクスプローラー**: ブック内のモジュール一覧が表示される場所
- **コードウィンドウ**: VBAコードを編集する場所
- **プロパティウィンドウ**: 選択した項目のプロパティ（設定値）を表示・編集する場所

> プロジェクトエクスプローラーが表示されていない場合は、メニューの
> 「表示」→「プロジェクトエクスプローラー」をクリックしてください。

### 2.4 ExcelToJson.bas のインポート手順

#### ファイルの場所

本システムのVBAモジュールファイルは以下の場所にあります：

```
scripts/excel/ExcelToJson.bas
```

プロジェクトのルートディレクトリからの相対パスです。
例えば、プロジェクトが `C:\Projects\ic-test-ai-agent\` にある場合：

```
C:\Projects\ic-test-ai-agent\scripts\excel\ExcelToJson.bas
```

#### インポート手順

1. **VBAエディタを開く**
   - `Alt + F11` でVBAエディタを開きます

2. **「ファイル」メニューを開く**
   - VBAエディタのメニューバーから「ファイル（File）」をクリックします

3. **「ファイルのインポート」を選択**
   - 「ファイルのインポート（Import File...）」をクリックします
   - ファイル選択ダイアログが表示されます

4. **ExcelToJson.bas を選択**
   - 先ほど確認したファイルパスに移動します
   - `ExcelToJson.bas` を選択して「開く」をクリックします

5. **インポート完了の確認**
   - プロジェクトエクスプローラーの「標準モジュール」フォルダ内に
     `ExcelToJson` というモジュールが追加されていれば成功です

```
VBAProject (ブック名.xlsm)
  ├── Microsoft Excel Objects
  │   ├── Sheet1 (Sheet1)
  │   └── ThisWorkbook
  └── 標準モジュール
      └── ExcelToJson    ← これが追加されていればOK
```

> **注意**: ファイルを `.xlsm`（マクロ有効ブック）として保存してください。
> `.xlsx` 形式ではマクロが保存されません。保存時に「マクロを含むブックは
> マクロ有効ブック形式で保存してください」という警告が出た場合は、
> 「はい」を選んで `.xlsm` で保存してください。

### 2.5 setting.json（設定ファイル）の準備

ExcelToJson.bas は `setting.json` という設定ファイルからAPI接続情報や列マッピングを読み込みます。
この設定ファイルは Excelファイルと同じフォルダに配置する必要があります。

#### setting.json のサンプル（Azure環境の場合）

```json
{
  "dataStartRow": 2,
  "sheetName": "",
  "batchSize": 5,
  "asyncMode": false,
  "pollingIntervalSec": 5,

  "inputColumns": {
    "id": "A",
    "testTarget": "B",
    "category": "C",
    "controlDescription": "D",
    "testProcedure": "E",
    "evidenceLink": "F"
  },

  "api": {
    "provider": "AZURE",
    "endpoint": "https://<APIM_NAME>.azure-api.net/api/evaluate",
    "key": "<YOUR_APIM_SUBSCRIPTION_KEY>",
    "authHeader": "Ocp-Apim-Subscription-Key",
    "client": "POWERSHELL",
    "authType": "functionsKey"
  },

  "outputColumns": {
    "evaluationResult": "G",
    "executionPlanSummary": "H",
    "judgmentBasis": "I",
    "documentReference": "J",
    "fileName": "K"
  },

  "booleanDisplay": {
    "true": "有効",
    "false": "不備"
  }
}
```

#### 各プラットフォーム別のAPI設定

**Azure 環境**:
```json
{
  "api": {
    "provider": "AZURE",
    "endpoint": "https://<APIM_NAME>.azure-api.net/api/evaluate",
    "key": "<YOUR_APIM_SUBSCRIPTION_KEY>",
    "authHeader": "Ocp-Apim-Subscription-Key",
    "client": "POWERSHELL",
    "authType": "functionsKey"
  }
}
```

- `<APIM_NAME>`: Azure API Management のリソース名（管理者に確認してください）
- `<YOUR_APIM_SUBSCRIPTION_KEY>`: サブスクリプションキー（Azure Portalで取得）

**AWS 環境**:
```json
{
  "api": {
    "provider": "AWS",
    "endpoint": "https://<API_ID>.execute-api.ap-northeast-1.amazonaws.com/prod/evaluate",
    "key": "<YOUR_AWS_API_KEY>",
    "authHeader": "X-Api-Key",
    "client": "POWERSHELL",
    "authType": "functionsKey"
  }
}
```

- `<API_ID>`: API Gateway のID（管理者に確認してください）
- `<YOUR_AWS_API_KEY>`: API Gateway のAPIキー（AWS Consoleで取得）

**GCP 環境**:
```json
{
  "api": {
    "provider": "GCP",
    "endpoint": "https://<APIGEE_ENDPOINT>/evaluate",
    "key": "<YOUR_GCP_API_KEY>",
    "authHeader": "X-Api-Key",
    "client": "POWERSHELL",
    "authType": "functionsKey"
  }
}
```

- `<APIGEE_ENDPOINT>`: Apigee のエンドポイント（管理者に確認してください）
- `<YOUR_GCP_API_KEY>`: GCP のAPIキー（GCP Consoleで取得）

> **APIキーの取得場所がわからない場合**:
> システム管理者に問い合わせてください。APIキーは機密情報です。
> メールやチャットでの平文送信は避け、安全な方法で受け取ってください。

### 2.6 Excel テンプレートの準備

#### 列の構成（A列〜G列）

本システムで使用するExcelのデータ形式は以下の通りです。
1行目はヘッダー行で、2行目以降に実際のデータを入力します。

| 列 | ヘッダー名 | 説明 | 入力例 |
|----|-----------|------|--------|
| A | ID | 項目の識別番号。一意の番号をつけてください | `001` |
| B | テスト対象 | この行を処理対象にするか（TRUE/FALSE） | `TRUE` |
| C | カテゴリ | 統制の分類名 | `統制環境` |
| D | 統制記述 | 統制の内容を記述 | `経営者の誠実性と倫理観` |
| E | テスト手続き | 評価の方法を記述 | `行動規範の文書確認、全社員へのアンケート実施` |
| F | 証憑リンク | エビデンスファイルが格納されたフォルダパス | `C:\Evidence\001\` |
| G | ステータス | 現在の処理状態（自動更新） | `実施中` |

> **補足**: 列の位置は `setting.json` で変更できます。上記はデフォルト設定の場合です。

#### サンプルデータ

```
| A   | B    | C          | D                        | E                              | F                    | G      |
|-----|------|------------|--------------------------|--------------------------------|----------------------|--------|
| ID  |対象  | カテゴリ    | 統制記述                  | テスト手続き                    | 証憑リンク            | ステータス |
| 001 | TRUE | 統制環境   | 経営者の誠実性と倫理観     | 行動規範の文書確認              | C:\Evidence\001\     | 実施中  |
| 002 | TRUE | リスク評価 | 不正リスクの評価           | リスク評価書のレビュー           | C:\Evidence\002\     | 実施中  |
| 003 | FALSE| 統制活動   | 職務分掌                  | 権限一覧表の確認               | C:\Evidence\003\     | 未着手  |
```

- B列が `TRUE` の行のみ処理対象になります
- B列が `FALSE` または空白の行はスキップされます
- F列のフォルダにPDF、画像、Word等のエビデンスファイルを格納しておくと、APIに送信されます

### 2.7 マクロ実行手順

#### 手順1: Excelファイルを準備する

1. テスト項目データを入力したExcelファイル（`.xlsm`）を開きます
2. `setting.json` が同じフォルダにあることを確認します
3. `scripts/powershell/CallCloudApi.ps1`（または `CallCloudApiAsync.ps1`）が
   利用可能な場所にあることを確認します

#### 手順2: マクロを実行する

**方法1: マクロダイアログから実行（推奨）**

1. `Alt + F8` を押してマクロ一覧ダイアログを表示します
2. `ProcessWithApi` を選択します
3. 「実行」ボタンをクリックします

**方法2: VBAエディタから実行**

1. `Alt + F11` でVBAエディタを開きます
2. `ProcessWithApi` プロシージャ内にカーソルを置きます
3. `F5` キーを押して実行します

#### 手順3: 処理の進行を確認する

- 処理中はExcelのステータスバー（画面最下部）に進捗が表示されます
- バッチ処理の場合は「バッチ 1/3 処理中...」のように進捗が表示されます
- 完了すると確認ダイアログが表示されます

> **処理時間の目安**:
> - 1項目: 約10〜30秒（AIモデルやネットワーク速度による）
> - 10項目（バッチサイズ5）: 約1〜3分
> - 非同期モード（asyncMode: true）の場合: 項目数に関わらず送信は数秒で完了し、
>   バックグラウンドで処理が進みます

### 2.8 結果の見方

マクロ実行後、setting.json で指定した出力列に以下の結果が書き込まれます。

| 出力列 | 内容 | 説明 |
|--------|------|------|
| G列（デフォルト） | 評価結果 | 「有効」または「不備」（setting.json の booleanDisplay で変更可） |
| H列（デフォルト） | 実行計画サマリー | AIが作成したテスト計画の要約 |
| I列（デフォルト） | 判断根拠 | AIがその判断に至った理由の詳細説明 |
| J列（デフォルト） | 文書参照 | 参照したエビデンス文書の情報 |
| K列（デフォルト） | ファイル名 | 処理されたエビデンスファイル名 |

> **注意**: 出力列は `setting.json` の `outputColumns` で変更可能です。
> 入力データの列と重ならないように設定してください。

### 2.9 よくあるエラーと対策

#### エラー1: 「型が一致しません」（Type Mismatch）

**症状**: マクロ実行中に「実行時エラー '13': 型が一致しません」と表示される

**原因**: APIから返されたJSONデータの形式が想定と異なる場合に発生します。
ネットワークエラー等でHTMLのエラーページが返された場合にも発生します。

**対策**:
1. VBAエディタの「イミディエイトウィンドウ」（`Ctrl + G`で表示）で
   レスポンスの内容を確認してください
2. APIエンドポイントのURLが正しいか確認してください
3. APIキーが正しいか確認してください

```vba
' デバッグ用にレスポンスの内容を確認する方法:
' VBAエディタの「イミディエイトウィンドウ」（Ctrl+G）に出力される
Debug.Print httpReq.responseText
```

#### エラー2: 「接続できません」（Connection Error）

**症状**: 「実行時エラー '-2147012867': サーバーに接続できませんでした」等のエラー

**原因**: 以下のいずれかが考えられます
- インターネットに接続されていない
- プロキシサーバーの設定が必要
- ファイアウォールにブロックされている
- SSL証明書のエラー

**対策**:

```vba
' プロキシサーバーを使用する場合の設定:
httpReq.setProxy 2, "proxy.example.com:8080"

' 証明書検証を無効化する場合（開発環境のみ！本番では使わないこと）:
httpReq.setOption 2, 13056  ' SXH_SERVER_CERT_IGNORE_ALL_SERVER_ERRORS
```

> **プロキシサーバーのアドレスがわからない場合**:
> 社内のIT部門に問い合わせてください。ブラウザの設定（インターネットオプション →
> 接続 → LANの設定）からも確認できます。

#### エラー3: タイムアウト

**症状**: 長時間待った後に「タイムアウト」エラーが表示される

**原因**: 処理対象のデータ量が多い、またはネットワークが遅い場合に発生します。

**対策**:
1. `setting.json` の `batchSize` を小さくしてください（例: 5 → 2）
2. `setting.json` の `asyncMode` を `true` に変更してください
   - 非同期モードでは、ジョブを送信後にポーリングで結果を取得するため、
     504 Gateway Timeout が発生しにくくなります

```json
{
  "batchSize": 2,
  "asyncMode": true,
  "pollingIntervalSec": 5
}
```

#### エラー4: 「設定ファイルが見つかりません」

**症状**: 「setting.jsonが見つかりません」というエラーメッセージ

**原因**: `setting.json` がExcelファイルと同じフォルダにない

**対策**:
1. Excelファイル（`.xlsm`）が保存されていることを確認してください
   - 「新規作成」で開いたまま保存していない場合、パスが確定していません
2. `setting.json` をExcelファイルと同じフォルダにコピーしてください

#### エラー5: PowerShellスクリプトが見つからない

**症状**: 「CallCloudApi.ps1が見つかりません」というエラーメッセージ

**原因**: `setting.json` の `client` が `POWERSHELL` に設定されているが、
PowerShellスクリプトが見つからない場合に発生します。

**対策**:
- `scripts/powershell/CallCloudApi.ps1` がプロジェクト内に存在することを確認してください
- `setting.json` でスクリプトのパスを正しく設定してください

### 2.10 デバッグ方法

VBAマクロがうまく動かない場合のデバッグ手法を紹介します。

#### Debug.Print でデータを確認する

`Debug.Print` は、VBAエディタの「イミディエイトウィンドウ」にデータを出力する命令です。

1. VBAエディタで `Ctrl + G` を押して「イミディエイトウィンドウ」を表示します
2. コード内の確認したい箇所に `Debug.Print` を追加します

```vba
' 例: 送信するJSONデータの内容を確認
Debug.Print "JSON内容: " & jsonText
Debug.Print "送信先URL: " & config.ApiEndpoint
Debug.Print "行数: " & rowCount
```

#### ブレークポイントで処理を一時停止する

ブレークポイントとは、処理を一時停止させるポイントのことです。
停止した状態で変数の値を確認できます。

1. VBAエディタのコードウィンドウで、停止したい行の左端（グレーの領域）をクリックします
2. その行が赤くハイライトされればブレークポイントが設定されています
3. マクロを実行すると、ブレークポイントの位置で停止します
4. 停止中に変数にマウスカーソルを合わせると、現在の値がツールチップで表示されます
5. `F8` キーで1行ずつ実行を進められます（ステップ実行）
6. `F5` キーで通常実行を再開します

#### ログファイルの確認

ExcelToJson.bas は自動的にログを `%TEMP%\ExcelToJson_Log.txt` に出力します。

ログファイルの場所を確認する方法:
1. Windowsキー + R を押して「ファイル名を指定して実行」を開く
2. `%TEMP%` と入力して「OK」をクリック
3. 開いたフォルダ内で `ExcelToJson_Log.txt` を探す

ログには処理の各ステップの情報やエラーの詳細が記録されています。
問題解決の大きな手がかりになります。

---

## 3. PowerShell クライアント（超詳細版）

### 3.1 PowerShell とは（初心者向け概要）

**PowerShell** は、Windows に標準搭載されているコマンドライン操作ツールです。
テキストでコマンド（命令）を入力して、コンピューターを操作します。

本システムでは、PowerShellスクリプトを使って以下のことを行います：

1. JSONファイルに書かれたテスト項目データを読み込む
2. データをクラウドAIのAPIに送信する
3. AIの評価結果をJSONファイルに保存する

ExcelのVBAマクロも内部的にPowerShellスクリプトを呼び出しています。
PowerShellスクリプトを直接使う場面は、以下のようなケースです：

- Excel以外のデータソース（データベース等）から直接処理したい場合
- バッチ処理（定期実行）で自動化したい場合
- 大量データを効率的に処理したい場合

#### PowerShellを開く方法

1. **スタートメニューから**:
   - スタートメニューで「PowerShell」と検索
   - 「Windows PowerShell」をクリック

2. **エクスプローラーから**:
   - 任意のフォルダを開く
   - アドレスバーに `powershell` と入力してEnter

3. **右クリックメニューから**（Windows 11）:
   - フォルダ内で右クリック
   - 「ターミナルで開く」を選択

### 3.2 PowerShell 実行ポリシー設定

PowerShellはセキュリティのため、初期状態ではスクリプト（`.ps1`ファイル）の実行が
制限されています。本システムのスクリプトを実行するには、実行ポリシーを変更する必要があります。

#### 現在の実行ポリシーを確認する

```powershell
Get-ExecutionPolicy
```

`Restricted` と表示された場合、スクリプトは実行できません。

#### 実行ポリシーを変更する

**PowerShellを管理者として開いて**、以下のコマンドを実行します：

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

確認メッセージが表示されたら `Y` を入力して Enter を押します。

> **各ポリシーの意味**:
> | ポリシー | 説明 |
> |---------|------|
> | Restricted | スクリプトの実行を全面禁止（初期値） |
> | RemoteSigned | ローカルスクリプトは実行可、ダウンロードしたスクリプトは署名が必要（推奨） |
> | Unrestricted | すべてのスクリプトを実行可（セキュリティリスクあり） |

### 3.3 スクリプトの場所

PowerShellスクリプトは以下の場所にあります：

```
scripts/powershell/CallCloudApi.ps1       ← 同期処理用
scripts/powershell/CallCloudApiAsync.ps1  ← 非同期処理用
```

プロジェクトのルートディレクトリからの相対パスです。

### 3.4 同期処理（CallCloudApi.ps1）の使い方

同期処理では、APIにリクエストを送信し、レスポンスが返ってくるまで待機します。
少量のデータ（1〜10項目程度）を処理する場合に適しています。

#### 基本的な使い方

```powershell
.\scripts\powershell\CallCloudApi.ps1 `
    -JsonFilePath ".\input.json" `
    -Endpoint "https://<APIM_NAME>.azure-api.net/api/evaluate" `
    -ApiKey "<YOUR_API_KEY>" `
    -OutputFilePath ".\output.json" `
    -Provider "AZURE"
```

#### 全パラメータの説明

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| `-JsonFilePath` | はい | 入力JSONファイルのパス | `.\input.json` |
| `-Endpoint` | はい | APIエンドポイントのURL | `https://xxx.azure-api.net/api/evaluate` |
| `-ApiKey` | いいえ | APIキー | `abc123...` |
| `-OutputFilePath` | はい | 結果を保存するJSONファイルのパス | `.\output.json` |
| `-Provider` | はい | クラウドプロバイダー名 | `AZURE` / `AWS` / `GCP` |
| `-AuthHeader` | いいえ | 認証ヘッダー名（カスタム） | `Ocp-Apim-Subscription-Key` |
| `-TimeoutSec` | いいえ | タイムアウト秒数（デフォルト: 600） | `300` |
| `-AuthType` | いいえ | 認証方式（デフォルト: functionsKey） | `functionsKey` / `azureAd` |
| `-TenantId` | いいえ | Azure ADテナントID（AuthType=azureAd時） | `xxxxxxxx-xxxx-...` |
| `-ClientId` | いいえ | Azure ADクライアントID（AuthType=azureAd時） | `xxxxxxxx-xxxx-...` |
| `-Scope` | いいえ | Azure ADスコープ（AuthType=azureAd時） | `api://xxx/.default` |

#### プラットフォーム別の実行例

**Azure（APIM経由）**:
```powershell
.\scripts\powershell\CallCloudApi.ps1 `
    -JsonFilePath ".\input.json" `
    -Endpoint "https://myapim.azure-api.net/api/evaluate" `
    -ApiKey "your-subscription-key" `
    -OutputFilePath ".\output.json" `
    -Provider "AZURE" `
    -AuthHeader "Ocp-Apim-Subscription-Key"
```

**AWS（API Gateway経由）**:
```powershell
.\scripts\powershell\CallCloudApi.ps1 `
    -JsonFilePath ".\input.json" `
    -Endpoint "https://abc123.execute-api.ap-northeast-1.amazonaws.com/prod/evaluate" `
    -ApiKey "your-aws-api-key" `
    -OutputFilePath ".\output.json" `
    -Provider "AWS" `
    -AuthHeader "X-Api-Key"
```

**GCP（Apigee経由）**:
```powershell
.\scripts\powershell\CallCloudApi.ps1 `
    -JsonFilePath ".\input.json" `
    -Endpoint "https://your-apigee-endpoint/evaluate" `
    -ApiKey "your-gcp-api-key" `
    -OutputFilePath ".\output.json" `
    -Provider "GCP" `
    -AuthHeader "X-Api-Key"
```

**Azure AD認証を使用する場合**:
```powershell
.\scripts\powershell\CallCloudApi.ps1 `
    -JsonFilePath ".\input.json" `
    -Endpoint "https://myapim.azure-api.net/api/evaluate" `
    -OutputFilePath ".\output.json" `
    -Provider "AZURE" `
    -AuthType "azureAd" `
    -TenantId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" `
    -ClientId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" `
    -Scope "api://xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/.default"
```

### 3.5 非同期処理（CallCloudApiAsync.ps1）の使い方

非同期処理では、以下の3段階でAPIとやり取りします：

1. **ジョブ送信**: `POST /api/evaluate/submit` でデータを送信し、ジョブIDを受け取る
2. **ステータス確認**: `GET /api/evaluate/status/{job_id}` で処理状況をポーリング
3. **結果取得**: `GET /api/evaluate/results/{job_id}` で完了後に結果を取得

大量のデータを処理する場合や、API Gateway の 504 タイムアウトを回避したい場合に適しています。

#### 基本的な使い方

```powershell
.\scripts\powershell\CallCloudApiAsync.ps1 `
    -JsonFilePath ".\input.json" `
    -Endpoint "https://<APIM_NAME>.azure-api.net/api/evaluate" `
    -ApiKey "<YOUR_API_KEY>" `
    -OutputFilePath ".\output.json" `
    -Provider "AZURE"
```

#### 追加パラメータ

同期版のパラメータに加えて、以下が利用できます：

| パラメータ | 必須 | 説明 | デフォルト |
|-----------|------|------|-----------|
| `-TimeoutSec` | いいえ | 全体のタイムアウト（秒） | `1800`（30分） |
| `-PollingIntervalSec` | いいえ | ステータス確認の間隔（秒） | `5` |

#### 実行例

```powershell
# 非同期処理（ポーリング間隔10秒、タイムアウト60分）
.\scripts\powershell\CallCloudApiAsync.ps1 `
    -JsonFilePath ".\input.json" `
    -Endpoint "https://myapim.azure-api.net/api/evaluate" `
    -ApiKey "your-subscription-key" `
    -OutputFilePath ".\output.json" `
    -Provider "AZURE" `
    -AuthHeader "Ocp-Apim-Subscription-Key" `
    -PollingIntervalSec 10 `
    -TimeoutSec 3600
```

#### 実行中の出力例

```
============================================================
[CallCloudApiAsync] 非同期API呼び出し開始
============================================================
[CallCloudApiAsync] JSONファイル読み込み: .\input.json
[CallCloudApiAsync] 処理対象: 10 件
[CallCloudApiAsync] 証跡ファイルを準備中...
[CallCloudApiAsync]   - ID: 001, 証跡: 3 ファイル
[CallCloudApiAsync]   - ID: 002, 証跡: 1 ファイル
[CallCloudApiAsync] 認証方式: Functions Key
[CallCloudApiAsync] ジョブ送信中...
[CallCloudApiAsync] ジョブ送信完了
[CallCloudApiAsync]   - ジョブID: abc12345-def6-7890-ghij-klmnopqrstuv
[CallCloudApiAsync]   - 推定処理時間: 120 秒
[CallCloudApiAsync] 処理完了を待機中...
[CallCloudApiAsync]   進捗: 10% - 処理中...
[CallCloudApiAsync]   進捗: 50% - 処理中...
[CallCloudApiAsync]   進捗: 100% - 完了
[CallCloudApiAsync] 処理完了。結果を取得中...
[CallCloudApiAsync] 結果保存完了: .\output.json
[CallCloudApiAsync] 処理件数: 10 件
[CallCloudApiAsync] 総処理時間: 95.3 秒
============================================================
```

### 3.6 JSON リクエストファイルの作成

PowerShellスクリプトに渡すJSONファイルのフォーマットを説明します。

#### 基本フォーマット

```json
[
  {
    "ID": "001",
    "Category": "統制環境",
    "ControlDescription": "経営者の誠実性と倫理観",
    "TestProcedure": "行動規範の文書確認、全社員へのアンケート実施",
    "EvidenceLink": "C:\\Evidence\\001",
    "Status": "実施中"
  },
  {
    "ID": "002",
    "Category": "リスク評価",
    "ControlDescription": "不正リスクの評価",
    "TestProcedure": "リスク評価書のレビュー、経営会議議事録の確認",
    "EvidenceLink": "C:\\Evidence\\002",
    "Status": "実施中"
  }
]
```

> **注意**: JSONファイルのパス区切り文字は `\\`（バックスラッシュ2つ）にしてください。
> JSON形式では `\` は特殊文字として扱われるため、エスケープ（二重化）が必要です。

#### 各フィールドの説明

| フィールド名 | 必須 | 説明 |
|-------------|------|------|
| `ID` | はい | テスト項目の識別番号 |
| `Category` | はい | 統制の分類（統制環境、リスク評価、統制活動 等） |
| `ControlDescription` | はい | 統制の内容を説明するテキスト |
| `TestProcedure` | はい | テスト手続きの内容を説明するテキスト |
| `EvidenceLink` | いいえ | エビデンスファイルが格納されたフォルダパス |
| `Status` | いいえ | 現在のステータス |

### 3.7 結果ファイルの確認

スクリプト実行後、`-OutputFilePath` で指定したファイルに結果が保存されます。

#### 成功時の結果ファイル例

```json
[
  {
    "ID": "001",
    "evaluationResult": true,
    "executionPlanSummary": "行動規範の文書確認とアンケート結果の分析を実施",
    "judgmentBasis": "行動規範は2025年度版が文書化されており...",
    "documentReference": "倫理規定.pdf (p.3-5)",
    "fileName": "倫理規定.pdf"
  },
  {
    "ID": "002",
    "evaluationResult": false,
    "executionPlanSummary": "リスク評価書のレビューを実施",
    "judgmentBasis": "リスク評価書の更新日が2023年で...",
    "documentReference": "リスク評価書_2023.pdf",
    "fileName": "リスク評価書_2023.pdf"
  }
]
```

#### エラー時の結果ファイル例

```json
{
  "error": true,
  "message": "API Error: 401 Unauthorized",
  "details": "APIキーが無効です。正しいキーを設定してください。",
  "responseBody": "{\"error\":\"invalid_api_key\"}"
}
```

### 3.8 よくあるエラーと対策（PowerShell）

#### エラー1: スクリプトの実行が無効

**症状**: 「このシステムではスクリプトの実行が無効になっているため...」

**対策**: セクション3.2の「実行ポリシー設定」を参照してください。

#### エラー2: 証明書エラー

**症状**: 「基になる接続が閉じられました: SSL/TLS...」

**対策**（開発環境のみ）:
```powershell
# 証明書検証を一時的に無効化（開発環境のみ！本番では使わないこと）
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {$true}
```

#### エラー3: タイムアウト

**症状**: 「操作はタイムアウトしました」

**対策**:
1. `-TimeoutSec` パラメータで時間を延長してください
2. 非同期版（`CallCloudApiAsync.ps1`）の使用を検討してください

```powershell
# タイムアウトを10分に設定
.\scripts\powershell\CallCloudApi.ps1 `
    -JsonFilePath ".\input.json" `
    -Endpoint "https://..." `
    -ApiKey "..." `
    -OutputFilePath ".\output.json" `
    -Provider "AZURE" `
    -TimeoutSec 600
```

#### エラー4: 文字化け

**症状**: 結果ファイルの日本語が文字化けしている

**対策**: 結果ファイルはUTF-8（BOMなし）で保存されます。
テキストエディタで開く際は、文字コードをUTF-8に指定してください。

```powershell
# PowerShellで結果を表示する場合
Get-Content -Path ".\output.json" -Encoding UTF8 | ConvertFrom-Json | Format-List
```

#### エラー5: ジョブ送信失敗（非同期版）

**症状**: 「ジョブ送信失敗（3回リトライ後）」

**対策**:
1. APIエンドポイントのURLが正しいか確認してください
2. `/evaluate/submit` エンドポイントがデプロイされているか確認してください
3. ネットワーク接続を確認してください

---

## 4. 相関ID活用ガイド

### 4.1 相関IDとは

**相関ID（Correlation ID）** とは、1つのリクエストを追跡するための識別子です。
「注文番号」のようなものだと考えてください。

例えば、あなたがExcelからテスト項目をAPIに送信したとします。
そのリクエストは以下のような経路を辿ります：

```
[Excel VBA] → [API Gateway] → [AI処理エンジン] → [LLMモデル]
```

もしどこかでエラーが発生した場合、相関IDがあれば、
この一連の処理を特定して原因を追跡できます。

### 4.2 なぜ必要なのか（トレーサビリティの概念）

本システムは複数のコンポーネント（部品）が連携して動作する分散システムです。
問題が発生したとき、「どこで」「なぜ」エラーが起きたのかを特定するのは容易ではありません。

相関IDがあると：

- **サポートへの問い合わせ時**: 「相関ID: 20260209_1707484800_0001 のリクエストでエラーが出ました」
  と伝えるだけで、管理者はサーバー側のログからすぐに原因を特定できます
- **自己解決時**: 自分のリクエストに対応するログだけを抽出して確認できます

### 4.3 相関IDのフォーマット

本システムの相関IDは以下の形式です：

```
YYYYMMDD_UNIXTIME_NNNN
```

| 部分 | 説明 | 例 |
|------|------|-----|
| `YYYYMMDD` | 処理日（年月日） | `20260209` |
| `UNIXTIME` | UNIXタイムスタンプ（1970年1月1日からの経過秒数） | `1707484800` |
| `NNNN` | 連番（0001〜9999） | `0001` |

完全な例: `20260209_1707484800_0001`

### 4.4 VBAでの相関ID生成と送信

ExcelToJson.bas には相関ID生成機能が組み込まれています。
以下は内部で使われているコードの抜粋と解説です。

```vba
' =============================================================
' 相関IDを生成する関数
' =============================================================
' 戻り値の例: "20260209_1707484800_0001"
'
' 仕組み:
' 1. 今日の日付を YYYYMMDD 形式にする
' 2. 1970年1月1日からの経過秒数（UNIXタイムスタンプ）を計算する
' 3. 連番（0001〜9999）をつける
' 4. これらを "_" でつなげる
' =============================================================
Public Function GenerateCorrelationId() As String
    Dim datePart As String
    Dim unixTime As Long
    Dim seqPart As String

    ' 日付部分（YYYYMMDD）
    datePart = Format(Now, "yyyymmdd")

    ' UNIXタイムスタンプ（秒）
    unixTime = DateDiff("s", #1/1/1970#, Now)

    ' 連番（4桁ゼロ埋め）
    mSequenceNumber = mSequenceNumber + 1
    If mSequenceNumber > 9999 Then mSequenceNumber = 1
    seqPart = Format(mSequenceNumber, "0000")

    GenerateCorrelationId = datePart & "_" & CStr(unixTime) & "_" & seqPart
End Function
```

**APIリクエスト時の送信方法**:

```vba
' 相関IDをHTTPヘッダーに設定して送信
Dim correlationId As String
correlationId = GenerateCorrelationId()

httpReq.setRequestHeader "X-Correlation-ID", correlationId

' 後で確認できるようにログに記録
Debug.Print "相関ID: " & correlationId
```

### 4.5 PowerShellでの相関ID生成と送信

PowerShellスクリプト（CallCloudApi.ps1 / CallCloudApiAsync.ps1）では、
以下のように相関IDを生成してHTTPヘッダーに含めて送信できます。

```powershell
# =============================================================
# 相関IDを生成する
# =============================================================
# 出力例: "20260209_1707484800_0001"

$script:SequenceNumber = 0

function New-CorrelationId {
    $datePart = Get-Date -Format "yyyyMMdd"
    $unixTime = [int][double]::Parse((Get-Date -UFormat %s))
    $script:SequenceNumber++
    if ($script:SequenceNumber -gt 9999) { $script:SequenceNumber = 1 }
    $seqPart = $script:SequenceNumber.ToString("D4")

    return "${datePart}_${unixTime}_${seqPart}"
}

# 使用例: HTTPヘッダーに相関IDを含める
$correlationId = New-CorrelationId
$headers = @{
    "Content-Type"     = "application/json"
    "X-Api-Key"        = $apiKey
    "X-Correlation-ID" = $correlationId
}

Write-Host "相関ID: $correlationId"
```

### 4.6 ログ追跡方法（各プラットフォーム別クエリ）

問題が発生した場合、相関IDを使ってサーバー側のログを検索できます。
以下は各クラウドプラットフォームでの検索クエリです。

#### Azure Application Insights（Kusto Query Language）

```kusto
// 特定の相関IDに関連するすべてのログを時系列で表示
traces
| where customDimensions.correlation_id == "20260209_1707484800_0001"
| order by timestamp asc
| project timestamp, message, severityLevel,
    customDimensions.correlation_id

// 特定日のすべてのリクエストを一覧表示
traces
| where customDimensions.correlation_id startswith "20260209_"
| summarize
    request_count = count(),
    first_seen = min(timestamp),
    last_seen = max(timestamp),
    errors = countif(severityLevel >= 3)
    by tostring(customDimensions.correlation_id)
| order by first_seen desc
```

#### AWS CloudWatch Insights

```
# 特定の相関IDでログを検索
fields @timestamp, @message, correlation_id
| filter correlation_id = "20260209_1707484800_0001"
| sort @timestamp asc

# 特定日のリクエスト概要
fields @timestamp, correlation_id, @message
| filter correlation_id like /^20260209_/
| stats count() as request_count,
    earliest(@timestamp) as first_seen,
    latest(@timestamp) as last_seen
    by correlation_id
| sort first_seen desc
```

#### GCP Cloud Logging

```
# 特定の相関IDでフィルタ
resource.type="cloud_function"
jsonPayload.correlation_id="20260209_1707484800_0001"

# 特定日のリクエスト一覧
resource.type="cloud_function"
jsonPayload.correlation_id=~"^20260209_"
severity>=INFO
```

> **管理者に問い合わせる際のポイント**:
> エラーが発生した場合は、以下の情報を添えてサポートに連絡してください：
> 1. **相関ID**（例: `20260209_1707484800_0001`）
> 2. **エラーメッセージ**の全文
> 3. **発生日時**
> 4. **使用したプラットフォーム**（Azure / AWS / GCP）

---

## 5. セキュリティ注意事項

### 5.1 APIキーの安全な管理方法

APIキーは「パスワード」のようなものです。漏洩すると不正利用される可能性があるため、
以下のルールを厳守してください。

#### やってはいけないこと

- VBAコードにAPIキーをハードコード（直接記述）しない
- APIキーをメールやチャットで平文送信しない
- APIキーをGitリポジトリにコミットしない
- APIキーを共有フォルダに保存しない
- スクリーンショットにAPIキーが写り込んだ状態で共有しない

#### 推奨される管理方法

**方法1: setting.json で管理する（最もシンプル）**

`setting.json` にAPIキーを記述し、このファイルを `.gitignore` に追加して
Gitリポジトリにコミットされないようにします。

```
# .gitignore に以下を追加
setting.json
```

**方法2: 環境変数で管理する（推奨）**

Windows の環境変数にAPIキーを設定する方法です。

```powershell
# ユーザー環境変数にAPIキーを設定
[Environment]::SetEnvironmentVariable("IC_TEST_API_KEY", "your-api-key", "User")
```

VBAからは以下のように取得できます：

```vba
Dim apiKey As String
apiKey = Environ("IC_TEST_API_KEY")
```

PowerShellからは以下のように取得できます：

```powershell
$apiKey = $env:IC_TEST_API_KEY
```

**方法3: Windows 資格情報マネージャーで管理する（最も安全）**

Windowsの「資格情報マネージャー」にAPIキーを保存する方法です。
暗号化されて保存されるため、最も安全です。

### 5.2 本番環境での推奨設定

| 項目 | 推奨設定 |
|------|---------|
| APIキー管理 | 環境変数または資格情報マネージャー |
| SSL/TLS | 証明書検証を必ず有効にする |
| 通信プロトコル | HTTPS のみ使用（HTTP は使わない） |
| APIキーローテーション | 90日ごとに更新 |
| アクセスログ | 相関IDを含めて記録 |
| 証明書 | 自己署名証明書は使用しない |
| Azure AD認証 | 可能であれば `authType: "azureAd"` を使用する |

### 5.3 Azure AD 認証について

本システムはAPIキー認証に加えて、Azure AD認証もサポートしています。
Azure AD認証を使うと、組織のアカウント（メールアドレス）でログインして
APIにアクセスできるため、APIキーの管理が不要になります。

Azure AD認証を有効にするには、`setting.json` の `authType` を `"azureAd"` に変更し、
テナントID、クライアントID、スコープを設定してください。

```json
{
  "api": {
    "authType": "azureAd",
    "azureAd": {
      "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "scope": "api://xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/.default"
    }
  }
}
```

> Azure AD認証の設定値はシステム管理者から提供されます。

---

## 6. まとめ・参考資料

### 6.1 このドキュメントのまとめ

| 手順 | VBAクライアント | PowerShellクライアント |
|------|---------------|---------------------|
| 1. 準備 | マクロセキュリティ設定 | 実行ポリシー設定 |
| 2. 設定 | setting.json + ExcelToJson.bas インポート | パラメータ指定 |
| 3. データ準備 | Excelに直接入力 | JSONファイル作成 |
| 4. 実行 | Alt+F8 → ProcessWithApi | PowerShellコマンド実行 |
| 5. 結果確認 | Excel出力列を確認 | 出力JSONファイルを確認 |

### 6.2 どちらを使えばよいか

| ユースケース | 推奨クライアント |
|-------------|----------------|
| 少量のテスト項目を手動で評価したい | Excel VBA |
| 定期的にバッチ処理で自動実行したい | PowerShell |
| 非プログラマーのチームメンバーが使う | Excel VBA |
| CI/CDパイプラインに組み込みたい | PowerShell |
| 大量データ（50項目以上）を処理したい | PowerShell（非同期版） |

### 6.3 参考資料

- [前提条件セットアップ](./PREREQUISITES.md) - 開発環境の構築手順
- [Azure セットアップ](./AZURE_SETUP.md) - Azure環境の構築手順
- [AWS セットアップ](./AWS_SETUP.md) - AWS環境の構築手順
- [GCP セットアップ](./GCP_SETUP.md) - GCP環境の構築手順
- [デプロイガイド](../operations/DEPLOYMENT_GUIDE.md) - 本番環境へのデプロイ手順
- [トラブルシューティング](../operations/TROUBLESHOOTING.md) - 問題解決ガイド
- [相関ID詳細設計](../monitoring/CORRELATION_ID.md) - 相関IDの技術的な詳細
- [API仕様書](../../SYSTEM_SPECIFICATION.md) - APIの詳細仕様

---

> **このドキュメントに関するフィードバック**: 不明点や改善提案がありましたら、
> プロジェクトのIssueとして報告してください。
