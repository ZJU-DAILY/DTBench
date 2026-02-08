import os
import json
from typing import Dict, Any, List, Tuple, Optional
from concurrent.futures import as_completed
from utils import call_llm, logger, llm_executor, parse_json, safe_filename, write_json, read_json
from models import StrategyAssignment, FactWritingGuidance, VerificationResult
import prompts
import config
from strategies import DETAILED_STRATEGY_DEFINITIONS, SHORT_STRATEGY_DEFINITIONS


class RefinementAgent:
    def __init__(self):
        pass

    # =========================================================================
    # STEP 1: CELL & FACT WRITING GUIDANCE
    # =========================================================================

    def refine_all_cells(
        self,
        strategy_assignment: StrategyAssignment,
        table_data: Dict[str, Any],
        cache_dir: str
    ) -> Tuple[List[FactWritingGuidance], Dict[str, FactWritingGuidance]]:
        """
        Process all cells to generate fact guidance.
        Returns (fact_list, fact_map) where fact_map: primary_key+attribute -> FactWritingGuidance
        """
        # Parse table
        header, primary_key, pk_index = self._parse_table(table_data)
        row_lookup = self._build_row_lookup(table_data, header, primary_key, pk_index)
        markdown_table = self._json_to_markdown(table_data)

        # Setup cache directories
        cell_cache_dir = os.path.join(cache_dir, "cell_guidance")
        fact_cache_dir = os.path.join(cache_dir, "fact_guidance")
        os.makedirs(cell_cache_dir, exist_ok=True)
        os.makedirs(fact_cache_dir, exist_ok=True)

        fact_list = []
        fact_map = {}
        futures = []

        # Sort headers by length descending to match longest attributes first
        # This handles cases where attribute names contain commas
        sorted_headers = sorted(header, key=len, reverse=True)

        # Process each cell assignment
        for cell_key, strategies in strategy_assignment.assignments.items():
            pk = None
            attr = None

            # Try to identify attribute by matching known headers (robust to commas in attribute names)
            for h in sorted_headers:
                suffix = f",{h}"
                if cell_key.endswith(suffix):
                    possible_pk = cell_key[:-len(suffix)]
                    # Verify this PK exists in row_lookup
                    if possible_pk in row_lookup:
                        pk = possible_pk
                        attr = h
                        break

            # Fallback to simple split if heuristic fails
            if pk is None:
                try:
                    pk, attr = cell_key.rsplit(",", 1)
                except ValueError:
                    logger.warning(f"Skipping malformed cell_key: {cell_key}")
                    continue

            cache_key = safe_filename(cell_key)

            futures.append(llm_executor.submit(
                self._process_single_cell,
                pk, attr, strategies,
                row_lookup, markdown_table,
                cell_cache_dir, fact_cache_dir, cache_key,
                table_data
            ))

        # Collect results
        for future in as_completed(futures):
            result = future.result()
            if result:
                fact_list.append(result)
                # Build map: primary_key+attribute -> FactWritingGuidance
                map_key = f"{result.primary_key}+{result.attribute}"
                fact_map[map_key] = result

        return fact_list, fact_map

    def _process_single_cell(
        self,
        pk: str,
        attr: str,
        strategies: List[str],
        row_lookup: Dict[str, Dict[str, str]],
        markdown_table: str,
        cell_cache_dir: str,
        fact_cache_dir: str,
        cache_key: str,
        table_data: Dict[str, Any]
    ) -> Optional[FactWritingGuidance]:
        """Process a single cell through both Step 1a and 1b."""

        # Get cell value
        row = row_lookup[pk]
        if not row:
            logger.error(f"Row not found for PK: {pk}")
            return None
        value = row[attr]

        # Check fact cache first
        fact_cache_path = os.path.join(fact_cache_dir, f"{cache_key}.json")
        if os.path.exists(fact_cache_path):
            try:
                data = read_json(fact_cache_path)
                return FactWritingGuidance(**data)
            except Exception as e:
                logger.warning(f"Failed to load fact cache for {cache_key}: {e}")

        # Step 1a: Generate Cell Guidance
        cell_guidance = self._generate_cell_guidance(
            pk, attr, value, strategies, markdown_table, cell_cache_dir, cache_key, table_data
        )
        if not cell_guidance:
            error_msg = f"Failed to generate cell guidance for {pk},{attr} with strategies {strategies} after all retries."
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Step 1b: Generate Fact Guidance
        fact_guidance = self._generate_fact_guidance(
            pk, attr, value, cell_guidance, strategies, markdown_table, fact_cache_path, table_data
        )

        return fact_guidance

    def _generate_cell_guidance(
        self, pk: str, attr: str, value: str, strategies: List[str],
        markdown_table: str, cache_dir: str, cache_key: str, table_data: Dict[str, Any]
    ) -> Optional[str]:
        """Step 1a: Generate and verify cell writing guidance."""

        cache_path = os.path.join(cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_path):
            try:
                data = read_json(cache_path)
                return data["guidance"]
            except Exception as e:
                logger.warning(f"Failed to load cell guidance cache: {e}")

        if not strategies:
            # Generate semantic description based on primary key type
            pk_desc = self._get_pk_description(pk, table_data)
            guidance = f"Naturally weave into the narrative that the '{attr}' for {pk_desc} is '{value}'. Avoid merely listing the fact; it should be integrated smoothly into a descriptive sentence or analytical point."
            write_json(cache_path, {"guidance": guidance})
            return guidance

        # Construct detailed strategy definitions
        detailed_defs = "\n\n".join([DETAILED_STRATEGY_DEFINITIONS[s] for s in strategies if s in DETAILED_STRATEGY_DEFINITIONS])

        # Format primary key value for display
        pk_display = self._get_pk_description(pk, table_data)

        prompt = prompts.CELL_GUIDANCE_PROMPT.format(
            markdown_table=markdown_table,
            primary_key=pk_display,
            attribute=attr,
            value=value,
            strategies=json.dumps(strategies),
            detailed_strategy_definitions=detailed_defs
        )

        messages = [
            {"role": "system", "content": prompts.CELL_GUIDANCE_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(config.REFINE_MAX_RETRIES):
            try:
                response = call_llm(messages, model=config.REFINER_MODEL, json_mode=True)
                data = parse_json(response)
                guidance = data["guidance"]

                # Verify guidance
                ok, error_msg = self._verify_cell_guidance(pk, attr, value, strategies, guidance, markdown_table, detailed_defs, table_data)
                if ok:
                    write_json(cache_path, {"guidance": guidance})
                    return guidance

                logger.warning(f"Cell guidance verification failed for {pk},{attr}, retrying...")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"The guidance failed verification.\n\n{error_msg}\n\nPlease revise based on the suggestions above."})

            except Exception as e:
                logger.error(f"Failed to generate cell guidance for {pk},{attr}: {e}")
                messages = [
                    {"role": "system", "content": prompts.CELL_GUIDANCE_SYSTEM},
                    {"role": "user", "content": prompt}
                ]

        return None

    def _verify_cell_guidance(self, pk: str, attr: str, value: str, strategies: List[str], guidance: str, markdown_table: str, detailed_defs: str, table_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify cell guidance using LLM.
        Returns (ok, error_message)
        """
        # Use short definitions for verification
        short_defs = "\n\n".join([SHORT_STRATEGY_DEFINITIONS[s] for s in strategies if s in SHORT_STRATEGY_DEFINITIONS])

        # Format primary key value for display
        pk_display = self._get_pk_description(pk, table_data)

        prompt = prompts.CELL_GUIDANCE_VERIFY_PROMPT.format(
            markdown_table=markdown_table,
            primary_key=pk_display,
            attribute=attr,
            value=value,
            strategies=json.dumps(strategies),
            detailed_guidance=guidance,
            strategy_definitions=short_defs
        )

        messages = [
            {"role": "system", "content": prompts.CELL_GUIDANCE_VERIFY_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        verify_model = config.CELL_GUIDANCE_VERIFY_MODEL or config.REFINER_MODEL
        response = call_llm(messages, model=verify_model, json_mode=True)
        data = parse_json(response)
        ok = data["ok"]

        if not ok:
            errors = data["errors"]
            error_messages = []
            for err in errors:
                desc = err["description"]
                sugg = err["suggestion"]
                error_messages.append(f"Error: {desc}\nSuggestion: {sugg}")
            error_text = "\n\n".join(error_messages) if error_messages else "Verification failed without specific errors."
            return False, error_text
        else:
            return True, ""

    def _generate_fact_guidance(
        self, pk: str, attr: str, value: str, cell_guidance: str,
        strategies: List[str], markdown_table: str, cache_path: str, table_data: Dict[str, Any]
    ) -> Optional[FactWritingGuidance]:
        """Step 1b: Generate and verify fact writing guidance (with potential sub-facts)."""

        # Generate semantic fact description based on primary key type
        pk_desc = self._get_pk_description(pk, table_data)
        main_fact = f"The {attr} for {pk_desc} is {value}"

        # Check if strategies contain R or D
        has_r_or_d = any(s.startswith('R') or s.startswith('D') for s in strategies)

        if not has_r_or_d:
            # Simple case: no R/D strategies, directly create fact guidance
            fact_obj = FactWritingGuidance(
                primary_key=pk,
                attribute=attr,
                fact=main_fact,
                writing_guidance=cell_guidance,
                sub_facts={}
            )
            write_json(cache_path, fact_obj.model_dump())
            return fact_obj

        # Complex case: has R or D, need to check if should split
        prompt = prompts.FACT_GUIDANCE_PROMPT.format(
            primary_key=pk,
            attribute=attr,
            value=value,
            guidance=cell_guidance
        )

        messages = [
            {"role": "system", "content": prompts.FACT_GUIDANCE_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(config.REFINE_MAX_RETRIES):
            try:
                response = call_llm(messages, model=config.REFINER_MODEL, json_mode=True)
                data = parse_json(response)

                is_split = data["is_split"]

                if is_split:
                    # Split mode: use sub_facts
                    sub_facts_dict = data["sub_facts"]
                    fact_obj = FactWritingGuidance(
                        primary_key=pk,
                        attribute=attr,
                        fact=main_fact,
                        writing_guidance="",
                        sub_facts=sub_facts_dict
                    )

                    # Verify fact guidance only for split mode
                    ok, error_msg = self._verify_fact_guidance(attr, value, cell_guidance, main_fact, sub_facts_dict)
                    if not ok:
                        logger.warning(f"Fact guidance verification failed for {pk},{attr}, retrying...")
                        messages.append({"role": "assistant", "content": response})
                        messages.append({"role": "user", "content": f"The fact guidance failed verification.\n\n{error_msg}\n\nPlease revise based on the suggestions above."})
                        continue
                else:
                    fact_obj = FactWritingGuidance(
                        primary_key=pk,
                        attribute=attr,
                        fact=main_fact,
                        writing_guidance=cell_guidance,
                        sub_facts={}
                    )

                write_json(cache_path, fact_obj.model_dump())
                return fact_obj

            except Exception as e:
                logger.error(f"Failed to generate fact guidance for {pk},{attr}: {e}")
                messages = [
                    {"role": "system", "content": prompts.FACT_GUIDANCE_SYSTEM},
                    {"role": "user", "content": prompt}
                ]

        return None

    def _verify_fact_guidance(self, attr: str, value: str, original_guidance: str, original_fact: str, sub_facts: Dict[str, str]) -> Tuple[bool, str]:
        """Verify fact guidance splitting using LLM.
        Returns (ok, error_message)
        """
        prompt = prompts.FACT_GUIDANCE_VERIFY_PROMPT.format(
            attribute=attr,
            value=value,
            original_guidance=original_guidance,
            original_fact=original_fact,
            sub_facts_json=json.dumps(sub_facts, ensure_ascii=False)
        )

        messages = [
            {"role": "system", "content": prompts.FACT_GUIDANCE_VERIFY_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        try:
            verify_model = config.FACT_GUIDANCE_VERIFY_MODEL or config.REFINER_MODEL
            response = call_llm(messages, model=verify_model, json_mode=True)
            data = parse_json(response)
            ok = data["ok"]

            if not ok:
                errors = data["errors"]
                error_messages = []
                for err in errors:
                    desc = err["description"]
                    sugg = err["suggestion"]
                    error_messages.append(f"Error: {desc}\nSuggestion: {sugg}")
                error_text = "\n\n".join(error_messages) if error_messages else "Verification failed without specific errors."
                return False, error_text

            return True, ""
        except Exception as e:
            logger.error(f"Fact guidance verification failed: {e}")
            return False, f"Verification exception: {str(e)}"

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_pk_description(self, pk_value: str, table_data: Dict[str, Any]) -> str:
        """Generate a semantic description for primary key value."""
        primary_key = table_data["primary_key"]

        if isinstance(primary_key, list):
            # Composite primary key
            pk_parts = pk_value.split(", ")
            if len(pk_parts) == len(primary_key):
                pairs = [f"{col}='{val}'" for col, val in zip(primary_key, pk_parts)]
                return "the record with " + " and ".join(pairs)
            else:
                # Fallback if split doesn't match
                return f"'{pk_value}'"
        else:
            # Single primary key
            return f"'{pk_value}'"

    def _parse_table(self, table_data: Dict[str, Any]) -> Tuple[List[str], str, Any]:
        """Parse table header."""
        header = [h[0] if isinstance(h, list) and h else str(h) for h in table_data["header"]]
        primary_key = table_data["primary_key"]

        if isinstance(primary_key, list):
            pk_index = [header.index(pk) for pk in primary_key]
            primary_key_str = ", ".join(primary_key)
        else:
            pk_index = header.index(primary_key)
            primary_key_str = primary_key

        return header, primary_key_str, pk_index

    def _build_row_lookup(self, table_data: Dict[str, Any], header: List[str], primary_key: str, pk_index: Any) -> Dict[str, Dict[str, str]]:
        """Build lookup: pk_value -> {attr: value}."""
        data = table_data["data"]
        lookup = {}

        for row in data:
            flat_row = [str(c[0]) if isinstance(c, list) and c else str(c) for c in row]
            if not flat_row:
                continue

            if isinstance(pk_index, list):
                pk_val = ", ".join([str(flat_row[i]) for i in pk_index])
            else:
                pk_val = flat_row[pk_index]

            lookup[pk_val] = dict(zip(header, flat_row))

        return lookup

    def _json_to_markdown(self, table_data: Dict[str, Any]) -> str:
        """Convert table to markdown."""
        header = table_data["header"]
        data = table_data["data"]

        flat_header = [h[0] if isinstance(h, list) and h else str(h) for h in header]
        md = "| " + " | ".join(flat_header) + " |\n"
        md += "| " + " | ".join(["---"] * len(flat_header)) + " |\n"

        for row in data:
            flat_row = [str(c[0]) if isinstance(c, list) and c else str(c) for c in row]
            md += "| " + " | ".join(flat_row) + " |\n"

        return md
