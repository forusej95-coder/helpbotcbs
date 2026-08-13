# Trust Bank AI Backend

This is a NEW backend. It does not reuse the old RAG/Search code.

Planned architecture:
Chrome Extension -> Flask API -> Azure AI Foundry model
                                      |
                                      +-> Vector Store / File Search
                                      |
                                      +-> Azure Speech (later)

Step 1 only tests the Azure AI Foundry model connection.
