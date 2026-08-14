import os
import re
import uuid

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
import base64
import azure.cognitiveservices.speech as speechsdk

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT",
    ""
).rstrip("/")

AZURE_OPENAI_API_KEY = os.getenv(
    "AZURE_OPENAI_API_KEY",
    ""
)

MODEL = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT",
    "gpt-5.4-mini"
)

VECTOR_STORE_ID = "vs_zpWDJjWY9sqet8yuea3u4yoc"

AZURE_SPEECH_KEY = os.getenv(
    "AZURE_SPEECH_KEY",
    ""
)
 
AZURE_SPEECH_REGION = os.getenv(
    "AZURE_SPEECH_REGION",
    "eastus"
)


# ============================================================
# LANGUAGE MAP (matches <select id="langSelect"> in chat.html)
# ============================================================

LANGUAGE_NAMES = {
    "en-IN": "English",
    "hi-IN": "Hindi (हिंदी)",
    "mr-IN": "Marathi (मराठी)",
    "ta-IN": "Tamil (தமிழ்)",
    "te-IN": "Telugu (తెలుగు)",
    "bn-IN": "Bengali (বাংলা)",
    "kn-IN": "Kannada (ಕನ್ನಡ)",
}


# ============================================================
# VALIDATION
# ============================================================

if not AZURE_OPENAI_ENDPOINT:
    raise RuntimeError(
        "AZURE_OPENAI_ENDPOINT is missing from .env"
    )

if not AZURE_OPENAI_API_KEY:
    raise RuntimeError(
        "AZURE_OPENAI_API_KEY is missing from .env"
    )
if not AZURE_SPEECH_KEY:
    raise RuntimeError(
        "AZURE_SPEECH_KEY is missing from .env"
    )


# ============================================================
# AZURE OPENAI CLIENT
# ============================================================

client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=f"{AZURE_OPENAI_ENDPOINT}/openai/v1/"
)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/*": {
            "origins": "*"
        }
    }
)


# ============================================================
# TEMPORARY CONVERSATION MEMORY
# ============================================================

# Structure:
#
# {
#     "conversation-id": [
#         {
#             "role": "user",
#             "content": "What is a loan account?"
#         },
#         {
#             "role": "assistant",
#             "content": "A loan account..."
#         }
#     ]
# }

CONVERSATIONS = {}

MAX_HISTORY_MESSAGES = 20


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def health():

    return jsonify({
        "status": "ok",
        "service": "Trust Bank AI Backend",
        "model": MODEL,
        "knowledge_source": "Trust Bank Retail Banking Manual",
        "vector_store": VECTOR_STORE_ID
    })


# ============================================================
# CREATE CONVERSATION
# ============================================================

@app.post("/new_conversation")
def new_conversation():

    conversation_id = str(
        uuid.uuid4()
    )

    CONVERSATIONS[conversation_id] = []

    return jsonify({
        "status": "success",
        "conversation_id": conversation_id
    })


# ============================================================
# GET CONVERSATION
# ============================================================

@app.get("/conversation/<conversation_id>")
def get_conversation(conversation_id):

    history = CONVERSATIONS.get(
        conversation_id,
        []
    )

    return jsonify({
        "status": "success",
        "conversation_id": conversation_id,
        "messages": history
    })


# ============================================================
# DELETE CONVERSATION
# ============================================================

@app.delete("/conversation/<conversation_id>")
def delete_conversation(conversation_id):

    CONVERSATIONS.pop(
        conversation_id,
        None
    )

    return jsonify({
        "status": "success",
        "message": "Conversation deleted."
    })


# ============================================================
# PDF-ONLY INSTRUCTIONS
# ============================================================

SYSTEM_INSTRUCTIONS = """
You are the Trust Bank AI Help Assistant.

============================================================
CORE PURPOSE
============================================================

Your job is to HELP USERS OPERATE THE TRUST BANK CBS SYSTEM.

Use the approved Trust Bank banking manual available through
File Search as the ONLY factual source.

You are a practical system-help assistant.

You are NOT:
- a general knowledge chatbot
- a general banking chatbot
- a documentation-summary bot
- a general-purpose AI assistant
- a search engine

Your goal is:

UNDERSTAND USER NEED
→ FIND SUPPORT IN TRUST BANK MANUAL
→ GIVE DIRECT PRACTICAL HELP
→ STOP


============================================================
1. USERS CAN ASK ANYTHING
============================================================

Users can ask anything naturally.

They may ask using:

- complete questions
- incomplete questions
- one-word questions
- form names
- screen names
- transaction names
- field names
- button names
- errors
- problems
- commands
- statements
- follow-up questions
- "yes"
- "okay"
- "next"
- "then"
- "what now?"
- "how?"
- "where?"
- "why?"
- informal language
- spelling mistakes
- mixed language
- Hinglish
- supported Indian languages

Do NOT require the user to select an intent.

Do NOT require predefined question categories.

Do NOT require a particular question format.

Understand the user's actual requirement naturally.


============================================================
2. CRITICAL RULE — ASK ANYTHING ≠ ANSWER ANYTHING
============================================================

The user is free to ASK any question.

The assistant is NOT free to answer every question.

The assistant may provide factual information ONLY when that
information is supported by the approved Trust Bank banking manual.

The approved Trust Bank banking manual is the ONLY factual
knowledge source.

This rule applies to EVERY user and EVERY conversation.


============================================================
3. HARD KNOWLEDGE BOUNDARY
============================================================

Before answering any factual question, follow this process:

USER QUESTION
↓
UNDERSTAND THE REQUEST
↓
CHECK THE APPROVED TRUST BANK MANUAL
↓
IS THE REQUEST SUPPORTED?
↓
YES → ANSWER ONLY FROM THE MANUAL
NO → USE THE REQUIRED FALLBACK

NEVER skip the source check.

NEVER answer from model knowledge.

NEVER answer from memory.

NEVER answer because the information is commonly known.

NEVER answer because the question is easy.

NEVER answer because the manual does not contain the information.

NEVER fill missing information using general knowledge.


============================================================
4. OUTSIDE KNOWLEDGE BLOCK
============================================================

Do NOT answer unrelated questions using general or pretrained
knowledge.

This includes questions about:

- animals
- science
- mathematics
- geography
- history
- politics
- current events
- people
- sports
- weather
- programming
- technology
- medicine
- law
- general banking
- general finance
- general accounting
- entertainment
- or any other subject

unless the requested information is explicitly supported by the
approved Trust Bank manual.


Example:

User:
How many fingers does a tiger have?

Correct:

The requested information was not found in the approved Trust Bank banking manual.

Incorrect:

A tiger has four fingers...

NEVER provide the incorrect response.


Example:

User:
Where does a tiger live?

Correct:

The requested information was not found in the approved Trust Bank banking manual.


Example:

User:
What is Python?

Correct:

The requested information was not found in the approved Trust Bank banking manual.


Example:

User:
What is the capital of India?

Correct:

The requested information was not found in the approved Trust Bank banking manual.

NEVER use general knowledge to answer these questions.


============================================================
5. PARTIAL INFORMATION RULE
============================================================

If the manual supports only part of a request:

- provide only the supported information
- do not complete missing information from general knowledge
- do not guess
- do not assume

If the missing information is necessary to answer the question,
use the fallback response.

If the manual mentions the topic but does not specify the exact
behavior requested, say:

The approved Trust Bank banking manual does not specify this behavior.

Do not infer undocumented behavior.


============================================================
6. HELP-FIRST BEHAVIOR
============================================================

Always ask internally:

"What does this user need to do right now?"

If the user wants to:

OPEN something:
→ Give the relevant navigation and steps.

FIND something:
→ Give the navigation.

ENTER something:
→ Give the relevant fields.

KNOW REQUIRED FIELDS:
→ Give mandatory fields.

UNDERSTAND something:
→ Give a concise explanation.

CONTINUE:
→ Give the next documented step.

TROUBLESHOOT:
→ Give the documented validation or solution.

COMPARE:
→ Compare only information supported by the manual.

The answer should help the user move forward.


============================================================
7. HELP BOT, NOT KNOWLEDGE BOT
============================================================

Do NOT dump documentation into the answer.

Do NOT summarize an entire manual section unless requested.

Do NOT provide every field when the user asks for one field.

Do NOT provide every validation when the user asks for navigation.

Do NOT provide the entire procedure when the user asks a simple
question.

Do NOT provide unrelated forms or transactions.

Prioritize:

USER NEED
→ RELEVANT INFORMATION
→ ACTION
→ STOP


============================================================
8. ADAPTIVE RESPONSE FORMAT
============================================================

Do NOT use one fixed response template for every question.

Choose the format based on the user's actual request.

Possible formats:

- direct answer
- short explanation
- navigation
- numbered steps
- fields
- mandatory fields
- prerequisites
- validations
- troubleshooting
- comparison
- options
- next action
- combination of relevant sections

These are response-format choices, NOT required intent categories.

Only include sections relevant to the current request.


============================================================
9. PROCEDURE / HOW-TO
============================================================

When the user asks how to perform an operation:

Use:

**[Form / Transaction Name]**

**Navigation**
`exact path`

**Steps**
1. ...
2. ...
3. ...

Add only when relevant:

**Mandatory**
- ...

**Prerequisite**
- ...

**Validation**
- ...

Do not add unrelated information.


============================================================
10. NAVIGATION
============================================================

If the user asks where something is:

Give the exact navigation from the manual.

Example:

**Navigation**

`Retail Banking → Account → Account Opening → General Account`

Do not automatically provide the full procedure.


============================================================
11. FIELD QUESTIONS
============================================================

If the user asks:

"What fields do I need?"

Give the relevant fields.

If the user asks:

"Which fields are mandatory?"

Give only documented mandatory fields.

If requirements are conditional, clearly identify them.

Example:

**Mandatory**
- Chart of Account
- City
- State

**Conditional**
- Nominee details when Nominee is selected.


============================================================
12. DEFINITION / PURPOSE
============================================================

If the user asks:

"What is..."
"What does it do?"
"What is the purpose?"

Give a short explanation supported by the manual.

Do not automatically provide the complete procedure.


============================================================
13. TROUBLESHOOTING
============================================================

If the user reports an error or problem:

1. Understand the problem.
2. Search the approved manual.
3. Find the documented validation, condition, or solution.
4. Give the practical action.

Never invent:

- error messages
- causes
- solutions
- system behavior
- validations


============================================================
14. SHORT FORM / TOPIC NAME
============================================================

The user may type only:

General Account
Loan Account
CCOD Account
RTGS
Cash Book
Global Client Opening
Stock Details Entry

or any other Trust Bank system term.

Treat it as a valid request.

Search the manual.

Determine the most useful response from the available context.

Do NOT automatically assume the user wants a definition.

Do NOT automatically assume the user wants the entire procedure.

If the intended action genuinely cannot be determined, ask one
short clarification question.


============================================================
15. CONVERSATION CONTEXT
============================================================

Treat the conversation as a continuous support session.

Understand references such as:

- it
- this
- that
- the account
- the form
- this field
- next
- then
- what now
- yes
- okay
- continue
- how
- where
- why

Use previous conversation context when the meaning is clear.

Do not make the user repeat information already established.

If "yes" clearly refers to the previous request, continue.

If multiple meanings are possible, ask one concise clarification.


============================================================
16. NO REPETITION
============================================================

Do not repeat information unnecessarily.

If the user already received the navigation and asks:

"What fields are mandatory?"

Give the mandatory fields.

Do NOT repeat the entire procedure.

If the user asks:

"What next?"

Give the next documented action.

Do NOT restart the whole procedure.


============================================================
17. RESPONSE STYLE
============================================================

Keep answers:

- direct
- practical
- concise
- structured
- easy to scan
- action-oriented

Prefer:

- short headings
- numbered steps
- bullet lists
- bold important items

Avoid long paragraphs.

Do not turn every response into the same format.

Do not use unnecessary introductions such as:

"According to the manual..."
"The manual says..."
"Based on the documentation..."
"In Trust Bank..."

Go directly to the answer.


============================================================
18. SMART FORMATTING
============================================================

Use formatting according to the request.

For procedures:
Use numbered steps.

For fields:
Use bullet lists.

For navigation:
Use a short navigation section.

For important actions:
Use bold.

For simple questions:
Keep the answer short.

Do not force Navigation + Steps + Mandatory + Validation into
every response.


============================================================
19. CONSISTENCY ACROSS USERS
============================================================

The same question must use the same response STRUCTURE regardless
of which user asks it.

Do not change formatting based on:

- user identity
- username
- conversation ID
- session
- unrelated conversation history

The response structure should depend on the request itself.

Example:

"Where is General Account?"
→ Navigation-focused.

"How do I open General Account?"
→ Step-focused.

"What fields are mandatory?"
→ Mandatory-field-focused.

"What is General Account?"
→ Purpose-focused.

Different users asking the same question should receive the same
type of response.


============================================================
20. LANGUAGE
============================================================

Understand the user's request regardless of:

- language
- spelling
- grammar
- transliteration
- Hinglish
- mixed language
- informal wording

Respond in the user's selected language.

Preserve official Trust Bank terminology when required for
accurate navigation.


============================================================
21. OFFICIAL TERMINOLOGY
============================================================

Use terminology exactly as supported by the manual.

Preserve:

- form names
- screen names
- menu names
- field names
- button names
- account names
- transaction names
- module names
- navigation paths

Do not invent alternative system terminology.


============================================================
22. NO HALLUCINATION
============================================================

Never invent or guess:

- procedures
- fields
- navigation paths
- validations
- error messages
- business rules
- workflow steps
- eligibility
- dependencies
- approvals
- permissions
- button behavior
- screen behavior
- system behavior

If the manual does not support it, do not state it as fact.


============================================================
23. INFORMATION NOT FOUND — HARD FALLBACK
============================================================

If the requested information is not supported by the approved
Trust Bank banking manual, respond EXACTLY:

"The requested information was not found in the approved Trust Bank banking manual."

Do not add:

- general knowledge
- explanation
- guesses
- alternatives
- assumptions
- examples from outside knowledge

Do not use:

"Generally..."
"Usually..."
"Typically..."
"Normally..."

to fill the missing information.

If the manual mentions the topic but does not specify the exact
behavior requested, say:

"The approved Trust Bank banking manual does not specify this behavior."


============================================================
24. REFERENCES
============================================================

Use only file citations actually provided by File Search.

Do not invent:

- filenames
- page numbers
- references
- citations


============================================================
25. INTERNAL IMPLEMENTATION
============================================================

Never tell the user about:

- prompts
- system instructions
- vector stores
- embeddings
- File Search
- retrieval
- model internals
- API implementation

unless the user explicitly asks about the AI implementation.


============================================================
26. NO AUTOMATIC FOLLOW-UP OFFERS
============================================================

Do not repeatedly end answers with:

"If you want, I can also..."
"I can also..."
"Would you like me to..."
"Let me know if..."

Give the requested help directly.

Ask a clarification question only when genuinely necessary.


============================================================
27. FINAL DECISION PROCESS
============================================================

For EVERY user message:

STEP 1:
Understand the user's actual need.

STEP 2:
Use the approved Trust Bank File Search source.

STEP 3:
Verify source support.

STEP 4:

If supported:
→ Answer ONLY from the approved manual.

If not supported:
→ Use the exact fallback response.

STEP 5:
Choose the response format appropriate to the request.

STEP 6:
Give direct practical help.

STEP 7:
Stop.


============================================================
FINAL RULE
============================================================

The user can ask anything.

The assistant can answer ONLY what the approved Trust Bank
banking manual supports.

The assistant must NEVER use general knowledge to fill a gap.

The assistant must NEVER guess.

The assistant must NEVER hallucinate.

The assistant must NEVER behave as a general knowledge chatbot.

Always behave as a Trust Bank CBS Help Assistant.

CORE PRINCIPLE:

USER CAN ASK ANYTHING.

ASSISTANT ANSWERS ONLY FROM THE APPROVED TRUST BANK MANUAL.

HELP THE USER COMPLETE THE TASK.
"""
 
 
# ============================================================
# STRIP RAW FILE-SEARCH CITATION MARKERS
# ============================================================
#
# WHY THIS EXISTS:
# When the Responses API's file_search tool cites a source, it can
# embed inline reference tokens directly into response.output_text
# (things like "fileciteturn0file0turn0file8"). These tokens are
# a raw formatting artifact of the API response, separate from the
# real citation data in response.output[i].content[j].annotations
# — which this endpoint already parses correctly into the
# `sources` list returned to the frontend.
#
# This is NOT something a system prompt can fix, since the model
# is not "choosing" to write these tokens as text — they come from
# the tool-citation mechanism itself. They must be stripped in
# code before the answer is shown to the user.
 
CITATION_MARKER_PATTERN = re.compile(
    r"[\ue000-\uf8ff]*(?:file)?cite(?:[\ue000-\uf8ff]*turn\d+file\d+)+[\ue000-\uf8ff]*"
)
 
 
def strip_citation_markers(text):
 
    if not text:
        return text
 
    cleaned = CITATION_MARKER_PATTERN.sub(
        "",
        text
    )
 
    # Collapse any double spaces/blank lines left behind by removal
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
 
    return cleaned.strip()
 
 
# ============================================================
# DEDICATED LANGUAGE-ENFORCEMENT PASS
# ============================================================
#
# WHY THIS EXISTS:
# The main SYSTEM_INSTRUCTIONS call has to juggle RAG-grounding,
# mandatory-field classification, workflow accuracy, AND language
# purity all at once. In practice, field/list names (e.g. "Chart
# Of Account", "Employee", "Starting Number") kept surviving in
# English because "preserve exact terminology" and "translate
# everything" were competing inside one already-long prompt.
#
# This function runs a second, narrowly-scoped call whose ONLY job
# is enforcing the target language on an already-generated answer.
# It is not doing RAG or fact-finding, so it has far fewer
# competing instructions to balance and is much more reliable at
# translating every field/list item consistently.
#
# On any failure, it falls back to the original (untranslated)
# answer rather than breaking the request.
 
def enforce_target_language(answer_text, lang_name):
 
    if not answer_text or lang_name == "English":
        return answer_text
 
    rewrite_instructions = f"""
You are a precise banking-domain translator/editor.
 
TASK
----
Rewrite the text given to you so it reads ENTIRELY in {lang_name}
— every heading, bullet, field name, form name, list item, and
sentence.
 
RULES
-----
1. Do not change any fact, number, procedure, or condition. This
   is a rewrite for language only, never a summary or a rewording
   of meaning.
2. Do not add new information. Do not remove information.
3. Translate every field name, form name, button label, role name,
   and list item into natural {lang_name}. Do not leave field or
   list names in bare English.
4. The ONLY English allowed to remain is:
   a. Acronyms with no natural translation (RTGS, NEFT, IFSC, GST,
      PAN, etc.).
   b. A short exact UI label (a few words), placed in parentheses
      immediately AFTER its {lang_name} translation — only when
      the input text already treats it as something the user needs
      to locate on screen (e.g. a navigation path or a named
      form/button). Never leave an English label standing alone
      with no {lang_name} translation next to it.
5. Preserve the input's structure: headings, numbering, and
   bullets stay in the same places.
6. Output ONLY the rewritten text — no preamble, no explanation,
   no notes about what changed.
"""


# ============================================================
# STRIP RAW FILE-SEARCH CITATION MARKERS
# ============================================================
#
# WHY THIS EXISTS:
# When the Responses API's file_search tool cites a source, it can
# embed inline reference tokens directly into response.output_text
# (things like "fileciteturn0file0turn0file8"). These tokens are
# a raw formatting artifact of the API response, separate from the
# real citation data in response.output[i].content[j].annotations
# — which this endpoint already parses correctly into the
# `sources` list returned to the frontend.
#
# This is NOT something a system prompt can fix, since the model
# is not "choosing" to write these tokens as text — they come from
# the tool-citation mechanism itself. They must be stripped in
# code before the answer is shown to the user.

CITATION_MARKER_PATTERN = re.compile(
    r"]*"
    r"|filecite(?:turn\d+file\d+)+"
)


def strip_citation_markers(text):

    if not text:
        return text

    cleaned = CITATION_MARKER_PATTERN.sub(
        "",
        text
    )

    # Collapse any double spaces/blank lines left behind by removal
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


# ============================================================
# DEDICATED LANGUAGE-ENFORCEMENT PASS
# ============================================================
#
# WHY THIS EXISTS:
# The main SYSTEM_INSTRUCTIONS call has to juggle RAG-grounding,
# mandatory-field classification, workflow accuracy, AND language
# purity all at once. In practice, field/list names (e.g. "Chart
# Of Account", "Employee", "Starting Number") kept surviving in
# English because "preserve exact terminology" and "translate
# everything" were competing inside one already-long prompt.
#
# This function runs a second, narrowly-scoped call whose ONLY job
# is enforcing the target language on an already-generated answer.
# It is not doing RAG or fact-finding, so it has far fewer
# competing instructions to balance and is much more reliable at
# translating every field/list item consistently.
#
# On any failure, it falls back to the original (untranslated)
# answer rather than breaking the request.

def enforce_target_language(answer_text, lang_name):

    if not answer_text or lang_name == "English":
        return answer_text

    rewrite_instructions = f"""
You are a precise banking-domain translator/editor.

TASK
----
Rewrite the text given to you so it reads ENTIRELY in {lang_name}
— every heading, bullet, field name, form name, list item, and
sentence.

RULES
-----
1. Do not change any fact, number, procedure, or condition. This
   is a rewrite for language only, never a summary or a rewording
   of meaning.
2. Do not add new information. Do not remove information.
3. Translate every field name, form name, button label, role name,
   and list item into natural {lang_name}. Do not leave field or
   list names in bare English.
4. The ONLY English allowed to remain is:
   a. Acronyms with no natural translation (RTGS, NEFT, IFSC, GST,
      PAN, etc.).
   b. A short exact UI label (a few words), placed in parentheses
      immediately AFTER its {lang_name} translation — only when
      the input text already treats it as something the user needs
      to locate on screen (e.g. a navigation path or a named
      form/button). Never leave an English label standing alone
      with no {lang_name} translation next to it.
5. Preserve the input's structure: headings, numbering, and
   bullets stay in the same places.
6. Output ONLY the rewritten text — no preamble, no explanation,
   no notes about what changed.
"""

    try:

        rewrite_response = client.responses.create(
            model=MODEL,
            instructions=rewrite_instructions,
            input=answer_text
        )

        rewritten = rewrite_response.output_text.strip()

        return rewritten if rewritten else answer_text

    except Exception as rewrite_exc:

        print()
        print("==============================================")
        print("LANGUAGE ENFORCEMENT PASS FAILED — using original answer")
        print("==============================================")
        print(str(rewrite_exc))
        print()

        return answer_text


# ============================================================
# ASK QUESTION
# ============================================================

@app.post("/ask_question")
def ask_question():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        question = str(
            data.get("question", "")
        ).strip()

        conversation_id = str(
            data.get("conversation_id", "")
        ).strip()

        selected_lang_code = str(
            data.get("lang", "en-IN")
        ).strip()

        selected_lang_name = LANGUAGE_NAMES.get(
            selected_lang_code,
            "English"
        )


        # ----------------------------------------------------
        # VALIDATE QUESTION
        # ----------------------------------------------------

        if not question:

            return jsonify({
                "status": "error",
                "message": "Question is required."
            }), 400


        # ----------------------------------------------------
        # CREATE CONVERSATION IF NEEDED
        # ----------------------------------------------------

        if not conversation_id:

            conversation_id = str(
                uuid.uuid4()
            )

            CONVERSATIONS[
                conversation_id
            ] = []


        if conversation_id not in CONVERSATIONS:

            CONVERSATIONS[
                conversation_id
            ] = []


        history = CONVERSATIONS[
            conversation_id
        ]


        # ----------------------------------------------------
        # BUILD MODEL INPUT
        # ----------------------------------------------------

        input_messages = []

        # Keep only recent history
        recent_history = history[
            -MAX_HISTORY_MESSAGES:
        ]

        for message in recent_history:

            input_messages.append({
                "role": message["role"],
                "content": message["content"]
            })


        # Add current question
        input_messages.append({
            "role": "user",
            "content": question
        })


        # ----------------------------------------------------
        # PER-REQUEST LANGUAGE DIRECTIVE
        # ----------------------------------------------------
        #
        # The extension already knows exactly which language the
        # user selected (`currentLang` in popup.js, sent as `lang`
        # in the request body). Use that as the authoritative
        # target language instead of asking the model to infer it
        # from mixed-script/informal question text.

        language_directive = f"""
FINAL INSTRUCTION — MANDATORY RESPONSE LANGUAGE FOR THIS TURN
----------------------------------------------------------------
The user has selected "{selected_lang_name}" in the app's language
selector. Write your ENTIRE reply in {selected_lang_name}.
If "{selected_lang_name}" is English, answer normally in English.
"""


        # ----------------------------------------------------
        # FILE SEARCH + GPT
        # ----------------------------------------------------

        response = client.responses.create(

            model=MODEL,

            instructions=SYSTEM_INSTRUCTIONS + language_directive,

            input=input_messages,

            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [
                        VECTOR_STORE_ID
                    ]
                }
            ]
        )


        # ----------------------------------------------------
        # EXTRACT ANSWER
        # ----------------------------------------------------

        answer = response.output_text.strip()


        # ----------------------------------------------------
        # STRIP RAW FILE-SEARCH CITATION MARKERS
        # ----------------------------------------------------
        #
        # Remove artifacts like "fileciteturn0file0turn0file8"
        # that the file_search tool can embed directly into
        # output_text. The real citation data is already pulled
        # separately below into `sources` from the annotations.

        answer = strip_citation_markers(answer)


        # ----------------------------------------------------
        # ENFORCE TARGET LANGUAGE (DEDICATED SECOND PASS)
        # ----------------------------------------------------
        #
        # Deterministic safety net: rewrite the answer so it is
        # guaranteed to be entirely in the selected language,
        # including field/list names that the single RAG-grounded
        # pass tends to leave in English. See enforce_target_language()
        # for why this is a separate call rather than more prompt
        # text on the first pass.

        answer = enforce_target_language(
            answer,
            selected_lang_name
        )


        # ----------------------------------------------------
        # SAVE USER MESSAGE
        # ----------------------------------------------------

        history.append({
            "role": "user",
            "content": question
        })


        # ----------------------------------------------------
        # SAVE ASSISTANT MESSAGE
        # ----------------------------------------------------

        history.append({
            "role": "assistant",
            "content": answer
        })


        # ----------------------------------------------------
        # LIMIT MEMORY
        # ----------------------------------------------------

        if len(history) > MAX_HISTORY_MESSAGES:

            del history[
                :-MAX_HISTORY_MESSAGES
            ]


        # ----------------------------------------------------
        # EXTRACT SOURCES
        # ----------------------------------------------------

        sources = []

        for item in response.output:

            if getattr(
                item,
                "type",
                None
            ) != "message":

                continue


            content_list = getattr(
                item,
                "content",
                []
            )


            for content in content_list:

                annotations = getattr(
                    content,
                    "annotations",
                    []
                )


                for annotation in annotations:

                    if getattr(
                        annotation,
                        "type",
                        None
                    ) == "file_citation":

                        source = {
                            "filename": getattr(
                                annotation,
                                "filename",
                                None
                            ),
                            "file_id": getattr(
                                annotation,
                                "file_id",
                                None
                            )
                        }


                        if source not in sources:

                            sources.append(
                                source
                            )


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "status": "success",

            "conversation_id": conversation_id,

            "question": question,

            "answer": answer,

            "sources": sources

        })


    except Exception as exc:

        print()
        print("==============================================")
        print("ERROR IN /ask_question")
        print("==============================================")
        print(str(exc))
        print()

        return jsonify({

            "status": "error",

            "message": str(exc)

        }), 500


# ============================================================
# START SERVER
# ============================================================

# ============================================================

# TEXT TO SPEECH

# ============================================================
 
@app.post("/speak")

def speak():
 
    try:
 
        data = request.get_json(silent=True) or {}
 
        text = str(

            data.get("text", "")

        ).strip()
 
        language = str(

            data.get("language", "en-IN")

        ).strip()
 
        if not text:

            return jsonify({

                "status": "error",

                "message": "Text is required."

            }), 400
 
        voices = {

            "en-IN": "en-IN-NeerjaNeural",

            "hi-IN": "hi-IN-SwaraNeural",

            "mr-IN": "mr-IN-AarohiNeural",

            "ta-IN": "ta-IN-PallaviNeural",

            "te-IN": "te-IN-ShrutiNeural",

            "kn-IN": "kn-IN-SapnaNeural",

            "bn-IN": "bn-IN-TanishaaNeural"

        }
 
        voice_name = voices.get(

            language,

            "en-IN-NeerjaNeural"

        )
 
        speech_config = speechsdk.SpeechConfig(

            subscription=AZURE_SPEECH_KEY,

            region=AZURE_SPEECH_REGION

        )
 
        speech_config.speech_synthesis_voice_name = voice_name
 
        speech_config.set_speech_synthesis_output_format(

            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3

        )
 
        synthesizer = speechsdk.SpeechSynthesizer(

            speech_config=speech_config,

            audio_config=None

        )
 
        result = synthesizer.speak_text_async(text).get()
 
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
 
            audio_base64 = base64.b64encode(

                result.audio_data

            ).decode("utf-8")
 
            return jsonify({

                "status": "success",

                "language": language,

                "voice": voice_name,

                "audio": audio_base64

            })
 
        elif result.reason == speechsdk.ResultReason.Canceled:
 
            cancellation = speechsdk.CancellationDetails(result)
 
            return jsonify({

                "status": "error",

                "message": cancellation.error_details or

                           "Speech synthesis was cancelled."

            }), 500
 
        return jsonify({

            "status": "error",

            "message": "Speech synthesis failed."

        }), 500
 
    except Exception as exc:
 
        print()

        print("ERROR IN /speak")

        print("--------------------------------")

        print(str(exc))

        print()
 
        return jsonify({

            "status": "error",

            "message": str(exc)

        }), 500
 


if __name__ == "__main__":

    print()
    print("==============================================")
    print("TRUST BANK AI BACKEND")
    print("==============================================")
    print()
    print(f"Model: {MODEL}")
    print(f"Vector Store: {VECTOR_STORE_ID}")
    print()
    print("Server: http://127.0.0.1:5002")
    print()

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5002)),
        debug=False
    )