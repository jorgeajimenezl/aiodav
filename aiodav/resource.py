from typing import Iterable, Optional, Union
from aiodav.client import Client
from aiodav.urn import Urn

import os

class Resource(object):
    def __init__(
        self, 
        client: Client, 
        urn: Urn
    ) -> None:
        self.client = client
        self.urn = urn

    def __str__(self) -> str:
        return f"resource {self.urn.path()}"

    async def is_directory(self) -> bool:
        return await self.client.is_directory(self.urn.path())

    async def rename(
        self, 
        name: Union[str, "os.PathLike[str]"]
    ) -> None:
        old_path = self.urn.path()
        parent_path = self.urn.parent()
        name = Urn(name).filename()
        new_path = f"{parent_path}{name}"

        await self.client.move(source=old_path, destination=new_path)
        self.urn = Urn(new_path)

    async def move(
        self, 
        path: Union[str, "os.PathLike[str]"]
    ) -> None:
        new_urn = Urn(path)
        await self.client.move(source=self.urn.path(), destination=new_urn.path())
        self.urn = new_urn

    async def copy(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> "Resource":
        urn = Urn(path)
        await self.client.copy(source=self.urn.path(), destination=path)
        return Resource(self.client, urn)

    async def info(
        self, 
        filter: Optional[Iterable[str]] = None
    ):
        info = await self.client.info(self.urn.path())
        if not filter:
            return info
        return {key: value for (key, value) in info.items() if key in filter}

    async def unlink(self):
        return await self.client.unlink(self.urn.path())

    async def delete(self):
        await self.unlink()

    async def exists(self):
        return await self.client.exists(self.urn.path())