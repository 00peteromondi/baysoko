// Handles the listings grid functionality including filtering, sorting, and pagination
import { csrfUtils } from './utils/csrf-utils.js';
import { imageUtils } from './utils/image-utils.js';

export const listingsUtils = {
    // Debounce function to limit API calls
    debounce: (func, wait) => {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Get all filter values
    getFilterValues: () => {
        return {
            q: document.getElementById('search')?.value,
            category: document.getElementById('category')?.value,
            location: document.getElementById('location')?.value,
            min_price: document.getElementById('min_price')?.value,
            max_price: document.getElementById('max_price')?.value,
            sort_by: document.getElementById('sort-by')?.value || 'newest',
            page: window.currentPage || 1
        };
    },

    // Update listings via AJAX
    updateListings: async () => {
        const listingsContainer = document.getElementById('listings-container');
        const loadingOverlay = document.getElementById('loading-overlay');
        const resultsCount = document.getElementById('results-count');
        
        if (!listingsContainer || window.isLoading) return;

        window.isLoading = true;
        if (loadingOverlay) loadingOverlay.style.display = 'flex';
        if (listingsContainer) listingsContainer.style.opacity = '0.5';

        try {
            // Get filter values and build query string
            const filters = listingsUtils.getFilterValues();
            const params = new URLSearchParams();
            for (const [key, value] of Object.entries(filters)) {
                if (value && value !== 'all') {
                    params.append(key, value);
                }
            }

            // Make AJAX request
            const response = await fetch(`${window.location.pathname}?${params.toString()}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    ...csrfUtils.setupAjaxHeaders()
                }
            });

            if (!response.ok) throw new Error('Network response was not ok');

            const data = await response.json();
            listingsUtils.renderListings(data.listings);
            listingsUtils.updatePagination(data);
            
            if (resultsCount) {
                resultsCount.textContent = `${data.total_count} results found`;
            }

            // Update URL without reloading page
            const newUrl = `${window.location.pathname}?${params.toString()}`;
            window.history.replaceState({}, '', newUrl);

            // Update active filters display
            listingsUtils.updateActiveFilters(filters);

        } catch (error) {
            console.error('Error:', error);
            if (listingsContainer) {
                listingsContainer.innerHTML = `
                    <div class="col-12">
                        <div class="no-results">
                            <i class="bi bi-exclamation-triangle display-1 text-muted"></i>
                            <h4 class="mt-3">Error loading listings</h4>
                            <p class="text-muted">Please try again later.</p>
                            <button onclick="location.reload()" class="btn btn-primary">Reload Page</button>
                        </div>
                    </div>
                `;
            }
        } finally {
            window.isLoading = false;
            if (loadingOverlay) loadingOverlay.style.display = 'none';
            if (listingsContainer) listingsContainer.style.opacity = '1';
        }
    },

    // Initialize listings page functionality
    init: () => {
        // Set up filter event listeners
        const searchInput = document.getElementById('search');
        const categorySelect = document.getElementById('category');
        const locationSelect = document.getElementById('location');
        const minPriceInput = document.getElementById('min_price');
        const maxPriceInput = document.getElementById('max_price');
        const sortSelect = document.getElementById('sort-by');
        const applyFiltersBtn = document.getElementById('apply-filters');
        const resetFiltersBtn = document.getElementById('reset-filters');

        // Price chip handling
        document.querySelectorAll('.price-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const min = chip.dataset.min;
                const max = chip.dataset.max;
                
                if (minPriceInput) minPriceInput.value = min;
                if (maxPriceInput) maxPriceInput.value = max || '';
                
                window.currentPage = 1;
                listingsUtils.updateListings();
            });
        });

        // Filter input event listeners
        if (searchInput) {
            searchInput.addEventListener('input', listingsUtils.debounce(() => {
                window.currentPage = 1;
                listingsUtils.updateListings();
            }, 500));
        }

        if (categorySelect) {
            categorySelect.addEventListener('change', () => {
                window.currentPage = 1;
                listingsUtils.updateListings();
            });
        }

        if (locationSelect) {
            locationSelect.addEventListener('change', () => {
                window.currentPage = 1;
                listingsUtils.updateListings();
            });
        }

        if (minPriceInput) {
            minPriceInput.addEventListener('input', listingsUtils.debounce(() => {
                window.currentPage = 1;
                listingsUtils.updateListings();
            }, 500));
        }

        if (maxPriceInput) {
            maxPriceInput.addEventListener('input', listingsUtils.debounce(() => {
                window.currentPage = 1;
                listingsUtils.updateListings();
            }, 500));
        }

        if (sortSelect) {
            sortSelect.addEventListener('change', () => {
                window.currentPage = 1;
                listingsUtils.updateListings();
            });
        }

        if (applyFiltersBtn) {
            applyFiltersBtn.addEventListener('click', () => {
                window.currentPage = 1;
                listingsUtils.updateListings();
            });
        }

        if (resetFiltersBtn) {
            resetFiltersBtn.addEventListener('click', listingsUtils.resetAllFilters);
        }

        // Initialize Swiper if available
        if (typeof Swiper !== 'undefined') {
            new Swiper(".featuredSwiper", {
                slidesPerView: 1,
                spaceBetween: 20,
                navigation: {
                    nextEl: ".swiper-button-next",
                    prevEl: ".swiper-button-prev",
                },
                breakpoints: {
                    640: { slidesPerView: 2 },
                    768: { slidesPerView: 3 },
                    1024: { slidesPerView: 4 },
                },
            });
        }
    },

    // Reset all filters
    resetAllFilters: () => {
        const elements = {
            search: document.getElementById('search'),
            category: document.getElementById('category'),
            location: document.getElementById('location'),
            min_price: document.getElementById('min_price'),
            max_price: document.getElementById('max_price'),
            sort_by: document.getElementById('sort-by')
        };

        // Reset form values
        if (elements.search) elements.search.value = '';
        if (elements.category) elements.category.value = 'all';
        if (elements.location) elements.location.value = 'all';
        if (elements.min_price) elements.min_price.value = '';
        if (elements.max_price) elements.max_price.value = '';
        if (elements.sort_by) elements.sort_by.value = 'newest';

        window.currentPage = 1;
        listingsUtils.updateListings();
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', listingsUtils.init);