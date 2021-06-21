from re import sub
from typing import Optional
from urllib.parse import unquote, quote, urlsplit


class Urn(object):
    separate = "/"

    def __init__(self, path: str, directory: Optional[bool] = False) -> None:
        self._path = quote(path)
        expressions = "/\.+/", "/+"
        for expression in expressions:
            self._path = sub(expression, Urn.separate, self._path)

        if not self._path.startswith(Urn.separate):
            self._path = "{begin}{end}".format(
                begin=Urn.separate, end=self._path)

        if directory and not self._path.endswith(Urn.separate):
            self._path = "{begin}{end}".format(
                begin=self._path, end=Urn.separate)

    def __str__(self) -> str:
        return self.path()

    def path(self) -> str:
        return unquote(self._path)

    def quote(self) -> str:
        return self._path

    def filename(self) -> str:
        path_split = self._path.split(Urn.separate)
        name = path_split[-2] + \
            Urn.separate if path_split[-1] == '' else path_split[-1]
        return unquote(name)

    def parent(self) -> str:
        path_split = self._path.split(Urn.separate)
        nesting_level = self.nesting_level()
        parent_path_split = path_split[:nesting_level]
        parent = self.separate.join(
            parent_path_split) if nesting_level != 1 else Urn.separate
        if not parent.endswith(Urn.separate):
            return unquote(parent + Urn.separate)
        else:
            return unquote(parent)

    def nesting_level(self) -> int:
        return self._path.count(Urn.separate, 0, -1)

    def is_dir(self) -> bool:
        return self._path[-1] == Urn.separate

    @staticmethod
    def normalize_path(path: str) -> str:
        result = sub('/{2,}', '/', path)
        return result if len(result) < 1 or result[-1] != Urn.separate else result[:-1]

    @staticmethod
    def compare_path(path_a: str, href: str) -> bool:
        unqouted_path = Urn.separate + unquote(urlsplit(href).path)
        return Urn.normalize_path(path_a) == Urn.normalize_path(unqouted_path)
