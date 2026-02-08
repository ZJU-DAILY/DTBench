# ==============================================================================
#  SYSTEM MESSAGES
# ==============================================================================

STRATEGY_ASSIGNMENT_SYSTEM = "You are a professional writer responsible for assigning writing strategies to the cells in a table to make the text written based on the table more diverse and complex."

CELL_GUIDANCE_SYSTEM = "You are an expert writing strategist responsible for creating specific, creative writing instructions for individual table cells that guide writers to incorporate data in ways that are natural yet challenging for information extraction systems."

CELL_GUIDANCE_VERIFY_SYSTEM = "You are a detailed instruction verifier responsible for ensuring that writing instructions correctly follow assigned strategies, maintain data integrity, and do not hallucinate or misuse table data."

FACT_GUIDANCE_SYSTEM = "You are a narrative fact restructuring expert responsible for analyzing writing guidance and determining if facts should be split into multiple sub-facts to create more sophisticated and challenging narratives."

FACT_GUIDANCE_VERIFY_SYSTEM = "You are a fact consistency verifier responsible for ensuring that generated sub-facts are complete, accurate, and allow readers to recover original information while maintaining the intended difficulty for extraction systems."

DOCUMENT_PLAN_SYSTEM = "You are a document structural architect responsible for designing logical document structures and strategically assigning facts to sections based on the theme, genre, and dispersion strategy."

WRITE_SECTION_SYSTEM = "You are a world-class author and subject matter expert responsible for writing natural, engaging prose that seamlessly incorporates required facts according to their specific writing guidance while maintaining excellent narrative flow."

VERIFY_SECTION_SYSTEM = "You are a meticulous content verifier responsible for ensuring that written sections contain all required facts, follow their specific guidance correctly, and maintain complete factual accuracy."

REPAIR_SECTION_SYSTEM = "You are a precise content editor responsible for fixing verification errors in written sections while preserving the narrative flow and ensuring all other facts remain correct."


# ==============================================================================
#  DISPERSION STRATEGY DEFINITIONS
# ==============================================================================
SPARSE_DISPERSION_GUIDANCE = """3.  **SCATTER FACTS WIDELY:** You should disperse facts to maximize information spread.
    * **GROUP DISPERSION:** If facts are marked as members of the same Group (e.g., "Member of Group 1"), you MUST place them in **separate, non-adjacent** sections. Do NOT cluster them.
    * **EXAMPLE:** If Fact [1] and Fact [5] are both members of "Group 1", placing Fact [1] in Section 2 and Fact [5] in Section 2 (the same section) or Section 3 (an adjacent section) is a VIOLATION. You should place them in, for example, Section 2 and Section 5.
"""

DENSE_DISPERSION_GUIDANCE = """3.  **CLUSTER FACTS (CRITICAL - DENSE STRATEGY):** Your goal is to create *locally dense* concentrations of information.
    * **GROUP CLUSTERING:** Facts marked as members of the same Group (e.g., "Member of Group 1") are highly related and should be kept together. You MUST place them either **within a single, dedicated section** or **across a small group of continuous, related sections**.
    * **EXECUTION:** When you assign the *first* fact of a Group (e.g., Group 1) to a section, you must assign **all other facts** of that same Group within that same section or in the *immediately following, continuous sections*.
    * **CRITICAL VIOLATION (AVOID THIS):** Do NOT scatter facts from the same Group. A **BAD** plan would be: Group 1 facts are in Section 2, Section 5, and Section 8. A **GOOD** plan *must* keep them continuous (e.g., Section 2, 3, 4).
    * **BALANCING CONSTRAINTS (Achieving Density and Section Count):**
        * To meet the `{min_sections}` requirement, you are **encouraged to add thematic, introductory, analytical, or summary sections** that *do not contain any facts*.
        * **FLEXIBILITY (CRITICAL):** These 'fact-less' sections can be placed **anywhere in the document plan**. You can place them at the beginning, at the end, or **interleaved between the fact-bearing section blocks** to create a logical document flow and meet the total section count.
"""

# ==============================================================================
#  STEP 0: STRATEGY ASSIGNMENT
# ==============================================================================
STRATEGY_ASSIGNMENT_PROMPT = """
**Goal:** Assign writing strategies to every non-empty cell in the provided table.

**Input:**
* **Table:**
{markdown_table}
* **Primary Key:** {primary_key}

**Strategy Definitions:**
{strategy_definitions}

**Instructions:**
1. Select strategies to make information extraction challenging yet natural
2. A cell may have zero or one strategy. The default is no strategy.
3. Assign strategies creatively but ensure the text remains fluent. Avoid over-complicating simple facts, don't assign strategy to every cell.

**Output Format:**
Return only a JSON object as follows:
```json
{{
    "assignments": {{
        "<primary_key_1>": {{
            "<attribute_1>": []
            "<attribute_2>": []
            ...
        }},
        ...
    }}
}}
```

**Example 1 - Single Primary Key:**
* **Table:**
| a | b | c | d |
|----|----|----|----|
| 1 | 5 | 10 | 15 |
| 2 | 20 | 25 |  |
* **Primary Key:** a

**Example Output:**
```json
{{
    "assignments": {{
        "1": {{
            "b": ["T2"],
            "c": [],
            "d": []
        }},
        "2": {{
            "b": ["R1"],
            "c": ["D2"]
        }}
    }}
}}
```

**Example 2 - Composite Primary Key:**
* **Table:**
| Year | Quarter | Revenue | Profit |
|------|---------|---------|--------|
| 2023 | Q1      | 100M    | 20M    |
| 2023 | Q2      | 120M    | 25M    |
* **Primary Key:** [Year, Quarter] (composite key)

**Example Output:**
```json
{{
    "assignments": {{
        "2023, Q1": {{
            "Revenue": ["T1"],
            "Profit": ["R3"]
        }},
        "2023, Q2": {{
            "Revenue": [],
            "Profit": ["D1"]
        }}
    }}
}}
```

**CRITICAL for Composite Primary Keys:** When the table has a composite primary key (multiple columns), you MUST combine the values using ", " (comma followed by space) as the separator. For example, if primary key is [Year, Quarter] and the row has Year=2023 and Quarter=Q1, use "2023, Q1" as the key.

**FINAL INSTRUCTION: Ensure EVERY non-empty and non-primary key cell is included in the assignments. Each cell can have at most one strategy. Distribute strategies diversely and balanced across the table.**
"""


# ==============================================================================
#  STEP 1a: CELL WRITING GUIDANCE
# ==============================================================================
CELL_GUIDANCE_PROMPT = """
**Your Goal:**
Generate a **specific, creative writing instruction** for a single table cell. This instruction will guide a writer to incorporate the data point into a narrative in a way that is **natural** yet **challenging for information extraction systems**, strictly adhering to assigned strategies.

**Input:**
* **Table:**
{markdown_table}
* **Primary Key:** {primary_key}
* **Attribute:** {attribute}
* **Value:** {value}
* **Strategies:** {strategies}

**Your Task:**
1.  **Analyze Context:** Understand the value's meaning within the table.
2.  **Formulate Guidance:** Write a detailed instruction on how to express this value.
    *   **Apply Strategies:** Strictly follow the provided strategy definitions.
    *   **Natural Integration:** The guidance must ensure the resulting text flows naturally.
    *   **Factual Precision:** The value must be recoverable by a human reader. Do NOT suggest vague approximations (e.g., avoid "about", "around").
    *   **Isolation:** Focus ONLY on the target value. Do not include values from other cells in your guidance, do not reference other cells.

**Strategy Definitions:**
{detailed_strategy_definitions}

**Output Format:**
Return a JSON object:
```json
{{
    "guidance": "Detailed instruction string..."
}}
```
"""

CELL_GUIDANCE_VERIFY_PROMPT = """
**Your Goal:**
Verify a writing guidance for a specific table cell. Determine if it correctly handles the data value, strictly follows the assigned strategies, and does NOT hallucinate or misuse other table data.

**Input:**
* **Table:**
{markdown_table}
* **Primary Key:** {primary_key}
* **Attribute:** {attribute}
* **Value:** {value}
* **Assigned Strategies:** {strategies}
* **Guidance:**
{detailed_guidance}

**Strategy Definitions:**
{strategy_definitions}

**Your Task (Step-by-Step):**
1.  **Strategy Verification:** Check if the 'Guidance' follows the 'Assigned Strategies'. If it doesn't, identify the specific issue.
2.  **Value Verification:** Check whether the 'Value' can be expressed correctly according to the guidance. For guidance involving calculations, ensure the calculation result is mathematically exact by multiple verifications.
3.  **Data Integrity Verification (CRITICAL):**
    *   Check if the guidance hallucinates/invents any data that looks like it belongs to the table (e.g., inventing a new column or value not in the table).
    *   Check if the guidance incorrectly references or uses values from *other* cells in the table (cross-contamination). The guidance should focus ONLY on the target attribute/value.
4.  **Final Assessment:** If the guidance meets all requirements, set `ok` to true and `errors` to empty string. Otherwise, set `ok` to false and provide **specific, actionable modification suggestions** that explain how to fix the guidance.

**Output Format:**
Respond with ONLY a single, valid JSON object:
```json
{{
    "ok": true/false,
    "errors": [
        {{
            "description": "Error description",
            "suggestion": "How to fix it"
        }}
    ]
}}
```
"""


# ==============================================================================
#  STEP 1b: FACT WRITING GUIDANCE (SPLITTING)
# ==============================================================================
FACT_GUIDANCE_PROMPT = """
**Goal:** Analyze the cell's writing guidance and determine if it should be split into multiple sub-facts.

**Input (Table Cell):**
* **Primary Key:** {primary_key}
* **Attribute:** {attribute}
* **Value:** {value}
* **Initial Guidance:** {guidance}

**Instructions:**
1. **Analyze the Initial Guidance:** Check if the guidance requires expressing the cell value through multiple independent components that can be stated separately.
   - For example: "State component A as X, component B as Y" or "Mention distractor value P, then state correct value Q"

2. **Decide Split or No Split:**
   - **Split (is_split=true):** If the guidance describes multiple independent pieces of information.
     - Set `is_split` to true
     - Set `sub_facts` to a dict where each key is a sub-fact statement and value is its specific writing guidance

   - **No Split (is_split=false):** If the guidance is simple, direct, or best expressed as a single unit. Do not force a split if it makes the sentence unnatural.
     - Set `is_split` to false

3. **Constraints:**
    - Each sub-fact must be independently expressible and necessary to recover the original value. Sub-facts' guidance cannot refer to each other.
    - Each sub-fact statement MUST explicitly and naturally contains the entity it belongs to, ensuring the statement stands alone without external context. Avoid ambiguous or generic statements that could apply to any entity.

**Output Format:**
Return a single JSON object:

**No Split:**
```json
{{
    "is_split": false
}}
```

**Split:**
```json
{{
    "is_split": true,
    "sub_facts": {{
        "<sub_fact_1>": "<guidance_1>",
        "<sub_fact_2>": "<guidance_2>"
    }}
}}
```

**Example:**
**Input:**
* **Primary Key:** "University A"
* **Attribute:** "Enrollment"
* **Value:** "5000"
* **Initial Guidance:** "Express the total enrollment by stating the undergraduate enrollment as 3,000 students and the graduate enrollment as 2,000 students, ensuring the reader can deduce the total."

**Output:**
```json
{{
    "is_split": true,
    "sub_facts": {{
        "The undergraduate enrollment of University A is 3,000 students": "Naturally express the undergraduate enrollment of University A as 3,000 students",
        "The graduate enrollment of University A is 2,000 students": "Naturally express the graduate enrollment of University A as 2,000 students"
    }}
}}
```
"""

FACT_GUIDANCE_VERIFY_PROMPT = """
**Goal:** Verify that the sub-facts splitting is appropriate and complete.

**Input:**
* **Attribute:** {attribute}
* **Value:** {value}
* **Original Fact:** {original_fact}
* **Original Guidance:** {original_guidance}
* **Generated Sub-facts and their Guidance:**
{sub_facts_json}

**Instructions:**
Verify the splitting by checking:

1. **Splitting Appropriateness:**
   - Does the Original Guidance actually require multiple independent pieces of information to be stated separately?
   - Are the sub-facts logically derived from the Original Guidance?
   - Is each sub-fact truly independent and necessary?
   - **Context Check:** Does every sub-fact statement explicitly name the entity it belongs to?

2. **Completeness & Recoverability:**
   - Can the Original Fact (attribute = value) be accurately recovered from all the sub-facts combined?
   - Are all necessary components present?
   - For R strategy: Do the components logically lead to the original value?
   - For D strategy: Are both distractors and correct value properly represented?

3. **Guidance Clarity:**
   - Is the guidance for each sub-fact clear and actionable?
   - Does each sub-fact's guidance properly reflect its role in the overall strategy?

**Output Format:**
Return a JSON object:
```json
{{
    "ok": true/false,
    "errors": [
        {{
            "description": "Error description",
            "suggestion": "How to fix"
        }}
    ]
}}
```
"""


# ==============================================================================
#  STEP 2: DOCUMENT PLAN
# ==============================================================================
DOCUMENT_PLAN_PROMPT = """
**Your Goal:**
Analyze the provided facts to determine an appropriate document theme, genre, and style. Then, design a logical document structure and strategically assign every provided fact to a specific section.

**Input:**
1. **Facts:** A list of facts to be incorporated into the document. Facts may be annotated with group membership (e.g., "Member of Group X").
2. **Constraints:**
   - Min Sections: Minimum number of sections.
   - Max Sections: Maximum number of sections.

**Output Format:**
Respond with ONLY a single, valid JSON object following this structure:
---
```json
{{
    "theme": "The central theme of the document",
    "genre": "The genre of the document",
    "sections": [
        {{
            "section_id": 0,
            "title": "<Title of Section_0>",
            "goal": "<The writing goal and core content for this section_0>",
            "summary": "<A summary of the key points and main content covered in this section>",
            "facts": ["1", "5", "12", ...]
        }},
        {{
            "section_id": 1,
            "title": "<Title of Section_1>",
            "goal": "<The writing goal and core content for this section_1>",
            "summary": "<A summary of the key points and main content covered in this section>",
            "facts": ["2", "8", ...]
        }},
        ...
    ]
}}
```
---

**Your Task:**
1.  **Analyze the Facts & Determine Context:** Understand the facts, their relationships, and data patterns. Infer a suitable document genre (e.g., financial report, historical analysis, technical specification, news article...) and theme based on the facts content.

2.  **Design the Document Structure:** Create a multi-section outline that fits the chosen genre and theme.
    *   The document should feel like a real-world document of that type, not just a list of facts.
    *   Define `title`, `goal`, `summary`, and sequential `section_id` (0-indexed) for each section.
    *   **Detailed Summary Field:** Write a substantive summary for each section. It must function as a comprehensive abstract, describing specific topics, arguments, or narratives covered. It should provide enough context so that a reader understands the section's essence without reading the full text.
    *   **Integration:** The facts should be woven into the narrative as supporting evidence or details, not as the sole content.

    **CRITICAL CONSTRAINTS:**
    *   **FULL COVERAGE:** You MUST assign **every provided fact** to one section. No fact should be omitted.
    *   **NO DUPLICATION:** Each fact must be assigned to **exactly one** section. Do not assign the same fact to multiple sections.
    *   **FACT ID FORMAT:** Each fact in the input list has a numeric ID in brackets like `[1]`, `[2]`, etc. In your JSON output, use ONLY the numeric IDs (e.g., "1", "2", "3") as strings in the "facts" array.
    *   **SECTION LIMITS:** The plan MUST have between **{min_sections}** and **{max_sections}** sections.
    *   **SECTION WITH NO FACTS (Zero-Fact Sections):** You MUST include sections with zero assigned facts (`facts: []`) to satisfy the constraint, improve readability and decrease facts density. These sections must NOT be "filler" or "spacers". They must be **meaningful, substantial parts of the narrative**
    *   **NATURALNESS:** The document structure must be authentic to the chosen genre. `title` and `goal` must be driven by the narrative flow. Do not customize document just to fit facts.
    *   **TITLE INDEPENDENCE:** `title` MUST NOT contain specific values from the facts assigned to that section.
    *   **PURE TEXT DOCUMENT:** The final document must be plain prose only. Do NOT include cover pages, table of contents, any structured/visual artifacts.

3.  **Apply Dispersion Strategy:**
{dispersion_guidance}

---
**Input Data:**
* **Min Sections:** {min_sections}
* **Max Sections:** {max_sections}
* **Facts:**
{facts_list}

---
**FINAL INSTRUCTION: Output ONLY the valid JSON object. Ensure the plan has between {min_sections} and {max_sections} sections. Verify that every provided fact is assigned exactly once.**
"""


# ==============================================================================
#  STEP 3: WRITE SECTION
# ==============================================================================
WRITE_SECTION_PROMPT = """
**Your Goal:**
Write a comprehensive and detailed section titled "{title}".

**Context and Instructions:**
1.  **Document Context:**
    *   **Theme:** {theme}
    *   **Genre:** {genre}
2.  **Previous Section Summary:** {previous_summary}
3.  **Section Title:** `{title}`
4.  **This Section Summary:** {current_summary}
5.  **Core Content Goal:** You must strictly adhere to this goal: `{content_goal}`.

6.  **Mandatory Facts and Writing Instructions:** Weave every fact into your narrative following its `Guidance`. Do NOT write the instructions themselves into the text. If list is empty, write naturally per the content goal.

    ---
    {facts_with_guidance}
    ---

7.  **Alignment with Summary:** Ensure your writing aligns with and fulfills the 'This Section Summary'. The summary describes what this section should cover.
8.  **Narrative Continuity:** If a previous section summary is provided, make your writing naturally transitions from it if needed.
9.  **Factual Grounding:** Only use data from 'Mandatory Facts' list. Do not invent numerical data not listed in Mandatory Facts.
10. **Length:** Write as long as possible while remaining natural. Add contextual knowledge that enriches the narrative.
11. **Pure Prose Only:** Do NOT include tables, charts, figures, images, diagrams, or any visual/structured elements. Write only in natural paragraph form.
12. **Highlighting:** Wrap sentences containing 'Mandatory Facts' with ***. Example: `***Revenue was $100M.***`

**Your Steps:**
1. **Deeply Understand Each Fact and Instruction:** Before writing, ensure you fully grasp the meaning of each fact and the nuances of its corresponding writing instruction.
2. **Plan Your Narrative:** Outline how you will structure the section to naturally incorporate each fact according to its instruction. Decide how many paragraphs need to be written, what content to cover in each paragraph and how many words to write in each paragraph. Make sure the narrative is coherent and natural.
3. **Write the Section:** Craft the text, weaving in each fact as per its instruction, while maintaining a coherent and engaging narrative throughout the entire section.

**Output Format:**
Output ONLY the final section text. No titles, no metadata, no markdown code blocks.
"""


# ==============================================================================
#  STEP 4: VERIFY SECTION
# ==============================================================================
VERIFY_SECTION_PROMPT = """
**Your Goal:**
Verify that a generated text section contains all required facts, follows all writing guidance, and includes no fabricated data.

**Input:**
* **Table Content:**
---
{markdown_table}
---
* **Section Title:** {title}
* **Generated Text:**
---
{content}
---
* **Required Facts (with Cell Keys and Guidance):**
---
{facts_with_guidance}
---

**Verification Checks:**
1.  **Fact Completeness:** Every fact in Required Facts must be extractable (directly or indirectly) from the text.
2.  **Guidance Compliance:** Each fact must be expressed exactly as specified by its guidance.
3.  **No Fabrication:** The text must not contain any invented data belong to the table schema but is not in Required Facts. Compare against the Table Content to ensure no hallucinated table values.

**Output Format:**
Respond with ONLY a single, valid JSON object:
---
```json
{{
    "ok": true/false,
    "errors": [
        {{
            "description": "Error description",
            "suggestion": "How to fix"
        }}
    ]
}}
```
---

**FINAL INSTRUCTION: Output ONLY the valid JSON object. If any fact is missing, incorrect, guidance-violated, or fabricated data is present, set `ok` to false and include all issues in `errors`.**
"""

REPAIR_SECTION_PROMPT = """
**Goal:** Repair a section of text that failed verification.

**Input:**
* **Original Text:**
{content}
* **Errors:**
{errors}
* **Required Facts:**
{facts_with_guidance}

**Instructions:**
1. Repair the section to fix the reported errors.
2. Ensure all required facts remain correct.
3. Keep the narrative flow natural.
4. Use `***` markers for facts.

**Output Format:**
Return ONLY the repaired text content. No titles, no metadata, no markdown code blocks.
"""
