// Gallery features
import { imageUtils } from './image-utils.js';

export const galleryUtils = {
    setupGallery: (container) => {
        const mainImage = container.querySelector('#main-image');
        const thumbnails = container.querySelectorAll('.thumbnail');
        const currentImageSpan = container.querySelector('#current-image');
        const totalImagesSpan = container.querySelector('#total-images');
        const zoomToggle = container.querySelector('#zoom-toggle');
        const fullscreenToggle = container.querySelector('#fullscreen-toggle');
        const thumbPrev = container.querySelector('#thumb-prev');
        const thumbNext = container.querySelector('#thumb-next');

        let currentImageIndex = 0;
        const images = [];

        // Collect image URLs
        if (mainImage) {
            images.push(mainImage.src);
            thumbnails.forEach((thumb, index) => {
                if (index > 0) images.push(thumb.dataset.image);
            });
        }

        // Update counter
        if (totalImagesSpan) totalImagesSpan.textContent = images.length;

        // Set up image fallbacks
        if (mainImage) {
            imageUtils.setupImageFallback(mainImage);
        }
        thumbnails.forEach(thumb => {
            imageUtils.setupImageFallback(thumb.querySelector('img'));
        });

        // Thumbnail navigation
        if (thumbPrev) {
            thumbPrev.addEventListener('click', () => {
                currentImageIndex = (currentImageIndex - 1 + images.length) % images.length;
                updateMainImage();
            });
        }

        if (thumbNext) {
            thumbNext.addEventListener('click', () => {
                currentImageIndex = (currentImageIndex + 1) % images.length;
                updateMainImage();
            });
        }

        // Thumbnail click handlers
        thumbnails.forEach((thumbnail, index) => {
            thumbnail.addEventListener('click', () => {
                currentImageIndex = index;
                updateMainImage();
            });
        });

        // Update main image and UI
        function updateMainImage() {
            if (!mainImage) return;
            
            mainImage.src = images[currentImageIndex];
            mainImage.dataset.zoom = images[currentImageIndex];
            thumbnails.forEach((t, i) => t.classList.toggle('active', i === currentImageIndex));
            
            if (currentImageSpan) {
                currentImageSpan.textContent = currentImageIndex + 1;
            }
        }

        // Zoom functionality
        if (zoomToggle && mainImage) {
            zoomToggle.addEventListener('click', () => {
                mainImage.classList.toggle('zoomed');
                zoomToggle.innerHTML = mainImage.classList.contains('zoomed') ? 
                    '<i class="bi bi-zoom-out"></i>' : '<i class="bi bi-zoom-in"></i>';
            });
        }

        // Fullscreen functionality
        if (fullscreenToggle) {
            fullscreenToggle.addEventListener('click', () => {
                galleryUtils.openFullscreen(images, currentImageIndex);
            });
        }

        // Keyboard navigation when image is zoomed
        if (mainImage) {
            document.addEventListener('keydown', (e) => {
                if (mainImage.classList.contains('zoomed')) {
                    if (e.key === 'Escape') {
                        mainImage.classList.remove('zoomed');
                        zoomToggle.innerHTML = '<i class="bi bi-zoom-in"></i>';
                    }
                }
            });
        }
    },

    openFullscreen: (images, startIndex) => {
        const fullscreenHTML = `
            <div class="image-fullscreen">
                <button class="fullscreen-close">
                    <i class="bi bi-x-lg"></i>
                </button>
                <img src="${images[startIndex]}" class="fullscreen-image" alt="Fullscreen view">
                <button class="fullscreen-nav fullscreen-prev">
                    <i class="bi bi-chevron-left"></i>
                </button>
                <button class="fullscreen-nav fullscreen-next">
                    <i class="bi bi-chevron-right"></i>
                </button>
                <div class="fullscreen-counter">
                    ${startIndex + 1} / ${images.length}
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', fullscreenHTML);
        galleryUtils.setupFullscreenHandlers(images, startIndex);
    },

    setupFullscreenHandlers: (images, startIndex) => {
        let currentIndex = startIndex;
        const fullscreen = document.querySelector('.image-fullscreen');
        const close = fullscreen.querySelector('.fullscreen-close');
        const prev = fullscreen.querySelector('.fullscreen-prev');
        const next = fullscreen.querySelector('.fullscreen-next');
        const counter = fullscreen.querySelector('.fullscreen-counter');
        const image = fullscreen.querySelector('.fullscreen-image');

        const update = () => {
            image.src = images[currentIndex];
            counter.textContent = `${currentIndex + 1} / ${images.length}`;
        };

        // Setup image fallback
        imageUtils.setupImageFallback(image);

        close.addEventListener('click', () => fullscreen.remove());
        prev.addEventListener('click', () => {
            currentIndex = (currentIndex - 1 + images.length) % images.length;
            update();
        });
        next.addEventListener('click', () => {
            currentIndex = (currentIndex + 1) % images.length;
            update();
        });

        // Keyboard navigation
        document.addEventListener('keydown', function handler(e) {
            if (!document.querySelector('.image-fullscreen')) {
                document.removeEventListener('keydown', handler);
                return;
            }
            if (e.key === 'Escape') fullscreen.remove();
            else if (e.key === 'ArrowLeft') prev.click();
            else if (e.key === 'ArrowRight') next.click();
        });
    }
};