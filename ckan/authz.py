# encoding: utf-8

import functools
from sqlalchemy import or_, and_
from collections import defaultdict, OrderedDict
from logging import getLogger

import six

from ckan.common import config
from ckan.common import asbool

import ckan.plugins as p
import ckan.model as model
from ckan.common import _, g

import ckan.lib.maintain as maintain
from ckan.plugins import PluginImplementations
from ckan.plugins.interfaces import IAuthorization

log = getLogger(__name__)


class AuthFunctions:
    ''' This is a private cache used by get_auth_function() and should never be
    accessed directly we will create an instance of it and then remove it.'''
    _functions = {}

    def clear(self):
        ''' clear any stored auth functions. '''
        self._functions.clear()

    def keys(self):
        ''' Return a list of known auth functions.'''
        if not self._functions:
            self._build()
        return self._functions.keys()

    def get(self, function):
        ''' Return the requested auth function. '''
        if not self._functions:
            self._build()
        return self._functions.get(function)

    @staticmethod
    def _is_chained_auth_function(func):
        '''
        Helper function to check if a function is a chained auth function, i.e.
        it has been decorated with the chain auth function decorator.
        '''
        return getattr(func, 'chained_auth_function', False)

    def _build(self):
        ''' Gather the auth functions.

        First get the default ones in the ckan/logic/auth directory Rather than
        writing them out in full will use __import__ to load anything from
        ckan.auth that looks like it might be an authorisation function'''

        module_root = 'ckan.logic.auth'

        for auth_module_name in ['get', 'create', 'update', 'delete', 'patch']:
            module_path = '%s.%s' % (module_root, auth_module_name,)
            try:
                module = __import__(module_path)
            except ImportError:
                log.debug('No auth module for action "%s"' % auth_module_name)
                continue

            for part in module_path.split('.')[1:]:
                module = getattr(module, part)

            for key, v in module.__dict__.items():
                if not key.startswith('_'):
                    # Whitelist all auth functions defined in
                    # logic/auth/get.py as not requiring an authorized user,
                    # as well as ensuring that the rest do. In both cases, do
                    # nothing if a decorator has already been used to define
                    # the behaviour
                    if not hasattr(v, 'auth_allow_anonymous_access'):
                        if auth_module_name == 'get':
                            v.auth_allow_anonymous_access = True
                        else:
                            v.auth_allow_anonymous_access = False
                    self._functions[key] = v

        # Then overwrite them with any specific ones in the plugins:
        resolved_auth_function_plugins = {}
        fetched_auth_functions = {}
        chained_auth_functions = defaultdict(list)
        for plugin in p.PluginImplementations(p.IAuthFunctions):
            for name, auth_function in plugin.get_auth_functions().items():
                if self._is_chained_auth_function(auth_function):
                    chained_auth_functions[name].append(auth_function)
                elif name in resolved_auth_function_plugins:
                    raise Exception(
                        'The auth function %r is already implemented in %r' % (
                            name,
                            resolved_auth_function_plugins[name]
                        )
                    )
                else:
                    resolved_auth_function_plugins[name] = plugin.name
                    fetched_auth_functions[name] = auth_function

        for name, func_list in six.iteritems(chained_auth_functions):
            if (name not in fetched_auth_functions and
                    name not in self._functions):
                raise Exception('The auth %r is not found for chained auth' % (
                    name))
            # create the chain of functions in the correct order
            for func in reversed(func_list):
                if name in fetched_auth_functions:
                    prev_func = fetched_auth_functions[name]
                else:
                    # fallback to chaining off the builtin auth function
                    prev_func = self._functions[name]

                new_func = (functools.partial(func, prev_func))
                # persisting attributes to the new partial function
                for attribute, value in six.iteritems(func.__dict__):
                    setattr(new_func, attribute, value)

                fetched_auth_functions[name] = new_func

        # Use the updated ones in preference to the originals.
        self._functions.update(fetched_auth_functions)

_AuthFunctions = AuthFunctions()
#remove the class
del AuthFunctions


def clear_auth_functions_cache():
    _AuthFunctions.clear()


def auth_functions_list():
    '''Returns a list of the names of the auth functions available.  Currently
    this is to allow the Auth Audit to know if an auth function is available
    for a given action.'''
    return _AuthFunctions.keys()


def is_sysadmin(username):
    ''' Returns True is username is a sysadmin '''
    user = _get_user(username)
    return user and user.sysadmin


def _get_user(username):
    '''
    Try to get the user from g, if possible.
    If not fallback to using the DB
    '''
    if not username:
        return None
    # See if we can get the user without touching the DB
    try:
        if g.userobj and g.userobj.name == username:
            return g.userobj
    except AttributeError:
        # g.userobj not set
        pass
    except TypeError:
        # c is not available (py2)
        pass
    except RuntimeError:
        # g is not available (py3)
        pass

    # Get user from the DB
    return model.User.get(username)


def get_group_or_org_admin_ids(group_id):
    '''
    Returns a list of user IDs which have the highest role (a.k.a. admin role) for a group or organization

    :param group_id: id of the group or organization
    :type group_id: string

    :return: list of user IDs
    :rtype: list of strings
    '''
    if not group_id:
        return []
    group = model.Group.get(group_id)
    if not group:
        return []
    object_type = 'organization' if group.is_organization else 'group'
    capacity = get_admin_role(object_type)
    q = model.Session.query(model.Member) \
        .filter(model.Member.group_id == group.id) \
        .filter(model.Member.table_name == 'user') \
        .filter(model.Member.state == 'active') \
        .filter(model.Member.capacity == capacity)
    return [a.table_id for a in q.all()]


def is_authorized_boolean(action, context, data_dict=None):
    ''' runs the auth function but just returns True if allowed else False
    '''
    outcome = is_authorized(action, context, data_dict=data_dict)
    return outcome.get('success', False)


def is_authorized(action, context, data_dict=None):
    '''
    Wrapper around the actual authorization functions. Checks additionally for:

    - ignore_auth in context
    - deleted and/or sysadmin users (see also :py:func:`~ckan.plugins.toolkit.ckan.plugins.toolkit.auth_sysadmins_check`)
    - anonymous users (see also :py:func:`~ckan.plugins.toolkit.ckan.plugins.toolkit.auth_allow_anonymous_access`)

    :param action: name of the action
    :type action: string
    :param context: request context
    :type context: dictionary
    :param data_dict: additional information to pass to the authorization function, defaults to None
    :type data_dict: dictionary, optional

    :return: list of user ID's
    :rtype: list of strings
    '''
    if context.get('ignore_auth'):
        return {'success': True}

    auth_function = _AuthFunctions.get(action)
    if auth_function:
        username = context.get('user')
        user = _get_user(username)

        if user:
            # deleted users are always unauthorized
            if user.is_deleted():
                return {'success': False}
            # sysadmins can do anything unless the auth_sysadmins_check
            # decorator was used in which case they are treated like all other
            # users.
            elif user.sysadmin:
                if not getattr(auth_function, 'auth_sysadmins_check', False):
                    return {'success': True}

        # If the auth function is flagged as not allowing anonymous access,
        # and an existing user object is not provided in the context, deny
        # access straight away
        if not getattr(auth_function, 'auth_allow_anonymous_access', False) \
           and not context.get('auth_user_obj'):
            return {
                'success': False,
                'msg': 'Action {0} requires an authenticated user'.format(
                    (auth_function if not isinstance(auth_function, functools.partial)
                        else auth_function.func).__name__)
            }

        return auth_function(context, data_dict)
    else:
        raise ValueError(_('Authorization function not found: %s' % action))


DEFAULT_PERMISSIONS = {
    'user_read': 'Read an user',
    'organization_read': 'Read an organization',
    'organization_create': 'Create an organization',
    'organization_update': 'Update an organization',
    'organization_delete': 'Delete an organization',
    'organization_manage_users': 'Manage organization members',
    'organization_manage_packages': 'Manage organization datasets',
    'group_read': 'Read a group',
    'group_create': 'Create a group',
    'group_update': 'Update a group',
    'group_delete': 'Delete a group',
    'group_manage_users': 'Manage group members',
    'group_manage_packages': 'Manage group datasets',
    'package_create': 'Create a dataset',
    'package_update': 'Update a dataset',
    'package_delete': 'Delete a dataset',
    'package_manage_users': 'Manage dataset users (collaborators)',
    'package_read_activity': 'Manage dataset users (collaborators)',
}


def _get_permissions_with_prefix(prefix=None):
    '''
    Helper function to get all permissions based on a prefix (e.g. 'group_' or 'package_') or multiple prefixes.

    :param prefix: name of the action, defaults to None
    :type prefix: string or list of strings, optional

    :return: list of permissions
    :rtype: list of strings
    '''
    if prefix is None:
        return []
    if isinstance(prefix, str):
        prefix = [prefix]
    return [p for p in DEFAULT_PERMISSIONS if p.startswith(tuple(prefix))]


DEFAULT_ORGANIZATION_ROLE_PERMISSIONS = OrderedDict([
    ('admin', {
        'permissions': _get_permissions_with_prefix(['organization', 'package']),
        'label': lambda: _('Admin'),
        'description': lambda: _('Can add/edit and delete datasets, as well as manage organization members.'),
    }),
    ('editor', {
        'permissions': ['organization_read', 'package_create', 'package_update', 'package_delete',
                        'organization_manage_packages'],
        'label': lambda: _('Editor'),
        'description': lambda: _('Can add and edit datasets, but not manage organization members.'),
    }),
    ('member', {
        'permissions': ['organization_read'],
        'label': lambda: _('Member'),
        'description': lambda: _('Can view the organization\'s private datasets, but not add new datasets.'),
    }),
])

DEFAULT_GROUP_ROLE_PERMISSIONS = OrderedDict([
    ('admin', {
        'permissions': _get_permissions_with_prefix('group'),
        'label': lambda: _('Admin'),
        'description': lambda: _('Can edit group information, as well as manage group members.'),
    }),
    ('member', {
        'permissions': ['group_read', 'group_manage_packages'],
        'label': lambda: _('Member'),
        'description': lambda: _('Can add/remove datasets from groups.'),
    }),
])

DEFAULT_DATASET_ROLE_PERMISSIONS = OrderedDict([
    ('admin', {
        'permissions': ['organization_read', 'organization_manage_packages'] + _get_permissions_with_prefix('package_'),
        'label': _('Admin'),
        'description':
            _('In addition to managing the dataset, admins can add and remove collaborators from a dataset.'),
    }),
    ('editor', {
        'permissions': ['organization_read', 'package_create', 'package_update', 'package_delete'],
        'label': _('Editor'),
        'description': _('Editors can edit the dataset and its resources, as well accessing the dataset if private.'),
    }),
    ('member', {
        'permissions': ['organization_read'],
        'label': _('Member'),
        'description': _('Members can access the dataset if private, but not edit it.'),
    }),
])

ANON_ROLE_PERMISSIONS = None
USER_ROLE_PERMISSIONS = None
CREATOR_ROLE_PERMISSIONS = None
ROLE_PERMISSIONS = None
PERMISSIONS = None
PERMISSION_GROUPS = None


def get_permissions():
    assert PERMISSIONS is not None
    return PERMISSIONS


def get_anon_permissions():
    assert ANON_ROLE_PERMISSIONS is not None
    return ANON_ROLE_PERMISSIONS


def get_user_role_permissions():
    assert USER_ROLE_PERMISSIONS is not None
    return USER_ROLE_PERMISSIONS


def get_creator_role_permissions():
    assert CREATOR_ROLE_PERMISSIONS is not None
    return CREATOR_ROLE_PERMISSIONS


def get_role_permission_object_types():
    assert ROLE_PERMISSIONS is not None
    return list(ROLE_PERMISSIONS.keys())


def get_role_by_index(object_type, index):
    try:
        return get_roles(object_type)[index]
    except IndexError as e:
        return None


def get_role_label(object_type, role):
    '''
    Returns the translated label for a role

    :param object_type:
    :type object_type: string
    :param role:
    :type role: string
    :return: label of the given ``role`` for the given ``object_type``
    :rtype string
    '''
    return ROLE_PERMISSIONS[object_type][role]['label']()


def get_role_description(object_type, role):
    '''
    Returns the translated description for a role

    :param object_type: type of object
    :type object_type: string
    :param role: role name
    :type role: string
    :return: description of the given ``role`` for the given ``object_type``
    :rtype string
    '''
    return ROLE_PERMISSIONS[object_type][role]['description']()


def get_least_role(object_type):
    '''
    Returns the least/member role for a given ``object_type``

    :param object_type: type of object
    :type object_type: string
    :return: role name
    :rtype string
    '''
    return get_role_by_index(object_type, -1)


def get_admin_role(object_type):
    '''
    Returns the highest/member role for a given ``object_type``

    :param object_type: type of object
    :type object_type: string
    :return: role name
    :rtype string
    '''
    return get_role_by_index(object_type, 0)


def get_roles(object_type):
    '''
    Returns the list of role names for a given ``object_type``

    :param object_type: type of object
    :type object_type: string
    :return: list of role names
    :rtype list of strings
    '''
    assert ROLE_PERMISSIONS is not None
    return list(ROLE_PERMISSIONS[object_type])


def get_role_permissions(object_type):
    assert ROLE_PERMISSIONS is not None
    return ROLE_PERMISSIONS[object_type]


def get_roles_with_permission(object_type, permission):
    '''
    Returns the list of role names for a given ``object_type`` which have the given ``permission``

    :param object_type: type of object
    :type object_type: string
    :param permission: permission
    :type permission: string
    :return: list of role names
    :rtype list of strings
    '''
    _check_permission(permission)
    role_permissions = get_role_permissions(object_type)
    roles = [role for role in role_permissions if permission in role_permissions[role]['permissions']]
    print(f"get_roles_with_permission(object_type='{object_type}', permission='{permission}') => {roles}")
    return roles


def get_roles_with_cascading_permission(object_type, permission):
    '''
    Returns a list of role names for a given ``object_type`` which have the corresponding permission as a cascading
    permission

    :param object_type: type of object
    :type object_type: string
    :param permission: permission
    :type permission: string
    :return: list of role names
    :rtype list of strings
    '''
    _check_permission(permission)
    role_permissions = get_role_permissions(object_type)
    roles = [
        role for role in role_permissions
        if 'cascading' in role_permissions[role] and permission in role_permissions[role]['cascading']
    ]
    return roles


def register_role_permissions():
    global ANON_ROLE_PERMISSIONS, USER_ROLE_PERMISSIONS, CREATOR_ROLE_PERMISSIONS, ROLE_PERMISSIONS, PERMISSIONS
    ccp = check_config_permission

    def _append(list, value):
        if value not in list: list.append(value)

    def _remove(list, value):
        if value in list: list.remove(value)

    PERMISSIONS = DEFAULT_PERMISSIONS
    ROLE_PERMISSIONS = {
        'organization': dict(DEFAULT_ORGANIZATION_ROLE_PERMISSIONS),
        'group': dict(DEFAULT_GROUP_ROLE_PERMISSIONS),
        'package': dict(DEFAULT_DATASET_ROLE_PERMISSIONS),
    }

    USER_ROLE_PERMISSIONS = []
    ANON_ROLE_PERMISSIONS = []
    CREATOR_ROLE_PERMISSIONS = []

    # anon_create_dataset, create_dataset_if_not_in_organization, and create_unowned_dataset
    if ccp('create_dataset_if_not_in_organization') and ccp('create_unowned_dataset'):
        CREATOR_ROLE_PERMISSIONS = ['package_create', 'package_update', 'package_delete', 'package_manage_users']
        USER_ROLE_PERMISSIONS = ['package_create', 'package_update', 'package_delete', 'user_read']
        if ccp('anon_create_dataset'):
            ANON_ROLE_PERMISSIONS = ['package_create', 'package_update', 'package_delete']

    if ccp('user_create_groups'):
        _append(USER_ROLE_PERMISSIONS, 'group_create')
    if ccp('user_create_organizations'):
        _append(USER_ROLE_PERMISSIONS, 'organization_create')

    if ccp('user_delete_groups'):
        _append(ROLE_PERMISSIONS['group']['admin']['permissions'], 'group_delete')
    if ccp('user_delete_organizations'):
        _append(ROLE_PERMISSIONS['organization']['admin']['permissions'], 'organization_delete')

    if not ccp('allow_dataset_collaborators'):
        ROLE_PERMISSIONS['package'] = OrderedDict()
        _remove(CREATOR_ROLE_PERMISSIONS, 'package_manage_users')
    elif not ccp('allow_admin_collaborators'):
        if 'admin' in ROLE_PERMISSIONS['package']:
            del ROLE_PERMISSIONS['package']['admin']

    if ccp('allow_dataset_collaborators') and not ccp('allow_collaborators_to_change_owner_org'):
        p = 'organization_manage_datasets'
        for role in ROLE_PERMISSIONS['package']:
            _remove(ROLE_PERMISSIONS['package'][role]['permissions'], p)

    if ccp('public_user_details'):
        _append(ANON_ROLE_PERMISSIONS, 'user_read')

    for role in ccp('roles_that_cascade_to_sub_groups'):
        if role in ROLE_PERMISSIONS['group']:
            ROLE_PERMISSIONS['group'][role]['cascading'] = ROLE_PERMISSIONS['group'][role]['permissions']

    for plugin in PluginImplementations(IAuthorization):
        PERMISSIONS = plugin.get_permissions(PERMISSIONS)
        PERMISSIONS = plugin.get_user_permissions(PERMISSIONS)
        ROLE_PERMISSIONS = plugin.get_object_role_permissions(ROLE_PERMISSIONS)

    errors = {}
    check_dict = {
        ('anon',): ANON_ROLE_PERMISSIONS,
        ('user',): ANON_ROLE_PERMISSIONS,
    }
    check_dict.update({(ot,r,): rp['permissions'] for ot, orp in ROLE_PERMISSIONS.items() for r, rp in orp.items()})

    for check_key, check_permissions in check_dict.items():
        for check_permission in check_permissions:
            try:
                _check_permission(check_permission)
            except ValueError as e:
                _dict = errors
                for check_key_item in check_key:
                    _dict.setdefault(check_key_item, {})
                    _dict = _dict.get(check_key_item)
                _dict.setdefault(check_permission, str(e))

    if errors:
        raise ValueError(errors)


def _check_permission(permission):
    if permission not in PERMISSIONS:
        raise ValueError(f"Invalid permission '{permission}': should be one of {list(PERMISSIONS.keys())}!")


def has_user_permission(user_name_or_id, permission, is_creator=False):
    print(f"has_user_permission(user_name_or_id={user_name_or_id}, permission={permission}, is_creator={is_creator})")
    # check for user_name_or_id
    user_id = get_user_id_for_username(user_name_or_id, allow_none=True)
    if is_sysadmin(user_id):
        return True

    _check_permission(permission)

    if user_id:
        if is_creator:
            return permission in CREATOR_ROLE_PERMISSIONS
        else:
            return permission in USER_ROLE_PERMISSIONS
    else:
        return permission in ANON_ROLE_PERMISSIONS


def has_user_permission_for_package(package_id, user_name_or_id, permission):
    print(f"has_user_permission_for_package(package_id={package_id}, user_name_or_id={user_name_or_id}, permission={permission})")

    # check for package
    package = model.Package.get(package_id)
    if not package:
        return False

    # check for user_name_or_id
    user_id = get_user_id_for_username(user_name_or_id, allow_none=True)
    if is_sysadmin(user_id):
        return True

    _check_permission(permission)

    is_creator = package.creator_user_id == user_id

    if user_id:
        # check if this user is a member of this package
        print(f"roles = {get_roles_with_permission('package', permission)}")
        q = model.Session.query(model.PackageMember) \
            .filter(model.PackageMember.user_id == user_id) \
            .filter(model.PackageMember.package_id == package.id) \
            .filter(model.PackageMember.capacity.in_(get_roles_with_permission('package', permission)))

        if q.count() > 0:
            return True

    if package.owner_org:
        return has_user_permission_for_organization(package.owner_org, user_name_or_id, permission)

    return has_user_permission(user_id, permission, package.creator_user_id == user_id)


def has_user_permission_for_organization(organization_id, user_name, permission):
    print(f"has_user_permission_for_organization(organization_id={organization_id}, user_name={user_name}, permission={permission})")
    return has_user_permission_for_group_or_org(organization_id, user_name, permission)


def _has_user_cascading_permission_for_group_or_org(group, user_id, permission):
    print(f"_has_user_cascading_permission_for_group_or_org(group={group}, user_id={user_id}, permission={permission})")

    group_roles = get_roles_with_cascading_permission('group', permission)
    organization_roles = get_roles_with_cascading_permission('organization', permission)

    if not group_roles and not organization_roles:
        return False

    parent_groups = group.get_parent_group_hierarchy(type=group.type)
    for parent_group in parent_groups:
        check = False
        if parent_group.is_organization and organization_roles:
            check = users_role_for_group_or_org(parent_group.id, user_id) in organization_roles
        elif group_roles:
            check = users_role_for_group_or_org(parent_group.id, user_id) in group_roles
        if check:
            return True
    return False


def has_user_permission_for_group_or_org(group_id, user_name, permission):
    ''' Check if the user has the given permissions for the group, allowing for
    sysadmin rights and permission cascading down a group hierarchy.

    '''

    print(f"has_user_permission_for_group_or_org(group_id={group_id}, user_name={user_name}, permission={permission})")

    if not group_id:
        return False
    group = model.Group.get(group_id)
    if not group:
        return False
    group_id = group.id

    # Sys admins can do anything
    if is_sysadmin(user_name):
        return True

    user_id = get_user_id_for_username(user_name, allow_none=True)
    if not user_id:
        return False
    if _has_user_permission_for_groups(user_id, permission, [group_id]):
        return True

    # Handle when permissions cascade. Check the user's roles on groups higher
    # in the group hierarchy for permission.
    return _has_user_cascading_permission_for_group_or_org(group, user_id, permission)


def _has_user_permission_for_groups(user_id, permission, group_ids, capacity=None):
    ''' Check if the user has the given permissions for the particular
    group (ignoring permissions cascading in a group hierarchy).
    Can also be filtered by a particular capacity.
    '''
    print(f"_has_user_permission_for_groups(user_id={user_id}, permission={permission}, group_ids={group_ids}, capacity={capacity})")
    if not group_ids:
        return False

    group_permissions = get_roles_with_permission('group', permission)
    organization_permissions = get_roles_with_permission('organization', permission)
    print(f"group_permissions = {group_permissions}")
    print(f"organization_permissions = {organization_permissions}")
    q = model.Session.query(model.Member, model.Group) \
        .join(model.Group, model.Member.group_id == model.Group.id) \
        .filter(model.Member.group_id.in_(group_ids)) \
        .filter(model.Member.table_name == 'user') \
        .filter(model.Member.state == 'active') \
        .filter(model.Member.table_id == user_id) \
        .filter(
            or_(
                and_(model.Member.capacity.in_(group_permissions), model.Group.is_organization == False),
                and_(model.Member.capacity.in_(organization_permissions), model.Group.is_organization == True)
            )
        )
    if capacity:
        q = q.filter(model.Member.capacity == capacity)
    # see if any role has the required permission
    return bool(q.count())


def users_role_for_group_or_org(group_id, user_name):
    ''' Returns the user's role for the group. (Ignores privileges that cascade
    in a group hierarchy.)

    '''
    if not group_id:
        return None
    group_id = model.Group.get(group_id).id

    user_id = get_user_id_for_username(user_name, allow_none=True)
    if not user_id:
        return None
    # get any roles the user has for the group
    q = model.Session.query(model.Member) \
        .filter(model.Member.group_id == group_id) \
        .filter(model.Member.table_name == 'user') \
        .filter(model.Member.state == 'active') \
        .filter(model.Member.table_id == user_id)
    # return the first role we find
    for row in q.all():
        return row.capacity
    return None


def has_user_permission_for_some_org(user_name, permission):
    ''' Check if the user has the given permission for any organization. '''
    user_id = get_user_id_for_username(user_name, allow_none=True)
    if not user_id:
        return False
    roles = get_roles_with_permission('organization', permission)

    if not roles:
        return False
    # get any groups the user has with the needed role
    join_on = model.Member.group_id == model.Group.id and model.Group.is_organization and model.Group.state == 'active'
    q = model.Session.query(model.Member) \
        .join(model.Group, join_on) \
        .filter(model.Member.table_name == 'user') \
        .filter(model.Member.state == 'active') \
        .filter(model.Member.capacity.in_(roles)) \
        .filter(model.Member.table_id == user_id)

    return bool(q.count())


def get_user_id_for_username(user_name, allow_none=False):
    ''' Helper function to get user id '''
    # first check if we have the user object already and get from there
    user = _get_user(user_name)
    if user:
        return user.id
    if allow_none:
        return None
    raise Exception('Not logged in user')


CONFIG_PERMISSIONS_DEFAULTS = {
    # permission and default
    # these are prefixed with ckan.auth. in config to override
    'anon_create_dataset': False,
    'create_dataset_if_not_in_organization': True,
    'create_unowned_dataset': True,
    'user_create_groups': True,
    'user_create_organizations': True,
    'user_delete_groups': True,
    'user_delete_organizations': True,
    'create_user_via_api': False,
    'create_user_via_web': False,
    'roles_that_cascade_to_sub_groups': 'admin',
    'public_user_details': True,
    'public_activity_stream_detail': False,
    'allow_dataset_collaborators': False,
    'allow_admin_collaborators': False,
    'allow_collaborators_to_change_owner_org': False,
    'create_default_api_keys': False,
}


def check_config_permission(permission):
    '''Returns the configuration value for the provided permission

    Permission is a string indentifying the auth permission (eg
    `anon_create_dataset`), optionally prefixed with `ckan.auth.`.

    The possible values for `permission` are the keys of
    CONFIG_PERMISSIONS_DEFAULTS. These can be overriden in the config file
    by prefixing them with `ckan.auth.`.

    Returns the permission value, generally True or False, except on
    `roles_that_cascade_to_sub_groups` which is a list of strings.

    '''

    key = permission.replace('ckan.auth.', '')

    if key not in CONFIG_PERMISSIONS_DEFAULTS:
        return False

    default_value = CONFIG_PERMISSIONS_DEFAULTS.get(key)

    config_key = 'ckan.auth.' + key

    value = config.get(config_key, default_value)

    if key == 'roles_that_cascade_to_sub_groups':
        # This permission is set as a list of strings (space separated)
        value = value.split() if value else []
    else:
        value = asbool(value)

    return value


@maintain.deprecated('Use auth_is_loggedin_user instead')
def auth_is_registered_user():
    '''
    This function is deprecated, please use the auth_is_loggedin_user instead
    '''
    return auth_is_loggedin_user()


def auth_is_loggedin_user():
    ''' Do we have a logged in user '''
    try:
        context_user = g.user
    except TypeError:
        context_user = None
    return bool(context_user)


def auth_is_anon_user(context):
    ''' Is this an anonymous user?
        eg Not logged in if a web request and not user defined in context
        if logic functions called directly

        See ckan/lib/base.py:232 for pylons context object logic
    '''
    context_user = context.get('user')
    is_anon_user = not bool(context_user)

    return is_anon_user
