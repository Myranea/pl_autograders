**Changing members of a test case**
===================================

UTSGDecoratorFactory
====================

.. autoclass:: utsg_decorators.UTSGDecoratorFactory

.. autofunction:: utsg_decorators.UTSGDecoratorFactory.__init__

.. autofunction:: utsg_decorators.UTSGDecoratorFactory.__call__

Decorator factories created as partial functions are ``name``, ``description``, ``max_points``, ``points_lost_on_failure``, ``include_in_results``
, ``hidden``, ``message``, ``output``, and ``images``, which can be used to create a UTSG decorator 
by instantiating a decorator with just a member value, which sets the member value it is named after
with the value passed.

.. note:: TODO explain how the decorators work better? 