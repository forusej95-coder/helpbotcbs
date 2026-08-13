import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")

VECTOR_STORE_ID = "vs_zpWDJjWY9sqet8yuea3u4yoc"

client = OpenAI(
    api_key=api_key,
    base_url=f"{endpoint}/openai/v1/"
)

question = "What is a loan account?"

response = client.responses.create(
    model=model,

    instructions="""
You are a Trust Bank banking documentation assistant.

Use ONLY the Trust Bank banking manual available
through the File Search tool.

Do not use general knowledge.

Do not invent information.

If the requested information is not available
in the document, say:

"The requested information was not found in the
approved Trust Bank banking manual."
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
print("==============================================")
print("QUESTION")
print("==============================================")
print(question)

print()
print("==============================================")
print("FINAL ANSWER")
print("==============================================")
print(response.output_text)

print()
print("==============================================")
print("ALL RESPONSE ITEMS")
print("==============================================")

for index, item in enumerate(response.output):

    print()
    print(f"ITEM #{index + 1}")
    print("----------------------------------------------")

    print("TYPE:", getattr(item, "type", None))

    # Print the complete SDK object
    print(item)

    # If the item contains annotations/citations,
    # expose them explicitly.
    if hasattr(item, "content"):

        for content in item.content:

            print()
            print("CONTENT ITEM:")
            print(content)

            if hasattr(content, "annotations"):
                print("ANNOTATIONS:")
                print(content.annotations)