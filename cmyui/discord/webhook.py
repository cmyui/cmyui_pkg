# -*- coding: utf-8 -*-

import orjson
import aiohttp
from typing import Optional

__all__ = ('EmbedFooter', 'EmbedImage', 'EmbedThumbnail',
           'EmbedVideo', 'EmbedProvider', 'EmbedAuthor',
           'EmbedField', 'Embed', 'Webhook')

class EmbedFooter:
    def __init__(self, text: str, **kwargs) -> None:
        self.text = text
        self.icon_url = kwargs.pop('icon_url', '')
        self.proxy_icon_url = kwargs.pop('proxy_icon_url', '')

class EmbedImage:
    def __init__(self, **kwargs) -> None:
        self.url = kwargs.pop('url', '')
        self.proxy_url = kwargs.pop('proxy_url', '')
        self.height = kwargs.pop('height', 0)
        self.width = kwargs.pop('width', 0)

class EmbedThumbnail:
    def __init__(self, **kwargs) -> None:
        self.url = kwargs.pop('url', '')
        self.proxy_url = kwargs.pop('proxy_url', '')
        self.height = kwargs.pop('height', 0)
        self.width = kwargs.pop('width', 0)

class EmbedVideo:
    def __init__(self, **kwargs) -> None:
        self.url = kwargs.pop('url', '')
        self.height = kwargs.pop('height', 0)
        self.width = kwargs.pop('width', 0)

class EmbedProvider:
    def __init__(self, **kwargs) -> None:
        self.url = kwargs.pop('url', '')
        self.name = kwargs.pop('name', '')

class EmbedAuthor:
    def __init__(self, **kwargs) -> None:
        self.name = kwargs.pop('name', '')
        self.url = kwargs.pop('url', '')
        self.icon_url = kwargs.pop('icon_url', '')
        self.proxy_icon_url = kwargs.pop('proxy_icon_url', '')

class EmbedField:
    def __init__(self, name: str, value: str,
                 **kwargs) -> None:
        self.name = name
        self.value = value
        self.inline = kwargs.pop('inline', False)

class Embed:
    def __init__(self, **kwargs) -> None:
        self.title = kwargs.get('title')
        self.type = kwargs.get('type')
        self.description = kwargs.get('description')
        self.url = kwargs.get('url')
        self.timestamp = kwargs.get('timestamp') # datetime
        self.color = kwargs.get('color', 0x000000)

        self.footer: Optional[EmbedFooter] = kwargs.get('footer')
        self.image: Optional[EmbedImage] = kwargs.get('image')
        self.thumbnail: Optional[EmbedThumbnail] = kwargs.get('thumbnail')
        self.video: Optional[EmbedVideo] = kwargs.get('video')
        self.provider: Optional[EmbedProvider] = kwargs.get('provider')
        self.author: Optional[EmbedAuthor] = kwargs.get('author')

        self.fields: list[EmbedField] = []

class Webhook:
    """A class to represent a single-use Discord webhook."""
    __slots__ = ('url', 'content', 'username',
                 'avatar_url', 'tts', 'file', 'embeds')
    def __init__(self, url: str, **kwargs) -> None:
        self.url = url
        self.content = kwargs.get('content')
        self.username = kwargs.get('username')
        self.avatar_url = kwargs.get('avatar_url')
        self.tts = kwargs.get('tts')
        self.file = kwargs.get('file')
        self.embeds = kwargs.get('embeds', [])

    def add_embed(self, embed: Embed) -> None:
        self.embeds.append(embed)

    @property
    def json(self):
        if not any([self.content, self.file, self.embeds]):
            raise Exception('Webhook must contain atleast one '
                            'of (content, file, embeds).')

        if self.content and len(self.content) > 2000:
            raise Exception('Webhook content must be under '
                            '2000 characters.')

        payload = {'embeds': []}

        for key in ('content', 'username',
                    'avatar_url', 'tts', 'file'):
            if (val := getattr(self, key)) is not None:
                payload[key] = val

        for embed in self.embeds:
            embed_payload = {}

            # simple params
            for key in ('title', 'type', 'description',
                        'url', 'timestamp', 'color'):
                if val := getattr(embed, key):
                    embed_payload[key] = val

            # class params, must turn into dict
            for key in ('footer', 'image', 'thumbnail',
                        'video', 'provider', 'author'):
                if val := getattr(embed, key):
                    embed_payload[key] = val.__dict__

            if embed.fields:
                embed_payload['fields'] = [f.__dict__ for f in embed.fields]

            payload['embeds'].append(embed_payload)

        return orjson.dumps(payload).decode()

    # TODO: add multipart support so we can upload files.
    async def post(self, http: Optional[aiohttp.ClientSession] = None) -> None:
        """Post the webhook in JSON format."""
        _http = http or aiohttp.ClientSession(json_serialize=orjson.dumps)

        headers = {'Content-Type': 'application/json'}
        async with _http.post(self.url, data=self.json,
                              headers=headers) as resp:
            if not resp or resp.status != 204:
                return # failed

        if not http:
            await _http.close()
