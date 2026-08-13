// Image handling utilities
export const imageUtils = {
    // Set up fallback image handling
    setupImageFallback: (img, placeholder = '/static/images/placeholder.jpg') => {
        img.onerror = () => {
            img.onerror = null;
            img.src = placeholder;
            img.classList.add('placeholder-img');
        };
    },

    // Enable lazy loading with placeholder fallback
    setupLazyLoading: (container) => {
        const images = container.querySelectorAll('img[data-src]');
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    imageUtils.setupImageFallback(img);
                    imageObserver.unobserve(img);
                }
            });
        });
        images.forEach(img => imageObserver.observe(img));
    }
};