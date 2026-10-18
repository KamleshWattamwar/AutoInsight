from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env once, before anything reads os.environ (db.py, tests, llm.py).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")