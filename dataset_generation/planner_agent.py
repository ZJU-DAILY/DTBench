import json
from typing import Dict, Any, List, Tuple
from collections import Counter
from utils import call_llm, logger, parse_json
from models import StrategyAssignment, DocumentPlan
import prompts
import config
from strategies import DETAILED_STRATEGY_DEFINITIONS, SHORT_STRATEGY_DEFINITIONS


class StrategicPlannerAgent:
    def __init__(self):
        pass

    # =========================================================================
    # STEP 0: STRATEGY ASSIGNMENT
    # =========================================================================

    def assign_strategies(self, table_data: Dict[str, Any]) -> StrategyAssignment:
        """
        Step 0: Assign strategies to every non-empty and and non-primary key cell.
        """
        if not config.ENABLE_STRATEGY_ASSIGNMENT:
            logger.info("Strategy assignment is disabled. Returning empty strategies.")
            header, primary_key, pk_index = self._parse_table_header(table_data)
            expected_cells = self._get_nonempty_cells(table_data, header, primary_key, pk_index)
            flat_assignments = {cell_key: [] for cell_key in expected_cells}
            return StrategyAssignment(assignments=flat_assignments)

        markdown_table = self._json_to_markdown(table_data)

        # Format SHORT_STRATEGY_DEFINITIONS dict to string
        strategy_defs_str = "\n".join([f"{i+1}. {definition}" for i, definition in enumerate(SHORT_STRATEGY_DEFINITIONS.values())])

        # Format primary key for display
        pk_raw = table_data["primary_key"]
        if isinstance(pk_raw, list):
            pk_display = f"[{', '.join(pk_raw)}] (composite key)"
        else:
            pk_display = pk_raw

        prompt = prompts.STRATEGY_ASSIGNMENT_PROMPT.format(
            markdown_table=markdown_table,
            primary_key=pk_display,
            strategy_definitions=strategy_defs_str
        )

        messages = [
            {"role": "system", "content": prompts.STRATEGY_ASSIGNMENT_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(config.PLAN_MAX_RETRIES):
            try:
                response = call_llm(messages, model=config.PLANNER_MODEL, json_mode=True)
                data = parse_json(response)
                flat_assignments = {
                    f"{pk},{col}": strategies
                    for pk, cols in data["assignments"].items()
                    for col, strategies in cols.items()
                }
                assignment = StrategyAssignment(assignments=flat_assignments)

                # validation: check all non-empty cells are assigned
                error_msg = self._validate_strategy_assignment(assignment, table_data)
                if not error_msg:
                    return assignment

                logger.warning(f"Strategy assignment validation failed (Attempt {attempt+1}): {error_msg}")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"Error: {error_msg}. Please assign strategies to all missing cells."})

            except Exception as e:
                logger.error(f"Failed to assign strategies (Attempt {attempt+1}): {e}")

        raise RuntimeError("Failed to assign strategies after max retries")

    def _validate_strategy_assignment(self, assignment: StrategyAssignment, table_data: Dict[str, Any]) -> str:
        """
        Validate that every non-empty cell is assigned.
        Returns error message if invalid, empty string if valid.
        """
        header, primary_key, pk_index = self._parse_table_header(table_data)
        expected_cells = self._get_nonempty_cells(table_data, header, primary_key, pk_index)

        assigned_cells = set(assignment.assignments.keys())
        missing_cells = expected_cells - assigned_cells

        if missing_cells:
            return f"Missing cells: {list(missing_cells)}"  # Show first 10
        return ""

    # =========================================================================
    # STEP 2: DOCUMENT PLAN
    # =========================================================================

    def plan_document(self, facts: List[str], table_data: Dict[str, Any], fact_map: Dict[str, Any] = None) -> DocumentPlan:
        """
        Step 2: Plan document structure and assign facts to sections.
        Uses code-based validation (check all facts assigned, no duplicates).
        """
        # Create fact ID mapping (id -> fact_string)
        fact_id_to_string = {}
        fact_string_to_id = {}

        # Format facts list with IDs
        fact_to_groups = {f: [] for f in facts}
        group_counter = 1

        if fact_map:
            # 1. Identify all Primary Keys in the table
            header, _, pk_index = self._parse_table_header(table_data)
            all_pks = []
            for row in table_data['data']:
                flat_row = [str(c[0]) if isinstance(c, list) and c else str(c) for c in row]
                if not flat_row: continue
                r_pk = ", ".join([str(flat_row[i]) for i in pk_index]) if isinstance(pk_index, list) else flat_row[pk_index]
                if r_pk not in all_pks:
                    all_pks.append(r_pk)

            # Sort PKs by length descending to prevent partial matches (e.g. "India" matching "Indiana")
            all_pks.sort(key=len, reverse=True)
            pk_to_facts = {pk: [] for pk in all_pks}

            # 2. Process Cell-level (Split) Groups and Map Sub-facts to Rows
            for cell_key, guid in fact_map.items():
                if guid.sub_facts:
                    # pk is the part before the last comma in cell_key ("pk,col")
                    pk = cell_key.rsplit(",", 1)[0]

                    # Create a "Split Group" for this cell
                    sg_name = f"Group {group_counter}"
                    group_counter += 1

                    for sf in guid.sub_facts:
                        if sf in fact_to_groups:
                            fact_to_groups[sf].append(sg_name)
                            if pk in pk_to_facts:
                                pk_to_facts[pk].append(sf)

        lines = []
        for idx, f in enumerate(facts, start=1):
            fact_id = str(idx)
            fact_id_to_string[fact_id] = f
            fact_string_to_id[f] = fact_id

            entry = f"- [{fact_id}] {f}"
            if fact_to_groups.get(f):
                groups_str = ", ".join(fact_to_groups[f])
                entry += f" (Member of {groups_str})"
            lines.append(entry)

        facts_list = "\n".join(lines)

        # Get dispersion guidance
        if config.DISPERSION_STRATEGY == "sparse":
            dispersion_guidance = prompts.SPARSE_DISPERSION_GUIDANCE
        else:
            dispersion_guidance = prompts.DENSE_DISPERSION_GUIDANCE

        # Calculate min and max sections with lower bound
        calculated_min = round(len(facts) / config.FACTS_PER_SECTION_MAX)
        calculated_max = round(len(facts) / config.FACTS_PER_SECTION_MIN)

        if calculated_max < config.MIN_SECTIONS:
            min_sections = config.MIN_SECTIONS
            max_sections = config.MAX_SECTIONS
        else:
            min_sections = max(calculated_min, config.MIN_SECTIONS)
            max_sections = calculated_max

        prompt = prompts.DOCUMENT_PLAN_PROMPT.format(
            min_sections=min_sections,
            max_sections=max_sections,
            dispersion_guidance=dispersion_guidance,
            facts_list=facts_list
        )

        messages = [
            {"role": "system", "content": prompts.DOCUMENT_PLAN_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(config.PLAN_MAX_RETRIES):
            try:
                response = call_llm(messages, model=config.PLANNER_MODEL, json_mode=True)
                data = parse_json(response)

                # Convert fact IDs back to fact strings in the plan
                for section in data.get('sections', []):
                    fact_ids = section.get('facts', [])
                    fact_strings = []
                    for fid in fact_ids:
                        if fid in fact_id_to_string:
                            fact_strings.append(fact_id_to_string[fid])
                        else:
                            # If LLM returned the full fact string instead of ID, keep it
                            fact_strings.append(fid)
                    section['facts'] = fact_strings

                plan = DocumentPlan(**data)

                # Code-based validation: check all facts assigned exactly once
                error_msg = self._validate_document_plan(plan, facts)
                if not error_msg:
                    return plan

                logger.warning(f"Document plan validation failed (Attempt {attempt+1}): {error_msg}")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"Error: {error_msg}. Fix the plan."})

            except Exception as e:
                logger.error(f"Failed to plan document (Attempt {attempt+1}): {e}")

        raise RuntimeError("Failed to plan document after max retries")

    def _validate_document_plan(self, plan: DocumentPlan, facts: List[str]) -> str:
        """
        Validate that every fact is assigned exactly once.
        Returns error message if invalid, empty string if valid.
        """
        planned_facts = []
        for section in plan.sections:
            planned_facts.extend(section.facts)

        planned_set = set(planned_facts)
        expected_set = set(facts)

        missing = expected_set - planned_set
        counts = Counter(planned_facts)
        duplicates = [f for f, c in counts.items() if c > 1]

        error_message = ""
        if missing:
            error_message += (
                f"Validation Error: The following facts are missing from the document plan and were not assigned to any section:\n\n"
                f"{list(missing)}\n\n"
                f"Please add them to sections."
            )
        if duplicates:
            if error_message:
                error_message += "\n\n"
            error_message += (
                f"Validation Error: The following facts appear multiple times in the document plan:\n\n"
                f"{duplicates}\n\n"
                f"Please ensure that each fact is assigned to only one section, remove the duplicates."
            )

        if error_message:
            error_message += (
                "\n\n"
                "Please revise the document plan to ensure all facts are assigned exactly once. Do not change correctly assigned facts.\nOutput the a new complete document plan in JSON format."
            )
        return error_message

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _parse_table_header(self, table_data: Dict[str, Any]) -> Tuple[List[str], str, Any]:
        """Parse table header and return (header, primary_key, pk_index)."""
        header = [h[0] if isinstance(h, list) and h else str(h) for h in table_data["header"]]
        primary_key = table_data["primary_key"]

        if isinstance(primary_key, list):
            pk_index = [header.index(pk) for pk in primary_key]
            primary_key_str = ", ".join(primary_key)
        else:
            pk_index = header.index(primary_key)
            primary_key_str = primary_key

        return header, primary_key_str, pk_index

    def _get_nonempty_cells(self, table_data: Dict[str, Any], header: List[str], primary_key: str, pk_index: Any) -> set:
        """Get set of cell keys for all non-empty cells (excluding primary key column)."""
        data = table_data["data"]
        cells = set()

        for row in data:
            flat_row = [str(c[0]) if isinstance(c, list) and c else str(c) for c in row]
            if not flat_row:
                continue

            if isinstance(pk_index, list):
                row_pk = ", ".join([str(flat_row[i]) for i in pk_index])
            else:
                row_pk = flat_row[pk_index]

            for i, col_name in enumerate(header):
                if isinstance(pk_index, list):
                    if i in pk_index:
                        continue
                else:
                    if i == pk_index:
                        continue

                # Double check against primary_key string (might be comma joined now)
                # simpler to just check index

                val = flat_row[i]
                if val and str(val).strip():
                    cell_key = f"{row_pk},{col_name}"
                    cells.add(cell_key)

        return cells

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
