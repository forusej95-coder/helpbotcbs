import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# LOAD CONFIGURATION
# ============================================================

load_dotenv()

AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()

if not AZURE_ENDPOINT:
    raise RuntimeError(
        "AZURE_OPENAI_ENDPOINT is missing from .env"
    )

if not AZURE_API_KEY:
    raise RuntimeError(
        "AZURE_OPENAI_API_KEY is missing from .env"
    )


# ============================================================
# NORMALIZE AZURE OPENAI / FOUNDRY ENDPOINT
# ============================================================

AZURE_ENDPOINT = AZURE_ENDPOINT.rstrip("/")

if AZURE_ENDPOINT.endswith("/openai/v1"):
    BASE_URL = AZURE_ENDPOINT + "/"
else:
    BASE_URL = AZURE_ENDPOINT + "/openai/v1/"


# ============================================================
# CLIENT
# ============================================================

client = OpenAI(
    api_key=AZURE_API_KEY,
    base_url=BASE_URL
)


# ============================================================
# FIND PDF
# ============================================================

DATA_DIR = Path("data")

if not DATA_DIR.exists():
    raise RuntimeError(
        "data folder does not exist. Create it and put your PDF inside."
    )

pdf_files = list(DATA_DIR.glob("*.pdf"))

if not pdf_files:
    raise RuntimeError(
        "No PDF found inside the data folder."
    )

if len(pdf_files) > 1:
    print("Multiple PDFs found.")
    print("For STEP 2A we will use the first one.")

pdf_path = pdf_files[0]

print()
print("==============================================")
print("TRUST BANK KNOWLEDGE SETUP")
print("==============================================")
print()
print(f"PDF: {pdf_path.name}")
print(f"Size: {pdf_path.stat().st_size / (1024 * 1024):.2f} MB")
print()


# ============================================================
# STEP 1 — UPLOAD FILE
# ============================================================

print("Uploading PDF to Azure OpenAI Files...")

with open(pdf_path, "rb") as file:

    uploaded_file = client.files.create(
        file=file,
        purpose="assistants"
    )

print()
print("FILE UPLOAD COMPLETED")
print("----------------------------------------------")
print(f"File ID: {uploaded_file.id}")
print(f"Filename: {uploaded_file.filename}")
print(f"Status: {uploaded_file.status}")
print()


# ============================================================
# STEP 2 — CREATE VECTOR STORE
# ============================================================

print("Creating Azure Vector Store...")

vector_store = client.vector_stores.create(
    name="trustbank-retail-banking-knowledge",
    file_ids=[uploaded_file.id]
)

print()
print("VECTOR STORE CREATED")
print("----------------------------------------------")
print(f"Vector Store ID: {vector_store.id}")
print(f"Name: {vector_store.name}")
print(f"Status: {vector_store.status}")
print()


# ============================================================
# STEP 3 — WAIT FOR FILE PROCESSING
# ============================================================

print("Waiting for Azure to process the PDF...")
print("(Do not close this terminal.)")
print()

while True:

    files = client.vector_stores.files.list(
        vector_store_id=vector_store.id,
        limit=100
    )

    if files.data:

        current_file = files.data[0]

        status = current_file.status

        print(
            f"File processing status: {status}"
        )

        if status == "completed":
            break

        if status in ["failed", "cancelled"]:
            raise RuntimeError(
                f"PDF processing failed. Status: {status}"
            )

    time.sleep(5)


# ============================================================
# SUCCESS
# ============================================================

print()
print("==============================================")
print("STEP 2A COMPLETED SUCCESSFULLY")
print("==============================================")
print()
print(f"PDF File ID:")
print(uploaded_file.id)
print()
print(f"Vector Store ID:")
print(vector_store.id)
print()
print("The PDF is now ready for File Search.")
print()
print("SAVE THIS VECTOR STORE ID.")
print()