import json
from typing import Dict, Any, List
from utils import call_llm, logger, parse_json
from models import SectionPlan, FactWritingGuidance, VerificationResult
import prompts
import config


class VerifierAgent:
    def __init__(self):
        pass

    # =========================================================================
    # STEP 4: VERIFY SECTION
    # =========================================================================

    def verify_section(
        self,
        content: str,
        section_plan: SectionPlan,
        fact_map: Dict[str, FactWritingGuidance],
        table_data: Dict[str, Any],
        strategy_assignment: Any
    ) -> VerificationResult:
        """
        Step 4: Verify a section's content against required facts.
        """
        # Convert table to markdown
        markdown_table = self._json_to_markdown(table_data)

        # Build reverse lookup from fact strings to fact objects
        fact_lookup = {}
        for fact_obj in fact_map.values():
            fact_lookup[fact_obj.fact] = fact_obj
            for sub_fact in fact_obj.sub_facts.keys():
                fact_lookup[sub_fact] = fact_obj

        # Build facts with guidance (including cell key)
        facts_with_guidance = []
        for fact_str in section_plan.facts:
            if fact_str in fact_lookup:
                fact_obj = fact_lookup[fact_str]

                # Check if fact_str is a sub_fact
                if fact_str in fact_obj.sub_facts:
                    # If it's a sub_fact, use only this specific sub_fact
                    sub_guidance = fact_obj.sub_facts[fact_str]
                    facts_with_guidance.append(
                        f"- **Cell:** {fact_obj.primary_key}+{fact_obj.attribute}\n"
                        f"  **Fact:** {fact_str}\n"
                        f"  **Guidance:** {sub_guidance}"
                    )
                elif fact_obj.sub_facts:
                    # If it's the main fact and sub_facts exist, use ONLY sub_facts (they replace the main fact)
                    for sub_fact, sub_guidance in fact_obj.sub_facts.items():
                        facts_with_guidance.append(
                            f"- **Cell:** {fact_obj.primary_key}+{fact_obj.attribute}\n"
                            f"  **Fact:** {sub_fact}\n"
                            f"  **Guidance:** {sub_guidance}"
                        )
                else:
                    # No sub_facts, use the main fact
                    facts_with_guidance.append(
                        f"- **Cell:** {fact_obj.primary_key}+{fact_obj.attribute}\n"
                        f"  **Fact:** {fact_str}\n"
                        f"  **Guidance:** {fact_obj.writing_guidance}"
                    )

        facts_text = "\n".join(facts_with_guidance)

        prompt = prompts.VERIFY_SECTION_PROMPT.format(
            markdown_table=markdown_table,
            title=section_plan.title,
            content=content,
            facts_with_guidance=facts_text
        )

        messages = [
            {"role": "system", "content": prompts.VERIFY_SECTION_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        try:
            verify_model = config.VERIFIER_MODEL
            response = call_llm(messages, model=verify_model, json_mode=True)
            data = parse_json(response)
            return VerificationResult(**data)
        except Exception as e:
            logger.error(f"Section verification failed: {e}")
            return VerificationResult(ok=False, errors=[{"description": f"Verification error: {e}", "suggestion": "Retry"}])

    def _json_to_markdown(self, table_data: Dict[str, Any]) -> str:
        """Convert table data to markdown format."""
        header = table_data["header"]
        data = table_data["data"]

        if not header:
            return ""

        flat_header = [h[0] if isinstance(h, list) and h else str(h) for h in header]

        md = "| " + " | ".join(flat_header) + " |\n"
        md += "| " + " | ".join(["---"] * len(flat_header)) + " |\n"

        for row in data:
            flat_row = [str(c[0]) if isinstance(c, list) and c else str(c) for c in row]
            md += "| " + " | ".join(flat_row) + " |\n"

        return md
