- membership: `allowed to manage the collaborators of a given dataset` or `allowed to manage users of a organization/group`
- update_dataset: `allowed to update a dataset`
- update: `allowed to update a organization/group`
- read: `allowed to read a organization/group`
- delete: `allowed to delete a organization/group`
- create_dataset: `allowed to create a dataset`
- manage_group: `allowed to manage datasets within a group or organization`

roles_that_cascade_to_sub_groups
* create_dataset_if_not_in_organization
* create_unowned_dataset
* allow_admin_collaborators
* user_create_groups
* user_create_organizations
* allow_dataset_collaborators
* allow_collaborators_to_change_owner_org
* anon_create_dataset
* user_delete_groups
* user_delete_organizations


ROLE_PERMISSIONS = OrderedDict([
    ('admin', ['admin', 'membership']),
    ('editor', ['read', 'delete_dataset', 'create_dataset', 'update_dataset', 'manage_group']),
    ('member', ['read', 'manage_group']),
])










create_user_via_api
create_user_via_web
public_activity_stream_detail
