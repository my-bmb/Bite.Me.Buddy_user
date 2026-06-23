// main.js - Complete JavaScript with all features including live chat, group video call, and call notifications

// ============================================
// ✅ PASSWORD VISIBILITY TOGGLE
// ============================================

// Toggle password visibility
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const icon = input.nextElementSibling?.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        if (icon) {
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        }
    } else {
        input.type = 'password';
        if (icon) {
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    }
}

// ============================================
// ✅ GEOLOCATION
// ============================================

// Get user's current location
function getCurrentLocation(callback) {
    if (!navigator.geolocation) {
        alert('Geolocation is not supported by your browser');
        return;
    }
    
    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            
            try {
                // Try to get address from coordinates
                const response = await fetch(
                    `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`
                );
                const data = await response.json();
                
                if (data && data.display_name) {
                    callback(data.display_name);
                } else {
                    callback(`${lat.toFixed(6)}, ${lon.toFixed(6)}`);
                }
            } catch (error) {
                // Fallback to coordinates
                callback(`${lat.toFixed(6)}, ${lon.toFixed(6)}`);
            }
        },
        (error) => {
            let message = 'Unable to retrieve your location. ';
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    message += 'Permission denied. Please enable location access in your browser settings.';
                    break;
                case error.POSITION_UNAVAILABLE:
                    message += 'Location information is unavailable.';
                    break;
                case error.TIMEOUT:
                    message += 'The request to get your location timed out.';
                    break;
                default:
                    message += 'An unknown error occurred.';
            }
            alert(message);
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
    );
}

// ============================================
// ✅ FORMATTING FUNCTIONS
// ============================================

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2
    }).format(amount);
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Format time (IST)
function formatISTTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
        timeZone: 'Asia/Kolkata'
    });
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

// ============================================
// ✅ LOADING STATE
// ============================================

// Show loading state
function showLoading(element) {
    if (!element) return;
    element.classList.add('loading');
    element.setAttribute('disabled', true);
    element.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Loading...`;
}

function hideLoading(element) {
    if (!element) return;
    element.classList.remove('loading');
    element.removeAttribute('disabled');
}

// ============================================
// ✅ VALIDATION FUNCTIONS
// ============================================

// Validate email
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Validate phone number (Indian format)
function isValidPhone(phone) {
    const re = /^[6-9]\d{9}$/;
    return re.test(phone);
}

// Validate password strength
function isStrongPassword(password) {
    return password.length >= 8 && 
           /[a-z]/.test(password) && 
           /[A-Z]/.test(password) && 
           /[0-9]/.test(password) &&
           /[!@#$%^&*(),.?":{}|<>]/.test(password);
}

// ============================================
// ✅ NOTIFICATION SYSTEM
// ============================================

// Show notification/toast
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const icon = icons[type] || icons.info;
    const colors = {
        success: '#48bb78',
        error: '#f56565',
        warning: '#ed8936',
        info: '#4299e1'
    };
    const color = colors[type] || colors.info;
    
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${icon}" style="color: ${color};"></i>
            <span>${message}</span>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }
    }, 5000);
}

// Add notification styles if not present
if (!document.querySelector('#notification-styles')) {
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            max-width: 450px;
            z-index: 10000;
            animation: slideInRight 0.3s ease;
            border-left: 4px solid #4299e1;
        }
        
        .notification-success { border-left-color: #48bb78; }
        .notification-error { border-left-color: #f56565; }
        .notification-warning { border-left-color: #ed8936; }
        .notification-info { border-left-color: #4299e1; }
        
        .notification-content {
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
        }
        
        .notification-content i {
            font-size: 20px;
        }
        
        .notification-close {
            background: none;
            border: none;
            color: #a0aec0;
            cursor: pointer;
            font-size: 16px;
            padding: 4px;
            transition: color 0.2s;
        }
        
        .notification-close:hover {
            color: #718096;
        }
        
        @keyframes slideInRight {
            from {
                opacity: 0;
                transform: translateX(100%);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        @media (max-width: 768px) {
            .notification {
                left: 16px;
                right: 16px;
                max-width: none;
            }
        }
    `;
    document.head.appendChild(style);
}

// ============================================
// ✅ UTILITY FUNCTIONS
// ============================================

// Debounce function for search/resize events
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Escape HTML to prevent XSS
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Truncate text
function truncateText(text, maxLength = 100) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// ============================================
// ✅ NAVIGATION
// ============================================

// Handle responsive navigation
function initResponsiveNav() {
    const nav = document.querySelector('.bottom-nav');
    if (!nav) return;
    
    // Add active class based on current URL
    const currentPath = window.location.pathname;
    const navItems = nav.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPath || 
            (href !== '#' && currentPath.startsWith(href) && href !== '/')) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// ============================================
// ✅ FILE UPLOAD PREVIEW
// ============================================

// Preview image before upload
function previewImage(input, previewElementId) {
    const preview = document.getElementById(previewElementId);
    if (!preview) return;
    
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// ============================================
// ✅ CART FUNCTIONS
// ============================================

// Update cart count
function updateCartCount() {
    fetch('/api/cart/count')
        .then(response => response.json())
        .then(data => {
            const cartBadge = document.getElementById('cart-badge');
            if (cartBadge) {
                if (data.count > 0) {
                    cartBadge.textContent = data.count;
                    cartBadge.style.display = 'inline';
                } else {
                    cartBadge.style.display = 'none';
                }
            }
        })
        .catch(error => console.error('Error updating cart count:', error));
}

// ============================================
// ✅ LIVE CHAT FUNCTIONS
// ============================================

// Scroll to bottom of chat
function scrollToBottom(element) {
    if (!element) return;
    element.scrollTop = element.scrollHeight;
}

// Auto-resize textarea
function autoResize(textarea) {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

// ============================================
// ✅ GROUP VIDEO CALL FUNCTIONS
// ============================================

let groupCallActive = false;
let localStream = null;
let peerConnections = {};

// Toggle local video
function toggleLocalVideo() {
    if (!localStream) return;
    const videoTrack = localStream.getVideoTracks()[0];
    if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled;
        const icon = document.getElementById('video-toggle-icon');
        if (icon) {
            icon.className = videoTrack.enabled ? 'fas fa-video' : 'fas fa-video-slash';
        }
    }
}

// Toggle local audio
function toggleLocalAudio() {
    if (!localStream) return;
    const audioTrack = localStream.getAudioTracks()[0];
    if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        const icon = document.getElementById('audio-toggle-icon');
        if (icon) {
            icon.className = audioTrack.enabled ? 'fas fa-microphone' : 'fas fa-microphone-slash';
        }
    }
}

// ============================================
// ✅ CALL NOTIFICATIONS (From call-notification.js)
// ============================================

let callNotificationActive = false;
let currentCallData = null;
let notificationTimeout = null;

function showCallNotification(callerId, callerName, callType, offer) {
    // Don't show if already on call page
    const isOnCallPage = window.location.pathname.includes('/audio-call/') || 
                         window.location.pathname.includes('/video-call/');
    if (isOnCallPage) return;
    
    // Don't show duplicate notifications
    if (callNotificationActive) return;
    
    callNotificationActive = true;
    currentCallData = { callerId, callerName, callType, offer };

    // Remove existing notification if any
    let notifDiv = document.getElementById('global-call-notification');
    if (notifDiv) notifDiv.remove();

    // Create new notification
    notifDiv = document.createElement('div');
    notifDiv.id = 'global-call-notification';
    notifDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        left: auto;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        border-radius: 16px;
        padding: 16px 20px;
        z-index: 10001;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        gap: 16px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        min-width: 280px;
        max-width: 350px;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.15);
        animation: slideInRight 0.3s ease-out;
        cursor: pointer;
    `;
    
    // Add animation styles if not present
    if (!document.querySelector('#call-notification-styles')) {
        const style = document.createElement('style');
        style.id = 'call-notification-styles';
        style.textContent = `
            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes ring {
                0% { transform: rotate(0); }
                25% { transform: rotate(10deg); }
                50% { transform: rotate(-10deg); }
                75% { transform: rotate(5deg); }
                100% { transform: rotate(0); }
            }
            .call-avatar {
                width: 48px;
                height: 48px;
                background: linear-gradient(135deg, #00b4db, #0083b0);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                animation: ring 1s infinite;
                flex-shrink: 0;
            }
            .call-info {
                flex: 1;
                min-width: 0;
            }
            .caller-name {
                font-weight: 600;
                font-size: 16px;
                margin-bottom: 4px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .call-type {
                font-size: 12px;
                opacity: 0.8;
                display: flex;
                align-items: center;
                gap: 4px;
            }
            .call-buttons {
                display: flex;
                gap: 10px;
                flex-shrink: 0;
            }
            .accept-btn, .reject-btn {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                border: none;
                cursor: pointer;
                transition: transform 0.2s, opacity 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
            }
            .accept-btn {
                background: linear-gradient(135deg, #00b09b, #96c93d);
                color: white;
            }
            .reject-btn {
                background: linear-gradient(135deg, #cb356b, #bd3f32);
                color: white;
            }
            .accept-btn:hover, .reject-btn:hover {
                transform: scale(1.05);
            }
            .accept-btn:active, .reject-btn:active {
                transform: scale(0.95);
            }
            @media (max-width: 480px) {
                .call-avatar { width: 40px; height: 40px; font-size: 20px; }
                .accept-btn, .reject-btn { width: 36px; height: 36px; font-size: 16px; }
                .caller-name { font-size: 14px; }
                .call-type { font-size: 10px; }
                #global-call-notification {
                    left: 16px;
                    right: 16px;
                    min-width: unset;
                    max-width: none;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Get avatar initial
    const initial = callerName ? callerName.charAt(0).toUpperCase() : '?';
    const callTypeIcon = callType === 'audio' ? '📞' : '📹';
    const callTypeText = callType === 'audio' ? 'Audio Call' : 'Video Call';
    
    notifDiv.innerHTML = `
        <div class="call-avatar">
            <span>${escapeHtml(initial)}</span>
        </div>
        <div class="call-info">
            <div class="caller-name">${escapeHtml(callerName)}</div>
            <div class="call-type">
                <span>${callTypeIcon}</span>
                <span>Incoming ${callTypeText}</span>
            </div>
        </div>
        <div class="call-buttons">
            <button class="accept-btn" id="acceptCallNotif" title="Accept">
                <i class="fas fa-phone-alt"></i>
            </button>
            <button class="reject-btn" id="rejectCallNotif" title="Reject">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(notifDiv);
    
    // Auto hide after 30 seconds
    notificationTimeout = setTimeout(() => {
        if (notifDiv) {
            notifDiv.style.display = 'none';
            callNotificationActive = false;
            setTimeout(() => {
                if (notifDiv) notifDiv.remove();
            }, 300);
        }
    }, 30000);
    
    // Accept call handler
    const acceptBtn = document.getElementById('acceptCallNotif');
    if (acceptBtn) {
        acceptBtn.onclick = (e) => {
            e.stopPropagation();
            if (notificationTimeout) clearTimeout(notificationTimeout);
            notifDiv.style.display = 'none';
            callNotificationActive = false;
            sessionStorage.setItem('pendingOffer', JSON.stringify({ callerId, callType, offer }));
            // Small delay to ensure clean navigation
            setTimeout(() => {
                window.location.href = `/${callType}-call/${callerId}?role=receiver`;
            }, 100);
        };
    }
    
    // Reject call handler
    const rejectBtn = document.getElementById('rejectCallNotif');
    if (rejectBtn) {
        rejectBtn.onclick = (e) => {
            e.stopPropagation();
            if (notificationTimeout) clearTimeout(notificationTimeout);
            notifDiv.style.display = 'none';
            callNotificationActive = false;
            if (typeof socket !== 'undefined' && socket.connected) {
                socket.emit('reject_call', { caller_id: callerId });
            }
            setTimeout(() => {
                if (notifDiv) notifDiv.remove();
            }, 300);
        };
    }
    
    // Click anywhere on notification (but not buttons) - can be used to focus
    notifDiv.addEventListener('click', (e) => {
        if (e.target.closest('.accept-btn') || e.target.closest('.reject-btn')) return;
        // Just focus on the notification, don't auto-accept
    });
}

// Initialize socket event listener when socket is available
function initCallNotifications() {
    if (typeof socket !== 'undefined' && socket) {
        // Remove existing listener to avoid duplicates
        socket.off('incoming_call');
        
        socket.on('incoming_call', (data) => {
            console.log('📞 Incoming call from:', data.caller_name);
            showCallNotification(data.caller_id, data.caller_name, data.call_type, data.offer);
        });
        
        console.log('✅ Call notifications initialized');
    } else {
        console.warn('⚠️ Socket not defined, retrying in 1 second...');
        setTimeout(initCallNotifications, 1000);
    }
}

// ============================================
// ✅ INITIALIZATION
// ============================================

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initResponsiveNav();
    
    // Auto-hide flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = '0';
            flash.style.transition = 'opacity 0.3s ease';
            setTimeout(() => {
                if (flash.parentNode) {
                    flash.remove();
                }
            }, 300);
        }, 5000);
    });
    
    // Handle form submissions
    const forms = document.querySelectorAll('form[data-loading="true"]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                showLoading(submitBtn);
            }
        });
    });
    
    // Update cart count
    updateCartCount();
    
    // Auto-resize textareas
    document.querySelectorAll('textarea[data-auto-resize="true"]').forEach(textarea => {
        textarea.addEventListener('input', function() {
            autoResize(this);
        });
    });
    
    // Initialize call notifications
    if (typeof socket !== 'undefined') {
        initCallNotifications();
    }
});

// Handle window resize with debounce
window.addEventListener('resize', debounce(initResponsiveNav, 250));

// Handle before unload - notify server user is leaving
window.addEventListener('beforeunload', function() {
    if (typeof socket !== 'undefined' && socket.connected) {
        socket.emit('leave_live_chat');
    }
});