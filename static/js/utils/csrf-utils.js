// CSRF token utilities
export const csrfUtils = {
    getToken: () => {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    },

    setupAjaxHeaders: () => {
        const token = csrfUtils.getToken();
        return {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': token
        };
    }
};