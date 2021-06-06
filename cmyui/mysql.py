# -*- coding: utf-8 -*-

from typing import Any
from typing import AsyncGenerator
from typing import Optional
from typing import Sequence
from typing import Union

import aiomysql
import mysql.connector.pooling

__all__ = (
    # Informational
    'SQLParams',
    'DictSQLResult',
    'TupleSQLResult',

    # Functional
    'AsyncSQLPool',
    'SQLPool'
)

SQLParams = Sequence[Any]
DictSQLResult = Optional[dict[str, Any]]
TupleSQLResult = Optional[tuple[Any, ...]]

class AsyncSQLPool:
    """A thin wrapper around an asynchronous mysql pool
       for single query connections."""
    __slots__ = ('pool',)

    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None

    async def connect(self, config: dict[str, object]) -> None:
        """Connect to the mysql server with a given config."""
        self.pool = await aiomysql.create_pool(**config, autocommit=True)

    async def close(self) -> None:
        """Close active connection to the mysql server."""
        self.pool.close()
        await self.pool.wait_closed()

    async def execute(self, query: str, params: SQLParams = []) -> int:
        """Acquire a connection & execute a given querystring."""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cur:
                await cur.execute(query, params)
                await conn.commit()

                return cur.lastrowid

    async def fetch(
        self, query: str,
        params: SQLParams = [],
        _all: bool = False,
        _dict: bool = True
    ) -> Union[DictSQLResult, TupleSQLResult]:
        """Acquire a connection & fetch first result
           row for a given querystring."""
        cursor_type = (aiomysql.DictCursor if _dict else
                       aiomysql.Cursor)

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor_type) as cur:
                await cur.execute(query, params)
                return await (cur.fetchall if _all else cur.fetchone)()

    async def fetchall(
        self, query: str,
        params: SQLParams = [],
        _dict: bool = True
    ) -> tuple[Union[DictSQLResult, TupleSQLResult], ...]:
        """Acquire a connection & fetch all result
           rows for a given querystring."""
        return await self.fetch(query, params, _all=True, _dict=_dict)

    async def iterall(
        self, query: str,
        params: SQLParams = [],
        _dict: bool = True
    ) -> AsyncGenerator[Union[DictSQLResult, TupleSQLResult], None]:
        """Like fetchall, but returns an async generator."""
        cursor_type = (aiomysql.DictCursor if _dict else
                       aiomysql.Cursor)

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor_type) as cur:
                await cur.execute(query, params)

                async for row in cur:
                    yield row

# NOTE: i don't really use this anymore
class SQLPool(mysql.connector.pooling.MySQLConnectionPool):
    """A thin wrapper around a mysql pool for single query connections."""
    def execute(self, query: str, params: SQLParams = []) -> int:
        """Acquire a connection & execute a given querystring."""
        if not (cnx := self.get_connection()):
            raise Exception('mysql: failed to retrieve a worker for cmyui.execute()')

        cur = cnx.cursor()
        cur.execute(query, params)
        cur.fetchmany()

        # Since we are executing a command, we
        # simply return the last row affected's id.
        res = cur.lastrowid

        cur.close()
        cnx.close()
        return res

    def fetch(
        self, query: str,
        params: SQLParams = [],
       _all: bool = False,
       _dict: bool = True
    ) -> Union[DictSQLResult, TupleSQLResult]:
        """Acquire a connection & fetch first result
           row for a given querystring."""
        if not (cnx := self.conn.get_connection()):
            raise Exception('mysql: failed to retrieve a worker for cmyui.fetch()')

        cur = cnx.cursor(dictionary=_dict, buffered=True)
        cur.execute(query, params)

        # We are fetching data.
        res = (cur.fetchall if _all else cur.fetchone)()

        cur.close()
        cnx.close()
        return res

    def fetchall(
        self, query: str,
        params: SQLParams = [],
        _dict: bool = True
    ) -> tuple[Union[DictSQLResult, TupleSQLResult], ...]:
        """Acquire a connection & fetch all result rows for a given querystring."""
        return self.fetch(query, params, _all=True, _dict=_dict)
