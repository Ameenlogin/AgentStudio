import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# DB lives next to the backend package, regardless of where the process starts.
# In a container/hosted deployment, set AGENT_STUDIO_DB to a path on a mounted
# volume (e.g. /data/agent_studio.db) so chat history & settings survive redeploys.
_DB_PATH = os.environ.get("AGENT_STUDIO_DB") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_studio.db"
)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
