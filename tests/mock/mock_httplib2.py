import json
from typing import Callable
from urllib.parse import parse_qsl, urlparse

import httplib2

origin_request = httplib2.Http.request


class MockHttplib2Response(httplib2.Response):
    check_funcs: dict[tuple[str, str], Callable[[dict], str]] = {}
    rsp_cache: dict[str, str] = {}
    name = "httplib2"

    def __init__(self, http, uri, method="GET", **kwargs) -> None:
        ```
        """Initialize the class instance with HTTP request details and caching mechanism.
        
        Args:
            http: The HTTP client object used for making requests.
            uri (str): The URI of the request, including query parameters.
            method (str): The HTTP method for the request, defaults to "GET".
            **kwargs: Additional keyword arguments for the request.
        
        Returns:
            None: This method initializes the instance and doesn't return anything.
        """
        
        ```        url = uri.split("?")[0]
        result = urlparse(uri)
        params = dict(parse_qsl(result.query))
        fn = self.check_funcs.get((method, uri))
        new_kwargs = {"params": params}
        key = f"{self.name}-{method}-{url}-{fn(new_kwargs) if fn else json.dumps(new_kwargs)}"
        if key not in self.rsp_cache:
            _, self.content = origin_request(http, uri, method, **kwargs)
            self.rsp_cache[key] = self.content.decode()
        self.content = self.rsp_cache[key]

    def __iter__(self):
        """Returns an iterator for the HTTPResponse object.
        
        Args:
            self: The instance of the HTTPResponse class.
        
        Returns:
            iterator: An iterator that yields the HTTPResponse object itself and then its content encoded as bytes.
        """
        yield self
        yield self.content.encode()
