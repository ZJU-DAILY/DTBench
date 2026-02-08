# A single, authoritative source for all strategy definitions.
# Each strategy includes its generation guidance for the Refiner

DETAILED_STRATEGY_DEFINITIONS = {
    "T1": """* **T1 (Format Transformation):** Represent the number using a different format or linguistic style while preserving its exact value. Avoid standard digit representation; instead, use word forms (e.g., "twenty-one" for "21"), Roman numerals, or split digits where natural. The transformation must be precise and strictly reversible.""",

    "T2": """* **T2 (Unit Transformation):** Express the value using a different unit, magnitude, or currency standard. Perform valid conversions such as "2 GB" for "2048 MB", "2.5 million" for "2,500,000", or "50%" for "0.5". Ensure the converted value allows for precise recovery of the original number without information loss due to rounding.""",

    "T3": """* **T3 (Semantic Mapping):** Use idiomatic expressions, metaphors, or specific descriptors that imply the numeric value. Replace the explicit number with a term that carries specific numeric meaning in context, such as "a singleton" for 1, "a duo" for 2, "a dozen" for 12, or "a score" for 20. Use ranking terms like "runner-up" for 2nd place. The implied value must be unambiguous to a general reader.""",

    "R1": """* **R1 (Basic Arithmetic):** Present the target value as the result of a simple, two-number mathematical operation. Do not state the final value directly; instead, provide two component numbers and an operation (addition, subtraction, multiplication, or division) that yields the target (e.g., "50 plus 50" for 100). The operation must be simple, verifiable, and force the reader to perform the calculation.""",

    "R2": """* **R2 (Logical Reasoning):** Imply the value through logical inference rather than direct statement. Describe a scenario, set of conditions, or status where the target value is the only logical conclusion (e.g., describing a status as "meeting all acceptance criteria" instead of saying "Approved"). The conclusion must be inevitable based on the text provided.""",

    "R3": """* **R3 (Temporal Reasoning):** Handle all time-related values. This includes transforming date formats (e.g., YYYY-MM-DD to "May 5th, 2023") or obscuring the value by linking it to a specific time reference or duration. Describe the value as being valid at a specific relative time (e.g., "last year", "fiscal Q3"), or define it via a duration between dates. The temporal reference must be clear enough for the reader to identify the correct target value.""",

    "R4": """* **R4 (Multi-hop Reasoning):** Create a complex reasoning chain combining multiple steps or methods to derive the answer. Combine arithmetic with logic or temporal reasoning (e.g., "The value increased by Y from last year's X"), or use a sequence of dependent steps (e.g., "A is half of B, where B is..."). The reasoning path must be traceable and result in a single, correct value.""",

    "D1": """* **D1 (Falsehood Filtering):** Challenge the extraction system by presenting incorrect "distractor" values alongside the correct one. Explicitly mention errors, rumors, outdated estimates, or negated values (e.g., "incorrectly reported as 500") before clarifying the correct verified value. The linguistic distinction between the false and true values must be explicit and unambiguous.""",

    "D2": """* **D2 (Similarity Disambiguation):** Include values that are semantically similar or belong to related entities to test precision. Mention values for similar attributes (e.g., "Revenue" vs "Net Income") or related entities (e.g., competitor stats) in close proximity to the target value. Ensure the text explicitly attributes each value to its correct source so a human reader can distinguish them."""
}

SHORT_STRATEGY_DEFINITIONS = {
  "T1": "T1: Format Transformation — convert text-based numbers into standard digits (including stripping ordinal suffixes).",
  "T2": "T2: Unit Transformation — convert units, scale magnitudes, or normalize currency with precise reversibility.",
  "T3": "T3: Semantic Mapping — map idioms/metaphors/descriptors to a specific implied value.",
  "R1": "R1: Basic Arithmetic — derive the value using one simple operation on two numbers.",
  "R2": "R2: Logical Reasoning — infer the value via logic rather than direct statement.",
  "R3": "R3: Temporal Reasoning — handle date formatting or resolve timelines/durations/relative time to obtain the value.",
  "R4": "R4: Multi-hop Reasoning — combine multiple reasoning methods in sequence.",
  "D1": "D1: Falsehood Filtering — pick the verified fact while rejecting stated errors/rumors/outdated values.",
  "D2": "D2: Similarity Disambiguation — distinguish the correct value from nearby/related distractors."
}
