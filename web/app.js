/**
 * 内部統制テスト評価AI - Webフロントエンド JavaScript
 *
 * PowerShell/VBA制限環境向けのWebベースインターフェース
 */

// =============================================================================
// アプリケーション状態管理
// =============================================================================
const AppState = {
    currentStep: 1,
    selectedFile: null,
    fileContent: null,
    apiEndpoint: '',
    apiKey: '',
    authHeader: 'x-functions-key',
    isProcessing: false,
    abortController: null,
    results: null
};

// =============================================================================
// DOM要素の参照
// =============================================================================
const elements = {
    // ステップインジケーター
    steps: document.querySelectorAll('.step'),
    stepConnectors: document.querySelectorAll('.step-connector'),

    // ステップコンテンツ
    step1: document.getElementById('step1'),
    step2: document.getElementById('step2'),
    step3: document.getElementById('step3'),

    // ファイルアップロード
    dropZone: document.getElementById('dropZone'),
    fileInput: document.getElementById('fileInput'),
    browseBtn: document.getElementById('browseBtn'),
    fileInfo: document.getElementById('fileInfo'),
    fileName: document.getElementById('fileName'),
    fileSize: document.getElementById('fileSize'),
    removeFile: document.getElementById('removeFile'),

    // 設定
    apiEndpoint: document.getElementById('apiEndpoint'),
    apiKey: document.getElementById('apiKey'),
    authHeader: document.getElementById('authHeader'),

    // ボタン
    startEvaluation: document.getElementById('startEvaluation'),
    cancelEvaluation: document.getElementById('cancelEvaluation'),
    downloadResults: document.getElementById('downloadResults'),
    startNew: document.getElementById('startNew'),
    retryEvaluation: document.getElementById('retryEvaluation'),
    goBack: document.getElementById('goBack'),

    // 処理中
    progressPercent: document.getElementById('progressPercent'),
    processingMessage: document.getElementById('processingMessage'),
    statusUpload: document.getElementById('statusUpload'),
    statusProcess: document.getElementById('statusProcess'),
    statusComplete: document.getElementById('statusComplete'),

    // 結果
    resultSuccess: document.getElementById('resultSuccess'),
    resultError: document.getElementById('resultError'),
    totalItems: document.getElementById('totalItems'),
    passedItems: document.getElementById('passedItems'),
    failedItems: document.getElementById('failedItems'),
    errorMessage: document.getElementById('errorMessage'),
    errorTrace: document.getElementById('errorTrace'),
    toggleErrorDetails: document.getElementById('toggleErrorDetails')
};

// =============================================================================
// 初期化
// =============================================================================
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadSavedSettings();
});

function initializeEventListeners() {
    // ファイルアップロード
    elements.dropZone.addEventListener('click', () => elements.fileInput.click());
    elements.dropZone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            elements.fileInput.click();
        }
    });
    elements.browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        elements.fileInput.click();
    });
    elements.fileInput.addEventListener('change', handleFileSelect);
    elements.removeFile.addEventListener('click', removeSelectedFile);

    // ドラッグ&ドロップ
    elements.dropZone.addEventListener('dragover', handleDragOver);
    elements.dropZone.addEventListener('dragleave', handleDragLeave);
    elements.dropZone.addEventListener('drop', handleDrop);

    // 設定変更
    elements.apiEndpoint.addEventListener('input', handleSettingsChange);
    elements.apiKey.addEventListener('input', handleSettingsChange);
    elements.authHeader.addEventListener('change', handleSettingsChange);

    // パスワード表示切り替え
    document.querySelector('.toggle-password').addEventListener('click', togglePasswordVisibility);

    // アクションボタン
    elements.startEvaluation.addEventListener('click', startEvaluation);
    elements.cancelEvaluation.addEventListener('click', cancelEvaluation);
    elements.downloadResults.addEventListener('click', downloadResults);
    elements.startNew.addEventListener('click', resetToStart);
    elements.retryEvaluation.addEventListener('click', () => goToStep(1));
    elements.goBack.addEventListener('click', () => goToStep(1));

    // エラー詳細表示
    elements.toggleErrorDetails.addEventListener('click', toggleErrorDetails);
}

// =============================================================================
// ファイル処理
// =============================================================================
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        processFile(file);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    elements.dropZone.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    elements.dropZone.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    elements.dropZone.classList.remove('drag-over');

    const file = e.dataTransfer.files[0];
    if (file) {
        processFile(file);
    }
}

function processFile(file) {
    // ファイル形式チェック
    if (!file.name.endsWith('.json')) {
        showNotification('JSONファイル (.json) のみ対応しています。', 'error');
        return;
    }

    // ファイルサイズチェック (50MB制限)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
        showNotification('ファイルサイズが大きすぎます（最大50MB）。', 'error');
        return;
    }

    // ファイル内容を読み込み
    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            // JSONとして解析してバリデーション
            const content = JSON.parse(e.target.result);

            // 配列形式かチェック
            if (!Array.isArray(content)) {
                throw new Error('JSONは配列形式である必要があります。');
            }

            // 必須フィールドチェック
            if (content.length > 0) {
                const firstItem = content[0];
                if (!firstItem.ID) {
                    throw new Error('各項目にIDフィールドが必要です。');
                }
            }

            // 状態を更新
            AppState.selectedFile = file;
            AppState.fileContent = content;

            // UI更新
            showFileInfo(file);
            updateStartButton();

        } catch (error) {
            showNotification(`JSONファイルの解析に失敗しました: ${error.message}`, 'error');
            console.error('JSON parse error:', error);
        }
    };
    reader.onerror = () => {
        showNotification('ファイルの読み込みに失敗しました。', 'error');
    };
    reader.readAsText(file, 'UTF-8');
}

function showFileInfo(file) {
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);
    elements.fileInfo.classList.remove('hidden');
    elements.dropZone.style.display = 'none';
}

function removeSelectedFile() {
    AppState.selectedFile = null;
    AppState.fileContent = null;
    elements.fileInput.value = '';
    elements.fileInfo.classList.add('hidden');
    elements.dropZone.style.display = '';
    updateStartButton();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// =============================================================================
// 設定管理
// =============================================================================
function handleSettingsChange() {
    AppState.apiEndpoint = elements.apiEndpoint.value.trim();
    AppState.apiKey = elements.apiKey.value;
    AppState.authHeader = elements.authHeader.value;

    // ローカルストレージに保存（APIキーは除く）
    saveSettings();
    updateStartButton();
}

function saveSettings() {
    localStorage.setItem('ic-test-settings', JSON.stringify({
        apiEndpoint: AppState.apiEndpoint,
        authHeader: AppState.authHeader
    }));
}

function loadSavedSettings() {
    try {
        const saved = localStorage.getItem('ic-test-settings');
        if (saved) {
            const settings = JSON.parse(saved);
            elements.apiEndpoint.value = settings.apiEndpoint || '';
            elements.authHeader.value = settings.authHeader || 'x-functions-key';
            AppState.apiEndpoint = settings.apiEndpoint || '';
            AppState.authHeader = settings.authHeader || 'x-functions-key';
        }
    } catch (e) {
        console.warn('Failed to load saved settings:', e);
    }
}

function togglePasswordVisibility() {
    const input = elements.apiKey;
    const btn = document.querySelector('.toggle-password');

    if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/>
            </svg>
        `;
    } else {
        input.type = 'password';
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                <path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
            </svg>
        `;
    }
}

function updateStartButton() {
    const isValid = AppState.selectedFile &&
                    AppState.apiEndpoint &&
                    isValidUrl(AppState.apiEndpoint);
    elements.startEvaluation.disabled = !isValid;
}

function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

// =============================================================================
// API呼び出し
// =============================================================================
async function startEvaluation() {
    if (AppState.isProcessing) return;

    AppState.isProcessing = true;
    AppState.abortController = new AbortController();

    goToStep(2);
    updateProgress(0, 'データをアップロードしています...');
    setStatusActive('upload');

    try {
        // リクエストヘッダーを構築
        const headers = {
            'Content-Type': 'application/json; charset=UTF-8'
        };

        if (AppState.apiKey) {
            if (AppState.authHeader === 'Authorization') {
                headers['Authorization'] = `Bearer ${AppState.apiKey}`;
            } else {
                headers[AppState.authHeader] = AppState.apiKey;
            }
        }

        updateProgress(20, 'AI評価を実行中...');
        setStatusActive('process');

        // API呼び出し
        const response = await fetch(AppState.apiEndpoint, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(AppState.fileContent),
            signal: AppState.abortController.signal
        });

        updateProgress(80, '結果を処理中...');
        setStatusActive('complete');

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Error (${response.status}): ${errorText}`);
        }

        const results = await response.json();

        updateProgress(100, '完了しました！');

        // 少し待ってから結果表示
        await delay(500);

        AppState.results = results;
        showResults(results);

    } catch (error) {
        if (error.name === 'AbortError') {
            showNotification('処理がキャンセルされました。', 'warning');
            goToStep(1);
        } else {
            showError(error);
        }
    } finally {
        AppState.isProcessing = false;
        AppState.abortController = null;
    }
}

function cancelEvaluation() {
    if (AppState.abortController) {
        AppState.abortController.abort();
    }
}

// =============================================================================
// ステップ管理
// =============================================================================
function goToStep(stepNumber) {
    AppState.currentStep = stepNumber;

    // ステップインジケーター更新
    elements.steps.forEach((step, index) => {
        const num = index + 1;
        step.classList.remove('active', 'completed');
        if (num < stepNumber) {
            step.classList.add('completed');
        } else if (num === stepNumber) {
            step.classList.add('active');
        }
    });

    // コネクター更新
    elements.stepConnectors.forEach((connector, index) => {
        if (index < stepNumber - 1) {
            connector.classList.add('active');
        } else {
            connector.classList.remove('active');
        }
    });

    // コンテンツ表示切り替え
    elements.step1.classList.toggle('hidden', stepNumber !== 1);
    elements.step2.classList.toggle('hidden', stepNumber !== 2);
    elements.step3.classList.toggle('hidden', stepNumber !== 3);
}

// =============================================================================
// 処理状態表示
// =============================================================================
function updateProgress(percent, message) {
    elements.progressPercent.textContent = Math.round(percent);
    elements.processingMessage.textContent = message;

    // SVGプログレスリングの更新
    const ring = document.querySelector('.progress-ring-fill');
    const circumference = 2 * Math.PI * 54; // r=54
    const offset = circumference - (percent / 100) * circumference;
    ring.style.strokeDashoffset = offset;
}

function setStatusActive(status) {
    const statuses = ['upload', 'process', 'complete'];
    const statusElements = {
        upload: elements.statusUpload,
        process: elements.statusProcess,
        complete: elements.statusComplete
    };

    const currentIndex = statuses.indexOf(status);

    statuses.forEach((s, index) => {
        statusElements[s].classList.remove('active', 'completed');
        if (index < currentIndex) {
            statusElements[s].classList.add('completed');
        } else if (index === currentIndex) {
            statusElements[s].classList.add('active');
        }
    });
}

// =============================================================================
// 結果表示
// =============================================================================
function showResults(results) {
    goToStep(3);

    // 配列形式の場合
    const items = Array.isArray(results) ? results : [results];

    // 集計
    const total = items.length;
    const passed = items.filter(item => item.evaluationResult === true).length;
    const failed = total - passed;

    // UI更新
    elements.totalItems.textContent = total;
    elements.passedItems.textContent = passed;
    elements.failedItems.textContent = failed;

    // 成功表示
    elements.resultSuccess.classList.remove('hidden');
    elements.resultError.classList.add('hidden');
}

function showError(error) {
    goToStep(3);

    elements.resultSuccess.classList.add('hidden');
    elements.resultError.classList.remove('hidden');

    elements.errorMessage.textContent = error.message || 'エラーが発生しました。';
    elements.errorTrace.textContent = error.stack || '';
}

function toggleErrorDetails() {
    const trace = elements.errorTrace;
    const btn = elements.toggleErrorDetails;

    trace.classList.toggle('hidden');
    btn.classList.toggle('expanded');
    btn.querySelector('span') || (btn.firstChild.textContent = trace.classList.contains('hidden') ? '詳細を表示' : '詳細を隠す');
}

// =============================================================================
// ダウンロード
// =============================================================================
function downloadResults() {
    if (!AppState.results) return;

    const jsonString = JSON.stringify(AppState.results, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json; charset=utf-8' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `evaluation_results_${formatDate(new Date())}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showNotification('結果ファイルをダウンロードしました。', 'success');
}

function formatDate(date) {
    return date.toISOString().slice(0, 19).replace(/[-:T]/g, '').slice(0, 14);
}

// =============================================================================
// リセット
// =============================================================================
function resetToStart() {
    AppState.results = null;
    removeSelectedFile();
    goToStep(1);
}

// =============================================================================
// ユーティリティ
// =============================================================================
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function showNotification(message, type = 'info') {
    // 簡易的な通知（将来的にはトースト通知に置き換え可能）
    const colors = {
        success: '#10b981',
        error: '#ef4444',
        warning: '#f59e0b',
        info: '#3b82f6'
    };

    console.log(`[${type.toUpperCase()}] ${message}`);

    // 簡易アラート（本番ではトースト通知推奨）
    if (type === 'error') {
        alert(message);
    }
}
