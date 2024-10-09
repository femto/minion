import json
from typing import Callable

from aiohttp.client import ClientSession

origin_request = ClientSession.request


class MockAioResponse:
    check_funcs: dict[tuple[str, str], Callable[[dict], str]] = {}
    rsp_cache: dict[str, str] = {}
    name = "aiohttp"
    status = 200

    def __init__(self, session, method, url, **kwargs) -> None:
        """Initialize a request object with caching capabilities.
        
        Args:
            session: Any object representing the session for making requests.
            method (str): The HTTP method for the request (e.g., 'GET', 'POST').
            url (str): The URL for the request.
            **kwargs: Additional keyword arguments for the request.
        
        Returns:
            None: This method doesn't return anything, it initializes the object.
        """
        fn = self.check_funcs.get((method, url))
        _kwargs = {k: v for k, v in kwargs.items() if k != "proxy"}
        self.key = f"{self.name}-{method}-{url}-{fn(kwargs) if fn else json.dumps(_kwargs, sort_keys=True)}"
        self.mng = self.response = None
        if self.key not in self.rsp_cache:
            self.mng = origin_request(session, method, url, **kwargs)

    async def __aenter__(self):
        """Asynchronous context manager entry method.
        
        Args:
            self: The instance of the class.
        
        Returns:
            self: The instance of the class.
        """
        if self.response:
            await self.response.__aenter__()
            self.status = self.response.status
        elif self.mng:
            self.response = await self.mng.__aenter__()
        return self

    async def __aexit__(self, *args, **kwargs):
        """Asynchronous context manager exit method.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        
        Returns:
            None: This method doesn't return anything.
        """Asynchronously retrieves and caches JSON data from the response.
        
        Args:
            *args: Variable length argument list to be passed to response.json().
            **kwargs: Arbitrary keyword arguments to be passed to response.json().
        
        Returns:
            dict: The JSON data from the response, either from cache or freshly retrieved.
        """
        """
        if self.response:
            await self.response.__aexit__(*args, **kwargs)
            self.response = None
        elif self.mng:
            await self.mng.__aexit__(*args, **kwargs)
            self.mng = None

    """Returns the content of the object.
    
    Args:
        self: The instance of the class.
    
    Returns:
        object: The instance itself.
    """
    async def json(self, *args, **kwargs):
        if self.key in self.rsp_cache:
            """Raises an HTTPError if the HTTP request returned an unsuccessful status code.
            
            This method checks the status code of the response and raises an appropriate
            HTTPError if the request was unsuccessful.
            
            Args:
                self: The instance of the class containing this method.
            
            Returns:
                None: This method doesn't return anything, it only raises an exception if necessary.
            
            Raises:
                HTTPError: If the HTTP request returned an unsuccessful status code.
            """
            return self.rsp_cache[self.key]
        data = await self.response.json(*args, **kwargs)
        self.rsp_cache[self.key] = data
        return data

    @property
    def content(self):
        return self

    async def read(self):
        """Asynchronously reads and caches response content.
        
        Args:
            self: The instance of the class containing this method.
        
        Returns:
            bytes: The content of the response, either from cache or freshly read.
        """
        if self.key in self.rsp_cache:
            return eval(self.rsp_cache[self.key])
        data = await self.response.content.read()
        self.rsp_cache[self.key] = str(data)
        return data

    def raise_for_status(self):
        if self.response:
            self.response.raise_for_status()
