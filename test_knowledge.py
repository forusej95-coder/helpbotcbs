import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")

VECTOR_STORE_ID = "vs_zpWDJjWY9sqet8yuea3u4yoc"

if not endpoint:
    raise RuntimeError("AZURE_OPENAI_ENDPOINT is missing")

if not api_key:
    raise RuntimeError("AZURE_OPENAI_API_KEY is missing")

client = OpenAI(
    api_key=api_key,
    base_url=f"{endpoint}/openai/v1/"
)

question = "What is a loan account?"

response = client.responses.create(
    model=model,

    instructions="""
You are Trust Bank's banking documentation assistant.

Answer ONLY using information retrieved from the
approved Trust Bank banking manual through File Search.

Do not use your general knowledge to answer.

If the requested information cannot be found in
the document, say:

"The requested information was not found in the
approved Trust Bank banking manual."

Do not invent banking procedures, definitions,
fields, validations, or rules.
""",

    input=question,

    tools=[
        {
            "type": "file_search",
            "vector_store_ids": [VECTOR_STORE_ID]
        }
    ]
)

print()
print("====================================")
print("QUESTION")
print("====================================")
print(question)

print()
print("====================================")
print("ANSWER")
print("====================================")
print(response.output_text)

print()
print("====================================")
print("FILE SEARCH RESULTS")
print("====================================")

for item in response.output:

    if item.type == "file_search_call":
        print("File Search executed")
        print(item)

    elif item.type == "message":
        print("Answer message received")