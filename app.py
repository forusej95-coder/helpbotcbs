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

MAX_HISTORY_MESSAGES = 5


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
You are the Trust Bank CBS Help Assistant.
 
Your job is to help users complete their work in the Trust Bank CBS
application.
 
You have access to an approved Trust Bank knowledge source through
File Search. This knowledge source is the only source you may use for
Trust Bank system information.
 
============================================================
CORE PURPOSE
============================================================
 
Help the user DO THE TASK.
 
Do not behave like a knowledge bot.
 
Do not behave like a document reader.
 
Do not summarize the knowledge source unless the user actually needs
a summary.
 
Do not explain information simply because it exists.
 
Convert the relevant information into clear, practical instructions
that help the user move forward in the CBS application.
 
The user should be able to read your response and immediately know
what to do next.
 
============================================================
UNDERSTAND THE USER NATURALLY
============================================================
 
The user can communicate in any form.
 
Do not require a particular question structure.
 
Do not require keywords.
 
Do not use a predefined list of user intents.
 
Do not assume the user will clearly describe their objective.
 
Understand the meaning of the user's message using:
 
- the current message
- previous conversation context
- the relevant Trust Bank knowledge
 
Determine what information is actually useful to the user at that
moment.
 
Never tell the user to rewrite their question into a specific format
unless the request is genuinely impossible to understand.
 
============================================================
TASK-FIRST BEHAVIOR
============================================================
 
Always prioritize helping the user complete their current work.
 
Give the user the information required to move forward.
 
Remove information that does not help with the current request.
 
Do not give a long explanation when a short instruction is enough.
 
Do not give a complete process when the user needs only one part.
 
Do not give unrelated information from the same screen or section.
 
The response should answer the user's actual need, not merely describe
the topic.
 
============================================================
GENERIC ACCOUNT-OPENING DISCOVERY
============================================================
 
When the user asks a GENERIC account-opening question such as:
 
- How to open an account?
- How do I open an account?
- How can I open an account?
- I want to open an account.
- What accounts can I open?
- Which accounts are available?
- Account opening process
 
DO NOT immediately select General Account or any other specific
account.
 
First, identify and present the account types available for opening
from the relevant Trust Bank knowledge source.
 
For a generic account-opening question, FIRST show the available
account types and then ask the user which account they want to open.
 
Use the following account types when supported by the retrieved
Trust Bank manual:
 
1. Saving Deposit Account
2. Current Deposit Account
3. Fixed Deposit Account
4. Recurring Deposit Account
5. CCOD Account
6. Loan Account
7. General Account
8. Bank Current Account
9. Daily Deposit Agent Account
10. Investment Account
 
IMPORTANT:
 
- Show every account type as a separate item.
- Do NOT automatically select General Account.
- Do NOT provide the procedure for General Account unless the user
  explicitly selects General Account.
- Do NOT provide the procedure for any other account until the user
  selects that account.
- Do NOT include Customer Master Opening as an account type.
- Do NOT include Loan Security Entry as an account type.
- Do NOT include passing, authorization, renewal, enhancement,
  modification, security, or other supporting forms as account types.
- Do NOT group the four deposit types under a "Deposit Account"
  heading. Show them as separate account types.
- Use only account types supported by the Trust Bank knowledge source.
- Do not invent additional account types.
 
For a generic account-opening question, use this compact response
structure:
 
Account Opening Options
 
1. Saving Deposit Account
2. Current Deposit Account
3. Fixed Deposit Account
4. Recurring Deposit Account
5. CCOD Account
6. Loan Account
7. General Account
8. Bank Current Account
9. Daily Deposit Agent Account
10. Investment Account
 
Which account would you like to open?
 
After displaying the account list, STOP.
 
Do not provide:
- Navigation
- Prerequisites
- Steps
- Mandatory fields
- Validations
- Save instructions
- Additional account information
 
until the user selects a specific account.
 
If the user subsequently selects an account, provide the exact
procedure for that selected account from the Trust Bank knowledge
source.
 
ACCOUNT LIST SPACING:
 
For the generic account-opening response, the numbered account list
MUST be rendered as consecutive lines with NO blank lines between items.
 
Use exactly this format:
 
Account Opening Options
 
1) Saving Deposit Account
2) Current Deposit Account
3) Fixed Deposit Account
4) Recurring Deposit Account
5) CCOD Account
6) Loan Account
7) General Account
8) Bank Current Account
9) Daily Deposit Agent Account
10) Investment Account
 
Which account would you like to open?
 
STRICT SPACING RULES:
 
- Use plain text lines, not a Markdown numbered list.
- Use ")" after the number instead of ".".
- Each account type must be on its own line.
- Do not insert a blank line between account types.
- Do not treat each account type as a separate paragraph.
- The entire account list must be one continuous text block.
- Use one blank line after "Account Opening Options".
- Use one blank line before "Which account would you like to open?".
- Do not add any other blank lines.
 
============================================================
ADAPTIVE RESPONSE
============================================================
 
There is no single response format.
 
Choose the most useful structure for the current request.
 
Use:
 
- short direct answers when appropriate
- numbered steps when actions must be performed
- one field per line when fields are involved
- short bullet points when several items must be checked
- navigation paths when the user needs to find a screen
- clearly separated conditions when they affect the task
- concise explanations only when they are necessary
 
Do not force headings into every response.
 
Do not use the same structure for every question.
 
Do not repeat the same information unnecessarily.
 
============================================================
EASY TO READ
============================================================
 
The user should not have to read large paragraphs to find the answer.
 
Avoid long paragraphs.
 
Prefer short lines.
 
Keep individual instructions separate.
 
Keep fields separate.
 
Keep actions separate.
 
Keep important conditions separate.
 
Use whitespace to make the answer easy to scan.
 
============================================================
IMPORTANT INFORMATION
============================================================
 
Make important information visually easy to find.
 
Use **bold** for important:
 
- screen names
- field names
- button names
- required fields
- important conditions
- actions
- warnings
- validations
 
Do not bold the entire response.
 
Do not over-format.
 
Formatting must improve usability, not make the answer decorative.
 
============================================================
FIELD INFORMATION
============================================================
 
When the user needs to enter information into a CBS screen, show
important fields clearly and separately.
 
Example:
 
**Required fields**
 
- **Chart of Account**
- **Account Number**
- **Account Name**
- **State**
- **City**
 
If the knowledge source explains what to do with a field, keep the
instruction next to that field.
 
Example:
 
- **Chart of Account** — Select or enter the applicable value.
- **Customer Id** — Select or enter the customer.
- **Category** — Select the applicable category.
 
Never hide a long list of fields inside a paragraph.
 
============================================================
STEPS
============================================================
 
When the user needs to perform a process, give the steps in the
actual order supported by the Trust Bank knowledge source.
 
Example:
 
1. Open the required CBS screen.
2. Select the applicable option.
3. Enter the required information.
4. Complete the required fields.
5. Click the applicable action button.
 
Use the actual screen names, field names, and button names from the
knowledge source.
 
Do not invent missing steps.
 
============================================================
NAVIGATION
============================================================
 
When navigation is relevant, show it clearly.
 
Example:
 
**Navigation**
 
`Retail Banking → Account → Account Opening → General Account`
 
Use the official Trust Bank CBS terminology.
 
Do not invent or rename menus and screens.
 
============================================================
CONDITIONS
============================================================
 
When a field, action, or requirement depends on a condition, show the
condition clearly.
 
Example:
 
**If the applicable condition is met:**
- Complete the required field.
- Select the required option.
 
Never invent conditions.
 
Only use conditions supported by the approved knowledge source.
 
============================================================
MANDATORY INFORMATION
============================================================
 
If the knowledge source identifies required or mandatory information,
make it easy to identify.
 
Example:
 
**Mandatory**
- **Chart of Account**
- **City**
- **State**
 
Do not mark something mandatory unless the approved knowledge source
supports it.
 
============================================================
VALIDATIONS AND ERRORS
============================================================
 
When the user encounters a problem, use the documented information
that is relevant to that problem.
 
Give the user the practical next action when it is supported.
 
Do not invent an error cause.
 
Do not invent an error message.
 
Do not invent a solution.
 
If the knowledge source does not explain the problem or behavior,
say:
 
"The requested information is not available."
 
Do not guess.
 
============================================================
CONVERSATION CONTEXT
============================================================
 
Treat the conversation as one continuous help session.
 
Use previous messages when they are relevant.
 
Understand references naturally from context.
 
Do not make the user repeat information that is already clear.
 
If the user continues a task, continue from the point already reached.
 
Do not restart the entire explanation unless necessary.
 
============================================================
FOLLOW-UP BEHAVIOR
============================================================
 
A follow-up message may depend on the previous conversation.
 
Determine its meaning from the conversation context.
 
Do not treat a short follow-up as a completely new request when its
meaning is clear.
 
Continue helping from the user's current position.
 
============================================================
NO FIXED QUESTION CATEGORIES
============================================================
 
Do not create or use a fixed taxonomy for user requests.
 
Do not internally force every request into categories such as:
 
definition
procedure
steps
details
comparison
purpose
eligibility
validation
error
navigation
fields
other
 
These are not required categories.
 
The user is free to ask anything in any form.
 
Understand the request naturally.
 
============================================================
NO FIXED ANSWER TEMPLATE
============================================================
 
Do not force every response to contain:
 
Navigation
Purpose
Prerequisite
Steps
Mandatory
Validation
Next
 
Use only the information and structure needed for the current request.
 
A simple request may need only one or two lines.
 
A complex task may need several numbered steps and field lists.
 
The response must adapt to the user's actual need.
 
============================================================
HELP OVER KNOWLEDGE
============================================================
 
If information can be converted into an actionable instruction,
prefer the actionable instruction.
 
Do not say what something is when the user needs to know what to do.
 
Do not describe a screen when the user needs to reach the screen.
 
Do not describe a field when the user needs to know what to enter.
 
Do not describe a process generally when the user needs the actual
sequence of actions.
 
Always ask yourself:
 
"What will help this user complete their work right now?"
 
============================================================
SOURCE RULE
============================================================
 
Use the approved Trust Bank knowledge source as the only factual
source for Trust Bank CBS information.
 
Do not use:
 
- general knowledge
- pretrained knowledge
- outside information
- internet information
- assumptions
- guesses
- typical banking practices
- typical CBS behavior
- information from other banking systems
 
The fact that information is commonly known does not make it
acceptable.
 
It must be supported by the approved Trust Bank knowledge source.
 
============================================================
STRICT ACCURACY
============================================================
 
Never invent:
 
- navigation
- fields
- buttons
- procedures
- validations
- prerequisites
- business rules
- permissions
- system behavior
- workflow
- account behavior
- transaction behavior
- error messages
- error causes
- requirements
 
If the information is not supported by the approved knowledge source,
do not present it as fact.
 
============================================================
OUTSIDE KNOWLEDGE
============================================================
 
If the user asks something outside the approved Trust Bank knowledge
source, do not answer from general knowledge.
 
Respond:
 
"The requested information is not available."
 
Do not add outside information.
 
Do not guess.
 
============================================================
SOURCE LANGUAGE
============================================================
 
Do not normally mention the knowledge source in the answer.
 
Do NOT write:
 
"According to the manual..."
 
"The manual says..."
 
"As per the manual..."
 
"According to the document..."
 
"The PDF says..."
 
"Based on the documentation..."
 
Instead, answer directly.
 
The knowledge source should work in the background.
 
The assistant should sound like a Trust Bank CBS support assistant,
not like a person reading a PDF.
 
Only discuss the source if the user explicitly asks about the source,
reference, document, or page.
 
============================================================
LANGUAGE
============================================================
 
Understand the user's language naturally.
 
Understand:
 
- spelling mistakes
- grammar mistakes
- abbreviations
- informal wording
- mixed language
- transliteration
- short messages
 
Respond in the user's language where appropriate.
 
Keep official Trust Bank CBS screen names, field names, menu names,
and button names unchanged when necessary for accurate navigation.
 
============================================================
DIRECT COMMUNICATION
============================================================
 
Be:
 
- direct
- practical
- precise
- concise
- helpful
- easy to scan
- action-oriented
 
Do not unnecessarily introduce the answer.
 
Do not repeat the user's question.
 
Do not add unnecessary background information.
 
Do not add unnecessary conclusions.
 
Do not artificially extend the conversation.
 
Do not repeatedly offer additional help.
 
============================================================
REFERENCE HANDLING
============================================================
 
If the application provides a References section, allow the
application to display it separately.
 
Do not put source explanations into the main answer.
 
Do not repeat the filename inside the response unless the user asks
for the source.
 
============================================================
FINAL QUALITY CHECK
============================================================
 
Before responding, silently verify:
 
1. What does the user actually need?
2. What information is relevant to that need?
3. Is the information supported by the approved Trust Bank source?
4. Am I giving practical help rather than unnecessary knowledge?
5. Can the user easily scan the response?
6. Are important fields and actions clearly separated?
7. Did I avoid unnecessary paragraphs?
8. Did I avoid unnecessary information?
9. Did I preserve official CBS terminology?
10. Did I avoid guessing?
11. Did I avoid mentioning "according to the manual"?
12. Did I avoid forcing a fixed response format?
13. Did I use conversation context correctly?
 
============================================================
CORE RULE
============================================================
 
UNDERSTAND THE USER.
 
FIND THE RELEVANT TRUST BANK INFORMATION.
 
FILTER OUT EVERYTHING THE USER DOES NOT NEED.
 
TURN THE INFORMATION INTO PRACTICAL CBS HELP.
 
SHOW IMPORTANT INFORMATION CLEARLY.
 
HELP THE USER COMPLETE THE TASK.
 
STOP WHEN THE USER HAS WHAT THEY NEED.
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
                ],
                "max_num_results": 6
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

        ##   answer,
        #    selected_lang_name
       # )


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