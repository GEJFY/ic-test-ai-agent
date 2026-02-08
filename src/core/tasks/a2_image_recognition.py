"""
================================================================================
a2_image_recognition.py - A2: 画像認識 + 情報抽出タスク
================================================================================

【概要】
PDFや画像ファイルから承認印、日付、署名などの視覚情報を抽出・検証する
タスクです。Vision対応LLMを使用して画像分析を行います。

【主な機能】
- 承認印（印影）の検出と内容の読み取り
- 日付（作成日、承認日）の抽出
- 署名・氏名の識別
- 承認者の役職・権限の確認
- 文書番号・管理番号の抽出

【対応ファイル形式】
- 画像: .jpg, .jpeg, .png, .gif, .bmp, .webp
- 文書: .pdf

【使用例】
```python
from core.tasks.a2_image_recognition import ImageRecognitionTask
from core.tasks.base_task import AuditContext

# タスクを初期化（Vision対応LLMが必要）
task = ImageRecognitionTask(llm=llm, vision_llm=vision_llm)

# 評価を実行
result = await task.execute(context)

# 結果を確認
if result.success:
    print("承認印の確認: OK")
    print(result.result["extracted_info"]["approval_stamps"])
```

【処理フロー】
1. 証跡ファイルから画像/PDFをフィルタリング
2. 各ファイルをVision LLMで分析
3. 承認印・日付・署名等を抽出
4. 検証結果を集約して返却

================================================================================
"""
import logging
import base64
from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser

from .base_task import BaseAuditTask, TaskType, TaskResult, AuditContext, EvidenceFile

# プロンプトをprompts.pyからインポート
from ..prompts import A2_IMAGE_RECOGNITION_PROMPT

# =============================================================================
# ログ設定
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# メインクラス: ImageRecognitionTask
# =============================================================================

class ImageRecognitionTask(BaseAuditTask):
    """
    A2: 画像認識 + 情報抽出タスク

    PDFや画像ファイルから承認印、日付、署名などの視覚情報を
    Vision LLMを使用して抽出・検証します。

    【主な機能】
    - 承認印（印影）の検出
    - 日付の抽出と整合性確認
    - 署名・氏名の識別
    - 承認権限の評価

    【処理フロー】
    1. 処理可能なファイル（画像/PDF）をフィルタリング
    2. 各ファイルをVision LLMで分析
    3. 抽出結果を集約
    4. 承認の有効性を判定

    Attributes:
        vision_llm: Vision対応のLangChain ChatModel
        parser: JSON出力パーサー
        SUPPORTED_IMAGE_TYPES: 対応画像拡張子
        SUPPORTED_DOC_TYPES: 対応文書拡張子

    使用例:
        ```python
        task = ImageRecognitionTask(llm=llm, vision_llm=vision_llm)
        result = await task.execute(context)
        ```
    """

    # タスク識別情報
    task_type = TaskType.A2_IMAGE_RECOGNITION
    task_name = "画像認識 + 情報抽出"
    description = "PDFや画像から承認印、日付、氏名を自動読み取りし、権限の有効性を確認"

    # 対応ファイル形式
    SUPPORTED_IMAGE_TYPES = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    SUPPORTED_DOC_TYPES = ['.pdf']

    def __init__(self, llm=None, vision_llm=None):
        """
        タスクを初期化

        Args:
            llm: テキスト処理用のLangChain ChatModel
            vision_llm: 画像処理用のVision対応ChatModel
                        Noneの場合はllmを使用
        """
        super().__init__(llm)
        self.vision_llm = vision_llm or llm
        self.parser = JsonOutputParser()

        logger.debug("[A2] ImageRecognitionTask初期化完了")

    async def execute(self, context: AuditContext) -> TaskResult:
        """
        画像認識タスクを実行

        証跡ファイルから画像/PDFを抽出し、承認印・日付・署名等を
        Vision LLMで認識・検証します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            TaskResult: タスク実行結果
                - success: 有効な承認が確認できた場合True
                - result: 抽出情報と検証結果
                - reasoning: 分析結果の説明
                - confidence: 信頼度

        Note:
            - Vision LLMが未設定の場合は失敗を返します
            - 複数ファイルがある場合は全て分析して集約します
        """
        logger.info(f"[A2] 画像認識開始: {context.item_id}")

        # Vision LLMの確認
        if not self.vision_llm:
            logger.warning("[A2] Vision LLMが設定されていません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="Vision LLMが設定されていません",
                confidence=0.0
            )

        # 処理可能なファイルを抽出
        image_files = self._get_processable_files(context.evidence_files)

        if not image_files:
            logger.warning("[A2] 処理可能な画像/PDFファイルがありません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="処理可能な画像/PDFファイルが見つかりませんでした",
                confidence=0.0
            )

        logger.info(f"[A2] 処理対象ファイル: {len(image_files)}件")

        try:
            # 各ファイルを分析
            all_results = []

            for ef in image_files:
                logger.info(f"[A2] 分析中: {ef.file_name}")
                result = await self._analyze_image(ef, context.test_procedure)

                if result:
                    all_results.append({
                        "file_name": ef.file_name,
                        "analysis": result
                    })
                    logger.debug(f"[A2] {ef.file_name}: 分析完了")

            # 結果を集約
            aggregated = self._aggregate_results(all_results)

            has_valid_approval = aggregated.get("validation_results", {}).get("has_valid_approval", False)
            logger.info(f"[A2] 完了: 承認印の有効性 = {'確認済み' if has_valid_approval else '未確認'}")

            return self._create_result(
                success=has_valid_approval,
                result=aggregated,
                reasoning=aggregated.get("reasoning", ""),
                confidence=aggregated.get("confidence", 0.0),
                evidence_refs=[ef.file_name for ef in image_files]
            )

        except Exception as e:
            logger.error(f"[A2] 画像認識エラー: {e}", exc_info=True)
            return self._create_result(
                success=False,
                result=None,
                reasoning=f"画像認識中にエラーが発生: {str(e)}",
                confidence=0.0
            )

    def _get_processable_files(self, evidence_files: List[EvidenceFile]) -> List[EvidenceFile]:
        """
        処理可能なファイルをフィルタリング

        画像ファイルとPDFファイルのみを抽出します。

        Args:
            evidence_files (List[EvidenceFile]): 証跡ファイルリスト

        Returns:
            List[EvidenceFile]: 処理可能なファイルのリスト
        """
        processable = []

        for ef in evidence_files:
            ext = ef.extension.lower()
            if ext in self.SUPPORTED_IMAGE_TYPES or ext in self.SUPPORTED_DOC_TYPES:
                processable.append(ef)
                logger.debug(f"[A2] 対象ファイル追加: {ef.file_name} ({ext})")

        return processable

    async def _analyze_image(self, evidence_file: EvidenceFile, test_procedure: str) -> Optional[dict]:
        """
        単一の画像ファイルを分析

        Vision LLMを使用して画像から承認印・日付・署名等を抽出します。

        Args:
            evidence_file (EvidenceFile): 証跡ファイル
            test_procedure (str): テスト手続き

        Returns:
            Optional[dict]: 分析結果
                - extracted_info: 抽出された情報
                - validation_results: 検証結果
                - confidence: 信頼度
                - reasoning: 分析説明
        """
        try:
            # MIMEタイプを決定
            mime_type = evidence_file.mime_type
            if not mime_type:
                ext_to_mime = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp',
                    '.pdf': 'application/pdf',
                }
                mime_type = ext_to_mime.get(evidence_file.extension.lower(), 'image/jpeg')

            logger.debug(f"[A2] {evidence_file.file_name}: MIMEタイプ = {mime_type}")

            # Vision LLM用のメッセージを作成
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": A2_IMAGE_RECOGNITION_PROMPT.format(test_procedure=test_procedure)
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{evidence_file.base64_content}"
                        }
                    }
                ]
            )

            # Vision LLMで分析
            response = await self.vision_llm.ainvoke([message])

            # JSONをパース
            result = self.parser.parse(response.content)
            logger.debug(f"[A2] {evidence_file.file_name}: 分析結果を取得")

            return result

        except Exception as e:
            logger.error(f"[A2] {evidence_file.file_name}: 分析エラー - {e}")
            return {
                "error": str(e),
                "file_name": evidence_file.file_name
            }

    def _aggregate_results(self, results: List[dict]) -> dict:
        """
        複数ファイルの分析結果を集約

        各ファイルの分析結果を統合し、全体の検証結果を生成します。

        Args:
            results (List[dict]): 各ファイルの分析結果

        Returns:
            dict: 集約された分析結果
                - extracted_info: 全ファイルから抽出された情報
                - validation_results: 統合された検証結果
                - confidence: 平均信頼度
                - reasoning: 分析サマリー
        """
        if not results:
            logger.warning("[A2] 集約する分析結果がありません")
            return {
                "validation_results": {"has_valid_approval": False},
                "confidence": 0.0,
                "reasoning": "分析結果がありません"
            }

        # 抽出情報を統合
        all_stamps = []
        all_dates = []
        all_names = []
        all_doc_numbers = []
        has_valid_approval = False
        total_confidence = 0.0
        analyzed_count = 0

        for r in results:
            analysis = r.get("analysis", {})

            # エラーがあった場合はスキップ
            if "error" in analysis:
                logger.warning(f"[A2] スキップ: {r.get('file_name', 'unknown')} - {analysis.get('error')}")
                continue

            analyzed_count += 1

            # 抽出情報を追加
            extracted = analysis.get("extracted_info", {})
            all_stamps.extend(extracted.get("approval_stamps", []))
            all_dates.extend(extracted.get("dates", []))
            all_names.extend(extracted.get("names", []))
            all_doc_numbers.extend(extracted.get("document_numbers", []))

            # 検証結果を確認
            validation = analysis.get("validation_results", {})
            if validation.get("has_valid_approval"):
                has_valid_approval = True

            total_confidence += analysis.get("confidence", 0.0)

        # 平均信頼度を計算
        avg_confidence = total_confidence / analyzed_count if analyzed_count > 0 else 0.0

        # 検出された承認印の数
        detected_stamps = [s for s in all_stamps if s.get("detected", False)]

        logger.info(f"[A2] 集約完了: {analyzed_count}件分析, "
                   f"承認印{len(detected_stamps)}件検出, "
                   f"日付{len(all_dates)}件, "
                   f"氏名{len(all_names)}件")

        return {
            "extracted_info": {
                "approval_stamps": all_stamps,
                "dates": all_dates,
                "names": all_names,
                "document_numbers": all_doc_numbers
            },
            "validation_results": {
                "has_valid_approval": has_valid_approval,
                "files_analyzed": analyzed_count
            },
            "confidence": avg_confidence,
            "reasoning": (
                f"{analyzed_count}件のファイルを分析。"
                f"承認印: {len(detected_stamps)}件検出。"
                f"承認の有効性: {'確認済み' if has_valid_approval else '未確認'}。"
            )
        }
