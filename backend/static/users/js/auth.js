(() => {
    'use strict';

    const form = document.getElementById('auth-form');
    if (!form) {
        return;
    }

    const alertBox = document.getElementById('form-alert');
    const submitButton = document.getElementById('submit-button');
    const buttonLabel = submitButton?.querySelector('.button-label');
    const buttonSpinner = submitButton?.querySelector('.button-spinner');
    const mode = form.dataset.mode;
    const successDialog = document.getElementById('registration-success');
    const continueToLogin = document.getElementById('continue-to-login');
    let loginRedirectUrl = '/login/';

    function getCookie(name) {
        const match = document.cookie.match(
            new RegExp(`(?:^|; )${name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1')}=([^;]*)`)
        );
        return match ? decodeURIComponent(match[1]) : null;
    }

    function setLoading(isLoading) {
        if (!submitButton || !buttonLabel || !buttonSpinner) {
            return;
        }
        submitButton.disabled = isLoading;
        buttonSpinner.hidden = !isLoading;
        buttonLabel.textContent = isLoading
            ? (mode === 'register' ? 'Creating account…' : 'Signing in…')
            : (mode === 'register' ? 'Create account' : 'Sign in');
    }

    function clearFieldErrors() {
        form.querySelectorAll('.field__error').forEach((node) => {
            node.hidden = true;
            node.textContent = '';
        });
        form.querySelectorAll('input.is-invalid').forEach((input) => {
            input.classList.remove('is-invalid');
            input.removeAttribute('aria-invalid');
        });
    }

    function showAlert(message, type) {
        if (!alertBox) {
            return;
        }
        alertBox.hidden = false;
        alertBox.className = `alert alert--${type}`;
        alertBox.textContent = message;
    }

    function hideAlert() {
        if (!alertBox) {
            return;
        }
        alertBox.hidden = true;
        alertBox.textContent = '';
        alertBox.className = 'alert';
    }

    function firstErrorMessage(value) {
        if (Array.isArray(value)) {
            return value[0];
        }
        if (value && typeof value === 'object') {
            const nested = Object.values(value)[0];
            return firstErrorMessage(nested);
        }
        return typeof value === 'string' ? value : 'Something went wrong. Please try again.';
    }

    function applyFieldErrors(errors) {
        Object.entries(errors).forEach(([field, messages]) => {
            if (field === 'detail' || field === 'non_field_errors') {
                return;
            }
            const input = form.querySelector(`[name="${field}"]`);
            const errorNode = document.getElementById(`${field}-error`);
            const message = firstErrorMessage(messages);
            if (input) {
                input.classList.add('is-invalid');
                input.setAttribute('aria-invalid', 'true');
            }
            if (errorNode) {
                errorNode.hidden = false;
                errorNode.textContent = message;
            }
        });
    }

    function showLoginSuccess(payload) {
        const card = form.closest('.auth-card');
        if (!card) {
            return;
        }

        const username = payload?.user?.username || 'there';
        const redirectUrl = payload?.redirect_url || '/library/';
        form.hidden = true;
        showAlert(payload.detail || 'Signed in successfully.', 'success');

        let panel = card.querySelector('.success-panel');
        if (!panel) {
            panel = document.createElement('div');
            panel.className = 'success-panel';
            const heading = document.createElement('strong');
            const description = document.createElement('p');
            heading.textContent = `Welcome, ${username}.`;
            description.textContent =
                'Opening your library…';
            panel.append(heading, description);
            form.insertAdjacentElement('afterend', panel);
        }

        window.setTimeout(() => {
            window.location.assign(redirectUrl);
        }, 700);
    }

    document.querySelectorAll('.toggle-password').forEach((button) => {
        button.addEventListener('click', () => {
            const input = document.getElementById(button.dataset.target);
            if (!input) {
                return;
            }
            const showing = input.type === 'text';
            input.type = showing ? 'password' : 'text';
            const label = button.querySelector('span');
            if (label) {
                label.textContent = showing ? 'Show' : 'Hide';
            }
            button.setAttribute(
                'aria-label',
                showing ? 'Show password' : 'Hide password'
            );
        });
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearFieldErrors();
        hideAlert();
        setLoading(true);

        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());
        delete payload.csrfmiddlewaretoken;

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') || '',
                    Accept: 'application/json',
                },
                body: JSON.stringify(payload),
            });

            let data = {};
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                data = await response.json();
            }

            if (response.ok) {
                if (mode === 'register') {
                    loginRedirectUrl = data.redirect_url || '/login/';
                    form.reset();
                    if (successDialog?.showModal) {
                        successDialog.showModal();
                        continueToLogin?.focus();
                    } else {
                        showAlert(data.detail || 'Account created successfully.', 'success');
                        window.location.assign(loginRedirectUrl);
                    }
                    return;
                }

                showLoginSuccess(data);
                return;
            }

            if (data && typeof data === 'object') {
                applyFieldErrors(data);
                const detail = data.detail || data.non_field_errors;
                showAlert(
                    firstErrorMessage(detail || Object.values(data)[0] || 'Please fix the highlighted fields.'),
                    'error'
                );
            } else {
                showAlert('Unable to complete the request. Please try again.', 'error');
            }
        } catch (_error) {
            showAlert('Network error. Check your connection and try again.', 'error');
        } finally {
            if (!(mode === 'register' && alertBox && !alertBox.hidden && alertBox.classList.contains('alert--success'))) {
                setLoading(false);
            }
        }
    });

    continueToLogin?.addEventListener('click', () => {
        window.location.assign(loginRedirectUrl);
    });

    successDialog?.addEventListener('cancel', (event) => {
        event.preventDefault();
    });

    // Prefill success message when arriving from registration.
    const params = new URLSearchParams(window.location.search);
    if (mode === 'login' && params.get('registered') === '1') {
        showAlert('Account created successfully. Please sign in.', 'success');
    }
})();
