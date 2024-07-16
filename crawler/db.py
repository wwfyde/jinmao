import json
from typing import Mapping, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session

from crawler import log
from crawler.config import settings


def dumps(obj: Mapping) -> str:
    # return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS | orjson.OPT_NON_STR_KEYS).decode('utf-8')
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


engine = create_engine(
    str(settings.mysql_dsn),
    connect_args={},
    # echo=True,
    # json_serializer=dumps,
)
async_engine = create_async_engine(
    str(settings.mysql_async_dsn),
    connect_args={},
    # echo=True,
    # json_serializer=dumps,
)

engine_test = create_engine(
    str(settings.mysql_test_dsn),
    connect_args={},
    # echo=True,
    # json_serializer=dumps,
)
async_engine_test = create_async_engine(
    str(settings.mysql_test_async_dsn),
    connect_args={},
    # echo=True,
    # json_serializer=dumps,
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


if __name__ == "__main__":
    with Session(engine) as session:
        stmt = text("select version()")
        result = session.execute(stmt).scalars().one_or_none()
        log.info(result)
        # Base.metadata.create_all(engine)

    with next(get_db()) as session:
        stmt = text("select version()")
        result = session.execute(stmt).scalars().one_or_none()
        log.info(result)
        # Base.metadata.create_all(engine)
