-------------
Authorization
-------------

CKAN's authorization system controls which users are allowed to carry out which
actions on the site. All actions that users can carry out on a CKAN site are
controlled by the authorization system. For example, the authorization system
controls who can register new user accounts, delete user accounts, or create,
edit and delete datasets, groups and organizations.

Authorization in CKAN can be controlled in four ways:

1. Organizations
2. Dataset collaborators
3. Configuration file options
4. Extensions

The following sections explain each of the four methods in turn.

.. note::

   An **organization admin** in CKAN is an administrator of a particular
   organization within the site, with control over that organization and its
   members and datasets. A **sysadmin** is an administrator of the site itself.
   Sysadmins can always do everything, including adding, editing and deleting
   datasets, organizations and groups, regardless of the organization roles and
   configuration options described below.

------------

.. toctree::
   :maxdepth: 1

   object_types
   configuration
   extensions
   api
