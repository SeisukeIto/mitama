import cgi
import http
import http.cookies
import io
import json
import wsgiref.util as wsgiutil
from urllib.parse import parse_qs, urlencode

from yarl import URL


class _Cookies:
    def __init__(self, cookies):
        self._cookies = cookies

    def __getitem__(self, key):
        if key in self._cookies:
            return self._cookies[key].value
        else:
            raise KeyError("")

    def get(self, key):
        if key in self._cookies:
            return self._cookies[key].value
        else:
            return None


class _RequestPayload:
    def __init__(self, field_storage):
        self._field_storage = field_storage

    def __contains__(self, key):
        if key not in self._field_storage:
            return False
        elif isinstance(self._field_storage[key].file, io.BytesIO):
            return (self._field_storage[key].filename or "") != ""
        else:
            return len(self._field_storage[key].value) > 0

    def __getitem__(self, key):
        if key not in self._field_storage:
            raise KeyError
        elif (self._field_storage[key].filename or "") != "":
            return self._field_storage[key]
        elif len(self._field_storage[key].value) > 0:
            return self._field_storage[key].value
        else:
            raise KeyError

    def get(self, key, default=None):
        if key in self:
            return self[key]
        else:
            return default

    def getlist(self, key, default=list()):
        if key in self:
            return self._field_storage.getlist(key)
        else:
            return default

    @classmethod
    def parse_body(cls, rfile, content_type, length):
        environ = {"REQUEST_METHOD": "POST"}
        headers = {"content-type": content_type, "content-length": length}
        fs = cgi.FieldStorage(rfile, environ=environ, headers=headers)
        payload = cls(fs)
        return payload


class Request:
    MessageClass = http.client.HTTPMessage

    def __init__(self, environ):
        self._environ = environ
        self._rfile = environ["wsgi.input"]
        self._data = dict()

    def __setitem__(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self._data[key]

    def __delitem__(self, key):
        del self._data[key]

    def get(self, key):
        return self._data[key] if key in self._data else None

    @property
    def scheme(self):
        return wsgiutil.guess_scheme(self._environ)

    @property
    def host(self):
        return self._environ["HTTP_HOST"]

    @property
    def method(self):
        return self._environ["REQUEST_METHOD"]

    @property
    def raw_path(self):
        return self.path + (
            "?" + "&".join(["%s=%s" % (kv[0], kv[1][0]) for kv in self.query.items()])
            if "QUERY_STRING" in self._environ
            else ""
        )

    @property
    def path(self):
        return self._environ.get("PATH_INFO", "/")

    @property
    def query(self):
        return parse_qs(self._environ.get("QUERY_STRING", ""))

    @property
    def version(self):
        return self._environ["SERVER_PROTOCOL"]

    @property
    def headers(self):
        return self._headers

    @property
    def url(self):
        return wsgiutil.request_uri(self._environ)

    @property
    def cookies(self):
        if hasattr(self, "_cookies"):
            return self._cookies
        else:
            cookie_header = self._environ.get("HTTP_COOKIE", "")
            C = http.cookies.SimpleCookie(cookie_header)
            self._cookies = _Cookies(C)
            return self._cookies

    def post(self):
        if hasattr(self, "_post"):
            return self._post
        else:
            content_type = self._environ.get("CONTENT_TYPE", "")
            length = self._environ.get("CONTENT_LENGTH", 0)
            if length == "" or length is None:
                length = 0
            else:
                length = int(length)
            if content_type.startswith(
                "multipart/form-data"
            ) or content_type.startswith("application/x-www-form-urlencoded"):
                parsed_body = _RequestPayload.parse_body(
                    self._rfile, content_type, length
                )
            elif content_type == "application/json":
                payload = self._rfile.read(length)
                parsed_body = json.loads(payload)
            else:
                parsed_body = {}
            self._post = parsed_body if parsed_body is not None else {}
            return self._post

    def session(self):
        """セッション情報を取得します

        :return: セッションの辞書データ
        """
        sess = self.get("mitama_session")
        if sess is None:
            storage = self.get("mitama_session_storage")
            sess = storage.load_session(self)
            self["mitama_session"] = sess
        return sess

    @classmethod
    def parse_stream(cls, rfile, ssl=False):
        words = rfile.readline().decode().rstrip("\r\n").split(" ")
        version = words[-1]
        if not 2 <= len(words) <= 3:
            raise Exception("Bad Request")
        command, path = words[:2]
        if len(words) == 2:
            close_connection = True
            if command != "GET":
                raise Exception("Bad Request")
        try:
            headers = http.client.parse_headers(rfile, _class=cls.MessageClass)
        except http.client.LineTooLong as err:
            raise Exception("")
        except http.client.HTTPException as err:
            raise Exception("")
        return cls(command, path, version, headers, ssl, rfile)
