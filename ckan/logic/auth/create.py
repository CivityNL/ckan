# encoding: utf-8

import ckan.logic as logic
import ckan.authz as authz
import ckan.logic.auth as logic_auth

from ckan.common import _

@logic.auth_allow_anonymous_access
def package_create(context, data_dict=None):
    user = context['user']
    data_dict = data_dict or {}
    org_id = data_dict.get('owner_org')
    permission = 'package_create'
    if org_id and not authz.has_user_permission_for_group_or_org(org_id, user, permission):
        return {'success': False, 'msg': _('User %s not authorized to add dataset to this organization') % user}
    elif not authz.has_user_permission(user, permission):
        return {'success': False, 'msg': _('User %s not authorized to create packages') % user}
    elif not _check_group_auth(context, data_dict):
        return {'success': False, 'msg': _('User %s not authorized to edit these groups') % user}
    return {'success': True}


def file_upload(context, data_dict=None):
    # TODO check if this is an actual used auth function as no corresponding action exists
    user = context['user']
    if authz.auth_is_anon_user(context):
        return {'success': False, 'msg': _('User %s not authorized to create packages') % user}
    return {'success': True}


def resource_create(context, data_dict):
    model = context['model']
    user = context.get('user')

    package_id = data_dict.get('package_id')
    if not package_id and data_dict.get('id'):
        # This can happen when auth is deferred, eg from `resource_view_create`
        resource = logic_auth.get_resource_object(context, data_dict)
        package_id = resource.package_id

    if not package_id:
        raise logic.NotFound(
            _('No dataset id provided, cannot check auth.')
        )

    # check authentication against package
    pkg = model.Package.get(package_id)
    if not pkg:
        raise logic.NotFound(
            _('No package found for this resource, cannot check auth.')
        )

    pkg_dict = {'id': pkg.id}
    authorized = authz.is_authorized('package_update', context, pkg_dict).get('success')

    if not authorized:
        return {'success': False,
                'msg': _('User %s not authorized to create resources on dataset %s') % (str(user), package_id)}
    else:
        return {'success': True}


def resource_view_create(context, data_dict):
    return authz.is_authorized('resource_create', context, {'id': data_dict['resource_id']})


def resource_create_default_resource_views(context, data_dict):
    return authz.is_authorized('resource_create', context, {'id': data_dict['resource']['id']})


def package_create_default_resource_views(context, data_dict):
    return authz.is_authorized('package_update', context, data_dict['package'])


def package_relationship_create(context, data_dict):
    user = context['user']

    id = data_dict['subject']
    id2 = data_dict['object']

    # If we can update each package we can see the relationships
    authorized1 = authz.is_authorized_boolean(
        'package_update', context, {'id': id})
    authorized2 = authz.is_authorized_boolean(
        'package_update', context, {'id': id2})

    if not (authorized1 and authorized2):
        return {'success': False, 'msg': _('User %s not authorized to edit these packages') % user}
    else:
        return {'success': True}


def group_create(context, data_dict=None):
    user = context['user']
    if authz.has_user_permission(user, 'group_create'):
        return {'success': True}
    return {'success': False,
            'msg': _('User %s not authorized to create groups') % user}


def organization_create(context, data_dict=None):
    user = context['user']
    if authz.has_user_permission(user, 'organization_create'):
        return {'success': True}
    return {'success': False,
            'msg': _('User %s not authorized to create organizations') % user}


def rating_create(context, data_dict):
    # No authz check in the logic function
    return {'success': True}


@logic.auth_allow_anonymous_access
def user_create(context, data_dict=None):
    using_api = 'api_version' in context
    create_user_via_api = authz.check_config_permission('create_user_via_api')
    create_user_via_web = authz.check_config_permission('create_user_via_web')

    if using_api and not create_user_via_api:
        return {
            'success': False,
            'msg': _('User {user} not authorized to create users via the API').format(user=context.get('user'))
        }
    if not using_api and not create_user_via_web:
        return {'success': False, 'msg': _('Not authorized to create users')}
    return {'success': True}


def user_invite(context, data_dict):
    data_dict['id'] = data_dict['group_id']
    return group_member_create(context, data_dict)


def _check_group_auth(context, data_dict):
    '''Has this user got update permission for all of the given groups?
    If there is a package in the context then ignore that package's groups.
    (owner_org is checked elsewhere.)
    :returns: False if not allowed to update one (or more) of the given groups.
              True otherwise. i.e. True is the default. A blank data_dict
              mentions no groups, so it returns True.

    '''
    # FIXME This code is shared amoung other logic.auth files and should be
    # somewhere better
    if not data_dict:
        return True

    model = context['model']
    user = context['user']
    pkg = context.get("package")

    api_version = context.get('api_version') or '1'

    group_blobs = data_dict.get('groups', [])
    groups = set()
    for group_blob in group_blobs:
        # group_blob might be a dict or a group_ref
        if isinstance(group_blob, dict):
            # use group id by default, but we can accept name as well
            id = group_blob.get('id') or group_blob.get('name')
            if not id:
                continue
        else:
            id = group_blob
        grp = model.Group.get(id)
        if grp is None:
            raise logic.NotFound(_('Group was not found.'))
        groups.add(grp)

    if pkg:
        pkg_groups = pkg.get_groups()

        groups = groups - set(pkg_groups)

    for group in groups:
        if not authz.has_user_permission_for_group_or_org(group.id, user, 'group_manage_packages'):
            return False

    return True


def vocabulary_create(context, data_dict):
    # sysadmins only
    return {'success': False}


def activity_create(context, data_dict):
    # sysadmins only
    return {'success': False}


def tag_create(context, data_dict):
    # sysadmins only
    return {'success': False}


def _group_or_org_member_create(context, data_dict, is_org=False):
    user = context['user']
    group_id = data_dict['id']
    permission = 'organization_manage_users' if is_org else 'group_manage_users'
    if not authz.has_user_permission_for_group_or_org(group_id, user, permission):
        return {'success': False, 'msg': _('User %s not authorized to add members') % user}
    return {'success': True}


def organization_member_create(context, data_dict):
    return _group_or_org_member_create(context, data_dict, is_org=True)


def group_member_create(context, data_dict):
    return _group_or_org_member_create(context, data_dict)


def member_create(context, data_dict):
    group = logic_auth.get_group_object(context, data_dict)
    user = context['user']
    model = context['model']

    # User must be able to update the group to add a member to it
    prefix = 'organization' if group.is_organization else 'group'
    suffix = None

    if data_dict.get('object_type') == 'package':
        suffix = 'manage_packages'
    if data_dict.get('object_type') == 'user':
        suffix = 'manage_users'
    if data_dict.get('object_type') == 'group':
        group = model.Group.get(data_dict.get('object', None))
        suffix = 'manage_groups'
        if group and group.is_organization:
            suffix = 'manage_organizations'
    permission = '{prefix}_{suffix}'.format(prefix=prefix, suffix=suffix)
    authorized = authz.has_user_permission_for_group_or_org(group.id, user, permission)
    if not authorized:
        return {'success': False,
                'msg': _('User %s not authorized to edit group %s') % (str(user), group.id)}
    else:
        return {'success': True}


def api_token_create(context, data_dict):
    """Create new token for current user.
    """
    user = context['model'].User.get(data_dict['user'])
    return {'success': user.name == context['user']}



def package_collaborator_create(context, data_dict):
    '''Checks if a user is allowed to add collaborators to a dataset

    See :py:func:`~ckan.authz.can_manage_collaborators` for details
    '''
    user = context['user']
    model = context['model']

    pkg = model.Package.get(data_dict['id'])
    user_obj = model.User.get(user)

    if not authz.has_user_permission_for_package(pkg.id, user_obj.id, 'package_manage_users'):
        return {
            'success': False,
            'msg': _('User %s not authorized to add collaborators to this dataset') % user}

    return {'success': True}
