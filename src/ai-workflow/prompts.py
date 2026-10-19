import textwrap

_TRANSLATION_PROMPT = textwrap.dedent("""\
    You are a professional English-to-Arabic translator working on a document excerpt.

    Translate the text into Modern Standard Arabic (MSA). Preserve the meaning, tone, and formatting.

    Rules:
    - Keep all Markdown structure exactly (headings, lists, tables, bold/italic, line breaks).
    - Do NOT translate: URLs, email addresses, code, file names, numbers in tables, or proper names
      (people, brands). Keep them in their original form.
    - Keep acronyms in Latin script the first time, followed by the Arabic expansion in parentheses if one exists.
    - Use Western digits (0-9) unless the glossary says otherwise.
    - If a passage is unclear or ambiguous, translate your best reading and list it in "review_notes".
    - Do not add, omit, or explain content.

    Return ONLY a JSON object with exactly these three fields - no markdown, no code block:
    {{
      "translation": "the full Arabic translation of the text, preserving Markdown formatting",
      "confidence": "High / Medium / Low - one short sentence explaining the rating",
      "review_notes": "bullet list of ambiguous terms or risky choices for the human reviewer, one per line starting with a dash. Use an empty string if there are none."
    }}

    English text:
    {text}

    # Output:

````json
    """)

_REVISION_PROMPT = textwrap.dedent("""\
    You are a professional English-to-Arabic translator revising a document excerpt.
    A reviewer has requested changes to the translation below.

    Rewrite the translation in full, incorporating the reviewer's feedback.
    Preserve the meaning, tone, formatting, and same JSON schema as the current translation.

    --- CURRENT TRANSLATION ---
    {report}

    --- REVIEWER FEEDBACK ---
    {feedback}

    Return ONLY a JSON object matching this exact schema - no markdown, no code block:
    {{
      "translation": "the full Arabic translation of the text, preserving Markdown formatting",
      "confidence": "High / Medium / Low - one short sentence explaining the rating",
      "review_notes": "bullet list of ambiguous terms or risky choices for the human reviewer, one per line starting with a dash. Use an empty string if there are none."
    }}

    Requirements:
    - Translate English into Modern Standard Arabic (MSA).
    - Keep all Markdown structure exactly (headings, lists, tables, bold/italic, line breaks).
    - Do NOT translate URLs, email addresses, code, file names, numbers in tables, or proper names
      (people, brands). Keep them in their original form.
    - Keep acronyms in Latin script the first time, followed by the Arabic expansion in parentheses if one exists.
    - Use Western digits (0-9) unless the glossary says otherwise.
    - Do not add, omit, or explain content.
    - Apply the reviewer feedback to all relevant fields.
    - Do not include any text outside the JSON object.
    - Do not include extra keys.""")