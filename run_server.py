"""Run the FastAPI server with Windows-compatible event loop."""
import sys
import asyncio

if sys.platform == 'win32':
    # Set the event loop policy before uvicorn starts
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        loop="asyncio"
    )
