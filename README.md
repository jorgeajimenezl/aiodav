# Python Async WebDAV Client
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=jorgeajimenezl_aiodav&metric=alert_status)](https://sonarcloud.io/dashboard?id=jorgeajimenezl_aiodav)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=jorgeajimenezl_aiodav&metric=sqale_rating)](https://sonarcloud.io/dashboard?id=jorgeajimenezl_aiodav)
![PyPI](https://img.shields.io/pypi/v/aiodav)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aiodav)

A asynchronous WebDAV client that use `asyncio` 

> Based on [webdavclient3](https://github.com/ezhov-evgeny/webdav-client-python-3)

## Installation
We periodically publish source code and wheels [on PyPI](https://pypi.python.org/pypi/aiodav).
```bash
$ pip install aiodav
```

For install the most updated version:
```bash
$ git clone https://github.com/jorgeajimenezl/aiodav.git
$ cd aiodav
$ pip install -e .
```

## Getting started
```python
from aiodav import Client
import asyncio

async def main():
    async with Client('https://webdav.server.com', login='juan', password='cabilla') as client:
        space = await client.free()
        print(f"Free space: {space} bytes")
        
        async def progress(c, t):
            print(f"{c} bytes / {t} bytes")

        await client.download_file('/remote/file.zip', 
                                    '/local/file.zip',
                                    progress=progress)

asyncio.run(main())
```

## License
[MIT License](./LICENSE)
