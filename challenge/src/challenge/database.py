from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domotica_python.settings import Settings

settings = Settings()
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
