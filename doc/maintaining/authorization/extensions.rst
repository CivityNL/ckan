Extensions
----------

CKAN extensions can implement custom authorization rules by overriding the
authorization functions that CKAN uses. This is done by implementing the
:py:class:`~ckan.plugins.interfaces.IAuthFunctions` plugin interface.

Dataset visibility is determined by permission labels stored in the
search index.
Implement the :py:class:`~ckan.plugins.interfaces.IPermissionLabels`
plugin interface then :ref:`rebuild your search index <rebuild search index>`
to change your dataset visibility rules. There is no
no need to override the ``package_show`` auth function, it will inherit
these changes automatically.

To get started with writing CKAN extensions, see :doc:`/extensions/index`.
