import logging

logger = logging.getLogger(__name__)

class DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        logger.debug("DummySession.execute called")
        class DummyResult:
            def scalar(self):
                return None
        return DummyResult()

    def query(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def commit(self):
        pass

    def rollback(self):
        pass

    def add(self, obj):
        pass

    def flush(self):
        pass

SessionLocal = DummySession

def init_db():
    logger.info("Database initialization skipped in zero-external-services mode")
