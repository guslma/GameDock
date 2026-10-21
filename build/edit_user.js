    // GameDock: edit an existing user
    let editingUserId = null;
    const EDIT_USER_ERRORS = {
        not_found: 'This user no longer exists.',
        environment_user: 'This user is set by the USER_ADMIN or USER_GUEST variables of the container, which recreate it at every start. Change it there.',
        user_exists: 'User already exists',
        last_admin: 'Keep at least one admin account.',
    };

    function openEditUser(id) {
        const user = (allUsers || []).find(u => u.id === id);
        if (!user) {
            return;
        }
        editingUserId = id;
        $('#inputEditUser').val(user.user);
        $('#inputEditUserPassword').val('');
        $('#checkboxEditUserShopAccess').prop('checked', !!user.shop_access);
        $('#checkboxEditUserBackupAccess').prop('checked', !!user.backup_access);
        $('#checkboxEditUserAdminAccess').prop('checked', !!user.admin_access);
        syncEditUserAccess();
        $('#editUserError').addClass('d-none').text('');
        bootstrap.Modal.getOrCreateInstance(document.getElementById('editUserModal')).show();
    }

    // Admins always have shop and backup access, as in the new user form
    function syncEditUserAccess() {
        const admin = $('#checkboxEditUserAdminAccess').prop('checked');
        if (admin) {
            $('#checkboxEditUserShopAccess').prop('checked', true);
            $('#checkboxEditUserBackupAccess').prop('checked', true);
        }
        $('#checkboxEditUserShopAccess').prop('disabled', admin);
        $('#checkboxEditUserBackupAccess').prop('disabled', admin);
    }
    $('#checkboxEditUserAdminAccess').change(syncEditUserAccess);

    function showEditUserError(message) {
        $('#editUserError').removeClass('d-none').text(message);
    }

    function saveEditUser() {
        const user = $('#inputEditUser').val().trim();
        const password = $('#inputEditUserPassword').val();
        const usernameValidation = validateUsername(user);
        if (!usernameValidation.isValid) {
            showEditUserError(usernameValidation.message);
            return;
        }
        if (allUsers.some(u => u.user === user && u.id !== editingUserId)) {
            showEditUserError('User already exists');
            return;
        }
        if (password) {
            const passwordValidation = validatePassword(password);
            if (!passwordValidation.isValid) {
                showEditUserError(passwordValidation.message);
                return;
            }
        }
        $.ajax({
            url: '/api/user/update',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                user_id: editingUserId,
                user: user,
                password: password,
                shop_access: $('#checkboxEditUserShopAccess').prop('checked'),
                backup_access: $('#checkboxEditUserBackupAccess').prop('checked'),
                admin_access: $('#checkboxEditUserAdminAccess').prop('checked'),
            }),
            success: function (result) {
                if (result.success) {
                    bootstrap.Modal.getOrCreateInstance(document.getElementById('editUserModal')).hide();
                    fillUserTable();
                } else {
                    showEditUserError(EDIT_USER_ERRORS[result.error] || result.message || result.error);
                }
            },
            error: function () {
                showEditUserError('Could not save the user. Please try again.');
            }
        });
    }

