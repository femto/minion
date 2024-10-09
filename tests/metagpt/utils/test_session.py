#!/usr/bin/env python3
# _*_ coding: utf-8 _*_

import pytest


def test_nodeid(request):
    """
    Prints and asserts the node ID of the current test.
    
    Args:
        request (pytest.FixtureRequest): The pytest request object for the current test.
    
    Returns:
        None: This function doesn't return anything, but it has a side effect of printing
        the node ID and asserting its existence.
    """
    print(request.node.nodeid)
    assert request.node.nodeid


if __name__ == "__main__":
    pytest.main([__file__, "-s"])
