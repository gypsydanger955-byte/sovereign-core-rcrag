# Task for GPT-4: Fix Dependency Installation Issue

## Context

We attempted to install the dependencies for the RCRAG service, but encountered a build error with ChromaDB. The error indicates that `hnswlib` (a dependency of ChromaDB) requires C++11 compiler support, which is causing the installation to fail.

## The Error

```
RuntimeError: Unsupported compiler -- at least C++11 support is needed!
hint: This usually indicates a problem with the package or the build environment.
help: `hnswlib` (v0.8.0) was included because `chromadb` (v0.3.21) depends on `hnswlib`
```

## Current requirements.txt

```
fastapi==0.95.2
uvicorn[standard]==0.22.0
pydantic==1.10.7
chromadb==0.3.21
python-dotenv==1.0.0
```

## Your Mission

1. **Diagnose the issue**: What's causing this dependency problem?
2. **Propose a solution**: Should we:
   - Use a newer version of ChromaDB that doesn't have this issue?
   - Remove ChromaDB for now and use a mock/stub instead (since we're just scaffolding)?
   - Install system-level dependencies to support the build?
   - Use a different vector database client?

3. **Provide the fix**: Give me an updated `requirements.txt` and any additional setup instructions needed.

## Constraints

- We're running on Ubuntu 22.04 with Python 3.11
- We want to keep the service lightweight and easy to deploy
- For the scaffolding phase (Days 1-2), we don't actually need ChromaDB to work yet—we're just building the API structure

## What I Need From You

1. Your analysis of the problem
2. Your recommended solution with rationale
3. An updated `requirements.txt` file
4. Any additional setup steps (if needed)

Please provide your response now.
