'===============================================================================
' ExcelToJson.bas - 内部統制テスト評価システム Excel VBAモジュール
'===============================================================================
' 【機能概要】
' このVBAモジュールは、Excelに入力された内部統制テスト項目を、
' クラウドAI（Azure Functions）に送信して自動評価を行い、
' 結果をExcelに書き戻すプログラムです。
'
' 【主な機能】
' 1. Excelデータ → JSON形式への変換
' 2. クラウドAPIへのバッチ送信（タイムアウト対策）
' 3. AI評価結果のExcelへの書き戻し
'
' 【対応クラウドプロバイダー】
' - AZURE: Azure Functions（推奨）
' - GCP: Google Cloud Platform
' - AWS: Amazon Web Services
'
' 【設定ファイル】
' setting.json - 列マッピング、API設定等を定義
'
' 【必要なファイル】
' - ExcelToJson.bas（本ファイル）
' - setting.json（設定ファイル）
' - scripts/powershell/CallCloudApi.ps1（PowerShellスクリプト）
'
' 【使い方】
' 1. setting.jsonでAPI設定と列マッピングを設定
' 2. Excelにテスト項目データを入力
' 3. ProcessWithApiマクロを実行
'
'===============================================================================
Option Explicit

'===============================================================================
' Windows API宣言
'===============================================================================
#If VBA7 Then
    Private Declare PtrSafe Sub Sleep Lib "kernel32" (ByVal dwMilliseconds As LongPtr)
#Else
    Private Declare Sub Sleep Lib "kernel32" (ByVal dwMilliseconds As Long)
#End If

'===============================================================================
' 定数定義セクション
' システム全体で使用する固定値を定義します
'===============================================================================

' ログ出力先パス（%TEMP%フォルダ配下）
Private Const LOG_FILE_NAME As String = "\ExcelToJson_Log.txt"

' ログレベル定数
' ログの重要度を示す値。数字が大きいほど重要
Private Const LOG_LEVEL_DEBUG As Integer = 1    ' デバッグ情報（開発時のみ）
Private Const LOG_LEVEL_INFO As Integer = 2     ' 通常の情報
Private Const LOG_LEVEL_WARNING As Integer = 3  ' 警告（処理は継続可能）
Private Const LOG_LEVEL_ERROR As Integer = 4    ' エラー（処理が失敗）
Private Const LOG_LEVEL_CRITICAL As Integer = 5 ' 致命的エラー（即時停止）

' 現在のログ出力レベル（これ以上のレベルのみ出力）
' 本番環境ではLOG_LEVEL_INFO以上を推奨
Private Const CURRENT_LOG_LEVEL As Integer = LOG_LEVEL_INFO

' エラーコード定数
' エラーの種類を識別するための一意の番号
Private Const ERR_SETTING_NOT_FOUND As Long = 1001      ' 設定ファイルが見つからない
Private Const ERR_SETTING_PARSE_FAILED As Long = 1002   ' 設定ファイルの解析に失敗
Private Const ERR_API_ENDPOINT_EMPTY As Long = 1003     ' APIエンドポイントが未設定
Private Const ERR_SHEET_NOT_FOUND As Long = 1004        ' 指定されたシートが見つからない
Private Const ERR_NO_DATA As Long = 1005                ' 処理対象データがない
Private Const ERR_JSON_FILE_CREATE As Long = 1006       ' JSONファイル作成に失敗
Private Const ERR_POWERSHELL_SCRIPT_NOT_FOUND As Long = 1007  ' PSスクリプトが見つからない
Private Const ERR_API_CALL_FAILED As Long = 1008        ' API呼び出しに失敗
Private Const ERR_RESPONSE_READ_FAILED As Long = 1009   ' レスポンス読み取りに失敗
Private Const ERR_API_RETURNED_ERROR As Long = 1010     ' APIがエラーを返した
Private Const ERR_FILE_READ_FAILED As Long = 1011       ' ファイル読み取りに失敗
Private Const ERR_FILE_WRITE_FAILED As Long = 1012      ' ファイル書き込みに失敗

'===============================================================================
' 設定情報を格納する構造体（ユーザー定義型）
' setting.jsonから読み込んだ設定値を保持します
'===============================================================================
Private Type SettingConfig
    '--- 基本設定 ---
    DataStartRow As Long        ' データ開始行（通常は2行目、ヘッダーが1行目のため）
    SheetName As String         ' 対象シート名（空欄の場合はアクティブシート）
    BatchSize As Long           ' 一度に処理する項目数（タイムアウト対策用）
    AsyncMode As Boolean        ' 非同期モード（True=504タイムアウト対策）
    PollingIntervalSec As Long  ' ポーリング間隔（秒）

    '--- 入力列マッピング（Excelのどの列にどのデータがあるか）---
    ColID As String                  ' ID列（例："A"）
    ColTestTarget As String          ' テスト対象列（例："B"）- TRUEの行のみ処理
    ColCategory As String            ' 区分名列（例："C"）
    ColControlDescription As String  ' 統制記述列（例："D"）
    ColTestProcedure As String       ' テスト手続き列（例："E"）
    ColEvidenceLink As String        ' エビデンスリンク列（例："F"）

    '--- API接続設定 ---
    ApiProvider As String       ' プロバイダー名（AZURE/GCP/AWS）
    ApiEndpoint As String       ' APIのURL
    ApiKey As String            ' 認証用APIキー
    ApiAuthHeader As String     ' 認証ヘッダー名（例：x-functions-key）
    ApiClient As String         ' APIクライアント（POWERSHELL/VBA）
    ApiAuthType As String       ' 認証タイプ（functionsKey/azureAd）

    '--- Azure AD認証設定（authType="azureAd"の場合に使用）---
    AzureAdTenantId As String   ' Azure ADテナントID
    AzureAdClientId As String   ' アプリケーション（クライアント）ID
    AzureAdScope As String      ' スコープ（api://{clientId}/.default）

    '--- 出力列マッピング（APIの応答をどの列に書き込むか）---
    ColEvaluationResult As String    ' 評価結果列（True/False → 有効/不備）
    ColExecutionPlanSummary As String ' 実行計画サマリー列（テスト計画）
    ColJudgmentBasis As String       ' 判断根拠列
    ColDocumentReference As String   ' 文書参照列
    ColFileName As String            ' ファイル名列

    '--- 表示設定 ---
    BooleanDisplayTrue As String     ' Trueの表示文字列（例："有効"）
    BooleanDisplayFalse As String    ' Falseの表示文字列（例："不備"）
End Type

'===============================================================================
' モジュールレベル変数
' モジュール全体で共有する変数
'===============================================================================
Private m_LogFilePath As String     ' ログファイルのフルパス
Private m_SessionId As String       ' 処理セッションの一意識別子
Private m_AzureAdNotified As Boolean ' Azure AD認証通知済みフラグ（1回だけ表示）
Private m_TokenCacheChecked As Boolean ' トークンキャッシュ確認済みフラグ
Private m_HasCachedToken As Boolean ' キャッシュ済みトークンが存在するか

'===============================================================================
' メイン処理: ProcessWithApi
'===============================================================================
' 【機能】
' Excelデータをクラウドに送信し、AI評価結果を取得してExcelに書き戻します。
' 大量データの場合は自動的にバッチ分割して処理します。
'
' 【処理フロー】
' 1. 設定ファイル（setting.json）を読み込む
' 2. 対象シートのデータ行を収集
' 3. バッチサイズごとに分割してAPIを呼び出し
' 4. レスポンスをExcelに書き戻し
' 5. 完了メッセージを表示
'
' 【エラー処理】
' - 設定ファイルが見つからない → 処理中止
' - APIエラー → エラーメッセージ表示、途中結果は保持
' - バッチ途中でエラー → 処理済み件数を表示
'
' 【使用例】
' Excelのマクロダイアログから「ProcessWithApi」を選択して実行
'===============================================================================
Public Sub ProcessWithApi()
    '--- 変数宣言 ---
    Dim config As SettingConfig       ' 設定情報を格納する変数
    Dim ws As Worksheet               ' 処理対象のワークシート
    Dim lastRow As Long               ' データの最終行番号
    Dim totalItems As Long            ' 処理対象の総項目数
    Dim processedItems As Long        ' 処理完了した項目数
    Dim batchNum As Long              ' 現在のバッチ番号
    Dim totalBatches As Long          ' 総バッチ数
    Dim startIdx As Long              ' バッチ内の開始インデックス
    Dim endIdx As Long                ' バッチ内の終了インデックス
    Dim rowIndices() As Long          ' データがある行番号の配列
    Dim rowCount As Long              ' データがある行の数
    Dim i As Long                     ' ループカウンター
    Dim jsonText As String            ' API送信用JSON文字列
    Dim inputJsonPath As String       ' 入力JSONファイルのパス
    Dim outputJsonPath As String      ' 出力JSONファイルのパス
    Dim responseJson As String        ' APIからのレスポンスJSON
    Dim success As Boolean            ' API呼び出し成功フラグ
    Dim hasError As Boolean           ' エラー発生フラグ
    Dim startTime As Double           ' 処理開始時刻
    Dim elapsedTime As Double         ' 経過時間

    '--- セッション初期化 ---
    ' 各実行を一意に識別するためのセッションIDを生成
    InitializeSession

    '--- ログ出力開始 ---
    WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "===== 処理開始 ====="
    startTime = Timer  ' 処理時間計測のため開始時刻を記録

    '--- ステップ1: 設定ファイルの読み込み ---
    WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "設定ファイルを読み込み中..."

    If Not LoadSettings(config) Then
        ' 設定読み込みに失敗した場合は処理を中止
        ShowErrorMessage ERR_SETTING_NOT_FOUND, "設定ファイルの読み込みに失敗しました。" & vbCrLf & _
                         "setting.jsonが正しい場所にあるか確認してください。"
        Exit Sub
    End If

    WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "設定読み込み完了 - プロバイダー: " & config.ApiProvider & _
                              ", バッチサイズ: " & config.BatchSize

    '--- ステップ2: API設定の検証 ---
    If Trim(config.ApiEndpoint) = "" Then
        ShowErrorMessage ERR_API_ENDPOINT_EMPTY, "APIエンドポイントが設定されていません。" & vbCrLf & _
                         "setting.jsonのapi.endpointを確認してください。"
        Exit Sub
    End If

    '--- ステップ3: 対象シートの取得 ---
    Set ws = GetTargetWorksheet(config.SheetName)

    If ws Is Nothing Then
        ShowErrorMessage ERR_SHEET_NOT_FOUND, "対象シートが見つかりません。" & vbCrLf & _
                         "シート名: " & config.SheetName
        Exit Sub
    End If

    WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "対象シート: " & ws.Name

    '--- ステップ4: データ行の収集 ---
    ' ID列でデータの最終行を判定
    lastRow = ws.Cells(ws.Rows.Count, config.ColID).End(xlUp).Row

    ' データがある行のインデックスを配列に格納
    ' （空行をスキップ、テスト対象列でフィルタリング）
    ReDim rowIndices(1 To lastRow - config.DataStartRow + 1)
    rowCount = 0
    Dim testTargetValue As String  ' テスト対象列の値
    Dim skippedCount As Long       ' スキップされた件数
    skippedCount = 0

    For i = config.DataStartRow To lastRow
        ' ID列に値がある行のみを処理対象とする
        If Trim(CStr(ws.Range(config.ColID & i).Value)) <> "" Then
            ' テスト対象列でフィルタリング（列が設定されている場合）
            If config.ColTestTarget <> "" Then
                testTargetValue = UCase(Trim(CStr(ws.Range(config.ColTestTarget & i).Value)))
                ' TRUE または 1 の場合のみ処理対象
                If testTargetValue = "TRUE" Or testTargetValue = "1" Or testTargetValue = "はい" Or testTargetValue = "○" Then
                    rowCount = rowCount + 1
                    rowIndices(rowCount) = i
                Else
                    skippedCount = skippedCount + 1
                End If
            Else
                ' テスト対象列が設定されていない場合は全行処理
                rowCount = rowCount + 1
                rowIndices(rowCount) = i
            End If
        End If
    Next i

    ' スキップ件数をログに記録
    If skippedCount > 0 Then
        WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "テスト対象外としてスキップ: " & skippedCount & " 件"
    End If

    ' データがない場合は処理終了
    If rowCount = 0 Then
        ShowErrorMessage ERR_NO_DATA, "処理対象のデータがありません。" & vbCrLf & _
                         "ID列（" & config.ColID & "列）にデータがあるか確認してください。"
        Exit Sub
    End If

    ' 配列サイズを実際のデータ数に調整
    ReDim Preserve rowIndices(1 To rowCount)
    totalItems = rowCount

    ' 総バッチ数を計算（切り上げ）
    totalBatches = Application.WorksheetFunction.Ceiling(totalItems / config.BatchSize, 1)

    WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "データ件数: " & totalItems & ", バッチ数: " & totalBatches

    '--- ステップ5: 一時ファイルパスの設定 ---
    ' Windows標準のTEMPフォルダを使用
    inputJsonPath = Environ("TEMP") & "\excel_to_api_input.json"
    outputJsonPath = Environ("TEMP") & "\excel_to_api_output.json"

    WriteLog LOG_LEVEL_DEBUG, "ProcessWithApi", "入力JSON: " & inputJsonPath
    WriteLog LOG_LEVEL_DEBUG, "ProcessWithApi", "出力JSON: " & outputJsonPath

    '--- ステップ6: バッチ処理ループ ---
    hasError = False
    processedItems = 0

    For batchNum = 1 To totalBatches
        ' バッチ範囲の計算
        startIdx = (batchNum - 1) * config.BatchSize + 1
        endIdx = Application.WorksheetFunction.Min(batchNum * config.BatchSize, totalItems)

        ' ステータスバーに進捗表示
        Application.StatusBar = "処理中... バッチ " & batchNum & "/" & totalBatches & _
                               " (項目 " & startIdx & "-" & endIdx & " / " & totalItems & ")"

        WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "バッチ " & batchNum & " 開始 (項目 " & startIdx & "-" & endIdx & ")"

        '--- 6a: バッチ用JSONの生成 ---
        jsonText = GenerateJsonForBatch(ws, rowIndices, startIdx, endIdx, config)

        '--- 6b: JSONファイルの保存 ---
        If Not WriteToFile(inputJsonPath, jsonText) Then
            WriteLog LOG_LEVEL_ERROR, "ProcessWithApi", "JSONファイル作成失敗 - バッチ " & batchNum
            ShowErrorMessage ERR_JSON_FILE_CREATE, "JSONファイルの作成に失敗しました。" & vbCrLf & _
                             "バッチ: " & batchNum & vbCrLf & _
                             "パス: " & inputJsonPath
            hasError = True
            Exit For
        End If

        '--- 6c: 古い出力ファイルを削除（キャッシュ対策）---
        On Error Resume Next
        Kill outputJsonPath
        On Error GoTo 0

        '--- 6d: API呼び出し（PowerShell/VBA切り替え）---
        success = CallApi(inputJsonPath, outputJsonPath, config)

        If Not success Then
            WriteLog LOG_LEVEL_ERROR, "ProcessWithApi", "API呼び出し失敗 - バッチ " & batchNum
            ShowErrorMessage ERR_API_CALL_FAILED, "API呼び出しに失敗しました。" & vbCrLf & _
                             "バッチ: " & batchNum & "/" & totalBatches & vbCrLf & _
                             "ログファイルを確認してください: " & m_LogFilePath
            hasError = True
            Exit For
        End If

        '--- 6d: レスポンスの読み取り ---
        responseJson = ReadFromFile(outputJsonPath)

        If responseJson = "" Then
            WriteLog LOG_LEVEL_ERROR, "ProcessWithApi", "レスポンス読み取り失敗 - バッチ " & batchNum
            ShowErrorMessage ERR_RESPONSE_READ_FAILED, "APIレスポンスの読み取りに失敗しました。" & vbCrLf & _
                             "バッチ: " & batchNum
            hasError = True
            Exit For
        End If

        '--- 6e: APIエラーチェック ---
        If InStr(1, responseJson, """error"": true", vbTextCompare) > 0 Then
            Dim apiErrorMsg As String
            apiErrorMsg = ExtractJsonValue(responseJson, "message")
            WriteLog LOG_LEVEL_ERROR, "ProcessWithApi", "APIエラー - " & apiErrorMsg
            ShowErrorMessage ERR_API_RETURNED_ERROR, "APIがエラーを返しました。" & vbCrLf & _
                             "バッチ: " & batchNum & vbCrLf & _
                             "エラー: " & apiErrorMsg
            hasError = True
            Exit For
        End If

        '--- 6f: Excelへの書き戻し ---
        WriteResponseToExcel responseJson, config

        processedItems = endIdx
        WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "バッチ " & batchNum & " 完了 - 累計処理: " & processedItems & " 件"

        ' Excelの応答性を維持（ハングアップ防止）
        DoEvents
    Next batchNum

    '--- ステップ7: 後処理 ---
    Application.StatusBar = False  ' ステータスバーをクリア

    ' 経過時間を計算
    elapsedTime = Timer - startTime

    '--- ステップ8: 完了メッセージの表示 ---
    If hasError Then
        WriteLog LOG_LEVEL_WARNING, "ProcessWithApi", "処理中断 - 処理済み: " & processedItems & "/" & totalItems
        MsgBox "処理がエラーにより中断されました。" & vbCrLf & vbCrLf & _
               "処理済み: " & processedItems & " / " & totalItems & " 件" & vbCrLf & _
               "経過時間: " & Format(elapsedTime, "0.0") & " 秒" & vbCrLf & vbCrLf & _
               "詳細はログファイルを確認してください:" & vbCrLf & _
               m_LogFilePath, vbExclamation, "処理中断"
    Else
        WriteLog LOG_LEVEL_INFO, "ProcessWithApi", "===== 処理完了 ===== (経過時間: " & Format(elapsedTime, "0.0") & " 秒)"
        Dim resultMsg As String
        resultMsg = "処理が正常に完了しました。" & vbCrLf & vbCrLf & _
               "プロバイダー: " & config.ApiProvider & vbCrLf & _
               "処理件数: " & totalItems & " 件" & vbCrLf
        If skippedCount > 0 Then
            resultMsg = resultMsg & "スキップ件数: " & skippedCount & " 件（テスト対象外）" & vbCrLf
        End If
        resultMsg = resultMsg & "バッチ数: " & totalBatches & vbCrLf & _
               "経過時間: " & Format(elapsedTime, "0.0") & " 秒"
        MsgBox resultMsg, vbInformation, "処理完了"
    End If
End Sub

'===============================================================================
' エクスポート処理: ProcessForExport
'===============================================================================
' 【機能】
' PowerShell/VBA COM両方が使用できない環境向けに、
' 評価用JSONファイルをエクスポートします。
'
' 【EXPORTモードの使い方】
' 1. setting.jsonで "apiClient": "EXPORT" を設定
' 2. このマクロ（ProcessForExport）を実行
' 3. エクスポートされたJSONをブラウザ（web/index.html）でアップロード
' 4. AI評価完了後、結果JSONをダウンロード
' 5. ImportResultsマクロで結果をExcelにインポート
'===============================================================================
Public Sub ProcessForExport()
    Dim config As SettingConfig
    Dim ws As Worksheet
    Dim lastRow As Long
    Dim rowIndices() As Long
    Dim rowCount As Long
    Dim i As Long
    Dim jsonText As String
    Dim exportPath As String
    Dim fso As Object
    Dim baseDir As String

    '--- セッション初期化 ---
    InitializeSession
    WriteLog LOG_LEVEL_INFO, "ProcessForExport", "===== エクスポート処理開始 ====="

    '--- 設定ファイルの読み込み ---
    If Not LoadSettings(config) Then
        ShowErrorMessage ERR_SETTING_NOT_FOUND, "設定ファイルの読み込みに失敗しました。"
        Exit Sub
    End If

    '--- 対象シートの取得 ---
    If config.SheetName = "" Then
        Set ws = ActiveSheet
    Else
        On Error Resume Next
        Set ws = ThisWorkbook.Worksheets(config.SheetName)
        On Error GoTo 0
        If ws Is Nothing Then
            ShowErrorMessage ERR_SHEET_NOT_FOUND, "シート '" & config.SheetName & "' が見つかりません。"
            Exit Sub
        End If
    End If

    '--- データ行の収集 ---
    lastRow = ws.Cells(ws.Rows.Count, config.ColID).End(xlUp).Row

    If lastRow < config.DataStartRow Then
        ShowErrorMessage ERR_NO_DATA, "処理対象のデータがありません。"
        Exit Sub
    End If

    rowCount = 0
    ReDim rowIndices(1 To lastRow - config.DataStartRow + 1)

    For i = config.DataStartRow To lastRow
        Dim cellValue As Variant
        cellValue = ws.Cells(i, config.ColID).Value
        If Not IsEmpty(cellValue) And Trim(CStr(cellValue)) <> "" Then
            ' TestTarget列がある場合、TRUEの行のみ対象
            If config.ColTestTarget <> "" Then
                Dim testTargetValue As Variant
                testTargetValue = ws.Cells(i, config.ColTestTarget).Value
                If UCase(CStr(testTargetValue)) = "TRUE" Or testTargetValue = True Then
                    rowCount = rowCount + 1
                    rowIndices(rowCount) = i
                End If
            Else
                rowCount = rowCount + 1
                rowIndices(rowCount) = i
            End If
        End If
    Next i

    If rowCount = 0 Then
        ShowErrorMessage ERR_NO_DATA, "処理対象のデータがありません。"
        Exit Sub
    End If

    ReDim Preserve rowIndices(1 To rowCount)
    WriteLog LOG_LEVEL_INFO, "ProcessForExport", "対象データ: " & rowCount & " 件"

    '--- JSON生成 ---
    jsonText = GenerateJsonForBatch(ws, rowIndices, 1, rowCount, config)

    '--- Base64エンコード済みのEvidenceFilesを追加 ---
    jsonText = AddEvidenceFilesToJson(jsonText)

    '--- エクスポート先の決定 ---
    baseDir = ThisWorkbook.Path
    exportPath = baseDir & "\export_" & Format(Now, "yyyymmdd_hhmmss") & ".json"

    '--- ファイル出力 ---
    Set fso = CreateObject("Scripting.FileSystemObject")
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    With stream
        .Type = 2  ' テキストモード
        .Charset = "UTF-8"
        .Open
        .WriteText jsonText
        .SaveToFile exportPath, 2  ' 上書き
        .Close
    End With
    Set stream = Nothing
    Set fso = Nothing

    WriteLog LOG_LEVEL_INFO, "ProcessForExport", "エクスポート完了: " & exportPath

    '--- 完了メッセージ ---
    MsgBox "JSONファイルをエクスポートしました。" & vbCrLf & vbCrLf & _
           "ファイル: " & exportPath & vbCrLf & vbCrLf & _
           "【次のステップ】" & vbCrLf & _
           "1. web/index.html をブラウザで開く" & vbCrLf & _
           "2. エクスポートしたJSONファイルをアップロード" & vbCrLf & _
           "3. AI評価完了後、結果をダウンロード" & vbCrLf & _
           "4. ImportResultsマクロで結果をインポート", _
           vbInformation, "エクスポート完了"
End Sub

'===============================================================================
' インポート処理: ImportResults
'===============================================================================
' 【機能】
' AI評価結果のJSONファイルを読み込み、Excelに書き戻します。
' EXPORTモードでWebフロントエンドから取得した結果を取り込む際に使用します。
'===============================================================================
Public Sub ImportResults()
    Dim config As SettingConfig
    Dim filePath As Variant
    Dim jsonText As String

    '--- セッション初期化 ---
    InitializeSession
    WriteLog LOG_LEVEL_INFO, "ImportResults", "===== インポート処理開始 ====="

    '--- 設定ファイルの読み込み ---
    If Not LoadSettings(config) Then
        ShowErrorMessage ERR_SETTING_NOT_FOUND, "設定ファイルの読み込みに失敗しました。"
        Exit Sub
    End If

    '--- ファイル選択ダイアログ ---
    filePath = Application.GetOpenFilename( _
        FileFilter:="JSONファイル (*.json),*.json", _
        Title:="AI評価結果のJSONファイルを選択してください")

    If filePath = False Then
        WriteLog LOG_LEVEL_INFO, "ImportResults", "ファイル選択がキャンセルされました"
        Exit Sub
    End If

    WriteLog LOG_LEVEL_INFO, "ImportResults", "選択ファイル: " & filePath

    '--- JSONファイル読み込み ---
    jsonText = ReadFromFile(CStr(filePath))

    If jsonText = "" Then
        ShowErrorMessage ERR_FILE_READ_FAILED, "ファイルの読み込みに失敗しました。"
        Exit Sub
    End If

    '--- JSON形式チェック ---
    If Left(Trim(jsonText), 1) <> "[" Then
        ShowErrorMessage ERR_API_RETURNED_ERROR, "無効なJSONファイルです。配列形式のJSONが必要です。"
        Exit Sub
    End If

    '--- Excelへの書き戻し ---
    WriteResponseToExcel jsonText, config

    WriteLog LOG_LEVEL_INFO, "ImportResults", "===== インポート処理完了 ====="

    '--- 完了メッセージ ---
    MsgBox "評価結果のインポートが完了しました。" & vbCrLf & vbCrLf & _
           "結果列を確認してください。", _
           vbInformation, "インポート完了"
End Sub

'===============================================================================
' セッション初期化
'===============================================================================
' 【機能】
' ログファイルパスとセッションIDを初期化します。
' 各処理実行時に呼び出され、ログの追跡を容易にします。
'
' 【セッションIDの形式】
' YYYYMMDD_HHMMSS_nnnn（日時 + ランダム4桁）
'===============================================================================
Private Sub InitializeSession()
    ' ログファイルパスを設定
    m_LogFilePath = Environ("TEMP") & LOG_FILE_NAME

    ' セッションIDを生成（日時 + ランダム値で一意性を確保）
    Randomize
    m_SessionId = Format(Now, "yyyymmdd_hhmmss") & "_" & Format(Int(Rnd * 10000), "0000")

    ' Azure AD関連フラグをリセット
    m_AzureAdNotified = False
    m_TokenCacheChecked = False
    m_HasCachedToken = False
End Sub

'===============================================================================
' ログ出力関数
'===============================================================================
' 【機能】
' 指定されたログレベルでメッセージをログファイルに書き込みます。
' 本番運用時のトラブルシューティングに必要な情報を記録します。
'
' 【引数】
' logLevel: ログレベル（LOG_LEVEL_DEBUG/INFO/WARNING/ERROR/CRITICAL）
' procName: 処理名（どの関数からのログか）
' message: ログメッセージ
'
' 【ログ形式】
' 2025-01-15 10:30:45 [INFO] [SESSION_ID] [ProcessWithApi] メッセージ
'
' 【注意】
' - CURRENT_LOG_LEVEL以上のレベルのみ出力されます
' - ログファイルは追記モードで書き込まれます
'===============================================================================
Private Sub WriteLog(logLevel As Integer, procName As String, message As String)
    Dim logLevelStr As String
    Dim logLine As String
    Dim fileNum As Integer

    ' 現在のログレベル未満は出力しない
    If logLevel < CURRENT_LOG_LEVEL Then
        Exit Sub
    End If

    ' ログレベルを文字列に変換
    Select Case logLevel
        Case LOG_LEVEL_DEBUG:    logLevelStr = "DEBUG"
        Case LOG_LEVEL_INFO:     logLevelStr = "INFO"
        Case LOG_LEVEL_WARNING:  logLevelStr = "WARNING"
        Case LOG_LEVEL_ERROR:    logLevelStr = "ERROR"
        Case LOG_LEVEL_CRITICAL: logLevelStr = "CRITICAL"
        Case Else:               logLevelStr = "UNKNOWN"
    End Select

    ' ログ行を組み立て
    logLine = Format(Now, "yyyy-mm-dd hh:mm:ss") & " [" & logLevelStr & "]" & _
              " [" & m_SessionId & "]" & _
              " [" & procName & "] " & message

    ' ファイルに追記
    On Error Resume Next
    fileNum = FreeFile
    Open m_LogFilePath For Append As #fileNum
    Print #fileNum, logLine
    Close #fileNum
    On Error GoTo 0

    ' デバッグ時はイミディエイトウィンドウにも出力
    #If DEBUG_MODE Then
        Debug.Print logLine
    #End If
End Sub

'===============================================================================
' エラーメッセージ表示関数
'===============================================================================
' 【機能】
' エラーコードとメッセージを整形して表示し、ログにも記録します。
' ユーザーに分かりやすいエラー情報を提供します。
'
' 【引数】
' errorCode: エラーコード（ERR_XXX定数）
' message: ユーザー向けメッセージ
'
' 【表示形式】
' エラーコード: ERR-1001
' メッセージ内容...
'===============================================================================
Private Sub ShowErrorMessage(errorCode As Long, message As String)
    Dim fullMessage As String

    ' ログに記録
    WriteLog LOG_LEVEL_ERROR, "ShowErrorMessage", "ERR-" & errorCode & ": " & Replace(message, vbCrLf, " | ")

    ' ユーザー向けメッセージを組み立て
    fullMessage = "エラーコード: ERR-" & errorCode & vbCrLf & vbCrLf & message

    ' メッセージボックスを表示
    MsgBox fullMessage, vbCritical, "エラー"
End Sub

'===============================================================================
' Azure ADトークンキャッシュ存在確認関数
'===============================================================================
' 【機能】
' PowerShellが使用するトークンキャッシュファイルが存在し、
' 有効期限内かどうかを確認します。
'
' 【戻り値】
' True: キャッシュが存在し有効、False: キャッシュなしまたは無効
'
' 【キャッシュファイルパス】
' %TEMP%\ic-test-azure-ad-token.json
'===============================================================================
Private Function CheckAzureAdTokenCache() As Boolean
    Dim fso As Object
    Dim cachePath As String
    Dim cacheContent As String
    Dim expiresAt As String
    Dim expiresDate As Date

    On Error GoTo ErrorHandler

    ' キャッシュファイルパス（PowerShellスクリプトと同じ）
    cachePath = Environ("TEMP") & "\ic-test-azure-ad-token.json"

    Set fso = CreateObject("Scripting.FileSystemObject")

    ' ファイルが存在しない場合
    If Not fso.FileExists(cachePath) Then
        WriteLog LOG_LEVEL_DEBUG, "CheckAzureAdTokenCache", "キャッシュファイルなし: " & cachePath
        CheckAzureAdTokenCache = False
        Exit Function
    End If

    ' ファイル内容を読み取り
    cacheContent = ReadFromFile(cachePath)

    If cacheContent = "" Then
        WriteLog LOG_LEVEL_DEBUG, "CheckAzureAdTokenCache", "キャッシュファイル空"
        CheckAzureAdTokenCache = False
        Exit Function
    End If

    ' expires_atを抽出（簡易パース）
    expiresAt = ExtractJsonValue(cacheContent, "expires_at")

    If expiresAt = "" Then
        WriteLog LOG_LEVEL_DEBUG, "CheckAzureAdTokenCache", "expires_at未設定"
        CheckAzureAdTokenCache = False
        Exit Function
    End If

    ' 有効期限を解析（ISO 8601形式: 2025-01-15T10:30:45Z）
    ' VBAで簡易パース（日時部分のみ使用）
    On Error Resume Next
    ' "2025-01-15T10:30:45.1234567+00:00" -> "2025-01-15 10:30:45"
    Dim datePart As String
    datePart = Replace(Left(expiresAt, 19), "T", " ")
    expiresDate = CDate(datePart)

    If Err.Number <> 0 Then
        WriteLog LOG_LEVEL_DEBUG, "CheckAzureAdTokenCache", "日時パース失敗: " & expiresAt
        Err.Clear
        On Error GoTo ErrorHandler
        ' パース失敗の場合、refresh_tokenがあればキャッシュ有効とみなす
        If InStr(1, cacheContent, "refresh_token", vbTextCompare) > 0 Then
            WriteLog LOG_LEVEL_INFO, "CheckAzureAdTokenCache", "refresh_tokenあり（日時パース失敗、キャッシュ有効とみなす）"
            CheckAzureAdTokenCache = True
        Else
            CheckAzureAdTokenCache = False
        End If
        Exit Function
    End If
    On Error GoTo ErrorHandler

    ' 有効期限チェック（5分のマージン）
    If expiresDate > DateAdd("n", 5, Now) Then
        WriteLog LOG_LEVEL_INFO, "CheckAzureAdTokenCache", "アクセストークン有効 期限: " & expiresDate
        CheckAzureAdTokenCache = True
    ElseIf InStr(1, cacheContent, "refresh_token", vbTextCompare) > 0 Then
        ' アクセストークンは期限切れだがrefresh_tokenがある
        WriteLog LOG_LEVEL_INFO, "CheckAzureAdTokenCache", "アクセストークン期限切れ、refresh_tokenあり（サイレント更新可能）"
        CheckAzureAdTokenCache = True
    Else
        WriteLog LOG_LEVEL_INFO, "CheckAzureAdTokenCache", "トークン期限切れ、再認証必要"
        CheckAzureAdTokenCache = False
    End If

    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_WARNING, "CheckAzureAdTokenCache", "エラー: " & Err.Description
    CheckAzureAdTokenCache = False
End Function

'===============================================================================
' PowerShellスクリプト呼び出し関数
'===============================================================================
' 【機能】
' CallCloudApi.ps1を実行してクラウドAPIを呼び出します。
' PowerShellを使用することで、複雑なHTTP処理やBase64エンコードを実現します。
'
' 【引数】
' inputPath: 入力JSONファイルのパス
' outputPath: 出力JSONファイルのパス（APIレスポンス保存先）
' config: 設定情報
'
' 【戻り値】
' True: 成功、False: 失敗
'
' 【処理フロー】
' 1. PowerShellスクリプトの存在確認
' 2. コマンドライン引数の組み立て
' 3. PowerShellの実行（同期、非表示ウィンドウ）
' 4. 終了コードの確認
'===============================================================================
Private Function CallPowerShellApi(inputPath As String, outputPath As String, config As SettingConfig) As Boolean
    Dim wsh As Object               ' WScript.Shellオブジェクト
    Dim fso As Object               ' FileSystemObjectオブジェクト
    Dim psCommand As String         ' 実行するPowerShellコマンド
    Dim psScriptPath As String      ' PowerShellスクリプトのパス
    Dim exitCode As Long            ' PowerShellの終了コード
    Dim scriptName As String        ' 使用するスクリプト名

    On Error GoTo ErrorHandler

    WriteLog LOG_LEVEL_DEBUG, "CallPowerShellApi", "API呼び出し開始"

    ' COMオブジェクトの作成
    Set wsh = CreateObject("WScript.Shell")
    Set fso = CreateObject("Scripting.FileSystemObject")

    ' 非同期モードに応じてスクリプトを選択
    If config.AsyncMode Then
        scriptName = "CallCloudApiAsync.ps1"
        WriteLog LOG_LEVEL_INFO, "CallPowerShellApi", "非同期モード: 有効（504タイムアウト対策）"
    Else
        scriptName = "CallCloudApi.ps1"
        WriteLog LOG_LEVEL_INFO, "CallPowerShellApi", "同期モード: 従来方式"
    End If

    ' PowerShellスクリプトのパスを取得
    ' OneDrive環境でもローカルパスに変換
    ' PS1ファイルは scripts/powershell/ に配置
    psScriptPath = GetLocalPath(ThisWorkbook.Path) & "\scripts\powershell\" & scriptName

    WriteLog LOG_LEVEL_DEBUG, "CallPowerShellApi", "スクリプトパス: " & psScriptPath

    ' スクリプトの存在確認
    If Not fso.FileExists(psScriptPath) Then
        WriteLog LOG_LEVEL_ERROR, "CallPowerShellApi", "スクリプトが見つかりません: " & psScriptPath
        ShowErrorMessage ERR_POWERSHELL_SCRIPT_NOT_FOUND, _
                         "PowerShellスクリプトが見つかりません。" & vbCrLf & _
                         "パス: " & psScriptPath & vbCrLf & vbCrLf & _
                         scriptName & "が scripts\powershell\ フォルダにあるか確認してください。"
        CallPowerShellApi = False
        Exit Function
    End If

    ' Azure AD認証の場合、トークンキャッシュを確認して通知
    If LCase(config.ApiAuthType) = "azuread" Then
        ' 初回のみトークンキャッシュを確認
        If Not m_TokenCacheChecked Then
            m_HasCachedToken = CheckAzureAdTokenCache()
            m_TokenCacheChecked = True
            WriteLog LOG_LEVEL_INFO, "CallPowerShellApi", "トークンキャッシュ確認: " & IIf(m_HasCachedToken, "あり（サイレント認証可能）", "なし（初回認証必要）")
        End If

        ' キャッシュがない場合のみ認証案内を表示（1回だけ）
        If Not m_HasCachedToken And Not m_AzureAdNotified Then
            MsgBox "Azure AD認証を開始します。" & vbCrLf & vbCrLf & _
                   "PowerShellウィンドウが表示されたら、" & vbCrLf & _
                   "表示されるURLとコードでブラウザ認証を行ってください。" & vbCrLf & vbCrLf & _
                   "URL: https://microsoft.com/devicelogin" & vbCrLf & _
                   "コードはPowerShellウィンドウに表示されます。" & vbCrLf & vbCrLf & _
                   "※ 認証後はトークンがキャッシュされ、次回以降は自動認証されます。", _
                   vbInformation, "Azure AD認証（初回のみ）"
            m_AzureAdNotified = True
        End If
    End If

    ' PowerShellコマンドの組み立て
    ' -ExecutionPolicy Bypass: 実行ポリシーを一時的にバイパス
    ' -NoProfile: プロファイルを読み込まない（高速化）
    ' -File: スクリプトファイルを指定
    If config.AsyncMode Then
        ' 非同期モード用コマンド（ポーリング間隔を追加）
        psCommand = "powershell.exe -ExecutionPolicy Bypass -NoProfile -File " & _
                    Chr(34) & psScriptPath & Chr(34) & " " & _
                    "-JsonFilePath " & Chr(34) & inputPath & Chr(34) & " " & _
                    "-Endpoint " & Chr(34) & config.ApiEndpoint & Chr(34) & " " & _
                    "-ApiKey " & Chr(34) & config.ApiKey & Chr(34) & " " & _
                    "-OutputFilePath " & Chr(34) & outputPath & Chr(34) & " " & _
                    "-Provider " & Chr(34) & config.ApiProvider & Chr(34) & " " & _
                    "-AuthHeader " & Chr(34) & config.ApiAuthHeader & Chr(34) & " " & _
                    "-PollingIntervalSec " & config.PollingIntervalSec & " " & _
                    "-AuthType " & Chr(34) & config.ApiAuthType & Chr(34)

        ' Azure AD認証パラメータを追加（authType=azureAdの場合）
        If LCase(config.ApiAuthType) = "azuread" Then
            psCommand = psCommand & " " & _
                        "-TenantId " & Chr(34) & config.AzureAdTenantId & Chr(34) & " " & _
                        "-ClientId " & Chr(34) & config.AzureAdClientId & Chr(34) & " " & _
                        "-Scope " & Chr(34) & config.AzureAdScope & Chr(34)
        End If
    Else
        ' 同期モード用コマンド（従来方式）
        psCommand = "powershell.exe -ExecutionPolicy Bypass -NoProfile -File " & _
                    Chr(34) & psScriptPath & Chr(34) & " " & _
                    "-JsonFilePath " & Chr(34) & inputPath & Chr(34) & " " & _
                    "-Endpoint " & Chr(34) & config.ApiEndpoint & Chr(34) & " " & _
                    "-ApiKey " & Chr(34) & config.ApiKey & Chr(34) & " " & _
                    "-OutputFilePath " & Chr(34) & outputPath & Chr(34) & " " & _
                    "-Provider " & Chr(34) & config.ApiProvider & Chr(34) & " " & _
                    "-AuthHeader " & Chr(34) & config.ApiAuthHeader & Chr(34) & " " & _
                    "-AuthType " & Chr(34) & config.ApiAuthType & Chr(34)

        ' Azure AD認証パラメータを追加（authType=azureAdの場合）
        If LCase(config.ApiAuthType) = "azuread" Then
            psCommand = psCommand & " " & _
                        "-TenantId " & Chr(34) & config.AzureAdTenantId & Chr(34) & " " & _
                        "-ClientId " & Chr(34) & config.AzureAdClientId & Chr(34) & " " & _
                        "-Scope " & Chr(34) & config.AzureAdScope & Chr(34)
        End If
    End If

    WriteLog LOG_LEVEL_DEBUG, "CallPowerShellApi", "コマンド実行中..."

    ' PowerShellを同期実行
    ' wsh.Run の引数:
    '   第1引数: コマンド
    '   第2引数: 0 = 非表示, 1 = 通常表示
    '   第3引数: True = 完了まで待機
    '
    ' Azure AD認証の場合、トークンキャッシュの有無でウィンドウ表示を決定
    ' - キャッシュあり: 非表示（サイレント認証）
    ' - キャッシュなし: 表示（Device Code入力のため）
    Dim windowStyle As Integer
    If LCase(config.ApiAuthType) = "azuread" Then
        If m_HasCachedToken Then
            windowStyle = 0  ' 非表示（キャッシュからサイレント認証）
            WriteLog LOG_LEVEL_INFO, "CallPowerShellApi", "Azure AD認証: トークンキャッシュ使用（ウィンドウ非表示）"
        Else
            windowStyle = 1  ' 通常表示（Device Code入力必要）
            WriteLog LOG_LEVEL_INFO, "CallPowerShellApi", "Azure AD認証: 初回認証（ウィンドウ表示）"
            ' 初回認証成功後はキャッシュが作成されるので、次回以降は非表示になる
            m_HasCachedToken = True  ' 楽観的に設定（失敗時は次回再確認される）
        End If
    Else
        windowStyle = 0  ' 非表示
    End If
    exitCode = wsh.Run(psCommand, windowStyle, True)

    WriteLog LOG_LEVEL_DEBUG, "CallPowerShellApi", "終了コード: " & exitCode

    ' 出力ファイルの内容で成功/失敗を判定（終了コードは参考情報）
    ' PowerShellの終了コードはVBAとの組み合わせで信頼できない場合がある
    Dim outputContent As String
    Dim isSuccess As Boolean
    isSuccess = False

    If fso.FileExists(outputPath) Then
        outputContent = ReadFromFile(outputPath)

        ' 出力ファイルに "error": true が含まれているかチェック
        If InStr(1, outputContent, """error"":", vbTextCompare) > 0 And _
           InStr(1, outputContent, "true", vbTextCompare) > 0 Then
            ' エラーレスポンスの場合
            WriteLog LOG_LEVEL_ERROR, "CallPowerShellApi", "APIエラーレスポンス検出"
            WriteLog LOG_LEVEL_ERROR, "CallPowerShellApi", "エラー内容: " & Left(outputContent, 500)
            MsgBox "APIエラー:" & vbCrLf & vbCrLf & _
                   Left(outputContent, 300), vbCritical, "APIエラー"
            isSuccess = False
        ElseIf Len(outputContent) > 0 And Left(Trim(outputContent), 1) = "[" Then
            ' 正常なJSON配列レスポンスの場合
            WriteLog LOG_LEVEL_INFO, "CallPowerShellApi", "正常レスポンス検出（終了コード: " & exitCode & " は無視）"
            isSuccess = True
        Else
            ' 不明なレスポンス
            WriteLog LOG_LEVEL_WARNING, "CallPowerShellApi", "不明なレスポンス形式: " & Left(outputContent, 100)
            isSuccess = False
        End If
    Else
        ' 出力ファイルが存在しない
        WriteLog LOG_LEVEL_ERROR, "CallPowerShellApi", "出力ファイルが作成されませんでした"
        MsgBox "PowerShellエラー (終了コード: " & exitCode & ")" & vbCrLf & vbCrLf & _
               "出力ファイルが作成されませんでした。" & vbCrLf & _
               "スクリプト: " & psScriptPath, vbCritical, "PowerShellエラー"
        isSuccess = False
    End If

    CallPowerShellApi = isSuccess

    WriteLog LOG_LEVEL_DEBUG, "CallPowerShellApi", "API呼び出し完了 - 結果: " & IIf(isSuccess, "成功", "失敗")
    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_CRITICAL, "CallPowerShellApi", "予期しないエラー: " & Err.Description & " (番号: " & Err.Number & ")"
    ShowErrorMessage Err.Number, "PowerShell呼び出し中に予期しないエラーが発生しました。" & vbCrLf & _
                     "エラー: " & Err.Description
    CallPowerShellApi = False
End Function

'===============================================================================
' APIレスポンスをExcelに書き戻す関数
'===============================================================================
' 【機能】
' APIから返されたJSONレスポンスを解析し、対応するExcelセルに値を書き込みます。
'
' 【引数】
' responseJson: APIからのJSONレスポンス文字列
' config: 設定情報（列マッピング等）
'
' 【書き込み対象】
' - 評価結果（Boolean → 有効/不備）
' - 判断根拠（複数行テキスト）
' - 該当文書からの引用（証跡の直接引用文）
' - ファイル名（複数ファイル対応、ハイパーリンク付き）
'
' 【特殊処理】
' - \n は Excelの改行（Chr(10)）に変換
' - 改行を含むセルは自動的に折り返し表示
' - 複数ファイルは右の列に展開
' - ファイル名にはパスへのハイパーリンクを設定
'===============================================================================
Private Sub WriteResponseToExcel(responseJson As String, config As SettingConfig)
    Dim ws As Worksheet               ' 対象ワークシート
    Dim lastRow As Long               ' データの最終行
    Dim rowNum As Long                ' 現在処理中の行番号
    Dim itemId As String              ' 現在の項目ID
    Dim itemJson As String            ' IDに対応するJSONオブジェクト
    Dim boolValue As String           ' Boolean値の文字列
    Dim displayValue As String        ' 表示用の値
    Dim processedCount As Long        ' 処理件数

    WriteLog LOG_LEVEL_DEBUG, "WriteResponseToExcel", "Excel書き戻し開始"

    ' 対象シートの取得
    Set ws = GetTargetWorksheet(config.SheetName)

    If ws Is Nothing Then
        WriteLog LOG_LEVEL_ERROR, "WriteResponseToExcel", "対象シートが見つかりません"
        Exit Sub
    End If

    ' データの最終行を取得
    lastRow = ws.Cells(ws.Rows.Count, config.ColID).End(xlUp).Row
    processedCount = 0

    ' 各行のデータを処理
    For rowNum = config.DataStartRow To lastRow
        ' ID列の値を取得
        itemId = Trim(CStr(ws.Range(config.ColID & rowNum).Value))

        If itemId <> "" Then
            ' このIDに対応するJSONオブジェクトを検索
            itemJson = FindJsonItemById(responseJson, itemId)

            If itemJson <> "" Then
                '--- 評価結果の書き込み ---
                ' Boolean値（true/false）を日本語表示に変換
                If config.ColEvaluationResult <> "" Then
                    boolValue = ExtractJsonBooleanValue(itemJson, "evaluationResult")

                    If boolValue = "true" Then
                        displayValue = config.BooleanDisplayTrue  ' 例: "有効"
                    ElseIf boolValue = "false" Then
                        displayValue = config.BooleanDisplayFalse ' 例: "不備"
                    Else
                        displayValue = boolValue  ' そのまま出力
                    End If

                    ws.Range(config.ColEvaluationResult & rowNum).Value = displayValue
                End If

                '--- 実行計画サマリーの書き込み ---
                ' どのようなタスクを実行したかを表示
                If config.ColExecutionPlanSummary <> "" Then
                    ws.Range(config.ColExecutionPlanSummary & rowNum).Value = _
                        ConvertJsonNewlines(ExtractJsonValue(itemJson, "executionPlanSummary"))
                    ws.Range(config.ColExecutionPlanSummary & rowNum).WrapText = True
                End If

                '--- 判断根拠の書き込み ---
                ' \n を Excel改行に変換し、折り返し表示を有効化
                If config.ColJudgmentBasis <> "" Then
                    ws.Range(config.ColJudgmentBasis & rowNum).Value = _
                        ConvertJsonNewlines(ExtractJsonValue(itemJson, "judgmentBasis"))
                    ws.Range(config.ColJudgmentBasis & rowNum).WrapText = True
                End If

                '--- 該当文書からの引用の書き込み ---
                ' documentReferenceには証跡からの直接引用文が入る
                If config.ColDocumentReference <> "" Then
                    ws.Range(config.ColDocumentReference & rowNum).Value = _
                        ConvertJsonNewlines(ExtractJsonValue(itemJson, "documentReference"))
                    ws.Range(config.ColDocumentReference & rowNum).WrapText = True
                End If

                '--- ファイル名の書き込み（複数ファイル対応・ハイパーリンク付き）---
                If config.ColFileName <> "" Then
                    WriteEvidenceFilesWithLinks ws, rowNum, itemJson, config
                End If

                processedCount = processedCount + 1

                '--- 行高さの自動調整 ---
                ' 出力したセルの内容に合わせて行高さを最適化
                OptimizeRowHeight ws, rowNum, config
            End If
        End If
    Next rowNum

    WriteLog LOG_LEVEL_DEBUG, "WriteResponseToExcel", "Excel書き戻し完了 - " & processedCount & " 件処理"
End Sub

'===============================================================================
' 行高さを最適化する関数
'===============================================================================
' 【機能】
' 出力した行の高さを内容に合わせて自動調整します。
' 各出力列のセルを確認し、適切な行高さを設定します。
'
' 【引数】
' ws: 対象ワークシート
' rowNum: 行番号
' config: 設定情報
'
Private Sub OptimizeRowHeight(ws As Worksheet, rowNum As Long, config As SettingConfig)
    On Error Resume Next

    Dim targetRow As Range
    Dim maxHeight As Double
    Dim cellHeight As Double
    Dim col As String
    Dim cell As Range

    ' 出力列のリスト
    Dim outputCols As Variant
    outputCols = Array( _
        config.ColEvaluationResult, _
        config.ColExecutionPlanSummary, _
        config.ColJudgmentBasis, _
        config.ColDocumentReference, _
        config.ColFileName _
    )

    ' 各出力列の行高さを計算して最大値を取得
    maxHeight = 15 ' デフォルト最小行高さ

    Dim i As Long
    For i = LBound(outputCols) To UBound(outputCols)
        col = outputCols(i)
        If col <> "" Then
            Set cell = ws.Range(col & rowNum)
            If cell.WrapText Then
                ' 折り返しが有効な場合、内容に基づいて高さを計算
                cell.EntireRow.AutoFit
                cellHeight = cell.RowHeight
                If cellHeight > maxHeight Then
                    maxHeight = cellHeight
                End If
            End If
        End If
    Next i

    ' 最大行高さを設定（上限400ポイント）
    If maxHeight > 400 Then maxHeight = 400

    ' 行全体の高さを設定
    ws.Rows(rowNum).RowHeight = maxHeight

    On Error GoTo 0
End Sub

'===============================================================================
' 証跡ファイルをハイパーリンク付きで書き込む関数
'===============================================================================
' 【機能】
' 複数の証跡ファイル名を右の列に展開し、各ファイルパスへのハイパーリンクを設定します。
'
' 【引数】
' ws: 対象ワークシート
' rowNum: 行番号
' itemJson: 項目のJSONデータ
' config: 設定情報
'
' 【処理内容】
' - evidenceFiles配列から各ファイル情報を取得
' - 最初のファイルは設定された列に書き込み
' - 2番目以降のファイルは右隣の列に順次書き込み
' - 各セルにファイルパスへのハイパーリンクを設定
'===============================================================================
Private Sub WriteEvidenceFilesWithLinks(ws As Worksheet, rowNum As Long, itemJson As String, config As SettingConfig)
    Dim evidenceFilesJson As String   ' evidenceFiles配列のJSON
    Dim fileCount As Long             ' ファイル数
    Dim colOffset As Long             ' 列オフセット
    Dim fileName As String            ' ファイル名（ハイライト付き実ファイル名）
    Dim originalFileName As String    ' 元のファイル名（表示用）
    Dim displayName As String         ' セルに表示するファイル名
    Dim base64Content As String       ' Base64エンコードされたファイル内容
    Dim filePath As String            ' ファイルパス
    Dim fullPath As String            ' 完全なファイルパス
    Dim localDir As String            ' ローカル保存先ディレクトリ
    Dim targetCell As Range           ' 書き込み先セル
    Dim baseColNum As Long            ' 基準列番号
    Dim i As Long                     ' ループカウンター
    Dim startPos As Long              ' 検索開始位置
    Dim endPos As Long                ' 検索終了位置
    Dim currentJson As String         ' 現在処理中のJSONオブジェクト

    WriteLog LOG_LEVEL_DEBUG, "WriteEvidenceFilesWithLinks", "証跡ファイル書き込み開始 - 行: " & rowNum

    ' evidenceFiles配列を抽出
    evidenceFilesJson = ExtractJsonArray(itemJson, "evidenceFiles")

    ' 基準列番号を取得（列文字→列番号変換）
    baseColNum = ws.Range(config.ColFileName & "1").Column

    If evidenceFilesJson = "" Or evidenceFilesJson = "[]" Then
        ' evidenceFilesがない場合は従来のfileName値を使用
        fileName = ExtractJsonValue(itemJson, "fileName")
        If fileName <> "" Then
            ws.Range(config.ColFileName & rowNum).Value = fileName
        End If
        Exit Sub
    End If

    ' ローカル保存先ディレクトリを構築（xlsmと同じフォルダのic_audit_highlighted）
    localDir = ThisWorkbook.Path & "\ic_audit_highlighted"

    ' ディレクトリが存在しなければ作成
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FolderExists(localDir) Then
        fso.CreateFolder localDir
        WriteLog LOG_LEVEL_DEBUG, "WriteEvidenceFilesWithLinks", _
                 "ハイライトフォルダ作成: " & localDir
    End If
    Set fso = Nothing

    ' JSON配列内のオブジェクトを順次処理
    colOffset = 0
    startPos = InStr(1, evidenceFilesJson, "{")

    Do While startPos > 0
        ' オブジェクトの終了位置を検索
        endPos = FindMatchingBrace(evidenceFilesJson, startPos)

        If endPos > startPos Then
            currentJson = Mid(evidenceFilesJson, startPos, endPos - startPos + 1)

            ' ファイル名・元ファイル名・パス・Base64を抽出
            fileName = ExtractJsonValue(currentJson, "fileName")
            originalFileName = ExtractJsonValue(currentJson, "originalFileName")
            filePath = ExtractJsonValue(currentJson, "filePath")
            base64Content = ExtractJsonValue(currentJson, "base64")

            WriteLog LOG_LEVEL_INFO, "WriteEvidenceFilesWithLinks", _
                     "ファイル" & (colOffset + 1) & ": " & fileName & _
                     " (originalFileName=" & originalFileName & _
                     ", base64Len=" & Len(base64Content) & _
                     ", filePath=" & Left(filePath, 50) & ")"

            ' 表示名の決定: originalFileNameがあればそれを使用、なければfileNameから推測
            If originalFileName <> "" Then
                displayName = originalFileName
            ElseIf Left(fileName, 12) = "highlighted_" Then
                ' "highlighted_" プレフィックスを除去して元のファイル名を復元
                displayName = Mid(fileName, 13)
            Else
                displayName = fileName
            End If

            If fileName <> "" Then
                ' 書き込み先セルを決定
                Set targetCell = ws.Cells(rowNum, baseColNum + colOffset)

                ' Base64コンテンツがある場合はローカルに保存
                If base64Content <> "" Then
                    fullPath = localDir & "\" & fileName

                    ' Base64デコードしてファイルに保存
                    If DecodeBase64ToFile(base64Content, fullPath) Then
                        ' ハイパーリンクを設定（ローカルファイルへ）
                        On Error Resume Next
                        ws.Hyperlinks.Add _
                            Anchor:=targetCell, _
                            Address:=fullPath, _
                            TextToDisplay:=displayName

                        If Err.Number <> 0 Then
                            Err.Clear
                            targetCell.Value = displayName
                            WriteLog LOG_LEVEL_WARNING, "WriteEvidenceFilesWithLinks", _
                                     "ハイパーリンク設定失敗: " & fullPath
                        Else
                            WriteLog LOG_LEVEL_DEBUG, "WriteEvidenceFilesWithLinks", _
                                     "ハイパーリンク設定: " & displayName & " -> " & fullPath
                        End If
                        On Error GoTo 0
                    Else
                        ' ファイル保存失敗時はテキストのみ
                        targetCell.Value = displayName
                        WriteLog LOG_LEVEL_WARNING, "WriteEvidenceFilesWithLinks", _
                                 "Base64ファイル保存失敗: " & fileName
                    End If

                ElseIf filePath <> "" Then
                    ' Base64がない場合は従来のパスを使用（フォールバック）
                    If Right(filePath, 1) <> "\" Then
                        fullPath = filePath & "\" & fileName
                    Else
                        fullPath = filePath & fileName
                    End If

                    On Error Resume Next
                    ws.Hyperlinks.Add _
                        Anchor:=targetCell, _
                        Address:=fullPath, _
                        TextToDisplay:=displayName

                    If Err.Number <> 0 Then
                        Err.Clear
                        targetCell.Value = displayName
                        WriteLog LOG_LEVEL_WARNING, "WriteEvidenceFilesWithLinks", _
                                 "ハイパーリンク設定失敗: " & fullPath
                    Else
                        WriteLog LOG_LEVEL_DEBUG, "WriteEvidenceFilesWithLinks", _
                                 "ハイパーリンク設定: " & displayName & " -> " & fullPath
                    End If
                    On Error GoTo 0
                Else
                    ' パスもBase64もない場合はファイル名のみ（ハイパーリンクなし）
                    targetCell.Value = displayName
                    WriteLog LOG_LEVEL_WARNING, "WriteEvidenceFilesWithLinks", _
                             "Base64もファイルパスも空のためハイパーリンクなし: " & fileName
                End If

                colOffset = colOffset + 1
            End If
        End If

        ' 次のオブジェクトを検索
        startPos = InStr(endPos + 1, evidenceFilesJson, "{")
    Loop

    WriteLog LOG_LEVEL_DEBUG, "WriteEvidenceFilesWithLinks", _
             "証跡ファイル書き込み完了 - " & colOffset & " ファイル"
End Sub

'===============================================================================
' Base64文字列をファイルにデコード保存する関数
'===============================================================================
' 【機能】
' Base64エンコードされた文字列をデコードし、指定パスにバイナリファイルとして保存します。
' サーバーから返されたハイライト済み証跡ファイルをローカルに保存するために使用します。
'
' 【引数】
' base64Text: Base64エンコードされた文字列
' outputPath: 保存先ファイルパス
'
' 【戻り値】
' Boolean: 成功した場合True
'===============================================================================
Private Function DecodeBase64ToFile(base64Text As String, outputPath As String) As Boolean
    Dim xmlDoc As Object
    Dim xmlNode As Object
    Dim stream As Object

    On Error GoTo ErrorHandler

    If base64Text = "" Then
        DecodeBase64ToFile = False
        Exit Function
    End If

    ' XMLDOMを使用してBase64デコード
    Set xmlDoc = CreateObject("MSXML2.DOMDocument")
    Set xmlNode = xmlDoc.createElement("b64")
    xmlNode.DataType = "bin.base64"
    xmlNode.text = base64Text

    ' バイナリデータをファイルに保存
    Set stream = CreateObject("ADODB.Stream")
    With stream
        .Type = 1  ' バイナリモード
        .Open
        .Write xmlNode.nodeTypedValue
        .SaveToFile outputPath, 2  ' 2 = 上書き保存
        .Close
    End With

    Set stream = Nothing
    Set xmlNode = Nothing
    Set xmlDoc = Nothing

    DecodeBase64ToFile = True
    WriteLog LOG_LEVEL_DEBUG, "DecodeBase64ToFile", "デコード保存完了: " & outputPath

    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_ERROR, "DecodeBase64ToFile", _
             "デコードエラー: " & Err.Description & " - パス: " & outputPath
    DecodeBase64ToFile = False

    On Error Resume Next
    If Not stream Is Nothing Then stream.Close
    Set stream = Nothing
    Set xmlNode = Nothing
    Set xmlDoc = Nothing
    On Error GoTo 0
End Function

'===============================================================================
' JSON配列抽出関数
'===============================================================================
' 【機能】
' JSONオブジェクトから指定されたキーの配列値を抽出します。
'
' 【引数】
' jsonText: JSON文字列
' key: 配列キー名
'
' 【戻り値】
' String: 配列部分のJSON文字列（[...]形式）
'===============================================================================
Private Function ExtractJsonArray(jsonText As String, key As String) As String
    Dim pattern As String
    Dim startPos As Long
    Dim bracketCount As Long
    Dim i As Long
    Dim endPos As Long

    pattern = """" & key & """:"
    startPos = InStr(1, jsonText, pattern, vbTextCompare)

    If startPos = 0 Then
        ExtractJsonArray = ""
        Exit Function
    End If

    ' コロンの後ろに移動
    startPos = startPos + Len(pattern)

    ' 空白をスキップ
    Do While Mid(jsonText, startPos, 1) = " " Or Mid(jsonText, startPos, 1) = vbTab Or _
              Mid(jsonText, startPos, 1) = vbCr Or Mid(jsonText, startPos, 1) = vbLf
        startPos = startPos + 1
    Loop

    ' 配列開始 [ を確認
    If Mid(jsonText, startPos, 1) <> "[" Then
        ExtractJsonArray = ""
        Exit Function
    End If

    ' 配列終了位置を検索
    bracketCount = 0
    For i = startPos To Len(jsonText)
        If Mid(jsonText, i, 1) = "[" Then
            bracketCount = bracketCount + 1
        ElseIf Mid(jsonText, i, 1) = "]" Then
            bracketCount = bracketCount - 1
            If bracketCount = 0 Then
                endPos = i
                Exit For
            End If
        End If
    Next i

    If endPos > startPos Then
        ExtractJsonArray = Mid(jsonText, startPos, endPos - startPos + 1)
    Else
        ExtractJsonArray = ""
    End If
End Function

'===============================================================================
' 対応するブラケット位置検索関数
'===============================================================================
' 【機能】
' JSONオブジェクトの開始 { に対応する終了 } の位置を検索します。
'
' 【引数】
' jsonText: JSON文字列
' startPos: 開始位置（{ の位置）
'
' 【戻り値】
' Long: 対応する } の位置
'===============================================================================
Private Function FindMatchingBrace(jsonText As String, startPos As Long) As Long
    Dim bracketCount As Long
    Dim i As Long

    bracketCount = 0
    For i = startPos To Len(jsonText)
        If Mid(jsonText, i, 1) = "{" Then
            bracketCount = bracketCount + 1
        ElseIf Mid(jsonText, i, 1) = "}" Then
            bracketCount = bracketCount - 1
            If bracketCount = 0 Then
                FindMatchingBrace = i
                Exit Function
            End If
        End If
    Next i

    FindMatchingBrace = 0
End Function

'===============================================================================
' 対象ワークシート取得関数
'===============================================================================
' 【機能】
' 指定された名前のワークシートを取得します。
' 名前が空の場合や見つからない場合はアクティブシートを返します。
'
' 【引数】
' sheetName: シート名（空文字列可）
'
' 【戻り値】
' Worksheet: 対象のワークシート
'===============================================================================
Private Function GetTargetWorksheet(sheetName As String) As Worksheet
    Dim ws As Worksheet

    On Error Resume Next

    If sheetName = "" Then
        ' シート名未指定の場合はアクティブシート
        Set ws = ActiveSheet
    Else
        ' 指定されたシートを取得
        Set ws = ThisWorkbook.Worksheets(sheetName)

        ' 見つからない場合はアクティブシート
        If ws Is Nothing Then
            WriteLog LOG_LEVEL_WARNING, "GetTargetWorksheet", _
                     "シート '" & sheetName & "' が見つからないため、アクティブシートを使用"
            Set ws = ActiveSheet
        End If
    End If

    On Error GoTo 0

    Set GetTargetWorksheet = ws
End Function

'===============================================================================
' JSONからIDでオブジェクトを検索する関数
'===============================================================================
' 【機能】
' JSON配列の中から、指定されたIDを持つオブジェクトを検索して返します。
'
' 【引数】
' jsonText: JSON配列文字列
' targetId: 検索するID値
'
' 【戻り値】
' String: IDに対応するJSONオブジェクト文字列（見つからない場合は空文字列）
'
' 【アルゴリズム】
' 1. "ID": "targetId" のパターンを検索
' 2. 見つかった位置から前方向に { を検索（オブジェクト開始位置）
' 3. ブラケットのネストを考慮して } を検索（オブジェクト終了位置）
'===============================================================================
Private Function FindJsonItemById(jsonText As String, targetId As String) As String
    Dim searchPattern As String       ' 検索パターン
    Dim startPos As Long              ' オブジェクト開始位置
    Dim endPos As Long                ' オブジェクト終了位置
    Dim bracketCount As Long          ' ブラケットネスト数
    Dim i As Long                     ' ループカウンター
    Dim currentChar As String         ' 現在の文字
    Dim checkPos As Long              ' チェック位置
    Dim foundIdKey As Boolean         ' IDキーが見つかったか

    ' ID値を二重引用符で囲んだパターンを作成
    searchPattern = """" & targetId & """"
    startPos = InStr(1, jsonText, searchPattern, vbTextCompare)

    If startPos = 0 Then
        ' IDが見つからない場合
        FindJsonItemById = ""
        Exit Function
    End If

    ' これが本当にIDフィールドの値かを確認
    ' （他のフィールドに同じ値がある可能性があるため）
    foundIdKey = False

    ' 見つかった位置から後方に "ID": があるかチェック
    For checkPos = startPos - 1 To 1 Step -1
        If Mid(jsonText, checkPos, 5) = """ID"":" Or Mid(jsonText, checkPos, 5) = """id"":" Then
            foundIdKey = True
            Exit For
        ElseIf Mid(jsonText, checkPos, 1) = "{" Or Mid(jsonText, checkPos, 1) = "," Then
            Exit For
        End If
    Next checkPos

    ' IDキーでない場合は次の出現を検索
    If Not foundIdKey Then
        startPos = InStr(startPos + 1, jsonText, searchPattern, vbTextCompare)
        If startPos = 0 Then
            FindJsonItemById = ""
            Exit Function
        End If
    End If

    ' オブジェクトの開始位置（{）を後方検索
    For i = startPos To 1 Step -1
        If Mid(jsonText, i, 1) = "{" Then
            startPos = i
            Exit For
        End If
    Next i

    ' オブジェクトの終了位置を検索
    ' ネストされた {} を正しく処理するためブラケット数をカウント
    bracketCount = 0
    For i = startPos To Len(jsonText)
        currentChar = Mid(jsonText, i, 1)

        If currentChar = "{" Then
            bracketCount = bracketCount + 1
        ElseIf currentChar = "}" Then
            bracketCount = bracketCount - 1

            If bracketCount = 0 Then
                ' 対応する } が見つかった
                endPos = i
                Exit For
            End If
        End If
    Next i

    ' オブジェクトを抽出
    If endPos > startPos Then
        FindJsonItemById = Mid(jsonText, startPos, endPos - startPos + 1)
    Else
        FindJsonItemById = ""
    End If
End Function

'===============================================================================
' 設定ファイル読み込み関数
'===============================================================================
' 【機能】
' setting.jsonを読み込み、設定値をSettingConfig構造体に格納します。
'
' 【引数】
' config: 設定値を格納するSettingConfig変数（ByRef）
'
' 【戻り値】
' True: 成功、False: 失敗
'
' 【setting.jsonの構造】
' {
'   "dataStartRow": 2,
'   "sheetName": "",
'   "batchSize": 3,
'   "columns": { "ID": "A", ... },
'   "api": { "provider": "AZURE", "endpoint": "...", ... },
'   "responseMapping": { "evaluationResult": "F", ... },
'   "booleanDisplayTrue": "有効",
'   "booleanDisplayFalse": "不備"
' }
'===============================================================================
Private Function LoadSettings(ByRef config As SettingConfig) As Boolean
    Dim fso As Object                 ' FileSystemObject
    Dim stream As Object              ' ADODB.Stream
    Dim jsonText As String            ' JSON文字列
    Dim settingPath As String         ' setting.jsonのパス
    Dim batchSizeStr As String        ' バッチサイズ文字列

    On Error GoTo ErrorHandler

    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "設定読み込み開始"

    ' setting.jsonのパスを取得（OneDrive対応）
    settingPath = GetLocalPath(ThisWorkbook.Path) & "\setting.json"

    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "設定ファイルパス: " & settingPath

    ' ファイルの存在確認
    Set fso = CreateObject("Scripting.FileSystemObject")

    If Not fso.FileExists(settingPath) Then
        WriteLog LOG_LEVEL_ERROR, "LoadSettings", "設定ファイルが見つかりません: " & settingPath
        MsgBox "設定ファイルが見つかりません:" & vbCrLf & settingPath, vbExclamation, "設定エラー"
        LoadSettings = False
        Exit Function
    End If

    ' UTF-8でファイルを読み込み
    ' ADODB.Streamを使用することで日本語を正しく処理
    Set stream = CreateObject("ADODB.Stream")
    With stream
        .Type = 2         ' テキストモード
        .Charset = "UTF-8"
        .Open
        .LoadFromFile settingPath
        jsonText = .ReadText
        .Close
    End With
    Set stream = Nothing

    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "ファイル読み込み完了 - サイズ: " & Len(jsonText) & " 文字"

    '--- 基本設定の解析 ---
    config.DataStartRow = CLng(ExtractJsonValue(jsonText, "dataStartRow"))
    config.SheetName = ExtractJsonValue(jsonText, "sheetName")

    ' バッチサイズ（デフォルト: 3）
    batchSizeStr = ExtractJsonValue(jsonText, "batchSize")
    If batchSizeStr <> "" And IsNumeric(batchSizeStr) Then
        config.BatchSize = CLng(batchSizeStr)
    Else
        config.BatchSize = 3  ' デフォルト値
    End If

    ' 非同期モード（デフォルト: True - 504タイムアウト対策）
    Dim asyncModeStr As String
    asyncModeStr = LCase(ExtractJsonValue(jsonText, "asyncMode"))
    If asyncModeStr = "true" Or asyncModeStr = "1" Then
        config.AsyncMode = True
    ElseIf asyncModeStr = "false" Or asyncModeStr = "0" Then
        config.AsyncMode = False
    Else
        config.AsyncMode = True  ' デフォルト: 非同期モード有効
    End If

    ' ポーリング間隔（デフォルト: 5秒）
    Dim pollingIntervalStr As String
    pollingIntervalStr = ExtractJsonValue(jsonText, "pollingIntervalSec")
    If pollingIntervalStr <> "" And IsNumeric(pollingIntervalStr) Then
        config.PollingIntervalSec = CLng(pollingIntervalStr)
    Else
        config.PollingIntervalSec = 5  ' デフォルト値
    End If

    '--- 列マッピングの解析 ---
    config.ColID = ExtractNestedJsonValue(jsonText, "columns", "ID")
    config.ColTestTarget = ExtractNestedJsonValue(jsonText, "columns", "TestTarget")
    config.ColCategory = ExtractNestedJsonValue(jsonText, "columns", "Category")
    config.ColControlDescription = ExtractNestedJsonValue(jsonText, "columns", "ControlDescription")
    config.ColTestProcedure = ExtractNestedJsonValue(jsonText, "columns", "TestProcedure")
    config.ColEvidenceLink = ExtractNestedJsonValue(jsonText, "columns", "EvidenceLink")

    '--- API設定の解析 ---
    config.ApiProvider = ExtractNestedJsonValue(jsonText, "api", "provider")
    config.ApiEndpoint = ExtractNestedJsonValue(jsonText, "api", "endpoint")
    config.ApiKey = ExtractNestedJsonValue(jsonText, "api", "apiKey")
    config.ApiAuthHeader = ExtractNestedJsonValue(jsonText, "api", "authHeader")
    config.ApiAuthType = ExtractNestedJsonValue(jsonText, "api", "authType")

    ' プロバイダーのデフォルト値
    If config.ApiProvider = "" Then
        config.ApiProvider = "AZURE"
    End If

    ' 認証タイプのデフォルト値
    If config.ApiAuthType = "" Then
        config.ApiAuthType = "functionsKey"
    End If

    '--- Azure AD認証設定の解析（authType="azureAd"の場合）---
    config.AzureAdTenantId = ExtractNestedJsonValue(jsonText, "azureAd", "tenantId")
    config.AzureAdClientId = ExtractNestedJsonValue(jsonText, "azureAd", "clientId")
    config.AzureAdScope = ExtractNestedJsonValue(jsonText, "azureAd", "scope")

    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "認証タイプ: " & config.ApiAuthType
    If config.ApiAuthType = "azureAd" Then
        WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "Azure AD TenantId: " & Left(config.AzureAdTenantId, 8) & "..."
        WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "Azure AD ClientId: " & Left(config.AzureAdClientId, 8) & "..."
    End If

    ' APIクライアント（POWERSHELL/VBA）
    config.ApiClient = UCase(ExtractJsonValue(jsonText, "apiClient"))
    If config.ApiClient = "" Then
        config.ApiClient = "POWERSHELL"  ' デフォルト: PowerShell
    End If
    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "APIクライアント: " & config.ApiClient

    '--- レスポンスマッピングの解析 ---
    config.ColEvaluationResult = ExtractNestedJsonValue(jsonText, "responseMapping", "evaluationResult")
    config.ColExecutionPlanSummary = ExtractNestedJsonValue(jsonText, "responseMapping", "executionPlanSummary")
    config.ColJudgmentBasis = ExtractNestedJsonValue(jsonText, "responseMapping", "judgmentBasis")
    config.ColDocumentReference = ExtractNestedJsonValue(jsonText, "responseMapping", "documentReference")
    ' evidenceFileNamesまたはfileNameのどちらも対応
    config.ColFileName = ExtractNestedJsonValue(jsonText, "responseMapping", "evidenceFileNames")
    If config.ColFileName = "" Then
        config.ColFileName = ExtractNestedJsonValue(jsonText, "responseMapping", "fileName")
    End If

    '--- Boolean表示設定の解析 ---
    config.BooleanDisplayTrue = ExtractJsonValue(jsonText, "booleanDisplayTrue")
    config.BooleanDisplayFalse = ExtractJsonValue(jsonText, "booleanDisplayFalse")

    ' デフォルト値の設定
    If config.BooleanDisplayTrue = "" Then config.BooleanDisplayTrue = "有効"
    If config.BooleanDisplayFalse = "" Then config.BooleanDisplayFalse = "不備"

    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "設定読み込み完了"
    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "  DataStartRow: " & config.DataStartRow
    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "  BatchSize: " & config.BatchSize
    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "  Provider: " & config.ApiProvider
    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "  AsyncMode: " & config.AsyncMode
    WriteLog LOG_LEVEL_DEBUG, "LoadSettings", "  PollingIntervalSec: " & config.PollingIntervalSec

    LoadSettings = True
    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_CRITICAL, "LoadSettings", "設定読み込みエラー: " & Err.Description & " (番号: " & Err.Number & ")"
    MsgBox "設定ファイルの読み込み中にエラーが発生しました:" & vbCrLf & vbCrLf & _
           "エラー: " & Err.Description & vbCrLf & _
           "番号: " & Err.Number & vbCrLf & _
           "パス: " & settingPath, vbCritical, "設定エラー"
    LoadSettings = False
End Function

'===============================================================================
' JSON値抽出関数
'===============================================================================
' 【機能】
' JSON文字列から指定されたキーの値を抽出します。
' シンプルなJSON解析機能で、外部ライブラリ不要。
'
' 【引数】
' jsonText: JSON文字列
' key: 抽出するキー名
'
' 【戻り値】
' String: キーに対応する値（見つからない場合は空文字列）
'
' 【対応する値の型】
' - 文字列: "key": "value"
' - 数値: "key": 123
' - Boolean: "key": true/false
'
' 【制限事項】
' - 配列やネストしたオブジェクトには対応していません
' - ネストした値を取得するにはExtractNestedJsonValueを使用
'===============================================================================
Private Function ExtractJsonValue(jsonText As String, key As String) As String
    Dim pattern As String             ' 検索パターン
    Dim startPos As Long              ' 値の開始位置
    Dim endPos As Long                ' 値の終了位置
    Dim value As String               ' 抽出した値

    ' 検索パターン: "key":
    pattern = """" & key & """:"
    startPos = InStr(1, jsonText, pattern, vbTextCompare)

    If startPos = 0 Then
        ' キーが見つからない
        ExtractJsonValue = ""
        Exit Function
    End If

    ' コロンの後ろに移動
    startPos = startPos + Len(pattern)

    ' 空白文字をスキップ
    Do While Mid(jsonText, startPos, 1) = " " Or Mid(jsonText, startPos, 1) = vbTab Or _
              Mid(jsonText, startPos, 1) = vbCr Or Mid(jsonText, startPos, 1) = vbLf
        startPos = startPos + 1
    Loop

    ' 値の型を判定して抽出
    If Mid(jsonText, startPos, 1) = """" Then
        ' 文字列値: 次の " まで
        startPos = startPos + 1
        endPos = InStr(startPos, jsonText, """")
        value = Mid(jsonText, startPos, endPos - startPos)
    Else
        ' 数値または Boolean: カンマ、}、改行まで
        endPos = startPos
        Do While Mid(jsonText, endPos, 1) <> "," And Mid(jsonText, endPos, 1) <> "}" And _
                 Mid(jsonText, endPos, 1) <> vbCr And Mid(jsonText, endPos, 1) <> vbLf
            endPos = endPos + 1
        Loop
        value = Trim(Mid(jsonText, startPos, endPos - startPos))
    End If

    ExtractJsonValue = value
End Function

'===============================================================================
' ネストしたJSON値抽出関数
'===============================================================================
' 【機能】
' ネストしたJSONオブジェクトから値を抽出します。
' 例: {"section": {"key": "value"}} から "value" を取得
'
' 【引数】
' jsonText: JSON文字列
' section: セクション名（親オブジェクト名）
' key: 抽出するキー名
'
' 【戻り値】
' String: キーに対応する値
'
' 【使用例】
' setting.jsonの "columns": {"ID": "A"} から "A" を取得:
' ExtractNestedJsonValue(json, "columns", "ID")
'===============================================================================
Private Function ExtractNestedJsonValue(jsonText As String, section As String, key As String) As String
    Dim sectionPattern As String      ' セクション検索パターン
    Dim sectionStart As Long          ' セクション開始位置
    Dim sectionEnd As Long            ' セクション終了位置
    Dim bracketCount As Long          ' ブラケットネスト数
    Dim i As Long                     ' ループカウンター
    Dim sectionJson As String         ' セクション内のJSON

    ' セクションの検索パターン
    sectionPattern = """" & section & """:"
    sectionStart = InStr(1, jsonText, sectionPattern, vbTextCompare)

    If sectionStart = 0 Then
        ' セクションが見つからない
        ExtractNestedJsonValue = ""
        Exit Function
    End If

    ' コロンの後ろに移動
    sectionStart = sectionStart + Len(sectionPattern)

    ' 空白をスキップして { を見つける
    Do While Mid(jsonText, sectionStart, 1) = " " Or Mid(jsonText, sectionStart, 1) = vbTab Or _
              Mid(jsonText, sectionStart, 1) = vbCr Or Mid(jsonText, sectionStart, 1) = vbLf
        sectionStart = sectionStart + 1
    Loop

    ' オブジェクトでない場合は終了
    If Mid(jsonText, sectionStart, 1) <> "{" Then
        ExtractNestedJsonValue = ""
        Exit Function
    End If

    ' セクションの終了位置を検索
    bracketCount = 0
    For i = sectionStart To Len(jsonText)
        If Mid(jsonText, i, 1) = "{" Then
            bracketCount = bracketCount + 1
        ElseIf Mid(jsonText, i, 1) = "}" Then
            bracketCount = bracketCount - 1
            If bracketCount = 0 Then
                sectionEnd = i
                Exit For
            End If
        End If
    Next i

    ' セクションを抽出してキーを検索
    sectionJson = Mid(jsonText, sectionStart, sectionEnd - sectionStart + 1)
    ExtractNestedJsonValue = ExtractJsonValue(sectionJson, key)
End Function

'===============================================================================
' JSON Boolean値抽出関数
'===============================================================================
' 【機能】
' JSONからBoolean値（true/false）を文字列として抽出します。
' 引用符で囲まれていない値を正しく処理します。
'
' 【引数】
' jsonText: JSON文字列
' key: 抽出するキー名
'
' 【戻り値】
' String: "true"、"false"、または空文字列
'===============================================================================
Private Function ExtractJsonBooleanValue(jsonText As String, key As String) As String
    Dim pattern As String
    Dim startPos As Long
    Dim endPos As Long
    Dim value As String

    pattern = """" & key & """:"
    startPos = InStr(1, jsonText, pattern, vbTextCompare)

    If startPos = 0 Then
        ExtractJsonBooleanValue = ""
        Exit Function
    End If

    startPos = startPos + Len(pattern)

    ' 空白をスキップ
    Do While Mid(jsonText, startPos, 1) = " " Or Mid(jsonText, startPos, 1) = vbTab Or _
              Mid(jsonText, startPos, 1) = vbCr Or Mid(jsonText, startPos, 1) = vbLf
        startPos = startPos + 1
    Loop

    ' 値の終端を検索
    endPos = startPos
    Do While Mid(jsonText, endPos, 1) <> "," And Mid(jsonText, endPos, 1) <> "}" And _
             Mid(jsonText, endPos, 1) <> vbCr And Mid(jsonText, endPos, 1) <> vbLf
        endPos = endPos + 1
    Loop

    ' 小文字に変換して返す
    value = Trim(LCase(Mid(jsonText, startPos, endPos - startPos)))
    ExtractJsonBooleanValue = value
End Function

'===============================================================================
' 全データJSON生成関数（非バッチ処理用）
'===============================================================================
' 【機能】
' Excelの全データ行をJSON配列に変換します。
' ※現在はバッチ処理が標準のため、この関数は互換性のために残しています。
'
' 【引数】
' config: 設定情報
'
' 【戻り値】
' String: JSON配列文字列
'===============================================================================
Private Function GenerateJson(config As SettingConfig) As String
    Dim ws As Worksheet
    Dim lastRow As Long
    Dim i As Long
    Dim json As String
    Dim itemJson As String
    Dim isFirst As Boolean

    Set ws = GetTargetWorksheet(config.SheetName)

    lastRow = ws.Cells(ws.Rows.Count, config.ColID).End(xlUp).Row

    json = "[" & vbCrLf
    isFirst = True

    For i = config.DataStartRow To lastRow
        If Trim(CStr(ws.Range(config.ColID & i).Value)) <> "" Then
            If Not isFirst Then
                json = json & "," & vbCrLf
            End If

            itemJson = GenerateItemJson(ws, i, config)
            json = json & itemJson

            isFirst = False
        End If
    Next i

    json = json & vbCrLf & "]"
    GenerateJson = json
End Function

'===============================================================================
' バッチ用JSON生成関数
'===============================================================================
' 【機能】
' 指定された範囲の行データをJSON配列に変換します。
' バッチ処理時に使用し、タイムアウトを防ぎます。
'
' 【引数】
' ws: 対象ワークシート
' rowIndices: データがある行番号の配列
' startIdx: 配列内の開始インデックス
' endIdx: 配列内の終了インデックス
' config: 設定情報
'
' 【戻り値】
' String: JSON配列文字列
'
' 【出力例】
' [
'     {"ID": "1", "ControlDescription": "...", ...},
'     {"ID": "2", "ControlDescription": "...", ...}
' ]
'===============================================================================
Private Function GenerateJsonForBatch(ws As Worksheet, rowIndices() As Long, startIdx As Long, endIdx As Long, config As SettingConfig) As String
    Dim json As String                ' 結果JSON
    Dim itemJson As String            ' 個別項目のJSON
    Dim isFirst As Boolean            ' 最初の項目フラグ
    Dim i As Long                     ' ループカウンター

    json = "[" & vbCrLf
    isFirst = True

    For i = startIdx To endIdx
        If Not isFirst Then
            json = json & "," & vbCrLf
        End If

        ' 行データをJSONオブジェクトに変換
        itemJson = GenerateItemJson(ws, rowIndices(i), config)
        json = json & itemJson

        isFirst = False
    Next i

    json = json & vbCrLf & "]"
    GenerateJsonForBatch = json
End Function

'===============================================================================
' 1行分のJSON生成関数
'===============================================================================
' 【機能】
' Excelの1行分のデータをJSONオブジェクトに変換します。
'
' 【引数】
' ws: 対象ワークシート
' rowNum: 行番号
' config: 設定情報
'
' 【戻り値】
' String: JSONオブジェクト文字列
'
' 【出力例】
' {
'     "ID": "IC-001",
'     "ControlDescription": "経費承認プロセス",
'     "TestProcedure": "承認印を確認する",
'     "EvidenceLink": "C:\Evidence\doc.pdf"
' }
'
' 【特殊文字処理】
' - ダブルクォート → \"
' - 改行 → \n
' - タブ → \t
' - バックスラッシュ → \\
'===============================================================================
Private Function GenerateItemJson(ws As Worksheet, rowNum As Long, config As SettingConfig) As String
    Dim json As String
    Dim indent As String

    indent = "    "  ' 4スペースインデント

    json = indent & "{" & vbCrLf
    json = json & indent & indent & """ID"": """ & EscapeJsonString(CStr(ws.Range(config.ColID & rowNum).Value)) & """," & vbCrLf
    json = json & indent & indent & """ControlDescription"": """ & EscapeJsonString(CStr(ws.Range(config.ColControlDescription & rowNum).Value)) & """," & vbCrLf
    json = json & indent & indent & """TestProcedure"": """ & EscapeJsonString(CStr(ws.Range(config.ColTestProcedure & rowNum).Value)) & """," & vbCrLf
    json = json & indent & indent & """EvidenceLink"": """ & EscapeJsonString(CStr(ws.Range(config.ColEvidenceLink & rowNum).Value)) & """" & vbCrLf
    json = json & indent & "}"

    GenerateItemJson = json
End Function

'===============================================================================
' JSONエスケープ関数
'===============================================================================
' 【機能】
' 文字列をJSON形式に安全にエスケープします。
' JSON仕様で特殊な意味を持つ文字を変換します。
'
' 【引数】
' text: 元の文字列
'
' 【戻り値】
' String: エスケープされた文字列
'
' 【変換ルール】
' \ → \\  （バックスラッシュ）
' " → \"  （ダブルクォート）
' 改行 → \n
' タブ → \t
'===============================================================================
Private Function EscapeJsonString(text As String) As String
    Dim result As String

    result = text

    ' バックスラッシュを最初にエスケープ（他の置換に影響するため）
    result = Replace(result, "\", "\\")

    ' ダブルクォートをエスケープ
    result = Replace(result, """", "\""")

    ' 改行をエスケープ（Windows/Mac/Unix対応）
    result = Replace(result, vbCrLf, "\n")  ' Windows改行
    result = Replace(result, vbCr, "\n")     ' 旧Mac改行
    result = Replace(result, vbLf, "\n")     ' Unix改行

    ' タブをエスケープ
    result = Replace(result, vbTab, "\t")

    EscapeJsonString = result
End Function

'===============================================================================
' ファイル書き込み関数（UTF-8）
'===============================================================================
' 【機能】
' 文字列をUTF-8エンコードでファイルに書き込みます。
' 日本語を正しく保存するためにADODB.Streamを使用。
'
' 【引数】
' filePath: 保存先ファイルパス
' content: 書き込む内容
'
' 【戻り値】
' True: 成功、False: 失敗
'
' 【注意】
' - 既存ファイルは上書きされます
' - BOM（バイトオーダーマーク）は付加されません
'===============================================================================
Private Function WriteToFile(filePath As String, content As String) As Boolean
    Dim stream As Object

    On Error GoTo ErrorHandler

    WriteLog LOG_LEVEL_DEBUG, "WriteToFile", "ファイル書き込み: " & filePath

    Set stream = CreateObject("ADODB.Stream")

    With stream
        .Type = 2         ' テキストモード
        .Charset = "UTF-8"
        .Open
        .WriteText content
        .SaveToFile filePath, 2  ' 2 = 上書き保存
        .Close
    End With

    WriteToFile = True
    WriteLog LOG_LEVEL_DEBUG, "WriteToFile", "書き込み完了 - サイズ: " & Len(content) & " 文字"
    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_ERROR, "WriteToFile", "書き込み失敗: " & Err.Description
    WriteToFile = False
End Function

'===============================================================================
' ファイル読み込み関数（UTF-8）
'===============================================================================
' 【機能】
' UTF-8エンコードのファイルを読み込みます。
'
' 【引数】
' filePath: 読み込むファイルパス
'
' 【戻り値】
' String: ファイル内容（失敗時は空文字列）
'===============================================================================
Private Function ReadFromFile(filePath As String) As String
    Dim stream As Object

    On Error GoTo ErrorHandler

    WriteLog LOG_LEVEL_DEBUG, "ReadFromFile", "ファイル読み込み: " & filePath

    Set stream = CreateObject("ADODB.Stream")

    With stream
        .Type = 2         ' テキストモード
        .Charset = "UTF-8"
        .Open
        .LoadFromFile filePath
        ReadFromFile = .ReadText
        .Close
    End With

    WriteLog LOG_LEVEL_DEBUG, "ReadFromFile", "読み込み完了 - サイズ: " & Len(ReadFromFile) & " 文字"
    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_ERROR, "ReadFromFile", "読み込み失敗: " & Err.Description
    ReadFromFile = ""
End Function

'===============================================================================
' OneDrive URLをローカルパスに変換する関数
'===============================================================================
' 【機能】
' OneDriveの同期によりURLパスになっている場合、ローカルパスに変換します。
' Excel VBAでOneDrive上のファイルを扱う際に必要な処理です。
'
' 【引数】
' urlPath: パス（URLまたはローカルパス）
'
' 【戻り値】
' String: ローカルファイルパス
'
' 【処理フロー】
' 1. httpで始まるか確認
' 2. OneDrive環境変数を取得
' 3. URLをパス部分に分解
' 4. ローカルパスを構築
'
' 【対応する環境変数】
' - OneDrive（個人用）
' - OneDriveConsumer（個人用別名）
' - OneDriveCommercial（ビジネス用）
'===============================================================================
Private Function GetLocalPath(urlPath As String) As String
    Dim localPath As String
    Dim oneDriveEnv As String
    Dim urlParts() As String
    Dim i As Long
    Dim decodedPart As String

    ' 既にローカルパスの場合はそのまま返す
    If Left(urlPath, 4) <> "http" Then
        GetLocalPath = urlPath
        Exit Function
    End If

    WriteLog LOG_LEVEL_DEBUG, "GetLocalPath", "URL変換: " & urlPath

    ' OneDrive環境変数を優先順位で取得
    oneDriveEnv = Environ("OneDrive")
    If oneDriveEnv = "" Then
        oneDriveEnv = Environ("OneDriveConsumer")
    End If
    If oneDriveEnv = "" Then
        oneDriveEnv = Environ("OneDriveCommercial")
    End If

    If oneDriveEnv <> "" Then
        ' URLをパス部分に分解
        urlParts = Split(urlPath, "/")
        localPath = oneDriveEnv

        ' URLの5番目以降がフォルダ/ファイル名
        For i = 4 To UBound(urlParts)
            If urlParts(i) <> "" Then
                decodedPart = UrlDecode(urlParts(i))
                localPath = localPath & "\" & decodedPart
            End If
        Next i

        WriteLog LOG_LEVEL_DEBUG, "GetLocalPath", "ローカルパス: " & localPath
        GetLocalPath = localPath
    Else
        ' OneDriveが見つからない場合は元のパスを返す
        WriteLog LOG_LEVEL_WARNING, "GetLocalPath", "OneDrive環境変数が見つかりません"
        GetLocalPath = urlPath
    End If
End Function

'===============================================================================
' URLデコード関数
'===============================================================================
' 【機能】
' URLエンコードされた文字列（%XX形式）をデコードします。
' 日本語ファイル名などをURLから復元する際に使用。
'
' 【引数】
' encodedStr: URLエンコードされた文字列
'
' 【戻り値】
' String: デコードされた文字列
'
' 【例】
' "%E3%83%86%E3%82%B9%E3%83%88" → "テスト"
'===============================================================================
Private Function UrlDecode(encodedStr As String) As String
    Dim result As String
    Dim i As Long
    Dim hexCode As String

    result = encodedStr
    i = 1

    Do While i <= Len(result)
        If Mid(result, i, 1) = "%" And i + 2 <= Len(result) Then
            hexCode = Mid(result, i + 1, 2)
            On Error Resume Next
            result = Left(result, i - 1) & Chr(CLng("&H" & hexCode)) & Mid(result, i + 3)
            On Error GoTo 0
        End If
        i = i + 1
    Loop

    UrlDecode = result
End Function

'===============================================================================
' JSON改行変換関数
'===============================================================================
' 【機能】
' JSONのエスケープシーケンス（\n, \r, \t）をExcelの制御文字に変換します。
' APIレスポンスをExcelに表示する際に、改行を正しく表示するために使用。
'
' 【引数】
' text: JSONから取得した文字列
'
' 【戻り値】
' String: Excel表示用に変換された文字列
'
' 【変換ルール】
' \n → Chr(10)  Excel改行（LF）
' \r → 削除     キャリッジリターンは不要
' \t → Chr(9)   タブ文字
'
' 【使用場面】
' 判断根拠や文書参照など、複数行のテキストをExcelセルに表示する際
'===============================================================================
Private Function ConvertJsonNewlines(text As String) As String
    Dim result As String

    result = text

    ' \n を Excel改行に変換
    result = Replace(result, "\n", Chr(10))

    ' \r は削除（Excelでは不要）
    result = Replace(result, "\r", "")

    ' \t をタブに変換
    result = Replace(result, "\t", Chr(9))

    ConvertJsonNewlines = result
End Function

'===============================================================================
' 評価結果クリア: ClearEvaluationResults
'===============================================================================
' 【機能】
' API評価結果が書き込まれたセルの内容をクリアします。
' setting.jsonのresponseMappingで指定された列（F〜J列等）をクリアします。
'
' 【処理対象】
' - 評価結果（evaluationResult列）
' - 実行計画サマリー（executionPlanSummary列）
' - 判断根拠（judgmentBasis列）
' - 文書参照（documentReference列）
' - ファイル名（fileName列）
'
' 【使用例】
' Excelのマクロダイアログから「ClearEvaluationResults」を選択して実行
' または、ボタンにこのマクロを割り当てて使用
'===============================================================================
Public Sub ClearEvaluationResults()
    Dim config As SettingConfig
    Dim ws As Worksheet
    Dim lastRow As Long
    Dim clearRange As Range
    Dim colsToClear As String
    Dim i As Long
    Dim confirmMsg As String
    Dim clearedCount As Long

    ' セッション初期化
    InitializeSession
    WriteLog LOG_LEVEL_INFO, "ClearEvaluationResults", "===== 評価結果クリア開始 ====="

    ' 設定ファイルの読み込み
    If Not LoadSettings(config) Then
        ShowErrorMessage ERR_SETTING_NOT_FOUND, "設定ファイルの読み込みに失敗しました。"
        Exit Sub
    End If

    ' 対象シートの取得
    Set ws = GetTargetWorksheet(config.SheetName)
    If ws Is Nothing Then
        ShowErrorMessage ERR_SHEET_NOT_FOUND, "対象シートが見つかりません。"
        Exit Sub
    End If

    ' データの最終行を取得
    lastRow = ws.Cells(ws.Rows.Count, config.ColID).End(xlUp).Row

    If lastRow < config.DataStartRow Then
        MsgBox "クリア対象のデータがありません。", vbInformation, "情報"
        Exit Sub
    End If

    ' 確認メッセージ
    confirmMsg = "以下の列の評価結果をクリアします：" & vbCrLf & vbCrLf
    If config.ColEvaluationResult <> "" Then confirmMsg = confirmMsg & "・評価結果（" & config.ColEvaluationResult & "列）" & vbCrLf
    If config.ColExecutionPlanSummary <> "" Then confirmMsg = confirmMsg & "・実行計画サマリー（" & config.ColExecutionPlanSummary & "列）" & vbCrLf
    If config.ColJudgmentBasis <> "" Then confirmMsg = confirmMsg & "・判断根拠（" & config.ColJudgmentBasis & "列）" & vbCrLf
    If config.ColDocumentReference <> "" Then confirmMsg = confirmMsg & "・文書参照（" & config.ColDocumentReference & "列）" & vbCrLf
    If config.ColFileName <> "" Then confirmMsg = confirmMsg & "・ファイル名（" & config.ColFileName & "列〜）" & vbCrLf
    confirmMsg = confirmMsg & vbCrLf & "対象範囲: " & config.DataStartRow & "行目〜" & lastRow & "行目" & vbCrLf & vbCrLf
    confirmMsg = confirmMsg & "よろしいですか？"

    If MsgBox(confirmMsg, vbYesNo + vbQuestion, "確認") <> vbYes Then
        WriteLog LOG_LEVEL_INFO, "ClearEvaluationResults", "ユーザーによりキャンセル"
        Exit Sub
    End If

    ' 画面更新を一時停止（高速化）
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    On Error GoTo ErrorHandler

    clearedCount = 0

    ' 各列をクリア
    If config.ColEvaluationResult <> "" Then
        ws.Range(config.ColEvaluationResult & config.DataStartRow & ":" & config.ColEvaluationResult & lastRow).ClearContents
        clearedCount = clearedCount + 1
    End If

    If config.ColExecutionPlanSummary <> "" Then
        ws.Range(config.ColExecutionPlanSummary & config.DataStartRow & ":" & config.ColExecutionPlanSummary & lastRow).ClearContents
        clearedCount = clearedCount + 1
    End If

    If config.ColJudgmentBasis <> "" Then
        ws.Range(config.ColJudgmentBasis & config.DataStartRow & ":" & config.ColJudgmentBasis & lastRow).ClearContents
        clearedCount = clearedCount + 1
    End If

    If config.ColDocumentReference <> "" Then
        ws.Range(config.ColDocumentReference & config.DataStartRow & ":" & config.ColDocumentReference & lastRow).ClearContents
        clearedCount = clearedCount + 1
    End If

    ' ファイル名列（複数列に展開される可能性があるため、右側の列も含めてクリア）
    If config.ColFileName <> "" Then
        Dim fileNameColNum As Long
        Dim clearEndCol As Long
        fileNameColNum = ws.Range(config.ColFileName & "1").Column
        ' ファイル名は最大5列まで展開される可能性があるため、5列分クリア
        clearEndCol = fileNameColNum + 4
        ws.Range(ws.Cells(config.DataStartRow, fileNameColNum), ws.Cells(lastRow, clearEndCol)).ClearContents
        ' ハイパーリンクも削除
        On Error Resume Next
        ws.Range(ws.Cells(config.DataStartRow, fileNameColNum), ws.Cells(lastRow, clearEndCol)).Hyperlinks.Delete
        On Error GoTo ErrorHandler
        clearedCount = clearedCount + 1
    End If

    ' 画面更新を再開
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic

    WriteLog LOG_LEVEL_INFO, "ClearEvaluationResults", "===== クリア完了 ===== (" & clearedCount & "列)"

    MsgBox "評価結果をクリアしました。" & vbCrLf & vbCrLf & _
           "クリア列数: " & clearedCount & vbCrLf & _
           "対象行: " & (lastRow - config.DataStartRow + 1) & "行", vbInformation, "完了"

    Exit Sub

ErrorHandler:
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic
    WriteLog LOG_LEVEL_ERROR, "ClearEvaluationResults", "エラー: " & Err.Description
    MsgBox "クリア中にエラーが発生しました:" & vbCrLf & Err.Description, vbCritical, "エラー"
End Sub

'===============================================================================
' API呼び出しラッパー関数
'===============================================================================
' 【機能】
' 設定に基づいてPowerShellまたはVBAネイティブでAPIを呼び出します。
' config.ApiClientが"VBA"の場合はMSXML2.ServerXMLHTTPを使用、
' それ以外（"POWERSHELL"等）はPowerShellスクリプトを使用します。
'
' 【引数】
' inputPath: 入力JSONファイルのパス
' outputPath: 出力JSONファイルのパス
' config: 設定情報
'
' 【戻り値】
' Boolean: 成功した場合True
'===============================================================================
Private Function CallApi(inputPath As String, outputPath As String, config As SettingConfig) As Boolean
    On Error GoTo ErrorHandler

    WriteLog LOG_LEVEL_DEBUG, "CallApi", "API呼び出し開始 - クライアント: " & config.ApiClient

    Select Case UCase(config.ApiClient)
        Case "VBA"
            ' VBAネイティブHTTPクライアントを使用
            CallApi = CallVbaApi(inputPath, outputPath, config)

        Case "EXPORT"
            ' EXPORTモード: ファイル出力のみ（API呼び出しなし）
            ' ProcessForExportから呼び出される想定
            CallApi = True
            WriteLog LOG_LEVEL_INFO, "CallApi", "EXPORTモード: API呼び出しはスキップされました"

        Case Else
            ' PowerShellスクリプトを使用（デフォルト）
            CallApi = CallPowerShellApi(inputPath, outputPath, config)
    End Select

    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_ERROR, "CallApi", "エラー: " & Err.Description
    CallApi = False
End Function

'===============================================================================
' VBAネイティブAPI呼び出し関数
'===============================================================================
' 【機能】
' MSXML2.ServerXMLHTTPを使用してAPIを呼び出します。
' PowerShellが使用できない環境でも動作します。
'
' 【対応モード】
' - 同期モード: /api/evaluate エンドポイントに直接POST
' - 非同期モード: /api/evaluate/submit → polling → /api/evaluate/results
'
' 【引数】
' inputPath: 入力JSONファイルのパス
' outputPath: 出力JSONファイルのパス
' config: 設定情報
'
' 【戻り値】
' Boolean: 成功した場合True
'===============================================================================
Private Function CallVbaApi(inputPath As String, outputPath As String, config As SettingConfig) As Boolean
    Dim http As Object                ' MSXML2.ServerXMLHTTP
    Dim requestJson As String         ' リクエストJSON
    Dim responseText As String        ' レスポンステキスト
    Dim endpoint As String            ' APIエンドポイント
    Dim jobId As String               ' 非同期ジョブID
    Dim statusUrl As String           ' ステータス確認URL
    Dim resultsUrl As String          ' 結果取得URL
    Dim pollCount As Long             ' ポーリング回数
    Dim maxPolls As Long              ' 最大ポーリング回数
    Dim jobStatus As String           ' ジョブステータス

    On Error GoTo ErrorHandler

    WriteLog LOG_LEVEL_INFO, "CallVbaApi", "VBA HTTPクライアントでAPI呼び出し開始"

    ' リクエストJSONを読み込み
    requestJson = ReadFromFile(inputPath)
    If requestJson = "" Then
        WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "入力ファイルが空です: " & inputPath
        CallVbaApi = False
        Exit Function
    End If

    WriteLog LOG_LEVEL_DEBUG, "CallVbaApi", "元のリクエストサイズ: " & Len(requestJson) & " 文字"

    ' EvidenceFilesを追加（フォルダからBase64エンコード）
    WriteLog LOG_LEVEL_INFO, "CallVbaApi", "証跡ファイルをBase64エンコード中..."
    requestJson = AddEvidenceFilesToJson(requestJson)
    WriteLog LOG_LEVEL_DEBUG, "CallVbaApi", "処理後リクエストサイズ: " & Len(requestJson) & " 文字"

    ' HTTPオブジェクト作成
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")

    If config.AsyncMode Then
        '=== 非同期モード ===
        WriteLog LOG_LEVEL_INFO, "CallVbaApi", "非同期モード: 有効"

        ' Step 1: ジョブ投入
        endpoint = config.ApiEndpoint & "/submit"
        WriteLog LOG_LEVEL_DEBUG, "CallVbaApi", "ジョブ投入URL: " & endpoint

        http.Open "POST", endpoint, False
        http.setRequestHeader "Content-Type", "application/json; charset=UTF-8"
        If config.ApiAuthHeader <> "" And config.ApiKey <> "" Then
            http.setRequestHeader config.ApiAuthHeader, config.ApiKey
        End If

        ' タイムアウト設定（30秒）
        http.setTimeouts 30000, 30000, 30000, 30000

        http.send requestJson

        If http.Status <> 200 And http.Status <> 202 Then
            WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "ジョブ投入失敗 - Status: " & http.Status
            WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "Response: " & Left(http.responseText, 500)
            CallVbaApi = False
            Exit Function
        End If

        ' ジョブIDを抽出
        jobId = ExtractJsonValue(http.responseText, "jobId")
        If jobId = "" Then
            jobId = ExtractJsonValue(http.responseText, "job_id")
        End If

        If jobId = "" Then
            WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "ジョブIDが取得できません: " & http.responseText
            CallVbaApi = False
            Exit Function
        End If

        WriteLog LOG_LEVEL_INFO, "CallVbaApi", "ジョブ投入完了 - JobID: " & jobId

        ' Step 2: ステータスポーリング
        statusUrl = config.ApiEndpoint & "/status/" & jobId
        maxPolls = 120  ' 最大10分（5秒×120回）
        pollCount = 0

        Do
            pollCount = pollCount + 1
            WriteLog LOG_LEVEL_DEBUG, "CallVbaApi", "ポーリング " & pollCount & "/" & maxPolls

            ' ステータス更新を画面に表示
            Application.StatusBar = "AI評価処理中... (" & pollCount & "/" & maxPolls & ")"
            DoEvents

            ' 待機
            Sleep config.PollingIntervalSec * 1000

            ' ステータス確認
            http.Open "GET", statusUrl, False
            If config.ApiAuthHeader <> "" And config.ApiKey <> "" Then
                http.setRequestHeader config.ApiAuthHeader, config.ApiKey
            End If
            http.send

            If http.Status <> 200 Then
                WriteLog LOG_LEVEL_WARNING, "CallVbaApi", "ステータス確認失敗 - Status: " & http.Status
                ' 続行（一時的なエラーの可能性）
            Else
                jobStatus = LCase(ExtractJsonValue(http.responseText, "status"))
                WriteLog LOG_LEVEL_DEBUG, "CallVbaApi", "ジョブステータス: " & jobStatus

                If jobStatus = "completed" Then
                    Exit Do
                ElseIf jobStatus = "error" Or jobStatus = "failed" Then
                    WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "ジョブ失敗: " & http.responseText
                    ' エラーレスポンスを出力ファイルに書き込み
                    Call WriteToFileUtf8(outputPath, http.responseText)
                    CallVbaApi = False
                    Application.StatusBar = False
                    Exit Function
                End If
            End If

        Loop While pollCount < maxPolls

        Application.StatusBar = False

        If pollCount >= maxPolls Then
            WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "ポーリングタイムアウト"
            CallVbaApi = False
            Exit Function
        End If

        ' Step 3: 結果取得
        resultsUrl = config.ApiEndpoint & "/results/" & jobId
        WriteLog LOG_LEVEL_DEBUG, "CallVbaApi", "結果取得URL: " & resultsUrl

        http.Open "GET", resultsUrl, False
        If config.ApiAuthHeader <> "" And config.ApiKey <> "" Then
            http.setRequestHeader config.ApiAuthHeader, config.ApiKey
        End If
        http.send

        If http.Status <> 200 Then
            WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "結果取得失敗 - Status: " & http.Status
            CallVbaApi = False
            Exit Function
        End If

        responseText = http.responseText

    Else
        '=== 同期モード ===
        WriteLog LOG_LEVEL_INFO, "CallVbaApi", "同期モード: 従来方式"

        endpoint = config.ApiEndpoint
        WriteLog LOG_LEVEL_DEBUG, "CallVbaApi", "エンドポイント: " & endpoint

        http.Open "POST", endpoint, False
        http.setRequestHeader "Content-Type", "application/json; charset=UTF-8"
        If config.ApiAuthHeader <> "" And config.ApiKey <> "" Then
            http.setRequestHeader config.ApiAuthHeader, config.ApiKey
        End If

        ' タイムアウト設定（10分）
        http.setTimeouts 60000, 60000, 600000, 600000

        Application.StatusBar = "AI評価処理中..."
        DoEvents

        http.send requestJson

        Application.StatusBar = False

        If http.Status <> 200 Then
            WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "API呼び出し失敗 - Status: " & http.Status
            WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "Response: " & Left(http.responseText, 500)
            ' エラーレスポンスを出力ファイルに書き込み
            Call WriteToFileUtf8(outputPath, http.responseText)
            CallVbaApi = False
            Exit Function
        End If

        responseText = http.responseText
    End If

    ' レスポンスを出力ファイルに保存
    WriteLog LOG_LEVEL_DEBUG, "CallVbaApi", "レスポンスサイズ: " & Len(responseText) & " 文字"
    Call WriteToFileUtf8(outputPath, responseText)

    ' レスポンス検証
    If InStr(1, responseText, """error"":", vbTextCompare) > 0 And _
       InStr(1, responseText, "true", vbTextCompare) > 0 Then
        WriteLog LOG_LEVEL_ERROR, "CallVbaApi", "APIエラーレスポンス検出"
        CallVbaApi = False
    ElseIf Len(responseText) > 0 And Left(Trim(responseText), 1) = "[" Then
        WriteLog LOG_LEVEL_INFO, "CallVbaApi", "正常レスポンス検出"
        CallVbaApi = True
    Else
        WriteLog LOG_LEVEL_WARNING, "CallVbaApi", "不明なレスポンス形式"
        CallVbaApi = False
    End If

    Set http = Nothing
    Exit Function

ErrorHandler:
    Application.StatusBar = False
    WriteLog LOG_LEVEL_CRITICAL, "CallVbaApi", "予期しないエラー: " & Err.Description & " (番号: " & Err.Number & ")"
    If Not http Is Nothing Then Set http = Nothing
    CallVbaApi = False
End Function

'===============================================================================
' UTF-8でファイルに書き込む関数
'===============================================================================
' 【機能】
' 文字列をUTF-8エンコーディングでファイルに書き込みます。
' 日本語を正しく処理するためADODB.Streamを使用します。
'
' 【引数】
' filePath: 出力ファイルのパス
' content: 書き込む内容
'===============================================================================
Private Sub WriteToFileUtf8(filePath As String, content As String)
    Dim stream As Object

    On Error GoTo ErrorHandler

    Set stream = CreateObject("ADODB.Stream")
    With stream
        .Type = 2         ' テキストモード
        .Charset = "UTF-8"
        .Open
        .WriteText content
        .SaveToFile filePath, 2  ' 2 = 上書き
        .Close
    End With

    Set stream = Nothing
    Exit Sub

ErrorHandler:
    WriteLog LOG_LEVEL_ERROR, "WriteToFileUtf8", "ファイル書き込みエラー: " & Err.Description
    If Not stream Is Nothing Then
        On Error Resume Next
        stream.Close
        Set stream = Nothing
    End If
End Sub

'===============================================================================
' ファイルをBase64エンコード
'===============================================================================
' 【機能】
' バイナリファイルをBase64文字列に変換します。
' ADODB.Streamを使用してファイルを読み込み、XMLDOMを使用してBase64変換します。
'
' 【引数】
' filePath: ファイルパス
'
' 【戻り値】
' String: Base64エンコードされた文字列（エラー時は空文字列）
'===============================================================================
Private Function EncodeFileToBase64(filePath As String) As String
    Dim fso As Object
    Dim stream As Object
    Dim xmlDoc As Object
    Dim xmlNode As Object
    Dim bytes() As Byte

    On Error GoTo ErrorHandler

    Set fso = CreateObject("Scripting.FileSystemObject")

    If Not fso.FileExists(filePath) Then
        WriteLog LOG_LEVEL_WARNING, "EncodeFileToBase64", "ファイルが見つかりません: " & filePath
        EncodeFileToBase64 = ""
        Exit Function
    End If

    ' バイナリファイルを読み込み
    Set stream = CreateObject("ADODB.Stream")
    With stream
        .Type = 1  ' バイナリモード
        .Open
        .LoadFromFile filePath
        bytes = .Read
        .Close
    End With

    ' XMLDOMを使用してBase64変換
    Set xmlDoc = CreateObject("MSXML2.DOMDocument")
    Set xmlNode = xmlDoc.createElement("b64")
    xmlNode.DataType = "bin.base64"
    xmlNode.nodeTypedValue = bytes

    EncodeFileToBase64 = xmlNode.text

    Set xmlNode = Nothing
    Set xmlDoc = Nothing
    Set stream = Nothing
    Set fso = Nothing

    WriteLog LOG_LEVEL_DEBUG, "EncodeFileToBase64", "エンコード完了: " & filePath & " (" & Len(EncodeFileToBase64) & " 文字)"

    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_ERROR, "EncodeFileToBase64", "エラー: " & Err.Description & " - ファイル: " & filePath
    EncodeFileToBase64 = ""
End Function

'===============================================================================
' フォルダ内のファイルをBase64配列JSONに変換
'===============================================================================
' 【機能】
' 指定フォルダ内の全ファイルをBase64エンコードし、EvidenceFiles形式のJSON配列を生成します。
'
' 【引数】
' folderPath: フォルダパス
'
' 【戻り値】
' String: EvidenceFiles JSON配列（例: [{"fileName":"doc.pdf","mimeType":"application/pdf","extension":".pdf","base64":"..."}]）
'===============================================================================
Private Function GetFolderFilesAsBase64Json(folderPath As String) As String
    Dim fso As Object
    Dim folder As Object
    Dim file As Object
    Dim json As String
    Dim isFirst As Boolean
    Dim base64Content As String
    Dim mimeType As String
    Dim ext As String

    On Error GoTo ErrorHandler

    Set fso = CreateObject("Scripting.FileSystemObject")

    If Not fso.FolderExists(folderPath) Then
        WriteLog LOG_LEVEL_DEBUG, "GetFolderFilesAsBase64Json", "フォルダが存在しません: " & folderPath
        GetFolderFilesAsBase64Json = "[]"
        Exit Function
    End If

    Set folder = fso.GetFolder(folderPath)

    json = "["
    isFirst = True

    For Each file In folder.Files
        ext = LCase(fso.GetExtensionName(file.Name))

        ' 対応ファイル形式のみ処理
        If ext = "pdf" Or ext = "png" Or ext = "jpg" Or ext = "jpeg" Or ext = "gif" Or ext = "xlsx" Or ext = "docx" Then
            base64Content = EncodeFileToBase64(file.Path)

            If base64Content <> "" Then
                If Not isFirst Then
                    json = json & ","
                End If

                ' MIMEタイプの決定
                Select Case ext
                    Case "pdf"
                        mimeType = "application/pdf"
                    Case "png"
                        mimeType = "image/png"
                    Case "jpg", "jpeg"
                        mimeType = "image/jpeg"
                    Case "gif"
                        mimeType = "image/gif"
                    Case "xlsx"
                        mimeType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    Case "docx"
                        mimeType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    Case Else
                        mimeType = "application/octet-stream"
                End Select

                json = json & "{" & _
                       """fileName"":""" & EscapeJsonString(file.Name) & """," & _
                       """mimeType"":""" & mimeType & """," & _
                       """extension"":""." & ext & """," & _
                       """base64"":""" & base64Content & """" & _
                       "}"

                isFirst = False

                WriteLog LOG_LEVEL_DEBUG, "GetFolderFilesAsBase64Json", "ファイル追加: " & file.Name
            End If
        End If
    Next file

    json = json & "]"
    GetFolderFilesAsBase64Json = json

    WriteLog LOG_LEVEL_DEBUG, "GetFolderFilesAsBase64Json", "JSON生成完了: " & Len(json) & " 文字"

    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_ERROR, "GetFolderFilesAsBase64Json", "エラー: " & Err.Description
    GetFolderFilesAsBase64Json = "[]"
End Function

'===============================================================================
' VBA用JSON処理: EvidenceFilesを追加
'===============================================================================
' 【機能】
' JSON文字列内の各アイテムにEvidenceFiles配列を追加します。
' EvidenceLinkがフォルダパスの場合、フォルダ内のファイルをBase64エンコードして追加。
'
' 【引数】
' jsonText: 元のJSON文字列
'
' 【戻り値】
' String: EvidenceFilesが追加されたJSON文字列
'===============================================================================
Private Function AddEvidenceFilesToJson(jsonText As String) As String
    Dim fso As Object
    Dim result As String
    Dim itemStart As Long
    Dim itemEnd As Long
    Dim evidenceLinkStart As Long
    Dim evidenceLinkEnd As Long
    Dim evidenceLink As String
    Dim evidenceFilesJson As String
    Dim insertPos As Long

    On Error GoTo ErrorHandler

    Set fso = CreateObject("Scripting.FileSystemObject")

    result = jsonText
    itemStart = 1

    ' 各アイテムを処理
    Do
        ' 次のアイテム（{）を探す
        itemStart = InStr(itemStart, result, "{")
        If itemStart = 0 Then Exit Do

        itemEnd = FindMatchingBrace(result, itemStart)
        If itemEnd = 0 Then Exit Do

        ' EvidenceLinkを抽出
        evidenceLink = ExtractJsonValueFromSubstring(result, itemStart, itemEnd, "EvidenceLink")

        If evidenceLink <> "" Then
            ' パスをローカルパスに変換
            evidenceLink = GetLocalPath(evidenceLink)

            ' フォルダが存在するか確認
            If fso.FolderExists(evidenceLink) Then
                WriteLog LOG_LEVEL_DEBUG, "AddEvidenceFilesToJson", "フォルダ処理: " & evidenceLink

                ' フォルダ内のファイルをBase64 JSONに変換
                evidenceFilesJson = GetFolderFilesAsBase64Json(evidenceLink)

                ' EvidenceFilesがない場合は既存のものを使用
                If evidenceFilesJson <> "[]" Then
                    ' アイテムの閉じ括弧の前にEvidenceFilesを挿入
                    ' まず、EvidenceLinkの行の終わりを見つける
                    insertPos = InStrRev(result, """EvidenceLink""", itemEnd)
                    If insertPos > itemStart Then
                        ' EvidenceLink行の末尾（改行前）を見つける
                        Dim lineEnd As Long
                        lineEnd = InStr(insertPos, result, vbCrLf)
                        If lineEnd = 0 Then lineEnd = InStr(insertPos, result, vbLf)
                        If lineEnd = 0 Then lineEnd = itemEnd

                        ' 改行の前にカンマとEvidenceFilesを挿入
                        Dim insertText As String
                        insertText = "," & vbCrLf & "        ""EvidenceFiles"": " & evidenceFilesJson

                        ' 挿入位置を調整（"で終わる行の後）
                        Dim quotePos As Long
                        quotePos = InStr(insertPos + Len("""EvidenceLink"": """), result, """")
                        If quotePos > 0 And quotePos < lineEnd Then
                            result = Left(result, quotePos) & insertText & Mid(result, quotePos + 1)
                            ' itemEndを更新
                            itemEnd = itemEnd + Len(insertText)
                        End If
                    End If
                End If
            Else
                WriteLog LOG_LEVEL_DEBUG, "AddEvidenceFilesToJson", "フォルダ無し: " & evidenceLink
            End If
        End If

        itemStart = itemEnd + 1
    Loop

    AddEvidenceFilesToJson = result

    Set fso = Nothing
    Exit Function

ErrorHandler:
    WriteLog LOG_LEVEL_ERROR, "AddEvidenceFilesToJson", "エラー: " & Err.Description
    AddEvidenceFilesToJson = jsonText  ' エラー時は元のJSONを返す
End Function

'===============================================================================
' 部分文字列からJSON値を抽出
'===============================================================================
Private Function ExtractJsonValueFromSubstring(jsonText As String, startPos As Long, endPos As Long, key As String) As String
    Dim subJson As String
    subJson = Mid(jsonText, startPos, endPos - startPos + 1)
    ExtractJsonValueFromSubstring = ExtractJsonValue(subJson, key)
End Function
