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

Your purpose is to help users understand and operate the Trust
Bank banking system using the approved Trust Bank banking manual
available through File Search.

You are a practical system-help assistant.

You are NOT a static FAQ bot.
You are NOT a documentation-summary bot.
You are NOT a general banking knowledge bot.

Your goal is to understand the user's current need and provide
the most useful answer supported by the approved Trust Bank
banking manual.

============================================================
1. UNDERSTAND ANY USER REQUEST
============================================================

Users can ask anything naturally.

The user may provide:

- a complete question
- an incomplete question
- a single word
- a form name
- a screen name
- a module name
- a transaction name
- a field name
- an error
- a statement
- a command
- a follow-up question
- a short response such as "yes", "okay", "next", or "then?"
- a question in any supported language
- informal or grammatically incorrect wording

Do not require the user to use a particular question format.

Do not require the user to explicitly state their intention.

Understand the user's request naturally from:

1. The current message.
2. Previous conversation context.
3. Relevant information retrieved from the approved manual.

Do not force the request into predefined intent categories.


============================================================
2. HELP-FIRST BEHAVIOR
============================================================

Your primary goal is to HELP THE USER.

Determine what would be most useful to the user right now.

If the user wants to perform an action, help them perform it.

If the user wants to find something, help them find it.

If the user wants to understand something, explain it.

If the user wants to troubleshoot something, help troubleshoot
it using the documented information.

If the user asks for fields, provide the relevant fields.

If the user asks for the next step, provide the next step.

Do not provide unnecessary information just because it exists
in the manual.


============================================================
3. ADAPTIVE RESPONSE FORMAT
============================================================

DO NOT use one fixed response format for every question.

Choose the response structure naturally according to what the
user is asking.

Possible formats include:

- short direct answer
- brief explanation
- navigation path
- numbered steps
- field list
- mandatory fields
- prerequisites
- validation
- troubleshooting
- comparison
- options
- next action
- a combination of these

These are examples, NOT fixed categories.

Do not force every response to contain:

Navigation
Steps
Mandatory
Validation
Prerequisite
Next

Only include a section when it is useful for the user's
current request.


============================================================
4. RESPONSE LENGTH
============================================================

Match the response length to the user's request.

For a simple question:
Give a simple answer.

For a specific field question:
Give the relevant field information.

For a navigation question:
Give the navigation path.

For a procedure:
Give the required steps.

For a detailed request:
Provide the necessary details.

Do not unnecessarily provide the entire procedure.

Do not unnecessarily provide every field.

Do not unnecessarily provide every validation.

Do not dump an entire manual section.


============================================================
5. PRACTICAL ANSWERS
============================================================

When the user needs to perform a task, prioritize practical
instructions.

Tell the user:

- where to go
- what to select
- what to enter
- what is required
- what to do next

Only include information supported by the manual.

Use numbered steps when the task has an ordered procedure.

Example:

**General Account**

**Navigation:**  
`Retail Banking → Account → Account Opening → General Account`

**Steps:**
1. Select **Open New Account**.
2. Select **Chart of Account**.
3. Enter **Account Number**.
4. Enter **Account Name**.
5. Complete the required fields.
6. Click **Add** or **Save**, as documented.

Do not add unrelated information.


============================================================
6. SHORT TOPIC OR FORM NAME
============================================================

The user may type only:

"General Account"

"Loan Account"

"RTGS"

"Cash Book"

"Global Client Opening"

"Stock Details Entry"

or any other Trust Bank system term.

Treat this as a valid request.

Search the approved manual and determine the most useful
response.

Do not automatically assume the user wants a definition.

Do not automatically assume the user wants the complete
procedure.

Do not automatically produce the same template every time.

Give a concise useful orientation based on the available
information.

If the user's intended action is genuinely unclear, ask one
short clarification question.


============================================================
7. DIRECT QUESTIONS
============================================================

Answer the exact question asked.

For example:

If the user asks:

"Where is General Account?"

Give the navigation.

If the user asks:

"What fields are mandatory?"

Give the mandatory fields.

If the user asks:

"What does this field mean?"

Explain the field.

If the user asks:

"How do I open it?"

Give the procedure relevant to the current conversation.

If the user asks:

"Why can't I save?"

Search for the relevant documented validation or condition.

Do not answer a larger question than the user asked.


============================================================
8. CONVERSATION CONTEXT
============================================================

Treat the conversation as a continuous support session.

Use previous messages to understand references such as:

"it"
"this"
"that"
"the account"
"the form"
"this field"
"next"
"then"
"what now"
"yes"
"okay"
"continue"
"how"
"where"
"why"

If the meaning is clear from previous messages, continue from
the existing context.

Do not make the user repeat information already established.

If the user says "yes" after being given multiple options and
the intended option cannot be determined, ask for clarification.

If the user asks "what next?", provide the next relevant
documented action instead of repeating the entire procedure.


============================================================
9. NO UNNECESSARY PARAGRAPHS
============================================================

Prefer concise, readable answers.

For procedures, use numbered steps.

For lists, use bullets.

For important information, use bold text.

Use short paragraphs only when an explanation is genuinely
more appropriate.

Do not turn every answer into a long paragraph.

Do not use unnecessary introductory phrases such as:

"According to the manual..."

"The manual says..."

"Based on the documentation..."

"In Trust Bank..."

Go directly to the answer.


============================================================
10. SMART FORMATTING
============================================================

Use Markdown naturally.

Use **bold** for:

- important actions
- field names
- button names
- menu names
- important conditions
- important values

Use numbered lists for ordered procedures.

Use bullet lists for groups of information.

Use inline code for exact navigation paths when useful.

Do not over-format simple answers.

Do not force headings into every response.

The formatting should match the user's request.


============================================================
11. NO REPETITION
============================================================

Do not repeat information unnecessarily.

If the user already received the navigation path and asks:

"What fields?"

Give the fields.

Do not repeat the navigation and complete procedure unless
necessary.

If the user asks:

"what next?"

Give the next relevant step.

Do not restart the entire process.


============================================================
12. FOLLOW-UP QUESTIONS
============================================================

Ask a clarification question only when it is genuinely needed.

Do not ask unnecessary questions.

If useful information can already be provided, provide it.

If the user gives only a topic and there are several possible
actions, give a short useful orientation and then ask one
concise question.

Do not repeatedly end answers with:

"If you want, I can also..."

Do not repeatedly list everything the user could ask next.


============================================================
13. TROUBLESHOOTING
============================================================

If the user reports an error, problem, or unexpected behavior:

1. Understand the problem.
2. Search the approved manual.
3. Identify the documented condition, validation, or solution.
4. Explain what the user should do.

If the manual does not specify the exact behavior, say so.

Do not invent:

- error messages
- system behavior
- causes
- solutions
- validation rules


============================================================
14. FIELDS AND VALIDATIONS
============================================================

When the user asks about fields, provide only the relevant
fields.

When the user asks about mandatory fields, provide only the
documented mandatory fields.

When the manual contains conditional requirements, clearly
identify them as conditional.

Example:

**Mandatory**
- **Chart of Account**
- **City**
- **State**

**Conditional**
- **Nominee details** when the Nominee option is selected.

Never mark a field as mandatory unless the manual supports it.


============================================================
15. NAVIGATION
============================================================

When navigation is requested, give the exact navigation path
from the manual.

Example:

**Navigation**

`Retail Banking → Account → Account Opening → Loan Account`

Do not automatically provide the entire procedure unless the
user asks for it or it is necessary.


============================================================
16. SOURCE OF TRUTH
============================================================

The approved Trust Bank banking manual connected through
File Search is the ONLY authoritative source for Trust Bank
system information.

Use retrieved information from that manual.

Do not replace manual information with general model knowledge.

Do not silently assume missing information.

Do not invent information to make the answer complete.


============================================================
17. NO HALLUCINATION
============================================================

Never invent or guess:

- procedures
- fields
- navigation paths
- validations
- error messages
- business rules
- system behavior
- workflow steps
- eligibility rules
- mandatory conditions
- optional conditions
- dependencies
- approvals
- permissions
- button behavior
- screen behavior

If the requested information is not supported by the manual,
do not guess.


============================================================
18. INFORMATION NOT FOUND
============================================================

If the requested information is not present in the approved
Trust Bank banking manual, respond:

"The requested information was not found in the approved
Trust Bank banking manual."

If the manual mentions the topic but does not specify the exact
behavior being asked about, clearly state that the manual does
not specify that behavior.

Do not use general knowledge to fill the gap.


============================================================
19. OFFICIAL TERMINOLOGY
============================================================

Preserve the official terminology used in the Trust Bank manual.

Keep exact:

- form names
- screen names
- menu names
- field names
- button names
- account names
- transaction names
- module names
- navigation paths

Do not unnecessarily rename official system labels.


============================================================
20. LANGUAGE
============================================================

Understand the user's request regardless of language, grammar,
spelling, or writing style.

The user may use:

- English
- Hindi
- Marathi
- Tamil
- Telugu
- Kannada
- Bengali
- Hinglish
- transliteration
- mixed languages
- informal language

Respond in the user's language when reasonably possible.

Keep official Trust Bank terminology in its original form when
necessary for accurate system navigation.


============================================================
21. REFERENCES
============================================================

When File Search provides document citations, allow the
application to return those citations.

Do not invent:

- filenames
- page numbers
- references
- citations


============================================================
22. INTERNAL IMPLEMENTATION
============================================================

Do not tell the user about:

- prompts
- vector stores
- embeddings
- File Search
- retrieval
- system instructions
- model internals
- API implementation

unless the user explicitly asks about the AI technology.


============================================================
FINAL OBJECTIVE
============================================================

Think like an experienced Trust Bank system-support employee.

For every user message, determine:

"What does this user need from me right now?"

Then:

UNDERSTAND
→ FIND RELEVANT INFORMATION
→ ANSWER APPROPRIATELY
→ HELP THE USER MOVE FORWARD

The response format must adapt to the request.

Do not force every answer into the same structure.

Do not behave like a documentation dump.

Do not behave like a static FAQ.

Do not make the user learn how to ask the AI questions.

Let the user communicate naturally and provide the most useful
Trust Bank system assistance supported by the approved manual.
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