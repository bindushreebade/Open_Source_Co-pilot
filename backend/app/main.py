from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

import asyncio
import json
import threading

from app.github.client import GitHubClient
from app.agent.agent import CodingAgent


app = FastAPI(title="Open Source Copilot")


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Clients
# --------------------------------------------------

coding_agent = CodingAgent()
github_client = GitHubClient()


# --------------------------------------------------
# Request Models
# --------------------------------------------------

class AnalyzeIssueRequest(BaseModel):
    repository: str
    issue_number: int


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Open Source Copilot is running"
    }


# --------------------------------------------------
# Normal Analyze Endpoint
# --------------------------------------------------

@app.post("/analyze-issue")
def analyze_issue(request: AnalyzeIssueRequest):

    try:
        parts = request.repository.split("/")

        if len(parts) != 2:
            raise HTTPException(
                status_code=400,
                detail="Repository must be in owner/repository format"
            )

        owner = parts[0]
        repo = parts[1]

        repository_url = (
            f"https://github.com/{owner}/{repo}.git"
        )

        # Clone repository
        from app.repository.manager import RepositoryManager

        manager = RepositoryManager()

        clone_result = manager.clone_repository(
            repository_url
        )

        repository_path = clone_result["path"]

        # Run coding agent
        result = coding_agent.run(
            owner=owner,
            repo=repo,
            issue_number=request.issue_number,
            repository_path=repository_path
        )

        tests_result = result.get(
            "test_result",
            {}
        )

        return {
            "repository": request.repository,
            "issue_number": request.issue_number,

            "root_cause": result.get(
                "root_cause"
            ),

            "explanation": result.get(
                "explanation"
            ),

            "patch": result.get(
                "patch"
            ),

            "patch_result": result.get(
                "patch_result"
            ),

            "test_result": {
                "status": tests_result.get(
                    "status"
                ),

                "success": tests_result.get(
                    "success"
                ),

                "exit_code": tests_result.get(
                    "exit_code"
                ),

                "summary": tests_result.get(
                    "summary"
                ),
            },

            "repair_attempts": result.get(
                "repair_attempts",
                0
            ),

            "status": result.get(
                "status"
            ),
        }

    except HTTPException:
        raise

    except Exception as e:

        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# --------------------------------------------------
# Streaming Analyze Endpoint
# --------------------------------------------------

@app.post("/analyze-stream")
async def analyze_stream(
    request: AnalyzeIssueRequest
):

    queue = asyncio.Queue()
    event_loop = asyncio.get_running_loop()
    event_loop_thread_id = threading.get_ident()

    # --------------------------------------------------
    # Event emitter
    # --------------------------------------------------

    def emit(event):

        # Simple string log
        if isinstance(event, str):

            event = {
                "type": "log",
                "message": event
            }

        # `coding_agent.run` executes in a worker thread. asyncio.Queue is
        # not thread-safe, so marshal worker-thread events back to the loop.
        if threading.get_ident() == event_loop_thread_id:
            queue.put_nowait(event)
        else:
            event_loop.call_soon_threadsafe(queue.put_nowait, event)

    # --------------------------------------------------
    # Run agent in background
    # --------------------------------------------------

    async def run_agent():

        try:

            # ------------------------------------------
            # Validate repository
            # ------------------------------------------

            parts = request.repository.split("/")

            if len(parts) != 2:

                await queue.put({
                    "type": "error",
                    "message": (
                        "Repository must be in "
                        "owner/repository format"
                    )
                })

                return

            owner = parts[0]
            repo = parts[1]

            emit(
                f"→ Starting analysis for "
                f"{owner}/{repo}..."
            )

            # ------------------------------------------
            # Prepare repository
            # ------------------------------------------

            repository_url = (
                f"https://github.com/{owner}/{repo}.git"
            )

            from app.repository.manager import (
                RepositoryManager
            )

            manager = RepositoryManager()

            emit(
                "→ Preparing repository..."
            )

            clone_result = (
                manager.clone_repository(
                    repository_url
                )
            )

            repository_path = clone_result["path"]

            emit(
                "✓ Repository ready."
            )

            # ------------------------------------------
            # Run coding agent
            # ------------------------------------------

            result = await asyncio.to_thread(

                coding_agent.run,

                owner=owner,

                repo=repo,

                issue_number=request.issue_number,

                repository_path=repository_path,

                emit=emit
            )

            # ------------------------------------------
            # Send final result
            # ------------------------------------------

            await queue.put({

                "type": "result",

                "data": result

            })

        except Exception as e:

            import traceback
            traceback.print_exc()

            await queue.put({

                "type": "error",

                "message": str(e)

            })

        finally:

            await queue.put({

                "type": "done"

            })

    # Start agent without blocking request
    asyncio.create_task(
        run_agent()
    )

    # --------------------------------------------------
    # SSE event generator
    # --------------------------------------------------

    async def event_generator():

        while True:

            event = await queue.get()

            yield (
                f"data: "
                f"{json.dumps(event)}"
                f"\n\n"
            )

            if event["type"] == "done":

                break

    # --------------------------------------------------
    # Return SSE stream
    # --------------------------------------------------

    return StreamingResponse(

        event_generator(),

        media_type="text/event-stream",

        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
