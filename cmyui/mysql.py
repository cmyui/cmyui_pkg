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

        [x.close() for x in (cur, cnx)]
        return res

    def fetch(self, query: str, params: SQLParams = [],
              _all: bool = False, _dict: bool = True) -> SQLResult:
        if not (cnx := self.conn.get_connection()):
            raise Exception('MySQL: Failed to retrieve a worker.')

        cur = cnx.cursor(dictionary=_dict, buffered=True)
        cur.execute(query, params)

        # We are fetching data.
        if _all:
            res = cur.fetchall()
        else:
            res = cur.fetchone()

        [x.close() for x in (cur, cnx)]
        return res

    def fetchall(self, query: str, params: SQLParams = [],
                 _dict: bool = True ) -> tuple[SQLResult, ...]:
        return self.fetch(query, params, _all=True, _dict=_dict)

class AsyncSQLPool:
    __slots__ = ('pool',)

    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None

    async def connect(self, config):
        self.pool = await aiomysql.create_pool(**config)

    async def close(self) -> None:
        self.pool.close()
        await self.pool.wait_closed()

    async def execute(self, query: str, params: SQLParams = []) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                await conn.commit()

                lastrowid = cur.lastrowid

        return lastrowid

    async def fetch(self, query: str, params: SQLParams = [],
                    _all: bool = False, _dict: bool = True
                   ) -> SQLResult:
        cursor_type = aiomysql.DictCursor if _dict \
                 else aiomysql.Cursor

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor_type) as cur:
                await cur.execute(query, params)

                if _all:
                    res = await cur.fetchall()
                else:
                    res = await cur.fetchone()

        return res

    async def fetchall(self, query: str, params: SQLParams = [],
                       _dict: bool = True) -> tuple[SQLResult, ...]:
        return await self.fetch(query, params, _all=True, _dict=_dict)

    async def iterall(self, query: str, params: SQLParams = [],
                      _dict: bool = True) -> AsyncGenerator[SQLResult, None]:
        cursor_type = aiomysql.DictCursor if _dict \
                 else aiomysql.Cursor

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor_type) as cur:
                await cur.execute(query, params)

                async for row in cur:
                    yield row
