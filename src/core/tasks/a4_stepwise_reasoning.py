"""
A4: Stepwise Reasoning + Calculation Task
Breaks down complex calculations into steps using Chain-of-Thought.
"""
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .base_task import BaseAuditTask, TaskType, TaskResult, AuditContext

# プロンプトをprompts.pyからインポート
from ..prompts import A4_STEPWISE_REASONING_PROMPT


class StepwiseReasoningTask(BaseAuditTask):
    """
    A4: Stepwise Reasoning + Calculation
    Uses Chain-of-Thought to break down and verify complex calculations.
    """

    task_type = TaskType.A4_STEPWISE_REASONING
    task_name = "段階的推論 + 計算"
    description = "Chain-of-Thoughtで複雑な計算を1ステップずつ検証"

    def __init__(self, llm=None):
        super().__init__(llm)
        self.prompt = ChatPromptTemplate.from_template(A4_STEPWISE_REASONING_PROMPT)
        self.parser = JsonOutputParser()

    async def execute(self, context: AuditContext) -> TaskResult:
        """
        Execute stepwise reasoning and calculation verification.
        """
        if not self.llm:
            return self._create_result(
                success=False,
                result=None,
                reasoning="LLMが設定されていません",
                confidence=0.0
            )

        evidence_data = self._extract_evidence_data(context)

        try:
            chain = self.prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "evidence_data": evidence_data,
            })

            # Determine success based on calculation results
            final_result = result.get("final_result", {})
            integrity_checks = result.get("integrity_checks", [])

            # Success if final match and all integrity checks pass
            final_match = final_result.get("match", False)
            all_checks_passed = all(c.get("passed", False) for c in integrity_checks)

            success = final_match and (len(integrity_checks) == 0 or all_checks_passed)

            return self._create_result(
                success=success,
                result=result,
                reasoning=result.get("reasoning", ""),
                confidence=result.get("confidence", 0.0),
                evidence_refs=self._summarize_steps(result.get("calculation_steps", []))
            )

        except Exception as e:
            return self._create_result(
                success=False,
                result=None,
                reasoning=f"段階的推論中にエラーが発生: {str(e)}",
                confidence=0.0
            )

    def _extract_evidence_data(self, context: AuditContext) -> str:
        """Extract numerical data from evidence files"""
        data_parts = []

        for ef in context.evidence_files:
            ext = ef.extension.lower()
            if ext in ['.csv', '.txt', '.json']:
                try:
                    import base64
                    content = base64.b64decode(ef.base64_content).decode('utf-8')
                    data_parts.append(f"[{ef.file_name}]\n{content}")
                except Exception:
                    pass

        # Include control description for context
        if context.control_description:
            data_parts.insert(0, f"[統制記述]\n{context.control_description}")

        return "\n\n".join(data_parts) if data_parts else "データなし"

    def _summarize_steps(self, steps: List[dict]) -> List[str]:
        """Summarize calculation steps for evidence reference"""
        summaries = []
        for step in steps[:5]:  # Limit to first 5 steps
            desc = step.get("description", "")
            result = step.get("result", "")
            summaries.append(f"Step {step.get('step_number', '?')}: {desc} = {result}")
        return summaries
