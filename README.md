# Python Async WebDAV Client
![PyPI](https://img.shields.io/pypi/v/aiodav)
![Downloads](https://img.shields.io/pypi/dm/aiodav)
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
