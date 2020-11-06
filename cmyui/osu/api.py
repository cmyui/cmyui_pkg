# -*- coding: utf-8 -*-

from typing import Any, Optional, Union
import aiohttp
import orjson
import time

__all__ = ()

OSU_API_BASE = 'https://osu.ppy.sh/api/v2'

# the OsuAPIWrapper classes functions will accept both
# string and integral representations of gamemodes.
API_GameMode = Union[str, int]

class OsuAPIWrapper:
    def __init__(self, client_id: int, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

        self.access_token = {
            'token': None,
            'timeout': 0
        }

    async def __aenter__(self):
        self.http_sess = aiohttp.ClientSession(json_serialize=orjson.dumps)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.http_sess.close()

    async def _authorize(self) -> None:
        """Request authorization from the osu!api."""
        url = 'https://osu.ppy.sh/oauth/token'
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
            'scope': 'public'
        }

        async with self.http_sess.post(url, data=params) as resp:
            json = await resp.json()

            self.access_token = {
                'token': json['access_token'],
                'timeout': time.time() + json['expires_in']
            }

    async def _request(self, url: str, params: Optional[dict[str, Any]] = None) -> None:
        """Perform a request to the osu!api."""
        # check if oauth2 token is expired
        if time.time() > self.access_token['timeout']:
            await self._authorize()

        headers = {'Authorization': f'Bearer {self.access_token["token"]}'}

        # XXX: i don't think i need to support POST? will if needed
        async with self.http_sess.get(url, params=params, headers=headers) as resp:
            json = await resp.json()

        return json

    # GET /users/{user_id}/{mode?}
    async def get_user(self, user_id: int, mode: Optional[API_GameMode] = None) -> None:
        """This endpoint returns the detail of specified user."""
        url = f'{OSU_API_BASE}/users/{user_id}'

        # the user may pass a gamemode as either string or int,
        # but the osu!api requires the string version.
        if mode is not None:
            if isinstance(mode, str):
                if mode not in ('osu', 'taiko', 'fruits', 'mania'):
                    return

            elif isinstance(mode, int):
                if not (0 < mode <= 3):
                    return

                mode = ('osu', 'taiko', 'fruits', 'mania')[mode]

            url += f'/{mode}'

        return await self._request(url)


    # [TODO] GET /users/{user_id}/scores/{type}

    # TODO: finish lol
