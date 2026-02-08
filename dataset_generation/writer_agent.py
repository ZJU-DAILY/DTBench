from typing import Dict, Any, List
from utils import call_llm, logger, parse_json
from models import SectionPlan, FactWritingGuidance
import prompts
import config


class WriterAgent:
    def __init__(self):
        pass

    # =========================================================================
    # STEP 3: WRITE SECTION
    # =========================================================================

    def write_section(
        self,
        section_plan: SectionPlan,
        fact_map: Dict[str, FactWritingGuidance],
        theme: str,
        genre: str,
        previous_summary: str = None
    ) -> str:
        """
        Step 3: Write a section based on its plan and fact guidance.
        """
        # Build reverse lookup from fact strings to fact objects
        fact_lookup = {}
        for fact_obj in fact_map.values():
            fact_lookup[fact_obj.fact] = fact_obj
            for sub_fact in fact_obj.sub_facts.keys():
                fact_lookup[sub_fact] = fact_obj

        # Build facts with guidance
        facts_with_guidance = []
        for fact_str in section_plan.facts:
            if fact_str in fact_lookup:
                fact_obj = fact_lookup[fact_str]
                # Check if fact_str is a sub_fact
                if fact_str in fact_obj.sub_facts:
                    # If it's a sub_fact, use only this specific sub_fact
                    sub_guidance = fact_obj.sub_facts[fact_str]
                    facts_with_guidance.append(
                        f"- **Fact:** {fact_str}\n  **Guidance:** {sub_guidance}"
                    )
                elif fact_obj.sub_facts:
                    # If it's the main fact and sub_facts exist, use ONLY sub_facts (they replace the main fact)
                    for sub_fact, sub_guidance in fact_obj.sub_facts.items():
                        facts_with_guidance.append(
                            f"- **Fact:** {sub_fact}\n  **Guidance:** {sub_guidance}"
                        )
                else:
                    # No sub_facts, use the main fact
                    facts_with_guidance.append(
                        f"- **Fact:** {fact_str}\n  **Guidance:** {fact_obj.writing_guidance}"
                    )

        facts_text = "\n".join(facts_with_guidance) if facts_with_guidance else "No specific facts assigned."

        # Format previous summary
        prev_summary_text = previous_summary if previous_summary else "This is the first section of the document."

        prompt = prompts.WRITE_SECTION_PROMPT.format(
            theme=theme,
            genre=genre,
            previous_summary=prev_summary_text,
            title=section_plan.title,
            current_summary=section_plan.summary,
            content_goal=section_plan.goal,
            facts_with_guidance=facts_text
        )

        messages = [
            {"role": "system", "content": prompts.WRITE_SECTION_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        try:
            content = call_llm(messages, model=config.WRITER_MODEL)
            return content
        except Exception as e:
            logger.error(f"Failed to write section {section_plan.section_id}: {e}")
            return ""

    # =========================================================================
    # STEP 4: REPAIR SECTION
    # =========================================================================

    def repair_section(
        self,
        original_content: str,
        section_plan: SectionPlan,
        fact_map: Dict[str, FactWritingGuidance],
        errors: List[Dict[str, str]]
    ) -> str:
        """
        Step 4: Repair a section that failed verification.
        """
        # Build reverse lookup from fact strings to fact objects
        fact_lookup = {}
        for fact_obj in fact_map.values():
            fact_lookup[fact_obj.fact] = fact_obj
            for sub_fact in fact_obj.sub_facts.keys():
                fact_lookup[sub_fact] = fact_obj

        # Build facts with guidance
        facts_with_guidance = []
        for fact_str in section_plan.facts:
            if fact_str in fact_lookup:
                fact_obj = fact_lookup[fact_str]
                # Check if fact_str is a sub_fact
                if fact_str in fact_obj.sub_facts:
                    # If it's a sub_fact, use only this specific sub_fact
                    sub_guidance = fact_obj.sub_facts[fact_str]
                    facts_with_guidance.append(
                        f"- **Fact:** {fact_str}\n  **Guidance:** {sub_guidance}"
                    )
                else:
                    # If it's the main fact, include it and all sub_facts if any
                    facts_with_guidance.append(
                        f"- **Fact:** {fact_str}\n  **Guidance:** {fact_obj.writing_guidance}"
                    )
                    for sub_fact, sub_guidance in fact_obj.sub_facts.items():
                        facts_with_guidance.append(
                            f"- **Fact:** {sub_fact}\n  **Guidance:** {sub_guidance}"
                        )

        facts_text = "\n".join(facts_with_guidance)
        errors_text = "\n".join([f"- {e['description']}: {e['suggestion']}" for e in errors])

        prompt = prompts.REPAIR_SECTION_PROMPT.format(
            content=original_content,
            errors=errors_text,
            facts_with_guidance=facts_text
        )

        messages = [
            {"role": "system", "content": prompts.REPAIR_SECTION_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        try:
            content = call_llm(messages, model=config.WRITER_MODEL)
            return content
        except Exception as e:
            logger.error(f"Failed to repair section: {e}")
            return original_content
