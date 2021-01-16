# -*- coding: utf-8 -*-

import aiomysql
from typing import Sequence, Any
from mysql.connector.pooling import MySQLConnectionPool
from typing import Optional, AsyncGenerator

__all__ = (
    # Informational
    'SQLParams',
    'SQLResult',

    # Functional
    'SQLPool',
    'AsyncSQLPool'
)

SQLParams = Sequence[Any]
SQLResult = Optional[dict[str, Any]]

class SQLPool:
    __slots__ = ('conn',)

    def __init__(self, **kwargs):
        self.conn = MySQLConnectionPool(autocommit=True, **kwargs)

    def execute(self, query: str, params: SQLParams = []) -> int:
        if not (cnx := self.conn.get_connection()):
            raise Exception('MySQL: Failed to retrieve a worker.')

        cur = cnx.cursor()
        cur.execute(query, params)
        cur.fetchmany()

        # Since we are executing a command, we
        # simply return the last row affected's id.
        res = cur.lastrowid

        cur.close()
        cnx.close()
        return res

    def fetch(self, query: str, params: SQLParams = [],
              _all: bool = False, _dict: bool = True) -> SQLResult:
        if not (cnx := self.conn.get_connection()):
            raise Exception('MySQL: Failed to retrieve a worker.')

        cur = cnx.cursor(dictionary=_dict, buffered=True)
        cur.execute(query, params)

        # We are fetching data.
        res = (cur.fetchall if _all else cur.fetchone)()

        cur.close()
        cnx.close()
        return res

    def fetchall(self, query: str, params: SQLParams = [],
                 _dict: bool = True ) -> tuple[SQLResult, ...]:
        return self.fetch(query, params, _all=True, _dict=_dict)

class AsyncSQLPool:
    __slots__ = ('pool',)

    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None

    async def connect(self, config):
        self.pool = await aiomysql.create_pool(**config, autocommit=True)

    async def close(self) -> None:
        self.pool.close()
        await self.pool.wait_closed()

    async def execute(self, query: str, params: SQLParams = []) -> int:
        """Acquire a connection & execute a query with params."""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cur:
                await cur.execute(query, params)
                await conn.commit()

                return cur.lastrowid

    async def fetch(self, query: str, params: SQLParams = [],
                    _all: bool = False, _dict: bool = True
                   ) -> SQLResult:
        """Acquire a connection & execute query with params & fetch resultset(s)."""
        cursor_type = aiomysql.DictCursor if _dict \
                 else aiomysql.Cursor

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor_type) as cur:
                await cur.execute(query, params)
                return await (cur.fetchall if _all else cur.fetchone)()

    async def fetchall(self, query: str, params: SQLParams = [],
                       _dict: bool = True) -> tuple[SQLResult, ...]:
        return await self.fetch(query, params, _all=True, _dict=_dict)

    async def iterall(self, query: str, params: SQLParams = [],
                      _dict: bool = True) -> AsyncGenerator[SQLResult, None]:
        """Like fetchall, but as an async generator."""
        cursor_type = aiomysql.DictCursor if _dict \
                 else aiomysql.Cursor

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor_type) as cur:
                await cur.execute(query, params)

                async for row in cur:
                    yield row
