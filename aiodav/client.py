import logging
import asyncio
import os
import shutil
from types import TracebackType
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, Generator, IO, Iterable, Optional, Tuple, Type, Union, List
from aiofiles.threadpool.binary import AsyncBufferedIOBase

import aiohttp
import aiofiles
from aiohttp.client import DEFAULT_TIMEOUT

from aiodav.utils import WebDavXmlUtils
from aiodav.urn import Urn
from aiodav.exceptions import *

log = logging.getLogger(__name__)


class Client(object):
    """
    WebDAV Client

    Parameters:
        hostname (``str``):
            Url for WebDAV server should contain protocol (HTTP or HTTPS) and ip address or domain name.
            Example: `https://webdav.server.com`

        login (``str``, *optional*):
            Login name for WebDAV server can be empty in case using of token auth.

        password (``str``, *optional*):
            Password for WebDAV server can be empty in case using of token auth.

        token (``str``, *optional*):
            Token for WebDAV server can be empty in case using of login/password auth.

        root (``str``, *optional*):
            Root directory of WebDAV server. Defaults is `/`.

        timeout (``int``, *optional*):
            Time limit for all operations. Default is 300 (5 min).

        insecure (``bool``, *optional*):
            Allow insecure server connections when using SSL. Default is False.

        proxy (``str``, *optional*):
            Use this proxy with format [protocol://]host[:port]. Ex: http://localhost:3128

        proxy_user (``str``, *optional*):
            Set a user to use in proxy authentication.

        proxy_password (``str``, *optional*):
            Set a password to use in proxy authentication.

        chunk_size (``int``, *optional*):
            Size of buffer used to transfer data from/to server. This data will be
            loaded in memory. This parameter afect the progress callback in
            download/upload functions. Default is 65536 bytes (65K)
    """

    ROOT = '/'

    # HTTP headers for different actions
    DEFAULT_HTTP_HEADER = {
        'list': ["Accept: */*", "Depth: 1"],
        'free': ["Accept: */*", "Depth: 0", "Content-Type: text/xml"],
        'copy': ["Accept: */*"],
        'move': ["Accept: */*"],
        'mkdir': ["Accept: */*", "Connection: Keep-Alive"],
        'clean': ["Accept: */*", "Connection: Keep-Alive"],
        'check': ["Accept: */*"],
        'info': ["Accept: */*", "Depth: 1"],
        'get_property': ["Accept: */*", "Depth: 1", "Content-Type: application/x-www-form-urlencoded"],
        'set_property': ["Accept: */*", "Depth: 1", "Content-Type: application/x-www-form-urlencoded"]
    }

    # mapping of actions to WebDAV methods
    DEFAULT_REQUESTS = {
        'options': 'OPTIONS',
        'download': "GET",
        'upload': "PUT",
        'copy': "COPY",
        'move': "MOVE",
        'mkdir': "MKCOL",
        'clean': "DELETE",
        'check': "HEAD",
        'list': "PROPFIND",
        'free': "PROPFIND",
        'info': "PROPFIND",
        'publish': "PROPPATCH",
        'unpublish': "PROPPATCH",
        'published': "PROPPATCH",
        'get_property': "PROPFIND",
        'set_property': "PROPPATCH"
    }

    def __init__(
        self,
        hostname: str,
        login: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        root: Optional[str] = ROOT,
        timeout: Optional[int] = None,
        chunk_size: Optional[int] = None,
        proxy: Optional[str] = None,
        proxy_user: Optional[str] = None,
        proxy_password: Optional[str] = None,
        insecure: Optional[bool] = False,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        **kwargs: Any
    ) -> None:
        self._hostname = hostname.rstrip(Urn.separate)
        self._token = token
        self._root = (Urn(root).quote() if root else '').rstrip(Urn.separate)
        self._chunk_size = chunk_size if chunk_size else 65536
        self._proxy = proxy
        self._proxy_auth = aiohttp.BasicAuth(proxy_user, proxy_password) if (
            proxy_user and proxy_password) else None
        self._insecure = insecure
        self.session = aiohttp.ClientSession(
            loop=loop,
            timeout=aiohttp.ClientTimeout(total=timeout) if timeout else DEFAULT_TIMEOUT,
            auth=aiohttp.BasicAuth(login, password) if (
                login and password) else None,
            connector=kwargs.get('connector', None)
        )

    def _get_headers(
        self,
        action: str,
        headers_ext: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        headers = None
        if action in Client.DEFAULT_HTTP_HEADER:
            headers = dict([map(lambda s: s.strip(), x.split(':', 1)) for x in Client.DEFAULT_HTTP_HEADER[action]])
        else:
            headers = dict()

        if headers_ext:
            for k, v in headers_ext.items():
                headers[k] = v

        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'

        return headers

    def _get_url(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> str:
        return f"{self._hostname}{self._root}{path}"

    def get_full_path(
        self,
        urn: Urn
    ) -> str:
        return f"{self._root}{urn.path()}"

    async def _execute_request(self,
                               action: str,
                               path: Union[str, "os.PathLike[str]"],
                               data: Optional[Any] = None,
                               headers_ext: Optional[Dict[str, str]] = None
                               ) -> aiohttp.ClientResponse:
        try:
            if self.session.auth:
                await self.session.get(url=self._hostname)  # (Re)Authenticates against the proxy

            response = await self.session.request(
                method=Client.DEFAULT_REQUESTS[action],
                url=self._get_url(path),
                headers=self._get_headers(action, headers_ext),
                data=data,
                proxy=self._proxy,
                proxy_auth=self._proxy_auth,
                # chunked = self._chunk_size,
                ssl=False if self._insecure else None
            )

            if response.status == 507:
                raise NotEnoughSpace()
            if response.status == 404:
                raise RemoteResourceNotFound(path=path)
            if response.status == 405:
                raise MethodNotSupported(name=action, server=self._hostname)
            if response.status >= 400:
                raise ResponseErrorCode(url=self._get_url(path), code=response.status, message=response.content)

            return response
        except aiohttp.ClientConnectionError:
            raise NoConnection(self._hostname)
        except aiohttp.ClientResponseError as re:
            raise ConnectionException(re)
        except Exception as e:
            raise e

    def __enter__(self) -> None:
        raise TypeError("Use async with instead")

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Unable to call because you must use asyn with statement
        """
        pass

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.session.close()

    async def list(
        self,
        path: Optional[Union[str, "os.PathLike[str]"]] = ROOT,
        get_info: Optional[bool] = False
    ) -> Union[List[str], List[Dict[str, str]]]:
        """
        Returns list of nested files and directories for remote WebDAV directory by path.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PROPFIN

        Parameters:
            path (``str``):
                Path to remote directory.

            get_info (``bool``, *optional*):
                Set true to get more information like cmd 'ls -l'.

        Returns:
            List of :obj:`str` | List of :obj:`Dict[str, str]`: On success, if get_info=False it returns
                list of nested file or directory names, otherwise it returns list of information, the
                information is a dictionary and it values with following keys:

                `created`: date of resource creation,
                `name`: name of resource,
                `size`: size of resource,
                `modified`: date of resource modification,
                `etag`: etag of resource,
                `isdir`: type of resource,
                `path`: path of resource.
        """
        directory_urn = Urn(path, directory=True)
        if directory_urn.path() != Client.ROOT and not (await self.exists(directory_urn.path())):
            raise RemoteResourceNotFound(directory_urn.path())

        path = Urn.normalize_path(self.get_full_path(directory_urn))
        response = await self._execute_request(action='list', path=directory_urn.quote())
        text = await response.text()

        if get_info:
            subfiles = WebDavXmlUtils.parse_get_list_info_response(text)
            return [subfile for subfile in subfiles if Urn.compare_path(path, subfile.get('path')) is False]

        urns = WebDavXmlUtils.parse_get_list_response(text)
        return [urn.filename() for urn in urns if Urn.compare_path(path, urn.path()) is False]

    async def free(self) -> int:
        """
        Returns an amount of free space on remote WebDAV server.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PROPFIND

        Returns:
            :obj:`int`: An amount of free space in bytes.
        """

        data = WebDavXmlUtils.create_free_space_request_content()
        response = await self._execute_request(action='free', path='', data=data)
        text = await response.text()
        return WebDavXmlUtils.parse_free_space_response(text, self._hostname)

    async def exists(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> bool:
        """
        Checks an existence of remote resource on WebDAV server by remote path.
        More information you can find by link http://webdav.org/specs/rfc4918.html#rfc.section.9.4

        Parameters:
            path (``str``):
                Path to remote resource.

         Returns:
            :obj:`bool`: True if resource is exist or False otherwise.
        """

        urn = Urn(path)
        try:
            response = await self._execute_request(action='check', path=urn.quote())
        except RemoteResourceNotFound:
            return False
        except ResponseErrorCode:
            return False

        return (int(response.status) == 200)

    async def create_directory(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> bool:
        """
        Makes new directory on WebDAV server.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_MKCOL

        Parameters:
            path (``str``):
                Path to remote directory.

         Returns:
            :obj:`bool`: True if request executed with code 200 or 201 and False otherwise.
        """

        directory_urn = Urn(path, directory=True)
        if not (await self.exists(directory_urn.parent())):
            raise RemoteParentNotFound(directory_urn.path())

        try:
            response = await self._execute_request(action='mkdir', path=directory_urn.quote())
        except MethodNotSupported:
            # Yandex WebDAV returns 405 status code when directory already exists
            return True
        return response.status in (200, 201)

    async def _check_remote_resource(
        self,
        path: Union[str, "os.PathLike[str]"],
        urn: Urn
    ) -> None:
        if not (await self.exists(urn.path())) and not (await self.exists(Urn(path, directory=True).path())):
            raise RemoteResourceNotFound(path)

    async def is_directory(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> bool:
        """
        Checks is the remote resource directory.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PROPFINDL

        Parameters:
            path (``str``):
                Path to remote directory.

         Returns:
            :obj:`bool`: True in case the remote resource is directory and False otherwise.
        """

        urn = Urn(path)
        parent_urn = Urn(urn.parent())
        await self._check_remote_resource(path, urn)

        response = await self._execute_request(action='info', path=parent_urn.quote())
        text = await response.text()
        path = self.get_full_path(urn)
        return WebDavXmlUtils.parse_is_dir_response(content=text, path=path, hostname=self._hostname)

    async def info(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> Dict[str, str]:
        """
        Gets information about resource on WebDAV.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PROPFIND

        Parameters:
            path (``str``):
                Path to remote resource.

        Returns:
            :obj:`Dict[str, str]`: a dictionary of information attributes and them values with following keys:

                `created`: date of resource creation,
                `name`: name of resource,
                `size`: size of resource,
                `modified`: date of resource modification,
                `etag`: etag of resource.
        """

        urn = Urn(path)
        await self._check_remote_resource(path, urn)

        response = await self._execute_request(action='info', path=urn.quote())
        text = await response.text()
        path = self.get_full_path(urn)
        return WebDavXmlUtils.parse_info_response(content=text, path=path, hostname=self._hostname)

    async def unlink(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> None:
        """
        Cleans (Deletes) a remote resource on WebDAV server. The name of method is not changed for back compatibility
        with original library.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_DELETE

        Parameters:
            path (``str``):
                Path to remote resource.
        """

        urn = Urn(path)
        await self._execute_request(action='clean', path=urn.quote())

    async def delete(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> None:
        """
        Cleans (Deletes) a remote resource on WebDAV server. The name of method is not changed for back compatibility
        with original library.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_DELETE

        Parameters:
            path (``str``):
                Path to remote resource.
        """

        await self.unlink(path)

    async def move(
        self,
        source: Union[str, "os.PathLike[str]"],
        destination: Union[str, "os.PathLike[str]"],
        overwrite: Optional[bool] = False
    ) -> None:
        """
        Moves resource from one place to another on WebDAV server.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_MOVE

        Parameters:
            source (``str``):
                The path to resource which will be moved.

            destination (``str``):
                the path where resource will be moved.

            overwrite (``bool``, *optional*):
                The flag, overwrite file if it exists. Defaults is False.
        """

        urn_from = Urn(source)
        if not (await self.exists(urn_from.path())):
            raise RemoteResourceNotFound(urn_from.path())

        urn_to = Urn(destination)
        if not (await self.exists(urn_to.parent())):
            raise RemoteParentNotFound(urn_to.path())

        headers = {
            'Destination': self._get_url(urn_to.quote()),
            'Overwrite': ('T' if overwrite else 'F')
        }

        await self._execute_request(action='move', path=urn_from.quote(), headers_ext=headers)

    async def copy(
        self,
        source: Union[str, "os.PathLike[str]"],
        destination: Union[str, "os.PathLike[str]"],
        depth: Optional[int] = 1
    ) -> None:
        """
        Copies resource from one place to another on WebDAV server.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_COPY

        Parameters:
            source (``str``):
                The path to resource which will be copied.

            destination (``str``):
                the path where resource will be copied.

            depth (``int``, *optional*):
                Folder depth to copy. Default is 1
        """

        urn_from = Urn(source)
        if not (await self.exists(urn_from.path())):
            raise RemoteResourceNotFound(urn_from.path())

        urn_to = Urn(destination)
        if not (await self.exists(urn_to.parent())):
            raise RemoteParentNotFound(urn_to.path())

        headers = {
            "Destination": self._get_url(urn_to.quote())
        }
        if (await self.is_directory(urn_from.path())):
            headers["Depth"] = depth

        await self._execute_request(action='copy', path=urn_from.quote(), headers_ext=headers)

    async def download_iter(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> Generator[bytes, None, None]:
        """
        Downloads file from server and return content in generator.
        More information you can find by link http://webdav.org/specs/rfc4918.html#rfc.section.9.4

        Parameters:
            path (``str``):
                The path to remote resource

        Returns:
            :obj:`Generator[bytes]`: Return a generator to get file data

        Example:
            .. code-block:: python

                ...
                async for chunk in client.download_iter('/path/to/file.zip'):
                    file.write(chunk)
                ...
        """

        urn = Urn(path)
        if (await self.is_directory(urn.path())):
            raise OptionNotValid(name="path", value=path)

        if not (await self.exists(urn.path())):
            raise RemoteResourceNotFound(urn.path())

        response = await self._execute_request(action='download', path=urn.quote())
        return response.content.iter_chunked(self._chunk_size)

    async def download_to(
        self,
        path: Union[str, "os.PathLike[str]"],
        buffer: IO,
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> None:
        """
        Downloads file from server and writes it in buffer.
        More information you can find by link http://webdav.org/specs/rfc4918.html#rfc.section.9.4

        Parameters:
            path (``str``):
                The path to remote resource

            buffer (``IO``)
                IO like object to write the data of remote file.

            progress (``callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Example:
            .. code-block:: python

                ...
                # Keep track of the progress while downloading
                def progress(current, total):
                    print(f"{current * 100 / total:.1f}%")

                async with aiofiles.open('file.zip', 'wb') as file:
                    await client.download_to('/path/to/file.zip', file, progress=progress)
                ...
        """

        urn = Urn(path)
        if (await self.is_directory(urn.path())):
            raise OptionNotValid(name="path", value=path)

        if not (await self.exists(urn.path())):
            raise RemoteResourceNotFound(urn.path())

        response = await self._execute_request('download', urn.quote())
        total = int(response.headers['content-length'])
        current = 0

        if callable(progress):
            if asyncio.iscoroutinefunction(progress):
                await progress(current, total, *progress_args)
            else:
                progress(current, total, *progress_args)

        async for block in response.content.iter_chunked(self._chunk_size):
            if isinstance(buffer, AsyncBufferedIOBase):
                await buffer.write(block)
            else:
                buffer.write(block)

            current += len(block)

            if callable(progress):
                if asyncio.iscoroutinefunction(progress):
                    await progress(current, total, *progress_args)
                else:
                    progress(current, total, *progress_args)

    async def download_file(
        self,
        remote_path: Union[str, "os.PathLike[str]"],
        local_path: Union[str, "os.PathLike[str]"],
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> None:
        """
        Downloads file from server and write to a file.
        More information you can find by link http://webdav.org/specs/rfc4918.html#rfc.section.9.4

        Parameters:
            remote_path (``str``):
                The path to remote file for downloading.

            local_path (``str``):
                The path to save file locally.

            progress (``callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Example:
            .. code-block:: python

                ...
                # Keep track of the progress while downloading
                def progress(current, total):
                    print(f"{current * 100 / total:.1f}%")

                await client.download_to('/path/to/file.zip', '/home/file.zip', progress=progress)
                ...
        """

        async with aiofiles.open(local_path, 'wb') as file:
            await self.download_to(remote_path, file, progress=progress, progress_args=progress_args)

    async def download_directory(
        self,
        remote_path: Union[str, "os.PathLike[str]"],
        local_path: Union[str, "os.PathLike[str]"],
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> None:
        """
        Downloads directory and downloads all nested files and directories from remote server to local.
        If there is something on local path it deletes directories and files then creates new.
        More information you can find by link http://webdav.org/specs/rfc4918.html#rfc.section.9.4

        WARNING: Destructive method

        Parameters:
            remote_path (``str``):
                The path to directory for downloading form WebDAV server.

            local_path (``str``):
                The path to local directory for saving downloaded files and directories.

            progress (``callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.
        """

        urn = Urn(remote_path, directory=True)

        if not (await self.is_directory(urn.path())):
            raise OptionNotValid(name="remote_path", value=remote_path)

        if os.path.exists(local_path):
            shutil.rmtree(local_path)

        os.makedirs(local_path)
        async for resource_name in self.list(urn.path()):
            if urn.path().endswith(resource_name):
                continue
            _remote_path = f"{urn.path()}{resource_name}"
            _local_path = os.path.join(local_path, resource_name)
            await self.download(local_path=_local_path, remote_path=_remote_path, progress=progress, progress_args=progress_args)

    async def download(
        self,
        remote_path: Union[str, "os.PathLike[str]"],
        local_path: Union[str, "os.PathLike[str]"],
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> None:
        """
        Download a remote resourse and put in local path.
        More information you can find by link http://webdav.org/specs/rfc4918.html#rfc.section.9.4

        WARNING: DESTRUCTIVE METHOD (This method can call `self.download_directory`)

        Parameters:
            remote_path (``str``):
                The path to remote resource for downloading.

            local_path (``str``):
                The path to save resource locally.

            progress (``callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.
        """

        urn = Urn(remote_path)
        if (await self.is_directory(urn.path())):
            await self.download_directory(local_path=local_path, remote_path=remote_path, progress=progress, progress_args=progress_args)
        else:
            await self.download_file(local_path=local_path, remote_path=remote_path, progress=progress, progress_args=progress_args)

    async def upload_to(
        self,
        path: Union[str, "os.PathLike[str]"],
        buffer: Union[IO, AsyncGenerator[bytes, None]],
        buffer_size: Optional[int] = None,
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> None:
        """
        Uploads file from buffer to remote path on WebDAV server.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PUT

        Parameters:
            path (``str``):
                The path to remote resource

            buffer (``IO``)
                IO like object to read the data or a asynchronous generator to get buffer data.
                In order do you select use a async generator `progress` callback cannot be called.

            progress (``callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Example:
            .. code-block:: python

                ...
                # Keep track of the progress while uploading
                def progress(current, total):
                    print(f"{current * 100 / total:.1f}%")

                async with aiofiles.open('file.zip', 'rb') as file:
                    await client.upload_to('/path/to/file.zip', file, progress=progress)
                ...
        """

        urn = Urn(path)
        if urn.is_dir():
            raise OptionNotValid(name="path", value=path)

        if not (await self.exists(urn.parent())):
            raise RemoteParentNotFound(urn.path())

        if callable(progress) and not asyncio.iscoroutinefunction(buffer):
            async def file_sender(buff: IO):
                current = 0

                if asyncio.iscoroutinefunction(progress):
                    await progress(current, buffer_size, *progress_args)
                else:
                    progress(current, buffer_size, *progress_args)

                while current < buffer_size:
                    chunk = await buffer.read(self._chunk_size) if isinstance(buffer, AsyncBufferedIOBase) \
                        else buffer.read(self._chunk_size)
                    if not chunk:
                        break

                    current += len(chunk)

                    if asyncio.iscoroutinefunction(progress):
                        await progress(current, buffer_size, *progress_args)
                    else:
                        progress(current, buffer_size, *progress_args)
                    yield chunk

            await self._execute_request(action='upload', path=urn.quote(), data=file_sender(buffer))
        else:
            await self._execute_request(action='upload', path=urn.quote(), data=buffer)

    async def upload_file(
        self,
        remote_path: Union[str, "os.PathLike[str]"],
        local_path: Union[str, "os.PathLike[str]"],
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> None:
        """
        Uploads file to remote path on WebDAV server. File should be 2Gb or less.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PUT

        Parameters:
            remote_path (``str``):
                The path to uploading file on WebDAV server.

            local_path (``str``):
                The path to local file for uploading.

            progress (``callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Example:
            .. code-block:: python

                ...
                # Keep track of the progress while uploading
                def progress(current, total):
                    print(f"{current * 100 / total:.1f}%")

                await client.upload_file('/path/to/file.zip', 'file.zip', progress=progress)
                ...
        """

        async with aiofiles.open(local_path, 'rb') as file:
            size = os.path.getsize(local_path)
            await self.upload_to(path=remote_path, buffer=file, buffer_size=size,
                                 progress=progress, progress_args=progress_args)

    async def upload_directory(
        self,
        remote_path: Union[str, "os.PathLike[str]"],
        local_path: Union[str, "os.PathLike[str]"],
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> None:
        """
        Uploads directory to remote path on WebDAV server. In case directory is exist
        on remote server it will delete it and then upload directory with nested files
        and directories.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PUT

        WARNING: DESTRUCTIVE METHOD

        Parameters:
            remote_path (``str``):
                The path to directory for uploading on WebDAV server.

            local_path (``str``):
                The path to local directory for uploading.

            progress (``callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.
        """

        urn = Urn(remote_path, directory=True)
        if not urn.is_dir():
            raise OptionNotValid(name="remote_path", value=remote_path)

        if not os.path.isdir(local_path):
            raise OptionNotValid(name="local_path", value=local_path)

        if not os.path.exists(local_path):
            raise LocalResourceNotFound(local_path)

        if (await self.exists(urn.path())):
            await self.unlink(urn.path())

        await self.create_directory(remote_path)

        for resource_name in os.listdir(local_path):
            _remote_path = f"{urn.path()}{resource_name}".replace('\\', '')
            _local_path = os.path.join(local_path, resource_name)
            await self.upload(local_path=_local_path, remote_path=_remote_path, progress=progress, progress_args=progress_args)

    async def upload(
        self,
        remote_path: Union[str, "os.PathLike[str]"],
        local_path: Union[str, "os.PathLike[str]"],
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> None:
        """
        Uploads resource to remote path on WebDAV server.
        In case resource is directory it will upload all nested files and directories.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PUT

        WARNING: DESTRUCTIVE METHOD

        Parameters:
            remote_path (``str``):
                The path to resource for uploading on WebDAV server.

            local_path (``str``):
                The path to local resource for uploading.

            progress (``callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.
        """

        if os.path.isdir(local_path):
            self.upload_directory(local_path=local_path, remote_path=remote_path, progress=progress, progress_args=progress_args)
        else:
            self.upload_file(local_path=local_path, remote_path=remote_path, progress=progress, progress_args=progress_args)

    async def get_property(
        self,
        path: Union[str, "os.PathLike[str]"],
        option: Dict[str, str]
    ) -> Union[str, None]:
        """
        Gets metadata property of remote resource on WebDAV server.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PROPFIND

        Parameters:
            path (``str``):
                Path to remote directory.

            option (``Dict[str, str]``): the property attribute as dictionary with following keys:
                    `namespace`: (optional) the namespace for XML property which will be set,
                    `name`: the name of property which will be set.

        Returns:
            :obj:`str` | None: The value of property or None if property is not found.
        """

        urn = Urn(path)
        if not (await self.exists(urn.path())):
            raise RemoteResourceNotFound(urn.path())

        data = WebDavXmlUtils.create_get_property_request_content(option)
        response = await self._execute_request(action='get_property', path=urn.quote(), data=data)
        text = await response.text()
        return WebDavXmlUtils.parse_get_property_response(text, option['name'])

    async def set_property(
        self,
        path: Union[str, "os.PathLike[str]"],
        option: Dict[str, str]
    ) -> None:
        """
        Sets metadata property of remote resource on WebDAV server.
        More information you can find by link http://webdav.org/specs/rfc4918.html#METHOD_PROPPATCH

        Parameters:
            path (``str``):
                Path to remote directory.

            option (``Dict[str, str]``): the property attribute as dictionary with following keys:
                    `namespace`: (optional) the namespace for XML property which will be set,
                    `name`: the name of property which will be set,
                    `value`: (optional) the value of property which will be set. Defaults is empty string.
        """

        urn = Urn(path)
        if not (await self.check(urn.path())):
            raise RemoteResourceNotFound(urn.path())

        data = WebDavXmlUtils.create_set_property_batch_request_content(option)
        await self._execute_request(action='set_property', path=urn.quote(), data=data)

    async def close(self):
        """
        Close underlying http session.
        Release all acquired resources.
        """

        await self.session.close()

    def resource(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> "Resource":
        """
        Get associated resource from path

        Parameters:
            path (``str``):
                Path to remote directory.

        Returns:
            :obj:`aiodav.Resource`: Return Associated resource from path
        """

        urn = Urn(path)
        return Resource(self, urn)


class Resource(object):
    """
    Remote resource.
    """

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
        """
        Determine if the resource is a directory.

        Returns:
            :obj:`bool`: True if the resource is a directory or False else.
        """
        return await self.client.is_directory(self.urn.path())

    async def rename(
        self,
        name: str
    ) -> None:
        """
        Rename the resource.

        Parameters:
            name (``str``):
                New name to resource.
        """
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
        """
        Move the resource to new path.

        Parameters:
            path (``str``):
                New path of the resource.
        """
        new_urn = Urn(path)
        await self.client.move(source=self.urn.path(), destination=new_urn.path())
        self.urn = new_urn

    async def copy(
        self,
        path: Union[str, "os.PathLike[str]"]
    ) -> "Resource":
        """
        Copy the resource to a another path.

        Parameters:
            path (``str``):
                The path where resource will be copied.

        Returns:
            :obj:`Resource`: The value of property or None if property is not found.
        """
        urn = Urn(path)
        await self.client.copy(source=self.urn.path(), destination=path)
        return Resource(self.client, urn)

    async def info(
        self,
        filter: Optional[Iterable[str]] = None
    ) -> Dict[str, str]:
        """
        Get a dictionary with resource information.

        Parameters:
            filter (``Iterable[str]``, *optional*):
                If filter is not `None` then only return properties
                contained in filter iterable.

        Returns:
            :obj:`Dict[str, str]`: Information about the resource
        """

        info = await self.client.info(self.urn.path())
        if not filter:
            return info
        return {key: value for (key, value) in info.items() if key in filter}

    async def unlink(self) -> None:
        """
        Delete the resource.
        """

        await self.client.unlink(self.urn.path())

    async def delete(self):
        """
        Delete the resource.
        """

        await self.unlink()

    async def exists(self) -> bool:
        """
        Determine if the resource exists in the remote WebDAV server

        Returns:
            :obj:`bool`: True if the resource exists else return False.
        """

        return await self.client.exists(self.urn.path())
