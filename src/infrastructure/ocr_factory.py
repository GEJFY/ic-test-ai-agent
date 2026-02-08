# -*- coding: utf-8 -*-
"""
================================================================================
ocr_factory.py - OCRファクトリー（マルチプロバイダー対応）
================================================================================

【概要】
このモジュールは、複数のOCRプロバイダーに対応した
OCRクライアント生成ファクトリーを提供します。

環境変数の設定に基づいて適切なプロバイダーのOCRエンジンを
自動的に選択・作成します。

【設計思想】
- ファクトリーパターン: 利用者はプロバイダーの違いを意識しない
- 抽象化: 共通インターフェース(BaseOCRClient)で統一
- フォールバック: OCR無効時はpypdfでテキスト抽出

【対応プロバイダー】
┌─────────────────┬────────────────────────────────────────────────┐
│ プロバイダー    │ 説明                                           │
├─────────────────┼────────────────────────────────────────────────┤
│ AZURE           │ Azure Document Intelligence（高精度、日本語◎）│
│ AWS             │ Amazon Textract（表抽出に強い）                │
│ GCP             │ Google Cloud Document AI（多言語対応）         │
│ TESSERACT       │ Tesseract OCR（OSS、ローカル実行）             │
│ NONE            │ OCR無効（pypdfフォールバック）                 │
└─────────────────┴────────────────────────────────────────────────┘

【使用例】
```python
from infrastructure.ocr_factory import OCRFactory

# OCRクライアントを取得
ocr = OCRFactory.get_ocr_client()

# OCRを実行
result = ocr.extract_text(file_bytes, mime_type="application/pdf")
print(result.text_content)

# 設定状態を確認
status = OCRFactory.get_config_status()
print(f"プロバイダー: {status['provider']}")
```

【環境変数の設定例】
```bash
# Azure Document Intelligence の場合
export OCR_PROVIDER=AZURE
export AZURE_DI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
export AZURE_DI_KEY=your-key

# Tesseract の場合
export OCR_PROVIDER=TESSERACT
export TESSERACT_LANG=jpn+eng
```

【注意事項】
- OCR_PROVIDER=NONEの場合、画像内テキストは抽出できません
- 大きなPDFファイルは処理に時間がかかります
- クラウドOCRはネットワーク遅延の影響を受けます

================================================================================
"""

import os
import time
import traceback
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, field

# =============================================================================
# ログ設定
# =============================================================================
# 新しいログモジュールを使用（ファイル出力、ローテーション対応）

try:
    from infrastructure.logging_config import get_logger
except ImportError:
    # フォールバック：標準のloggingモジュールを使用
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    )
    def get_logger(name):
        return logging.getLogger(name)

# このモジュール用のロガーを取得
logger = get_logger(__name__)


# =============================================================================
# OCRプロバイダー定義
# =============================================================================

class OCRProvider(Enum):
    """
    対応OCRプロバイダー

    各プロバイダーの特徴:
    - AZURE: 高精度、レイアウト解析、座標情報、日本語に強い
    - AWS: 表抽出に強い、フォーム解析
    - GCP: 多言語対応、Document AI
    - TESSERACT: 無料、ローカル実行可、カスタマイズ可能
    - YOMITOKU: 日本語特化OCR（AWS Marketplace版、SageMaker Endpoint経由）
    - NONE: OCR無効（pypdfフォールバック）
    """
    AZURE = "AZURE"
    AWS = "AWS"
    GCP = "GCP"
    TESSERACT = "TESSERACT"
    YOMITOKU = "YOMITOKU"
    NONE = "NONE"


class OCRConfigError(Exception):
    """OCR設定エラー"""
    pass


# =============================================================================
# データクラス定義
# =============================================================================

@dataclass
class OCRTextElement:
    """
    OCR抽出テキスト要素（座標情報付き）

    Attributes:
        text: テキスト内容
        page_number: ページ番号（1始まり）
        bounding_box: 座標 [x1, y1, x2, y2]
        confidence: 認識信頼度（0.0〜1.0）
        element_type: 要素タイプ（line, word, paragraph等）
    """
    text: str
    page_number: int = 1
    bounding_box: Optional[List[float]] = None
    confidence: float = 1.0
    element_type: str = "line"


@dataclass
class OCRTableCell:
    """表のセル情報"""
    row_index: int
    column_index: int
    text: str
    row_span: int = 1
    column_span: int = 1


@dataclass
class OCRTable:
    """抽出された表"""
    table_id: str
    page_number: int
    row_count: int
    column_count: int
    cells: List[OCRTableCell] = field(default_factory=list)


@dataclass
class OCRResult:
    """
    OCR抽出結果

    Attributes:
        text_content: 抽出されたテキスト全文
        page_count: ページ数
        elements: テキスト要素リスト（座標情報付き）
        tables: 抽出された表リスト
        provider: 使用したOCRプロバイダー
        confidence: 全体の信頼度
        error: エラーメッセージ（エラー時のみ）
    """
    text_content: str
    page_count: int = 0
    elements: List[OCRTextElement] = field(default_factory=list)
    tables: List[OCRTable] = field(default_factory=list)
    provider: str = ""
    confidence: float = 1.0
    error: Optional[str] = None


# =============================================================================
# OCRクライアント基底クラス
# =============================================================================

class BaseOCRClient(ABC):
    """
    OCRクライアント基底クラス

    各プロバイダーはこのクラスを継承して実装します。
    """

    @abstractmethod
    def extract_text(self, file_bytes: bytes, mime_type: str = None) -> OCRResult:
        """
        ファイルからテキストを抽出

        Args:
            file_bytes: ファイルのバイナリデータ
            mime_type: MIMEタイプ（application/pdf, image/png等）

        Returns:
            OCRResult: 抽出結果
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """設定が完了しているか確認"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """プロバイダー名を返す"""
        pass


# =============================================================================
# Azure Document Intelligence クライアント
# =============================================================================

class AzureOCRClient(BaseOCRClient):
    """
    Azure Document Intelligence OCRクライアント

    高精度なOCR・レイアウト解析を提供します。
    prebuilt-layoutモデルを使用します。
    """

    def __init__(self):
        self.endpoint = os.getenv("AZURE_DI_ENDPOINT")
        self.key = os.getenv("AZURE_DI_KEY")
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.endpoint and self.key)

    @property
    def provider_name(self) -> str:
        return "Azure Document Intelligence"

    def _get_client(self):
        """クライアントを取得（遅延初期化）"""
        if self._client is None:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential

            self._client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key)
            )
        return self._client

    def extract_text(self, file_bytes: bytes, mime_type: str = None) -> OCRResult:
        """Azure Document Intelligenceでテキスト抽出"""
        if not self.is_configured():
            return OCRResult(
                text_content="",
                error="Azure Document Intelligence が設定されていません",
                provider=self.provider_name
            )

        try:
            from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

            client = self._get_client()
            logger.info(f"[Azure OCR] 抽出開始: {len(file_bytes):,} バイト")

            poller = client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=AnalyzeDocumentRequest(bytes_source=file_bytes),
                content_type=mime_type or "application/octet-stream"
            )
            result = poller.result()

            # 結果を処理
            text_parts = []
            elements = []
            tables = []

            page_count = len(result.pages) if result.pages else 0

            for page in result.pages or []:
                page_num = page.page_number
                text_parts.append(f"--- ページ {page_num} ---")

                for line in page.lines or []:
                    text_parts.append(line.content)
                    bbox = self._polygon_to_bbox(line.polygon) if line.polygon else None
                    elements.append(OCRTextElement(
                        text=line.content,
                        page_number=page_num,
                        bounding_box=bbox,
                        element_type="line"
                    ))

            # 表を処理
            for table_idx, table in enumerate(result.tables or []):
                table_cells = []
                for cell in table.cells or []:
                    table_cells.append(OCRTableCell(
                        row_index=cell.row_index,
                        column_index=cell.column_index,
                        text=cell.content or "",
                        row_span=cell.row_span or 1,
                        column_span=cell.column_span or 1
                    ))

                table_page = 1
                if table.bounding_regions:
                    table_page = table.bounding_regions[0].page_number

                tables.append(OCRTable(
                    table_id=f"table_{table_idx}",
                    page_number=table_page,
                    row_count=table.row_count or 0,
                    column_count=table.column_count or 0,
                    cells=table_cells
                ))

            full_text = "\n".join(text_parts)
            logger.info(f"[Azure OCR] 抽出完了: {len(full_text):,}文字, {page_count}ページ")

            return OCRResult(
                text_content=full_text,
                page_count=page_count,
                elements=elements,
                tables=tables,
                provider=self.provider_name
            )

        except ImportError:
            return OCRResult(
                text_content="",
                error="azure-ai-documentintelligence パッケージがインストールされていません",
                provider=self.provider_name
            )
        except Exception as e:
            logger.error(f"[Azure OCR] エラー: {e}")
            return OCRResult(
                text_content="",
                error=str(e),
                provider=self.provider_name
            )

    def _polygon_to_bbox(self, polygon: List) -> List[float]:
        """ポリゴン座標をバウンディングボックスに変換"""
        if not polygon or len(polygon) < 4:
            return [0, 0, 0, 0]
        xs = [polygon[i] for i in range(0, len(polygon), 2)]
        ys = [polygon[i] for i in range(1, len(polygon), 2)]
        return [min(xs), min(ys), max(xs), max(ys)]


# =============================================================================
# AWS Textract クライアント
# =============================================================================

class AWSTextractClient(BaseOCRClient):
    """
    AWS Textract OCRクライアント

    表抽出やフォーム解析に強いOCRサービスです。
    """

    def __init__(self):
        self.region = os.getenv("AWS_TEXTRACT_REGION") or os.getenv("AWS_REGION", "us-east-1")
        self._client = None

    def is_configured(self) -> bool:
        # AWSはIAMロールで認証可能なのでリージョンがあればOK
        return bool(self.region)

    @property
    def provider_name(self) -> str:
        return "AWS Textract"

    def _get_client(self):
        """Textractクライアントを取得"""
        if self._client is None:
            import boto3
            self._client = boto3.client('textract', region_name=self.region)
        return self._client

    def extract_text(self, file_bytes: bytes, mime_type: str = None) -> OCRResult:
        """AWS Textractでテキスト抽出"""
        if not self.is_configured():
            return OCRResult(
                text_content="",
                error="AWS Textract が設定されていません",
                provider=self.provider_name
            )

        try:
            client = self._get_client()
            logger.info(f"[AWS Textract] 抽出開始: {len(file_bytes):,} バイト")

            # DetectDocumentText APIを使用
            response = client.detect_document_text(
                Document={'Bytes': file_bytes}
            )

            text_parts = []
            elements = []

            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    text = block.get('Text', '')
                    text_parts.append(text)

                    bbox = block.get('Geometry', {}).get('BoundingBox', {})
                    confidence = block.get('Confidence', 100) / 100.0

                    elements.append(OCRTextElement(
                        text=text,
                        page_number=block.get('Page', 1),
                        bounding_box=[
                            bbox.get('Left', 0),
                            bbox.get('Top', 0),
                            bbox.get('Left', 0) + bbox.get('Width', 0),
                            bbox.get('Top', 0) + bbox.get('Height', 0)
                        ],
                        confidence=confidence,
                        element_type="line"
                    ))

            full_text = "\n".join(text_parts)
            logger.info(f"[AWS Textract] 抽出完了: {len(full_text):,}文字")

            return OCRResult(
                text_content=full_text,
                page_count=1,  # DetectDocumentTextは1ページのみ
                elements=elements,
                provider=self.provider_name
            )

        except ImportError:
            return OCRResult(
                text_content="",
                error="boto3 パッケージがインストールされていません",
                provider=self.provider_name
            )
        except Exception as e:
            logger.error(f"[AWS Textract] エラー: {e}")
            return OCRResult(
                text_content="",
                error=str(e),
                provider=self.provider_name
            )


# =============================================================================
# GCP Document AI クライアント
# =============================================================================

class GCPDocumentAIClient(BaseOCRClient):
    """
    GCP Document AI OCRクライアント

    多言語対応のOCRサービスです。
    """

    def __init__(self):
        self.project_id = os.getenv("GCP_DOCAI_PROJECT_ID") or os.getenv("GCP_PROJECT_ID")
        self.location = os.getenv("GCP_DOCAI_LOCATION", "us")
        self.processor_id = os.getenv("GCP_DOCAI_PROCESSOR_ID")
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.project_id and self.processor_id)

    @property
    def provider_name(self) -> str:
        return "GCP Document AI"

    def _get_client(self):
        """Document AIクライアントを取得"""
        if self._client is None:
            from google.cloud import documentai_v1 as documentai
            self._client = documentai.DocumentProcessorServiceClient()
        return self._client

    def extract_text(self, file_bytes: bytes, mime_type: str = None) -> OCRResult:
        """GCP Document AIでテキスト抽出"""
        if not self.is_configured():
            return OCRResult(
                text_content="",
                error="GCP Document AI が設定されていません",
                provider=self.provider_name
            )

        try:
            from google.cloud import documentai_v1 as documentai

            client = self._get_client()
            logger.info(f"[GCP Document AI] 抽出開始: {len(file_bytes):,} バイト")

            # プロセッサ名を構築
            name = f"projects/{self.project_id}/locations/{self.location}/processors/{self.processor_id}"

            # リクエストを作成
            raw_document = documentai.RawDocument(
                content=file_bytes,
                mime_type=mime_type or "application/pdf"
            )
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)

            # 処理を実行
            result = client.process_document(request=request)
            document = result.document

            text_content = document.text
            elements = []

            # ページごとに処理
            for page_idx, page in enumerate(document.pages):
                page_num = page_idx + 1
                for paragraph in page.paragraphs:
                    # テキストを取得
                    para_text = self._get_text_from_layout(document.text, paragraph.layout)
                    if para_text:
                        elements.append(OCRTextElement(
                            text=para_text,
                            page_number=page_num,
                            confidence=paragraph.layout.confidence if paragraph.layout else 1.0,
                            element_type="paragraph"
                        ))

            logger.info(f"[GCP Document AI] 抽出完了: {len(text_content):,}文字")

            return OCRResult(
                text_content=text_content,
                page_count=len(document.pages),
                elements=elements,
                provider=self.provider_name
            )

        except ImportError:
            return OCRResult(
                text_content="",
                error="google-cloud-documentai パッケージがインストールされていません",
                provider=self.provider_name
            )
        except Exception as e:
            logger.error(f"[GCP Document AI] エラー: {e}")
            return OCRResult(
                text_content="",
                error=str(e),
                provider=self.provider_name
            )

    def _get_text_from_layout(self, full_text: str, layout) -> str:
        """レイアウトからテキストを抽出"""
        if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
            return ""

        text_parts = []
        for segment in layout.text_anchor.text_segments:
            start = int(segment.start_index) if segment.start_index else 0
            end = int(segment.end_index) if segment.end_index else len(full_text)
            text_parts.append(full_text[start:end])

        return "".join(text_parts)


# =============================================================================
# Tesseract OCR クライアント
# =============================================================================

class TesseractOCRClient(BaseOCRClient):
    """
    Tesseract OCRクライアント

    オープンソースのOCRエンジンです。ローカル実行可能。
    pytesseractパッケージを使用します。
    """

    def __init__(self):
        self.tesseract_cmd = os.getenv("TESSERACT_CMD")
        self.lang = os.getenv("TESSERACT_LANG", "jpn+eng")
        self._configured = None

    def is_configured(self) -> bool:
        """Tesseractがインストールされているか確認"""
        if self._configured is not None:
            return self._configured

        try:
            import pytesseract

            # カスタムパスが指定されている場合は設定
            if self.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

            # バージョン確認でインストール状態を確認
            pytesseract.get_tesseract_version()
            self._configured = True
            return True

        except Exception:
            self._configured = False
            return False

    @property
    def provider_name(self) -> str:
        return "Tesseract OCR"

    def extract_text(self, file_bytes: bytes, mime_type: str = None) -> OCRResult:
        """Tesseractでテキスト抽出"""
        if not self.is_configured():
            return OCRResult(
                text_content="",
                error="Tesseract OCR がインストールされていません",
                provider=self.provider_name
            )

        try:
            import pytesseract
            from PIL import Image
            import io

            # カスタムパスを設定
            if self.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

            logger.info(f"[Tesseract] 抽出開始: {len(file_bytes):,} バイト")

            # PDFの場合はpdf2imageで変換が必要
            if mime_type and 'pdf' in mime_type.lower():
                try:
                    from pdf2image import convert_from_bytes
                    images = convert_from_bytes(file_bytes)
                except ImportError:
                    return OCRResult(
                        text_content="",
                        error="pdf2image パッケージがインストールされていません（PDF処理に必要）",
                        provider=self.provider_name
                    )
            else:
                # 画像として読み込み
                images = [Image.open(io.BytesIO(file_bytes))]

            text_parts = []
            elements = []

            for page_num, image in enumerate(images, 1):
                # OCR実行
                text = pytesseract.image_to_string(image, lang=self.lang)
                text_parts.append(f"--- ページ {page_num} ---")
                text_parts.append(text)

                # 詳細データを取得
                try:
                    data = pytesseract.image_to_data(image, lang=self.lang, output_type=pytesseract.Output.DICT)
                    for i, txt in enumerate(data['text']):
                        if txt.strip():
                            conf = data['conf'][i]
                            if conf > 0:  # 信頼度が0より大きいもののみ
                                elements.append(OCRTextElement(
                                    text=txt,
                                    page_number=page_num,
                                    bounding_box=[
                                        data['left'][i],
                                        data['top'][i],
                                        data['left'][i] + data['width'][i],
                                        data['top'][i] + data['height'][i]
                                    ],
                                    confidence=conf / 100.0,
                                    element_type="word"
                                ))
                except Exception:
                    # 詳細データ取得に失敗しても続行
                    pass

            full_text = "\n".join(text_parts)
            logger.info(f"[Tesseract] 抽出完了: {len(full_text):,}文字, {len(images)}ページ")

            return OCRResult(
                text_content=full_text,
                page_count=len(images),
                elements=elements,
                provider=self.provider_name
            )

        except ImportError as e:
            return OCRResult(
                text_content="",
                error=f"必要なパッケージがインストールされていません: {e}",
                provider=self.provider_name
            )
        except Exception as e:
            logger.error(f"[Tesseract] エラー: {e}")
            return OCRResult(
                text_content="",
                error=str(e),
                provider=self.provider_name
            )


# =============================================================================
# YomiToku OCR クライアント（AWS Marketplace版）
# =============================================================================

class YomitokuOCRClient(BaseOCRClient):
    """
    YomiToku-Pro OCRクライアント（AWS Marketplace版）

    SageMaker Endpointを経由してYomiToku APIを呼び出します。
    日本語OCRに特化した高精度サービスです。

    【設定に必要な環境変数】
    - YOMITOKU_ENDPOINT_NAME: SageMaker Endpoint名
    - AWS_REGION: AWSリージョン（デフォルト: ap-northeast-1）

    【使用例】
    ```python
    os.environ["OCR_PROVIDER"] = "YOMITOKU"
    os.environ["YOMITOKU_ENDPOINT_NAME"] = "yomitoku-pro-endpoint"
    ocr = OCRFactory.get_ocr_client()
    result = ocr.extract_text(pdf_bytes)
    ```
    """

    def __init__(self):
        self.endpoint_name = os.getenv("YOMITOKU_ENDPOINT_NAME")
        self.region = os.getenv("AWS_REGION", "ap-northeast-1")
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.endpoint_name)

    @property
    def provider_name(self) -> str:
        return "YomiToku-Pro"

    def _get_client(self):
        """SageMaker Runtimeクライアントを取得"""
        if self._client is None:
            import boto3
            self._client = boto3.client(
                'sagemaker-runtime',
                region_name=self.region
            )
        return self._client

    def extract_text(self, file_bytes: bytes, mime_type: str = None) -> OCRResult:
        """YomiToku-Pro SageMaker Endpointでテキスト抽出"""
        if not self.is_configured():
            return OCRResult(
                text_content="",
                error="YomiToku-Pro が設定されていません（YOMITOKU_ENDPOINT_NAME未設定）",
                provider=self.provider_name
            )

        try:
            import json

            client = self._get_client()
            logger.info(f"[YomiToku] 抽出開始: {len(file_bytes):,} バイト")

            # ContentTypeを決定
            content_type = mime_type or "application/pdf"
            if 'pdf' in content_type.lower():
                content_type = "application/pdf"
            elif 'png' in content_type.lower():
                content_type = "image/png"
            elif 'jpeg' in content_type.lower() or 'jpg' in content_type.lower():
                content_type = "image/jpeg"

            # SageMaker Endpointを呼び出し
            response = client.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType=content_type,
                Accept="application/json",
                Body=file_bytes
            )

            # レスポンスを解析
            result_body = response['Body'].read().decode('utf-8')
            result_data = json.loads(result_body)

            # YomiToku APIのレスポンス形式に応じて解析
            # 注: 実際のAPI仕様に合わせて調整が必要
            text_content = ""
            elements = []
            page_count = 1

            # 標準的なレスポンス形式を想定
            if isinstance(result_data, dict):
                # テキスト取得
                text_content = result_data.get("text", "")
                if not text_content and "pages" in result_data:
                    # ページごとのテキストを結合
                    text_parts = []
                    for page_idx, page in enumerate(result_data.get("pages", []), 1):
                        page_text = page.get("text", "")
                        if page_text:
                            text_parts.append(f"--- ページ {page_idx} ---")
                            text_parts.append(page_text)
                        # 行ごとの要素を取得
                        for line in page.get("lines", []):
                            elements.append(OCRTextElement(
                                text=line.get("text", ""),
                                page_number=page_idx,
                                bounding_box=line.get("bbox"),
                                confidence=line.get("confidence", 1.0),
                                element_type="line"
                            ))
                    text_content = "\n".join(text_parts)
                    page_count = len(result_data.get("pages", []))

                # 単純なテキストレスポンスの場合
                if not text_content and "result" in result_data:
                    text_content = result_data.get("result", "")

            elif isinstance(result_data, str):
                text_content = result_data

            logger.info(f"[YomiToku] 抽出完了: {len(text_content):,}文字")

            return OCRResult(
                text_content=text_content,
                page_count=page_count,
                elements=elements,
                provider=self.provider_name
            )

        except ImportError:
            return OCRResult(
                text_content="",
                error="boto3 パッケージがインストールされていません",
                provider=self.provider_name
            )
        except Exception as e:
            logger.error(f"[YomiToku] エラー: {e}")
            error_msg = str(e)
            if "ValidationError" in error_msg:
                error_msg = f"SageMaker Endpointエラー: {error_msg}"
            return OCRResult(
                text_content="",
                error=error_msg,
                provider=self.provider_name
            )


# =============================================================================
# OCRファクトリー
# =============================================================================

class OCRFactory:
    """
    OCRファクトリークラス

    環境変数の設定に基づいてOCRクライアントを生成します。
    Azure, AWS, GCP, Tesseractに対応。

    【主な機能】
    - 環境変数からプロバイダーを自動検出
    - 適切なOCRクライアントを作成
    - 設定状態の確認
    """

    # 各プロバイダーの必須環境変数
    REQUIRED_ENV_VARS = {
        OCRProvider.AZURE: ["AZURE_DI_ENDPOINT", "AZURE_DI_KEY"],
        OCRProvider.AWS: [],  # IAMロールで認証可能
        OCRProvider.GCP: ["GCP_DOCAI_PROJECT_ID", "GCP_DOCAI_PROCESSOR_ID"],
        OCRProvider.TESSERACT: [],  # ローカルインストール
        OCRProvider.YOMITOKU: ["YOMITOKU_ENDPOINT_NAME"],  # SageMaker Endpoint
        OCRProvider.NONE: [],
    }

    # 言語→プロバイダーマッピング（言語ベース自動選択用）
    LANGUAGE_PROVIDER_MAP = {
        "jpn": OCRProvider.YOMITOKU,  # 日本語→YomiToku
        "ja": OCRProvider.YOMITOKU,
        "tha": OCRProvider.TESSERACT,  # タイ語→Tesseract
        "th": OCRProvider.TESSERACT,
        "nld": OCRProvider.TESSERACT,  # オランダ語→Tesseract
        "nl": OCRProvider.TESSERACT,
    }

    # シングルトンキャッシュ
    _client_cache: Optional[BaseOCRClient] = None
    _cached_provider: Optional[OCRProvider] = None

    @classmethod
    def get_provider(cls) -> OCRProvider:
        """
        設定されているOCRプロバイダーを取得

        Returns:
            OCRProvider: 設定されているプロバイダー
        """
        provider_str = os.getenv("OCR_PROVIDER", "NONE").upper()

        try:
            return OCRProvider(provider_str)
        except ValueError:
            logger.warning(f"[OCRFactory] 不正なOCR_PROVIDER: {provider_str}, NONEとして処理")
            return OCRProvider.NONE

    @classmethod
    def get_ocr_client(cls, force_new: bool = False) -> Optional[BaseOCRClient]:
        """
        OCRクライアントを取得

        Args:
            force_new: Trueの場合、キャッシュを無視して新規作成

        Returns:
            BaseOCRClient: OCRクライアント（NONE指定時はNone）
        """
        provider = cls.get_provider()

        if provider == OCRProvider.NONE:
            logger.info("[OCRFactory] OCR_PROVIDER=NONE, OCRは無効")
            return None

        # キャッシュがあり、プロバイダーが同じなら再利用
        if not force_new and cls._client_cache and cls._cached_provider == provider:
            return cls._client_cache

        logger.info(f"[OCRFactory] OCRクライアント作成: {provider.value}")

        client = None
        if provider == OCRProvider.AZURE:
            client = AzureOCRClient()
        elif provider == OCRProvider.AWS:
            client = AWSTextractClient()
        elif provider == OCRProvider.GCP:
            client = GCPDocumentAIClient()
        elif provider == OCRProvider.TESSERACT:
            client = TesseractOCRClient()
        elif provider == OCRProvider.YOMITOKU:
            client = YomitokuOCRClient()

        if client and client.is_configured():
            cls._client_cache = client
            cls._cached_provider = provider
            return client
        else:
            logger.warning(f"[OCRFactory] {provider.value}の設定が不完全です")
            return None

    @classmethod
    def get_config_status(cls) -> dict:
        """
        OCR設定状態を取得

        Returns:
            dict: 設定状態
                - provider: プロバイダー名
                - configured: 設定完了フラグ
                - missing_vars: 不足している環境変数
        """
        provider = cls.get_provider()

        status = {
            "provider": provider.value,
            "configured": False,
            "missing_vars": [],
        }

        if provider == OCRProvider.NONE:
            status["configured"] = True  # NONEは常に「設定完了」
            return status

        # 必須環境変数をチェック
        required_vars = cls.REQUIRED_ENV_VARS.get(provider, [])
        for var in required_vars:
            if not os.getenv(var):
                status["missing_vars"].append(var)

        # クライアントの設定状態を確認
        client = cls.get_ocr_client()
        status["configured"] = client is not None and client.is_configured()

        return status

    @classmethod
    def get_provider_info(cls) -> dict:
        """
        対応プロバイダー情報を取得

        Returns:
            dict: プロバイダー情報
        """
        return {
            "AZURE": {
                "name": "Azure Document Intelligence",
                "description": "高精度OCR + レイアウト解析、日本語に強い",
                "required_env_vars": cls.REQUIRED_ENV_VARS[OCRProvider.AZURE],
                "optional_env_vars": [],
                "documentation": "https://learn.microsoft.com/azure/ai-services/document-intelligence/"
            },
            "AWS": {
                "name": "AWS Textract",
                "description": "表抽出・フォーム解析に強い、IAMロール認証対応",
                "required_env_vars": cls.REQUIRED_ENV_VARS[OCRProvider.AWS],
                "optional_env_vars": ["AWS_TEXTRACT_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
                "documentation": "https://docs.aws.amazon.com/textract/"
            },
            "GCP": {
                "name": "GCP Document AI",
                "description": "多言語対応、カスタムモデル対応",
                "required_env_vars": cls.REQUIRED_ENV_VARS[OCRProvider.GCP],
                "optional_env_vars": ["GCP_DOCAI_LOCATION"],
                "documentation": "https://cloud.google.com/document-ai/docs"
            },
            "TESSERACT": {
                "name": "Tesseract OCR",
                "description": "オープンソース、ローカル実行可能、無料",
                "required_env_vars": cls.REQUIRED_ENV_VARS[OCRProvider.TESSERACT],
                "optional_env_vars": ["TESSERACT_CMD", "TESSERACT_LANG"],
                "documentation": "https://github.com/tesseract-ocr/tesseract"
            },
            "YOMITOKU": {
                "name": "YomiToku-Pro",
                "description": "日本語特化OCR、AWS Marketplace版、SageMaker Endpoint経由",
                "required_env_vars": cls.REQUIRED_ENV_VARS[OCRProvider.YOMITOKU],
                "optional_env_vars": ["AWS_REGION"],
                "documentation": "https://aws.amazon.com/marketplace/pp/prodview-xxx"
            },
            "NONE": {
                "name": "OCR無効",
                "description": "OCRを使用しない（pypdfでテキストPDFのみ処理）",
                "required_env_vars": [],
                "optional_env_vars": [],
                "documentation": ""
            }
        }

    @classmethod
    def get_ocr_client_for_language(cls, language: str) -> Optional[BaseOCRClient]:
        """
        言語に基づいてOCRクライアントを取得

        言語コードに応じて最適なOCRプロバイダーを自動選択します。
        - 日本語 (jpn, ja) → YomiToku-Pro
        - タイ語 (tha, th) → Tesseract
        - オランダ語 (nld, nl) → Tesseract
        - その他 → デフォルトプロバイダー（OCR_PROVIDER環境変数）

        Args:
            language: 言語コード（ISO 639-2/3 または ISO 639-1）

        Returns:
            BaseOCRClient: 言語に適したOCRクライアント

        使用例:
            ocr = OCRFactory.get_ocr_client_for_language("jpn")
            result = ocr.extract_text(japanese_pdf_bytes)
        """
        provider = cls.LANGUAGE_PROVIDER_MAP.get(language.lower())

        if provider:
            logger.info(f"[OCRFactory] 言語 '{language}' → {provider.value} を選択")
            return cls._create_client(provider)

        # マッピングにない場合はデフォルトプロバイダーを使用
        logger.info(f"[OCRFactory] 言語 '{language}' はマッピングなし、デフォルトを使用")
        return cls.get_ocr_client()

    @classmethod
    def _create_client(cls, provider: OCRProvider) -> Optional[BaseOCRClient]:
        """
        指定されたプロバイダーのOCRクライアントを作成

        Args:
            provider: OCRProvider

        Returns:
            BaseOCRClient: 作成されたクライアント（設定不完全の場合はNone）
        """
        client = None
        if provider == OCRProvider.AZURE:
            client = AzureOCRClient()
        elif provider == OCRProvider.AWS:
            client = AWSTextractClient()
        elif provider == OCRProvider.GCP:
            client = GCPDocumentAIClient()
        elif provider == OCRProvider.TESSERACT:
            client = TesseractOCRClient()
        elif provider == OCRProvider.YOMITOKU:
            client = YomitokuOCRClient()
        elif provider == OCRProvider.NONE:
            return None

        if client and client.is_configured():
            return client
        else:
            logger.warning(f"[OCRFactory] {provider.value}の設定が不完全です")
            return None
