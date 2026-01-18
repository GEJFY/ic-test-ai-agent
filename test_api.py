# -*- coding: utf-8 -*-
"""
評価APIのテストスクリプト
UTF-8エンコーディングを確実に行い、APIをテストする
"""
import json
import requests

def test_evaluate_api():
    """評価APIをテストする"""
    url = "http://localhost:7071/api/evaluate"

    # テストデータ（CLC-01とCLC-02の両方をテスト）
    test_data = [
        {
            "ID": "CLC-01",
            "ControlDescription": "コンプライアンス研修実施",
            "TestProcedure": "研修実施報告書を閲覧し、研修の実施状況を確認する",
            "EvidenceFiles": []
        },
        {
            "ID": "CLC-02",
            "ControlDescription": "承認プロセスの遵守",
            "TestProcedure": "承認フローの記録を閲覧し、適切な承認者による承認が行われているか確認する",
            "EvidenceFiles": []
        }
    ]

    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }

    print("=" * 60)
    print("評価APIテスト開始")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"送信データ: {json.dumps(test_data, ensure_ascii=False, indent=2)}")
    print("=" * 60)

    try:
        response = requests.post(
            url,
            data=json.dumps(test_data, ensure_ascii=False).encode('utf-8'),
            headers=headers,
            timeout=300  # 5分タイムアウト
        )

        print(f"ステータスコード: {response.status_code}")
        print("=" * 60)

        if response.status_code == 200:
            result = response.json()
            print("レスポンス:")
            print(json.dumps(result, ensure_ascii=False, indent=2))

            # 結果の検証
            print("\n" + "=" * 60)
            print("結果検証")
            print("=" * 60)

            if "results" in result:
                for item in result["results"]:
                    item_id = item.get("ID", "不明")
                    print(f"\n--- {item_id} ---")

                    # タスク計画の確認
                    task_plan = item.get("TaskPlan", "")
                    print(f"タスク計画（最初の200文字）: {task_plan[:200]}...")

                    # 判断根拠の確認
                    judgment_basis = item.get("JudgmentBasis", "")
                    print(f"判断根拠（最初の200文字）: {judgment_basis[:200]}...")

                    # 禁止フレーズのチェック
                    forbidden_phrases = [
                        "テスト手続きでは",
                        "テスト手続きに従い",
                        "手続きとして",
                        "確認を行いました",
                        "実施しました"
                    ]
                    for phrase in forbidden_phrases:
                        if phrase in judgment_basis:
                            print(f"  ⚠️ 禁止フレーズ検出: '{phrase}'")

                    # 引用の確認
                    quotes = item.get("DocumentQuotes", [])
                    print(f"引用数: {len(quotes)}")
                    for i, quote in enumerate(quotes):
                        quote_text = quote.get("quote", "")
                        quote_len = len(quote_text)
                        has_brackets = "「" in quote_text or "」" in quote_text
                        print(f"  引用{i+1}: {quote_len}文字, 括弧あり={has_brackets}")
                        if quote_len < 100:
                            print(f"    ⚠️ 引用が短すぎます（100文字未満）")
                        if quote_len > 400:
                            print(f"    ⚠️ 引用が長すぎます（400文字超）")
                        if has_brackets:
                            print(f"    ⚠️ 「」括弧が含まれています")
        else:
            print(f"エラーレスポンス: {response.text}")

    except requests.exceptions.ConnectionError:
        print("エラー: サーバーに接続できません。サーバーが起動しているか確認してください。")
    except requests.exceptions.Timeout:
        print("エラー: リクエストがタイムアウトしました。")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    test_evaluate_api()
