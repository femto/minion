#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024
@Author  : femto Zheng
@File    : async_example_tools.py
"""
# Example async tools to demonstrate asynchronous tool support

import asyncio
import json
from typing import Any, Dict, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from .async_base_tool import AsyncBaseTool, async_tool


class AsyncWebRequestTool(AsyncBaseTool):
    """异步Web请求工具，用于发送HTTP请求"""
    
    name = "async_web_request"
    description = "Send asynchronous HTTP requests to web APIs"
    inputs = {
        "url": {"type": "string", "description": "The URL to send request to"},
        "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, DELETE)"},
        "headers": {"type": "object", "description": "Optional HTTP headers"},
        "data": {"type": "object", "description": "Optional request body data"}
    }
    output_type = "object"
    
    async def forward(self, url: str, method: str = "GET", headers: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """
        Send an async HTTP request
        
        Args:
            url: The URL to request
            method: HTTP method to use
            headers: Optional headers dict
            data: Optional request body data
            
        Returns:
            Response data as dict
        """
        try:
            if not AIOHTTP_AVAILABLE:
                return {
                    "error": "aiohttp is not available. Please install it: pip install aiohttp",
                    "url": url,
                    "method": method
                }
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "url": str(response.url),
                    }
                    
                    # Try to parse as JSON, fallback to text
                    try:
                        result["data"] = await response.json()
                    except:
                        result["data"] = await response.text()
                    
                    return result
                    
        except Exception as e:
            return {
                "error": str(e),
                "url": url,
                "method": method
            }


class AsyncFileTool(AsyncBaseTool):
    """异步文件操作工具"""
    
    name = "async_file_tool"
    description = "Asynchronous file operations"
    inputs = {
        "operation": {"type": "string", "description": "Operation: read, write, append"},
        "file_path": {"type": "string", "description": "Path to the file"},
        "content": {"type": "string", "description": "Content to write (for write/append operations)"}
    }
    output_type = "string"
    
    async def forward(self, operation: str, file_path: str, content: Optional[str] = None) -> str:
        """
        Perform async file operations
        
        Args:
            operation: The operation to perform (read, write, append)
            file_path: Path to the file
            content: Content for write/append operations
            
        Returns:
            Result of the operation
        """
        try:
            if operation == "read":
                # Simulate async file reading
                await asyncio.sleep(0.1)  # Simulate I/O delay
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except FileNotFoundError:
                    return f"File not found: {file_path}"
                    
            elif operation == "write":
                if content is None:
                    return "Error: content parameter required for write operation"
                await asyncio.sleep(0.1)  # Simulate I/O delay
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Successfully wrote {len(content)} characters to {file_path}"
                
            elif operation == "append":
                if content is None:
                    return "Error: content parameter required for append operation"
                await asyncio.sleep(0.1)  # Simulate I/O delay
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(content)
                return f"Successfully appended {len(content)} characters to {file_path}"
                
            else:
                return f"Unsupported operation: {operation}. Use 'read', 'write', or 'append'"
                
        except Exception as e:
            return f"Error performing {operation} on {file_path}: {str(e)}"


@async_tool
async def async_calculate_pi(precision: int = 1000) -> float:
    """
    Asynchronously calculate Pi using the Leibniz formula
    
    Args:
        precision: Number of iterations for calculation
        
    Returns:
        Approximation of Pi
    """
    pi_estimate = 0.0
    sign = 1
    
    # Add some async delays to simulate computation
    for i in range(precision):
        pi_estimate += sign / (2 * i + 1)
        sign *= -1
        
        # Yield control every 100 iterations
        if i % 100 == 0:
            await asyncio.sleep(0.001)
    
    return pi_estimate * 4


@async_tool
async def async_fetch_data(url: str, delay: float = 1.0) -> Dict:
    """
    Simulate fetching data from a remote source with async delay
    
    Args:
        url: The URL to fetch data from
        delay: Delay in seconds to simulate network latency
        
    Returns:
        Simulated response data
    """
    # Simulate network delay
    await asyncio.sleep(delay)
    
    # Return simulated data
    return {
        "url": url,
        "status": "success",
        "data": f"Fetched data from {url} after {delay} seconds",
        "timestamp": asyncio.get_event_loop().time()
    }


class AsyncDatabaseTool(AsyncBaseTool):
    """模拟异步数据库操作工具"""
    
    name = "async_database"
    description = "Simulate asynchronous database operations"
    inputs = {
        "query": {"type": "string", "description": "SQL-like query string"},
        "operation": {"type": "string", "description": "Operation type: SELECT, INSERT, UPDATE, DELETE"}
    }
    output_type = "object"
    
    def __init__(self):
        super().__init__()
        self._data = {}  # Simulated database
    
    async def forward(self, query: str, operation: str = "SELECT") -> Dict:
        """
        Simulate async database operations
        
        Args:
            query: Query string
            operation: Type of database operation
            
        Returns:
            Query result
        """
        # Simulate database latency
        await asyncio.sleep(0.2)
        
        try:
            if operation.upper() == "SELECT":
                return {
                    "operation": "SELECT", 
                    "query": query,
                    "results": list(self._data.values()),
                    "count": len(self._data)
                }
            elif operation.upper() == "INSERT":
                # Simple simulation of insert
                record_id = len(self._data) + 1
                self._data[record_id] = {"id": record_id, "query": query}
                return {
                    "operation": "INSERT",
                    "inserted_id": record_id,
                    "success": True
                }
            elif operation.upper() == "UPDATE":
                # Simulate update
                updated_count = len(self._data)
                return {
                    "operation": "UPDATE",
                    "query": query,
                    "updated_rows": updated_count
                }
            elif operation.upper() == "DELETE":
                # Simulate delete
                deleted_count = len(self._data)
                self._data.clear()
                return {
                    "operation": "DELETE",
                    "deleted_rows": deleted_count
                }
            else:
                return {
                    "error": f"Unsupported operation: {operation}",
                    "supported": ["SELECT", "INSERT", "UPDATE", "DELETE"]
                }
        except Exception as e:
            return {
                "error": str(e),
                "operation": operation,
                "query": query
            }


# Collection of example async tools
EXAMPLE_ASYNC_TOOLS = {
    "async_web_request": AsyncWebRequestTool(),
    "async_file_tool": AsyncFileTool(), 
    "async_calculate_pi": async_calculate_pi,
    "async_fetch_data": async_fetch_data,
    "async_database": AsyncDatabaseTool(),
}