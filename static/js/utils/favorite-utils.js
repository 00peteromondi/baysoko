// Favorite functionality
import { csrfUtils } from './csrf-utils.js';

export const favoriteUtils = {
    setupFavoriteButtons: (container) => {
        container.querySelectorAll('.favorite-form').forEach(form => {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const button = form.querySelector('button');
                const icon = button.querySelector('i');

                // Add click animation
                button.style.transform = 'scale(0.95)';

                fetch(form.action, {
                    method: 'POST',
                    headers: csrfUtils.setupAjaxHeaders()
                })
                .then(response => response.json())
                .then(data => {
                    // Reset animation
                    setTimeout(() => {
                        button.style.transform = 'scale(1)';
                    }, 150);

                    if (data.is_favorited) {
                        button.classList.remove('secondary');
                        button.classList.add('primary', 'favorited');
                        icon.classList.remove('bi-heart');
                        icon.classList.add('bi-heart-fill');
                        if (data.favorite_count) {
                            button.innerHTML = `<i class="bi bi-heart-fill"></i> Liked (${data.favorite_count})`;
                        }
                    } else {
                        button.classList.remove('primary', 'favorited');
                        button.classList.add('secondary');
                        icon.classList.remove('bi-heart-fill');
                        icon.classList.add('bi-heart');
                        if (data.favorite_count) {
                            button.innerHTML = `<i class="bi bi-heart"></i> Like (${data.favorite_count})`;
                        }
                    }
                })
                .catch(error => console.error('Error:', error));
            });
        });
    }
};