// Delivery Management System JavaScript

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Copy to clipboard function
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copied to clipboard!', 'success');
    }).catch(function(err) {
        showToast('Failed to copy: ' + err, 'error');
    });
}

// Show toast notification
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.id = toastId;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Show toast
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove toast after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

// Update delivery status
function updateDeliveryStatus(deliveryId, status, notes = '') {
    const formData = new FormData();
    formData.append('status', status);
    if (notes) formData.append('notes', notes);
    
    fetch(`/delivery/deliveries/${deliveryId}/update-status/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Status updated successfully', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    });
}

// Get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Auto-refresh for tracking pages
function startAutoRefresh(interval = 30000) {
    if (window.location.pathname.includes('/track/')) {
        setInterval(() => {
            fetch(window.location.href)
                .then(response => response.text())
                .then(html => {
                    // Update only specific parts of the page
                    const parser = new DOMParser();
                    const newDoc = parser.parseFromString(html, 'text/html');
                    const timeline = newDoc.querySelector('.timeline');
                    if (timeline) {
                        document.querySelector('.timeline').innerHTML = timeline.innerHTML;
                    }
                });
        }, interval);
    }
}

// Initialize auto-refresh
document.addEventListener('DOMContentLoaded', startAutoRefresh);

// Location services
function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation not supported'));
            return;
        }
        
        navigator.geolocation.getCurrentPosition(
            position => {
                resolve({
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    accuracy: position.coords.accuracy
                });
            },
            error => {
                reject(error);
            },
            {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            }
        );
    });
}

// Distance calculator
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// Format distance
function formatDistance(km) {
    if (km < 1) {
        return Math.round(km * 1000) + ' m';
    }
    return km.toFixed(1) + ' km';
}

// Format time
function formatTime(minutes) {
    if (minutes < 60) {
        return minutes + ' min';
    }
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours + 'h ' + (mins > 0 ? mins + 'm' : '');
}

// Search deliveries
function searchDeliveries(query) {
    const table = document.querySelector('.table-delivery tbody');
    const rows = table.querySelectorAll('tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(query.toLowerCase())) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Initialize search
const searchInput = document.getElementById('deliverySearch');
if (searchInput) {
    searchInput.addEventListener('input', function() {
        searchDeliveries(this.value);
    });
}

// Export functions
window.deliveryUtils = {
    copyToClipboard,
    showToast,
    updateDeliveryStatus,
    getCurrentLocation,
    calculateDistance,
    formatDistance,
    formatTime,
    searchDeliveries
};