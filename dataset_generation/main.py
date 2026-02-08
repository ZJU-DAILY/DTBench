import os
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

import config
from utils import logger, safe_filename, llm_executor, read_json, write_json
from models import StrategyAssignment, FactWritingGuidance, DocumentPlan, Document, Section
from planner_agent import StrategicPlannerAgent
from refiner_agent import RefinementAgent
from writer_agent import WriterAgent
from verifier_agent import VerifierAgent

# Initialize Agents
planner = StrategicPlannerAgent()
refiner = RefinementAgent()
writer = WriterAgent()
verifier = VerifierAgent()


def process_task(file_path: str):
    """
    Process a single table file through the NEW 5-step pipeline.
    """

    filename = os.path.basename(file_path)
    task_name = filename.replace('.json', '')
    output_dir = os.path.join(config.OUTPUT_PATH, task_name)
    cache_dir = os.path.join(output_dir, "cache")

    logger.info(f"Starting Task: {task_name}")

    try:
        # Check if dir exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Check if task already completed
        final_doc_path = os.path.join(output_dir, "final_document.md")
        if os.path.exists(final_doc_path):
            logger.info(f"[{task_name}] Task already completed, skipping...")
            return

        # Load table data
        with open(file_path, 'r', encoding='utf-8') as f:
            table_data = json.load(f)

        # Copy table file to output directory
        table_copy_path = os.path.join(output_dir, "raw_table.json")
        if not os.path.exists(table_copy_path):
            shutil.copy2(file_path, table_copy_path)
            logger.debug(f"[{task_name}] Copied table file to output directory")

        # =================================================================
        # STEP 0: STRATEGY ASSIGNMENT
        # =================================================================
        logger.info(f"[{task_name}] Step 0: Assigning strategies...")

        strategy_cache_path = os.path.join(output_dir, "strategy_assignment.json")
        if os.path.exists(strategy_cache_path):
            try:
                data = read_json(strategy_cache_path)
                strategy_assignment = StrategyAssignment(**data)
                logger.debug(f"[{task_name}] Loaded strategy assignment from cache ({len(strategy_assignment.assignments)} cells)")
            except Exception as e:
                logger.warning(f"[{task_name}] Failed to load strategy cache: {e}, regenerating...")
                strategy_assignment = planner.assign_strategies(table_data)
                write_json(strategy_cache_path, strategy_assignment.model_dump())
                logger.debug(f"[{task_name}] Assigned strategies to {len(strategy_assignment.assignments)} cells")
        else:
            strategy_assignment = planner.assign_strategies(table_data)
            write_json(strategy_cache_path, strategy_assignment.model_dump())
            logger.debug(f"[{task_name}] Assigned strategies to {len(strategy_assignment.assignments)} cells")

        # =================================================================
        # STEP 1: GENERATE WRITING GUIDANCE
        # =================================================================
        logger.info(f"[{task_name}] Step 1: Generating writing guidance...")

        fact_guidance_cache_path = os.path.join(output_dir, "fact_guidance.json")
        if os.path.exists(fact_guidance_cache_path):
            try:
                data = read_json(fact_guidance_cache_path)
                fact_list = [FactWritingGuidance(**item) for item in data["fact_list"]]

                # build fact_map using primary_key+attribute as key
                fact_map = {}
                for fact_obj in fact_list:
                    map_key = f"{fact_obj.primary_key}+{fact_obj.attribute}"
                    fact_map[map_key] = fact_obj

                logger.debug(f"[{task_name}] Loaded fact guidance from cache ({len(fact_list)} facts)")
            except Exception as e:
                logger.warning(f"[{task_name}] Failed to load fact guidance cache: {e}, regenerating...")
                os.makedirs(cache_dir, exist_ok=True)
                fact_list, fact_map = refiner.refine_all_cells(strategy_assignment, table_data, cache_dir)
                write_json(fact_guidance_cache_path, {"fact_list": [f.model_dump() for f in fact_list]})
                logger.debug(f"[{task_name}] Generated {len(fact_list)} facts")
        else:
            os.makedirs(cache_dir, exist_ok=True)
            fact_list, fact_map = refiner.refine_all_cells(strategy_assignment, table_data, cache_dir)
            write_json(fact_guidance_cache_path, {"fact_list": [f.model_dump() for f in fact_list]})
            logger.debug(f"[{task_name}] Generated {len(fact_list)} facts")

        # =================================================================
        # STEP 2: PLAN DOCUMENT
        # =================================================================
        logger.info(f"[{task_name}] Step 2: Planning document structure...")

        document_plan_cache_path = os.path.join(output_dir, "document_plan.json")
        if os.path.exists(document_plan_cache_path):
            try:
                data = read_json(document_plan_cache_path)
                document_plan = DocumentPlan(**data)
                logger.debug(f"[{task_name}] Loaded document plan from cache ({len(document_plan.sections)} sections)")
            except Exception as e:
                logger.warning(f"[{task_name}] Failed to load document plan cache: {e}, regenerating...")
                # Extract facts for planning: use sub_facts if exist, otherwise use main fact
                fact_strings = []
                for f in fact_list:
                    if f.sub_facts:
                        fact_strings.extend(f.sub_facts.keys())
                    else:
                        fact_strings.append(f.fact)
                document_plan = planner.plan_document(fact_strings, table_data, fact_map)
                write_json(document_plan_cache_path, document_plan.model_dump())
                logger.debug(f"[{task_name}] Planned {len(document_plan.sections)} sections")
        else:
            # Extract facts for planning: use sub_facts if exist, otherwise use main fact
            fact_strings = []
            for f in fact_list:
                if f.sub_facts:
                    fact_strings.extend(f.sub_facts.keys())
                else:
                    fact_strings.append(f.fact)
            document_plan = planner.plan_document(fact_strings, table_data, fact_map)
            write_json(document_plan_cache_path, document_plan.model_dump())
            logger.debug(f"[{task_name}] Planned {len(document_plan.sections)} sections")

        # =================================================================
        # STEP 3: WRITE DOCUMENT
        # =================================================================
        logger.info(f"[{task_name}] Step 3: Writing sections...")
        os.makedirs(cache_dir, exist_ok=True)

        sections = [None] * len(document_plan.sections)
        futures = {}

        for i, section_plan in enumerate(document_plan.sections):
            cache_path = os.path.join(cache_dir, f"section_{section_plan.section_id}.json")

            # Use previous section's summary from plan
            current_prev_summary = None
            if i > 0:
                current_prev_summary = document_plan.sections[i-1].summary

            future = llm_executor.submit(
                write_section_task,
                section_plan,
                fact_map,
                document_plan.theme,
                document_plan.genre,
                current_prev_summary,
                cache_path,
                task_name
            )
            futures[future] = i

        for future in as_completed(futures):
            try:
                section = future.result()
                idx = futures[future]
                sections[idx] = section
            except Exception as e:
                 logger.error(f"[{task_name}] Error writing section: {e}")

        # Filter out Nones in case of failure
        sections = [s for s in sections if s is not None]

        document = Document(
            theme=document_plan.theme,
            genre=document_plan.genre,
            sections=sections
        )

        logger.info(f"[{task_name}] Wrote {len(sections)} sections")

        # =================================================================
        # STEP 4: VERIFY & REPAIR
        # =================================================================
        logger.info(f"[{task_name}] Step 4: Verifying and repairing sections...")

        for attempt in range(config.VERIFY_AND_REPAIR_MAX_RETRIES):
            unverified = [s for s in document.sections if not s.verified]
            if not unverified:
                break

            logger.debug(f"[{task_name}] Verify/Repair attempt {attempt+1}/{config.VERIFY_AND_REPAIR_MAX_RETRIES}, {len(unverified)} sections to process")

            futures = []
            for section in unverified:
                section_plan = next((sp for sp in document_plan.sections if sp.section_id == section.section_id), None)
                if section_plan:
                    cache_path = os.path.join(cache_dir, f"section_{section.section_id}.json")
                    futures.append(llm_executor.submit(
                        verify_repair_section_task,
                        section, section_plan, fact_map, table_data, strategy_assignment, cache_path
                    ))

            # Update sections
            for future in as_completed(futures):
                updated_section = future.result()
                if updated_section:
                    # Replace in document
                    idx = next((i for i, s in enumerate(document.sections) if s.section_id == updated_section.section_id), None)
                    if idx is not None:
                        document.sections[idx] = updated_section

        verified_count = sum(1 for s in document.sections if s.verified)
        logger.info(f"[{task_name}] Verified {verified_count}/{len(document.sections)} sections")

        # =================================================================
        # SYNTHESIZE FINAL DOCUMENT
        # =================================================================
        if verified_count != len(document.sections):
            logger.error(f"[{task_name}] Not all sections verified ({verified_count}/{len(document.sections)}), skipping final document synthesis")
            return

        logger.info(f"[{task_name}] Synthesizing final document...")

        with open(final_doc_path, 'w', encoding='utf-8') as f:
            for section in document.sections:
                f.write(f"{section.content}\n\n")

        # Cleanup cache only on success
        try:
            shutil.rmtree(cache_dir)
            logger.debug(f"[{task_name}] Cleaned up cache directory")
        except Exception as e:
            logger.warning(f"[{task_name}] Failed to clean cache dir: {e}")

        logger.info(f"[{task_name}] Task completed successfully!")

    except Exception as e:
        logger.error(f"[{task_name}] Task failed with exception: {e}", exc_info=True)


def write_section_task(section_plan, fact_map, theme, genre, previous_summary, cache_path, task_name):
    """Write a single section, using cache if available."""
    # Check cache
    if os.path.exists(cache_path):
        try:
            data = read_json(cache_path)
            section = Section(**data)
            logger.debug(f"[{task_name}] Using cached section {section_plan.section_id}")
            return section
        except Exception as e:
            logger.warning(f"Failed to load section cache: {e}")

    # Write section
    content = writer.write_section(section_plan, fact_map, theme, genre, previous_summary)
    section = Section(
        section_id=section_plan.section_id,
        title=section_plan.title,
        content=content,
        verified=False
    )
    write_json(cache_path, section.model_dump())
    logger.debug(f"[{task_name}] Wrote section {section_plan.section_id}")
    return section


def verify_repair_section_task(section, section_plan, fact_map, table_data, strategy_assignment, cache_path):
    """Verify a section and repair if needed."""
    verification = verifier.verify_section(section.content, section_plan, fact_map, table_data, strategy_assignment)

    if verification.ok:
        section.verified = True
        write_json(cache_path, section.model_dump())
        return section

    # Repair
    repaired_content = writer.repair_section(section.content, section_plan, fact_map, verification.errors)
    section.content = repaired_content
    section.verified = False  # Will be verified in next iteration
    write_json(cache_path, section.model_dump())
    return section

def main():
    if not os.path.exists(config.INPUT_PATH):
        print(f"✗ Input path {config.INPUT_PATH} does not exist.")
        return

    files = [os.path.join(config.INPUT_PATH, f) for f in os.listdir(config.INPUT_PATH) if f.endswith('.json')]

    logger.info("="*70)
    logger.info(f"Starting pipeline with {len(files)} tasks")
    logger.info(f"Configuration: MAX_PARALLEL_TASK={config.MAX_PARALLEL_TASK}")
    logger.info("="*70)

    with ThreadPoolExecutor(max_workers=config.MAX_PARALLEL_TASK) as executor:
        futures = [executor.submit(process_task, file) for file in files]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Task execution error: {e}", exc_info=True)

    logger.info("="*70)
    logger.info("PIPELINE COMPLETED")
    logger.info("="*70)


if __name__ == "__main__":
    main()
