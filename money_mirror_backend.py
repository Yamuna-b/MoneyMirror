"""
Backward-compatible entrypoint: `python money_mirror_backend.py` or `uvicorn money_mirror_backend:app`.
"""
from main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    print("\n[Money Mirror] API starting...")
    print("    -> API docs:  http://localhost:8000/docs")
    print("    -> Frontend:  http://localhost:8000/\n")
    uvicorn.run("money_mirror_backend:app", host="0.0.0.0", port=8000, reload=True)
