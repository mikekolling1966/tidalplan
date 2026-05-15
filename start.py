"""TidalPlan launch script."""
import os
import sys

# Ensure working directory is the project root (important when run as a service)
root = os.path.dirname(os.path.abspath(__file__))
os.chdir(root)
sys.path.insert(0, root)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8081)
