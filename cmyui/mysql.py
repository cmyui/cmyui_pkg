# -*- coding: utf-8 -*-

#import asyncio
#import aiomysql
from mysql.connector.pooling import MySQLConnectionPool
from typing import Dict, Tuple, Optional, Union

__all__ = (
    'SQLParams',
    'SQLResult',
    'SQLPool',
    #'AsyncMySQLPool'
)

SQLParams = Tuple[Union[int, float, str]]
SQLResult = Dict[str, Union[int, float, str]]

class SQLPool:
    __slots__ = ('conn',)

    def __init__(self, **kwargs):
        self.conn = MySQLConnectionPool(autocommit = True, **kwargs)

    def execute(self, query: str, params: SQLParams) -> int:
        if not (cnx := self.conn.get_connection()):
            raise Exception('MySQL: Failed to retrieve a worker.')

        cursor = cnx.cursor()
        cursor.execute(query, params)
        cursor.fetchmany()

        # Since we are executing a command, we
        # simply return the last row affected's id.
        res = cursor.lastrowid

        [x.close() for x in (cursor, cnx)]
        return res

    def fetch(self, query: str, params: SQLParams = (), _all: bool = False
             ) -> Optional[Union[Tuple[SQLResult], SQLResult]]:
        if not (cnx := self.conn.get_connection()):
            raise Exception('MySQL: Failed to retrieve a worker.')

        cursor = cnx.cursor(dictionary = True)
        cursor.execute(query, params)

        # We are fetching data.
        res = (cursor.fetchall if _all else cursor.fetchone)()

        [x.close() for x in (cursor, cnx)]
        return res

    def fetchall(self, query: str, params: SQLParams = ()
                ) -> Optional[Union[Tuple[SQLResult], SQLResult]]:
        return self.fetch(query, params, _all = True)


# Should work, just disabled since
# there's no async server yet xd.
'''
class AsyncMySQLPool:
    __slots__ = ('conn',)

    async def __init__(self, **kwargs):
        self.conn = await aiomysql.connect(**kwargs)

    async def execute(self, query: str, params: SQLParams
                     ) -> int:
        cur: aiomysql.Cursor = await self.conn.cursor()
        await cur.execute(query)
        #cur._clear_result()? cur.fetchmany()?
        ret = cur.lastrowid

        await cur.close()
        return ret

    async def fetch(self, query: str, params: SQLParams, _all: bool = False
                   ) -> Optional[Union[Tuple[SQLResult], SQLResult]]:
        cur: aiomysql.Cursor = await self.conn.cursor()
        await cur.execute(query)
        if not (res := (cur.fetchall if _all else cur.fetchone)()):
            print('SQLError: No rows in result set.')
            return None

        await cur.close()

    async def fetchall(self, query: str, params: SQLParams
                      ) -> Optional[Union[Tuple[SQLResult], SQLResult]]:
        return await self.fetch(query, params, _all = True)
'''
