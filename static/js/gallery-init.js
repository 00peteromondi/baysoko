/* gallery-init.js
 * Lightweight gallery initializer for storefront/listing pages
 * - Finds .gallery elements and wires main slides + thumbnails
 * - Supports next/prev buttons, thumbnail click, keyboard left/right and basic touch swipe
 */

document.addEventListener('DOMContentLoaded', function () {
  function initGallery(galleryEl) {
    const slides = Array.from(galleryEl.querySelectorAll('.gallery-slide'));
    const thumbs = Array.from(galleryEl.querySelectorAll('.gallery-thumb'));
    const prevBtn = galleryEl.querySelector('.gallery-prev');
    const nextBtn = galleryEl.querySelector('.gallery-next');

    if (!slides.length) return;

    let current = 0;

    function show(index) {
      if (index < 0) index = slides.length - 1;
      if (index >= slides.length) index = 0;
      slides.forEach((s, i) => {
        s.classList.toggle('active', i === index);
        // lazy-load data-src
        if (i === index && s.dataset && s.dataset.src && !s.src) {
          s.src = s.dataset.src;
        }
      });
      thumbs.forEach((t, i) => t.classList.toggle('selected', i === index));
      current = index;
    }

    show(0);

    if (prevBtn) prevBtn.addEventListener('click', () => show(current - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => show(current + 1));

    thumbs.forEach((thumb, idx) => {
      thumb.addEventListener('click', () => show(idx));
    });

    // keyboard navigation
    galleryEl.tabIndex = galleryEl.tabIndex || 0;
    galleryEl.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') show(current - 1);
      if (e.key === 'ArrowRight') show(current + 1);
    });

    // touch swipe
    let startX = 0;
    let isTouch = false;
    galleryEl.addEventListener('touchstart', function (e) {
      isTouch = true;
      startX = e.touches[0].clientX;
    }, { passive: true });

    galleryEl.addEventListener('touchend', function (e) {
      if (!isTouch) return;
      const dx = (e.changedTouches[0].clientX - startX);
      if (Math.abs(dx) > 40) {
        if (dx < 0) show(current + 1); else show(current - 1);
      }
      isTouch = false;
    });
  }

  // Initialize all galleries on the page
  const galleries = document.querySelectorAll('.gallery');
  galleries.forEach(initGallery);
});
// Main initialization file
import { imageUtils } from './utils/image-utils.js';
import { favoriteUtils } from './utils/favorite-utils.js';
import { galleryUtils } from './utils/gallery-utils.js';

// Initialize all utilities when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Setup image handling
    imageUtils.setupLazyLoading(document);
    
    // Setup favorite functionality
    favoriteUtils.setupFavoriteButtons(document);
    
    // Setup gallery if on detail page
    if (document.querySelector('.listing-gallery-container')) {
        galleryUtils.setupGallery(document);
    }
});