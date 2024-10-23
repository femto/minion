#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : symboltable.py
"""

from typing import Any, Dict

from pydantic import BaseModel, Field


class Symbol(BaseModel):
    output: str = ""
    output_type: str = ""
    output_description: str = ""

    def __init__(self, output, output_type, output_description):
        super().__init__()
        self.output = output
        self.output_type = output
        self.output_description = output_description


class SymbolTable(BaseModel):
    table: Dict[str, Any] = Field(default_factory=dict)
    # def __init__(self):
    # Internal dictionary to store the variables

    def __setitem__(self, name, value):
        # Set a variable in the symbol table using dict-like syntax
        self.table[name] = value

    def __getitem__(self, name):
        # Get a variable's value from the symbol table using dict-like syntax
        if name in self.table:
            return self.table[name]
        else:
            raise NameError(f"Variable '{name}' is not defined.")

    def __delitem__(self, name):
        # Delete a variable from the symbol table using dict-like syntax
        if name in self.table:
            del self.table[name]
        else:
            raise NameError(f"Variable '{name}' is not defined.")

    def __contains__(self, name):
        # Check if a variable exists in the symbol table using `in` operator
        return name in self.table

    def __repr__(self):
        # String representation of the symbol table for debugging
        return f"SymbolTable({self.table})"

    def items(self):
        """Return a view of the symbol table's key-value pairs."""
        return iter(self.table.items())
