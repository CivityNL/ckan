# encoding: utf-8

'''API functions for partial updates of existing data in CKAN'''

from ckan.logic import (
    get_action as _get_action,
    check_access as _check_access,
    get_or_bust as _get_or_bust,
)


def package_patch(context, data_dict):
    '''Patch a dataset (package).

    :param id: the id or name of the dataset
    :type id: string

    The difference between the update and patch methods is that the patch will
    perform an update of the provided parameters, while leaving all other
    parameters unchanged, whereas the update methods deletes all parameters
    not explicitly provided in the data_dict.

    You are able to partially update and/or create resources with
    package_patch. If you are updating existing resources be sure to provide
    the resource id. Existing resources excluded from the package_patch
    data_dict will be removed. Resources in the package data_dict without
    an id will be treated as new resources and will be added. New resources
    added with the patch method do not create the default views.

    You must be authorized to edit the dataset and the groups that it belongs
    to.
    '''
    _check_access('package_patch', context, data_dict)

    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
        'ignore_auth': context.get('ignore_auth', False),
        'for_update': True,
    }

    # CIVDEV-1062 required the package_patch to also treat the given resources
    # as patches instead of replacing the resources with (mostly incomplete) ones.

    package_dict = _get_action('package_show')(
        show_context,
        {'id': _get_or_bust(data_dict, 'id')})

    patched_package = dict(package_dict)

    # if resources are given we want to also patch those if an original resource
    # with the same `id` already exists and add these patched resources to the package
    if "resources" in data_dict:
        original_resources = package_dict.pop("resources", [])
        patched_resources = data_dict.pop("resources", [])
        for idx, patched_res in enumerate(patched_resources):
            for original_res in original_resources:
                if original_res.get("id") == patched_res.get("id", None):
                    patched_resources[idx] = dict(original_res, **patched_res)
                    break
        patched_package['resources'] = patched_resources

    patched_package.update(data_dict)
    patched_package['id'] = package_dict['id']

    return _get_action('package_update')(context, patched_package)


def resource_patch(context, data_dict):
    '''Patch a resource

    :param id: the id of the resource
    :type id: string

    The difference between the update and patch methods is that the patch will
    perform an update of the provided parameters, while leaving all other
    parameters unchanged, whereas the update methods deletes all parameters
    not explicitly provided in the data_dict
    '''
    _check_access('resource_patch', context, data_dict)

    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
        'for_update': True,
    }

    resource_dict = _get_action('resource_show')(
        show_context,
        {'id': _get_or_bust(data_dict, 'id')})

    patched = dict(resource_dict)
    patched.update(data_dict)
    return _get_action('resource_update')(context, patched)


def group_patch(context, data_dict):
    '''Patch a group

    :param id: the id or name of the group
    :type id: string

    The difference between the update and patch methods is that the patch will
    perform an update of the provided parameters, while leaving all other
    parameters unchanged, whereas the update methods deletes all parameters
    not explicitly provided in the data_dict
    '''
    _check_access('group_patch', context, data_dict)

    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }

    group_dict = _get_action('group_show')(
        show_context,
        {'id': _get_or_bust(data_dict, 'id')})

    patched = dict(group_dict)
    patched.pop('display_name', None)
    patched.update(data_dict)

    patch_context = context.copy()
    patch_context['allow_partial_update'] = True
    return _get_action('group_update')(patch_context, patched)


def organization_patch(context, data_dict):
    '''Patch an organization

    :param id: the id or name of the organization
    :type id: string

    The difference between the update and patch methods is that the patch will
    perform an update of the provided parameters, while leaving all other
    parameters unchanged, whereas the update methods deletes all parameters
    not explicitly provided in the data_dict
    '''
    _check_access('organization_patch', context, data_dict)

    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }

    organization_dict = _get_action('organization_show')(
        show_context,
        {'id': _get_or_bust(data_dict, 'id')})

    patched = dict(organization_dict)
    patched.pop('display_name', None)
    patched.update(data_dict)

    patch_context = context.copy()
    patch_context['allow_partial_update'] = True
    return _get_action('organization_update')(patch_context, patched)


def user_patch(context, data_dict):
    '''Patch a user
    :param id: the id or name of the user
    :type id: string
    The difference between the update and patch methods is that the patch will
    perform an update of the provided parameters, while leaving all other
    parameters unchanged, whereas the update methods deletes all parameters
    not explicitly provided in the data_dict
    '''
    _check_access('user_patch', context, data_dict)

    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }

    user_dict = _get_action('user_show')(
        show_context,
        {'id': _get_or_bust(data_dict, 'id')})

    patched = dict(user_dict)
    patched.pop('display_name', None)
    patched.update(data_dict)
    return _get_action('user_update')(context, patched)
