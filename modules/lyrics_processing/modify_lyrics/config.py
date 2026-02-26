# Standard Library Imports
from typing import List, Optional
import os

# Third-Party Imports
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, RootModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# CAL (code-cli-any-llm) proxy ayarları
# Docker container'dan host'a erişim: 172.17.0.1
CAL_BASE_URL = os.getenv("CAL_BASE_URL", "http://172.17.0.1:23062/api/v1/openai/v1")
CAL_API_KEY = os.getenv("CAL_API_KEY", "cal-proxy")
CAL_MODEL = os.getenv("CAL_MODEL", "gpt-5-codex")

# Prompt components\
PREFIX = """
You are an AI tasked with aligning and correcting transcribed lyrics from a raw speech-to-text model by comparing them to the provided reference lyrics.

## Important Rules:
1. **Never modify start or end times under any condition.** Every word must keep its original timing exactly.
2. **Correct words by matching them to the reference lyrics** while ensuring accurate spelling, pronunciation, and capitalization.
3. **Do not delete or change empty strings (`""`) or ghost words.** If a word appears in the raw lyrics as `""`, leave it unchanged.
4. **Each word must include a verse number that matches the reference lyrics.** Never leave a verse number blank.
5. **Standalone punctuation (`.`) must remain unchanged.** Do not add, remove, or adjust punctuation.
6. Each word in the corrected lyrics is paired with its corresponding verse number. The format is: **(word, verse_number)**

Your primary goal is to ensure the lyrics match the reference lyrics while keeping the word timings intact for accurate karaoke alignment.
"""

EXPECTATION = """
Your task is to:
1. **Correct the transcribed lyrics**:
  - Fix incorrect words by matching them with the reference lyrics.
  - Keep ghost words and empty strings exactly as they are.
  - Do not infer missing words or add extra words.
  - Maintain original punctuation and capitalization.

2. **Preserve All Timestamps Exactly**:
  - **Start and end times for each word must remain unchanged.**
  - **Do not shift, modify, or adjust word timing under any circumstances.**
  - If words are merged, the start time must be from the first word, and the end time from the last word.

3. **Ensure Verse Numbers Are Correct**:
  - Each word must include a verse number that corresponds to the reference lyrics.
  - No verse numbers should be missing or incorrect.
"""

EDGE_CASES = """
1. **Ghost words should be left as they are.** If a word is an empty string (`""`), do not remove or modify it.
2. **Standalone punctuation (e.g., `"."`, `","`) must remain exactly as it appears in the raw lyrics.**
3. **Merging Words:** If two words are merged, use the start time of the first word and the end time of the last word. But do not modify these times manually.
"""

# Define the WordAlignment schema
class WordAlignment(BaseModel):
    word: str = Field(..., description="The word from the lyrics.")
    start: float = Field(
        ...,
        description="The start time of the word in seconds. Do not modify. Must be a float."
    )
    end: float = Field(
        ...,
        description="The end time of the word in seconds. Do not modify. Must be a float."
    )
    # verse_number: Optional[int] = Field(
    verse_number: int = Field(
        ...,
        description="The verse number of the word. Must be an integer. The verse number of each word is provide in the reference lyrics"
    )

# Define a schema for a list of WordAlignment objectss
class WordAlignmentList(RootModel):
    root: List[WordAlignment]


# Initialize the parser
PARSER = PydanticOutputParser(pydantic_object=WordAlignmentList)
