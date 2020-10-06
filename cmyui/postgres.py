# -*- coding: utf-8 -*-

import asyncpg
from typing import Optional, Union, AsyncGenerator

__all__ = (
    'SQLParams',
    'SQLResult',
    'AsyncPGPool'
)

SQLParams = tuple[Union[int, float, str]]
SQLResult = asyncpg.Record

class AsyncPGPool:
    __slots__ = ('pool',)

    def __init__(self):
        self.pool: Optional[asyncpg.pool.Pool] = None

    async def connect(self, loop, **kwargs):
        self.pool = await asyncpg.create_pool(loop=loop, **kwargs)

    async def execute(self, query: str, *params: tuple[SQLParams]) -> int:
        async with self.pool.acquire() as con:
            async with con.transaction():
                res = await con.cursor(query, *params)

        return res

    async def fetch(self, query: str, *params: tuple[SQLParams], _all: bool = False
                   ) -> Optional[Union[list[SQLResult], SQLResult]]:
        async with self.pool.acquire() as con:
            async with con.transaction():
                cur = await con.cursor(query, *params)
                res = await (cur.fetch if _all else cur.fetchrow)()

        return res

    async def fetchall(self, query: str, *params: tuple[SQLParams]
                      ) -> Optional[Union[tuple[SQLResult], SQLResult]]:
        return await self.fetch(query, *params, _all = True)

    async def iterall(self, query: str, *params: tuple[SQLParams]
                     ) -> AsyncGenerator[SQLResult, None]:
        async with self.pool.acquire() as con:
            async with con.transaction():
                async for record in con.cursor(query, *params):
                    yield record
