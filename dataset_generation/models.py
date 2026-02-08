from pydantic import BaseModel, Field
from typing import List, Dict, Tuple, Optional, Any


# --- Step 0: Strategy Assignment ---

class StrategyAssignment(BaseModel):
    """Strategy assignment for all cells in the table."""
    assignments: Dict[str, List[str]] = Field(description="Mapping from cell key 'pk,attr' to strategies ['T1','T2','T3','R1','R2','R3','R4','D1','D2'].")

# --- Step 1: Writing Guidance ---

class FactWritingGuidance(BaseModel):
    """A fact with detailed writing guidance, potentially with sub-facts."""
    primary_key: str = Field(description="The primary key value.")
    attribute: str = Field(description="The attribute name.")
    fact: str = Field(description="The fact statement.")
    writing_guidance: str = Field(description="Detailed writing guidance.")
    sub_facts: Dict[str, str] = Field(default_factory=dict, description="Sub-facts as dict mapping fact statement to guidance.")

# --- Step 2: Document Plan ---

class SectionPlan(BaseModel):
    """Plan for a section of the document."""
    section_id: int = Field(description="The section ID.")
    title: str = Field(description="The section title.")
    goal: str = Field(description="The writing goal for this section.")
    summary: str = Field(description="A brief summary of this section's content for reference by subsequent sections.")
    facts: List[str] = Field(default_factory=list, description="Fact strings to incorporate.")

class DocumentPlan(BaseModel):
    """Complete document structure plan."""
    theme: str = Field(description="The central theme of the document.")
    genre: str = Field(description="The genre of the document.")
    sections: List[SectionPlan] = Field(default_factory=list, description="List of section plans.")

# --- Step 3: Document ---

class Section(BaseModel):
    """A section of the document."""
    section_id: int = Field(description="The section ID.")
    title: str = Field(description="The section title.")
    content: str = Field(description="The section content.")
    verified: bool = Field(default=False, description="True if the section has been verified.")

class Document(BaseModel):
    """The complete document."""
    theme: str = Field(description="The central theme of the document.")
    genre: str = Field(description="The genre of the document.")
    sections: List[Section] = Field(default_factory=list, description="List of sections.")

# --- Verification ---

class VerificationResult(BaseModel):
    """Verification result."""
    ok: bool = Field(description="True if verification passed.")
    errors: List[Dict[str, str]] = Field(default_factory=list, description="List of errors with 'description' and 'suggestion'.")
