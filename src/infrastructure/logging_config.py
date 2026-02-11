# -*- coding: utf-8 -*-
"""
=============================================================================
ログ設定モジュール (logging_config.py)
=============================================================================

このモジュールは、アプリケーション全体で使用するログ設定を提供します。

【主な機能】
- コンソールとファイルへの同時出力
- ログファイルの自動ローテーション（サイズベース）
- 日本語対応（UTF-8エンコーディング）
- ログレベルの環境変数による制御
- 構造化ログ出力（JSON形式オプション）

【使い方】
    from src.infrastructure.logging_config import get_logger

    # ロガーを取得
    logger = get_logger(__name__)

    # ログを出力
    logger.info("処理を開始します")
    logger.error("エラーが発生しました", exc_info=True)

【ログレベル】
- DEBUG: 詳細なデバッグ情報（開発時のみ）
- INFO: 一般的な情報（処理の開始/終了など）
- WARNING: 警告（処理は継続するが注意が必要）
- ERROR: エラー（処理が失敗した）
- CRITICAL: 致命的エラー（システムが動作不能）

【環境変数】
- LOG_LEVEL: ログレベル（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- LOG_DIR: ログファイルの出力ディレクトリ
- LOG_TO_FILE: ファイル出力の有効/無効（true/false）
- LOG_FORMAT: ログフォーマット（standard/json）

=============================================================================
"""

import logging
import logging.handlers
import os
import sys
import json
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


# =============================================================================
# 定数定義
# =============================================================================

# デフォルト設定値
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIR = "logs"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5  # 保持する古いログファイル数

# ログフォーマット
STANDARD_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
)
DETAILED_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | "
    "%(message)s"
)

# 日時フォーマット
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


# =============================================================================
# カスタムフォーマッター
# =============================================================================

class ColoredFormatter(logging.Formatter):
    """
    コンソール出力用のカラーフォーマッター

    ログレベルに応じて色を変えることで、視認性を向上させます。
    Windows/Linux/Mac すべてで動作します。

    【色の対応】
    - DEBUG: シアン（水色）
    - INFO: 緑
    - WARNING: 黄色
    - ERROR: 赤
    - CRITICAL: 赤背景
    """

    # ANSIエスケープコード（ターミナルで色を表示するためのコード）
    COLORS = {
        'DEBUG': '\033[36m',      # シアン
        'INFO': '\033[32m',       # 緑
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 赤
        'CRITICAL': '\033[41m',   # 赤背景
    }
    RESET = '\033[0m'  # 色をリセット

    def format(self, record: logging.LogRecord) -> str:
        """
        ログレコードをフォーマットする

        Args:
            record: ログレコード（ログ情報を保持するオブジェクト）

        Returns:
            フォーマット済みのログ文字列
        """
        # 元のフォーマット処理を実行
        formatted = super().format(record)

        # ログレベルに対応する色を取得
        color = self.COLORS.get(record.levelname, '')

        # 色がある場合は色を付けて返す
        if color:
            return f"{color}{formatted}{self.RESET}"
        return formatted


class JsonFormatter(logging.Formatter):
    """
    JSON形式のログフォーマッター

    ログをJSON形式で出力します。ログ集約システム（Elasticsearch、
    CloudWatch Logs など）との連携に便利です。

    【出力例】
    {
        "timestamp": "2024-01-15 10:30:45",
        "level": "INFO",
        "logger": "src.core.auditor_agent",
        "message": "評価を開始します",
        "function": "evaluate",
        "line": 123
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        ログレコードをJSON形式にフォーマットする

        Args:
            record: ログレコード

        Returns:
            JSON形式のログ文字列
        """
        # 基本情報を辞書に格納
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).strftime(
                DATETIME_FORMAT
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno,
        }

        # 相関IDを自動的に含める
        try:
            from core.correlation import get_correlation_id
            correlation_id = get_correlation_id()
            if correlation_id:
                log_data["correlation_id"] = correlation_id
        except (ImportError, Exception):
            # correlation モジュールが利用できない場合はスキップ
            pass

        # 例外情報がある場合は追加
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }

        # 追加の属性があれば含める（extra パラメータで渡された情報）
        extra_fields = {
            key: value for key, value in record.__dict__.items()
            if key not in logging.LogRecord(
                "", 0, "", 0, "", (), None
            ).__dict__ and not key.startswith('_')
        }
        if extra_fields:
            log_data["extra"] = extra_fields

        # JSON文字列に変換（日本語はそのまま表示）
        return json.dumps(log_data, ensure_ascii=False, default=str)


# =============================================================================
# ログ設定クラス
# =============================================================================

class LoggingConfig:
    """
    ログ設定を管理するクラス

    シングルトンパターンを使用し、アプリケーション全体で
    一貫したログ設定を提供します。

    【シングルトンパターンとは】
    クラスのインスタンスが1つしか存在しないことを保証する設計パターン。
    ログ設定は一度だけ行えばよいため、このパターンを使用します。
    """

    _instance: Optional['LoggingConfig'] = None
    _initialized: bool = False

    def __new__(cls) -> 'LoggingConfig':
        """
        シングルトンインスタンスを返す

        Returns:
            LoggingConfigのインスタンス（常に同じインスタンス）
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        初期化処理（最初の1回だけ実行される）
        """
        # 既に初期化済みの場合はスキップ
        if LoggingConfig._initialized:
            return

        # 環境変数から設定を読み込む
        self.log_level = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
        self.log_dir = os.environ.get("LOG_DIR", DEFAULT_LOG_DIR)
        self.log_format = os.environ.get("LOG_FORMAT", "standard").lower()

        # Azure Functions環境を検出（ファイル書き込みが制限される）
        is_azure_functions = os.environ.get("FUNCTIONS_WORKER_RUNTIME") is not None

        # LOG_TO_FILE設定（Azure Functionsではデフォルトでfalse）
        log_to_file_env = os.environ.get("LOG_TO_FILE")
        if log_to_file_env is not None:
            self.log_to_file = log_to_file_env.lower() == "true"
        else:
            # 環境変数未設定の場合、Azure Functionsではfalse、それ以外はtrue
            self.log_to_file = not is_azure_functions

        # ログディレクトリを作成（ファイル出力有効時のみ）
        if self.log_to_file:
            self._ensure_log_directory()

        # ルートロガーを設定
        self._configure_root_logger()

        LoggingConfig._initialized = True

    def _ensure_log_directory(self) -> None:
        """
        ログディレクトリが存在することを確認し、なければ作成する
        """
        log_path = Path(self.log_dir)
        if not log_path.exists():
            log_path.mkdir(parents=True, exist_ok=True)

    def _configure_root_logger(self) -> None:
        """
        ルートロガー（すべてのロガーの親）を設定する

        この設定は、get_logger() で取得したすべてのロガーに適用されます。
        """
        # ルートロガーを取得
        root_logger = logging.getLogger()

        # 既存のハンドラーをクリア（重複防止）
        root_logger.handlers.clear()

        # ログレベルを設定
        log_level = getattr(logging, self.log_level, logging.INFO)
        root_logger.setLevel(log_level)

        # コンソールハンドラーを追加
        console_handler = self._create_console_handler()
        root_logger.addHandler(console_handler)

        # ファイルハンドラーを追加（有効な場合）
        if self.log_to_file:
            file_handler = self._create_file_handler()
            root_logger.addHandler(file_handler)

            # エラー専用ファイルハンドラーも追加
            error_handler = self._create_error_file_handler()
            root_logger.addHandler(error_handler)

    def _create_console_handler(self) -> logging.Handler:
        """
        コンソール出力用ハンドラーを作成

        Returns:
            設定済みのStreamHandler
        """
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)  # すべてのレベルを出力

        # フォーマッターを設定
        if self.log_format == "json":
            formatter = JsonFormatter()
        else:
            # 色付きフォーマッターを使用
            formatter = ColoredFormatter(
                DETAILED_FORMAT,
                datefmt=DATETIME_FORMAT
            )

        handler.setFormatter(formatter)
        return handler

    def _create_file_handler(self) -> logging.Handler:
        """
        ファイル出力用ハンドラーを作成（ローテーション対応）

        ログファイルが一定サイズを超えると、自動的に新しいファイルに
        切り替わります（例: app.log → app.log.1 → app.log.2）

        Returns:
            設定済みのRotatingFileHandler
        """
        # ログファイル名を生成（日付を含む）
        log_file = Path(self.log_dir) / "app.log"

        # ローテーティングファイルハンドラーを作成
        handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=DEFAULT_MAX_BYTES,      # 10MB でローテーション
            backupCount=DEFAULT_BACKUP_COUNT, # 5世代保持
            encoding='utf-8'                  # 日本語対応
        )
        handler.setLevel(logging.DEBUG)

        # フォーマッターを設定（ファイルは常に標準フォーマット）
        formatter = logging.Formatter(
            DETAILED_FORMAT,
            datefmt=DATETIME_FORMAT
        )
        handler.setFormatter(formatter)

        return handler

    def _create_error_file_handler(self) -> logging.Handler:
        """
        エラー専用ファイルハンドラーを作成

        ERROR以上のログのみを別ファイルに出力します。
        エラーの調査時に便利です。

        Returns:
            設定済みのRotatingFileHandler
        """
        error_file = Path(self.log_dir) / "error.log"

        handler = logging.handlers.RotatingFileHandler(
            filename=str(error_file),
            maxBytes=DEFAULT_MAX_BYTES,
            backupCount=DEFAULT_BACKUP_COUNT,
            encoding='utf-8'
        )
        handler.setLevel(logging.ERROR)  # ERROR以上のみ

        formatter = logging.Formatter(
            DETAILED_FORMAT,
            datefmt=DATETIME_FORMAT
        )
        handler.setFormatter(formatter)

        return handler


# =============================================================================
# 公開関数
# =============================================================================

def setup_logging() -> None:
    """
    ログ設定を初期化する

    アプリケーションの起動時に一度だけ呼び出してください。

    【使用例】
        from src.infrastructure.logging_config import setup_logging

        # アプリケーション起動時
        setup_logging()
    """
    LoggingConfig()


def get_logger(name: str) -> logging.Logger:
    """
    名前付きロガーを取得する

    Args:
        name: ロガー名（通常は __name__ を使用）

    Returns:
        設定済みのロガーインスタンス

    【使用例】
        logger = get_logger(__name__)
        logger.info("処理を開始します")
    """
    # ログ設定を初期化（まだの場合）
    setup_logging()

    return logging.getLogger(name)


def log_function_call(logger: logging.Logger):
    """
    関数呼び出しをログに記録するデコレーター

    関数の開始・終了・エラーを自動的にログに記録します。

    【デコレーターとは】
    既存の関数に追加の機能を付与する仕組みです。
    @マークを使って関数定義の直前に記述します。

    【使用例】
        @log_function_call(logger)
        def my_function(arg1, arg2):
            # 処理
            return result
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 関数名を取得
            func_name = func.__name__

            # 開始ログ
            logger.debug(f"[START] {func_name}")

            try:
                # 元の関数を実行
                result = func(*args, **kwargs)

                # 正常終了ログ
                logger.debug(f"[END] {func_name}")

                return result

            except Exception as e:
                # エラーログ（スタックトレース付き）
                logger.error(
                    f"[ERROR] {func_name}: {type(e).__name__}: {e}",
                    exc_info=True
                )
                raise

        # 元の関数の情報を保持
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper
    return decorator


# =============================================================================
# 構造化ログヘルパー
# =============================================================================

class AuditLogger:
    """
    内部統制テスト専用のロガー

    評価処理の各ステップを構造化された形式でログに記録します。
    デバッグや監査証跡として使用できます。

    【使用例】
        audit_logger = AuditLogger(logger)
        audit_logger.log_evaluation_start("CLC-01", "研修実施確認")
        audit_logger.log_task_execution("A1", "セマンティック検索", success=True)
        audit_logger.log_evaluation_end("CLC-01", "有効", elapsed_time=5.2)
    """

    def __init__(self, logger: logging.Logger):
        """
        初期化

        Args:
            logger: 基底となるロガー
        """
        self.logger = logger

    def log_evaluation_start(
        self,
        item_id: str,
        control_description: str,
        evidence_count: int = 0
    ) -> None:
        """
        評価開始をログに記録

        Args:
            item_id: 評価項目ID（例: CLC-01）
            control_description: 統制の説明
            evidence_count: 証跡ファイル数
        """
        self.logger.info("=" * 70)
        self.logger.info(f"[評価開始] {item_id}")
        self.logger.info(f"  統制: {control_description[:100]}...")
        self.logger.info(f"  証跡ファイル数: {evidence_count}")
        self.logger.info("=" * 70)

    def log_task_execution(
        self,
        task_id: str,
        task_name: str,
        success: bool,
        details: Optional[str] = None,
        elapsed_time: Optional[float] = None
    ) -> None:
        """
        タスク実行結果をログに記録

        Args:
            task_id: タスクID（例: A1, A2）
            task_name: タスク名
            success: 成功したかどうか
            details: 追加の詳細情報
            elapsed_time: 実行時間（秒）
        """
        status = "SUCCESS" if success else "FAILED"
        time_str = f" ({elapsed_time:.2f}秒)" if elapsed_time else ""

        if success:
            self.logger.info(f"  [{status}] {task_id}: {task_name}{time_str}")
        else:
            self.logger.warning(f"  [{status}] {task_id}: {task_name}{time_str}")

        if details:
            self.logger.debug(f"    詳細: {details}")

    def log_llm_call(
        self,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        elapsed_time: Optional[float] = None
    ) -> None:
        """
        LLM呼び出しをログに記録

        Args:
            model: 使用したモデル名
            prompt_tokens: 入力トークン数
            completion_tokens: 出力トークン数
            elapsed_time: 応答時間（秒）
        """
        token_info = ""
        if prompt_tokens and completion_tokens:
            token_info = f" (入力: {prompt_tokens}, 出力: {completion_tokens})"

        time_str = f" {elapsed_time:.2f}秒" if elapsed_time else ""

        self.logger.debug(f"  [LLM] {model}{token_info}{time_str}")

    def log_evaluation_end(
        self,
        item_id: str,
        result: str,
        elapsed_time: Optional[float] = None,
        reflection_count: int = 0
    ) -> None:
        """
        評価完了をログに記録

        Args:
            item_id: 評価項目ID
            result: 評価結果（有効/無効/評価不能）
            elapsed_time: 総実行時間（秒）
            reflection_count: セルフリフレクション回数
        """
        time_str = f" ({elapsed_time:.2f}秒)" if elapsed_time else ""
        reflection_str = f" リフレクション: {reflection_count}回" if reflection_count > 0 else ""

        self.logger.info("-" * 70)
        self.logger.info(f"[評価完了] {item_id}: {result}{time_str}{reflection_str}")
        self.logger.info("-" * 70)

    def log_error(
        self,
        item_id: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        エラーをログに記録

        Args:
            item_id: 評価項目ID
            error_type: エラーの種類
            error_message: エラーメッセージ
            context: エラー発生時のコンテキスト情報
        """
        self.logger.error(f"[ERROR] {item_id}: {error_type}")
        self.logger.error(f"  メッセージ: {error_message}")

        if context:
            self.logger.error(f"  コンテキスト: {json.dumps(context, ensure_ascii=False)}")


# =============================================================================
# モジュール初期化
# =============================================================================

# NOTE: Azure Functions環境では自動初期化を無効化
# get_logger()を呼び出した時点で遅延初期化される
# ローカル開発時に明示的に初期化したい場合は setup_logging() を呼び出す
#
# 以前のコード（Azure Functionsで問題が発生）:
# setup_logging()
