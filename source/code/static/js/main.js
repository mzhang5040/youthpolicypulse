// Custom JavaScript for Flask Web Application

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Add smooth scrolling to anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add loading states to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Processing...';
                submitBtn.disabled = true;
            }
        });
    });

    // DISABLE ALL ANIMATIONS FOR DEBUGGING
    // const observerOptions = {
    //     threshold: 0.1,
    //     rootMargin: '0px 0px -50px 0px'
    // };

    // const observer = new IntersectionObserver(function(entries) {
    //     entries.forEach(entry => {
    //         if (entry.isIntersecting) {
    //             entry.target.style.opacity = '1';
    //             entry.target.style.transform = 'translateY(0)';
    //         }
    //     });
    // }, observerOptions);

    // DISABLE ALL CARD ANIMATIONS
    // document.querySelectorAll('.card:not(.bill-card)').forEach(card => {
    //     card.style.opacity = '0';
    //     card.style.transform = 'translateY(20px)';
    //     card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    //     observer.observe(card);
    // });

    // SIMPLIFIED: Just ensure all elements are visible
    function makeAllVisible() {
        document.querySelectorAll('*').forEach(element => {
            element.style.opacity = '1';
            element.style.visibility = 'visible';
            element.style.display = element.style.display || '';
        });
    }

    // Run immediately and periodically
    makeAllVisible();
    setInterval(makeAllVisible, 500);

    // Add click animation to buttons
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });

    // Add ripple effect CSS
    const style = document.createElement('style');
    style.textContent = `
        .btn {
            position: relative;
            overflow: hidden;
        }
        
        .ripple {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.6);
            transform: scale(0);
            animation: ripple-animation 0.6s linear;
            pointer-events: none;
        }
        
        @keyframes ripple-animation {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);

    // Add keyboard navigation for modals
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                const modal = bootstrap.Modal.getInstance(openModal);
                if (modal) {
                    modal.hide();
                }
            }
        }
    });

    // Add form validation feedback
    const inputs = document.querySelectorAll('input, textarea');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.checkValidity()) {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            } else {
                this.classList.remove('is-valid');
                this.classList.add('is-invalid');
            }
        });
    });

    // Add auto-resize for textareas
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });

    // Add copy-to-clipboard functionality for code blocks
    const codeBlocks = document.querySelectorAll('pre code');
    codeBlocks.forEach(block => {
        const button = document.createElement('button');
        button.className = 'btn btn-sm btn-outline-secondary position-absolute top-0 end-0 m-2';
        button.innerHTML = '<i class="fas fa-copy"></i>';
        button.title = 'Copy to clipboard';
        
        const wrapper = document.createElement('div');
        wrapper.className = 'position-relative';
        wrapper.style.position = 'relative';
        
        block.parentNode.insertBefore(wrapper, block);
        wrapper.appendChild(block);
        wrapper.appendChild(button);
        
        button.addEventListener('click', function() {
            navigator.clipboard.writeText(block.textContent).then(() => {
                button.innerHTML = '<i class="fas fa-check"></i>';
                button.classList.remove('btn-outline-secondary');
                button.classList.add('btn-success');
                
                setTimeout(() => {
                    button.innerHTML = '<i class="fas fa-copy"></i>';
                    button.classList.remove('btn-success');
                    button.classList.add('btn-outline-secondary');
                }, 2000);
            });
        });
    });
});

// Utility functions
function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.top = '20px';
    alertDiv.style.right = '20px';
    alertDiv.style.zIndex = '9999';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

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

// Watchlist functionality
function toggleWatchlist(billId, billTitle) {
    const btn = document.getElementById('watchlistBtn');
    const isCurrentlyWatched = btn.classList.contains('btn-success');
    
    if (isCurrentlyWatched) {
        // Remove from watchlist
        fetch(`/api/watchlist/${billId}`, {
            method: 'DELETE'
        })
        .then(response => {
            // Check if redirected to login (302 status)
            if (response.redirected || response.status === 302) {
                showNotification('Please log in to manage your watchlist', 'warning');
                window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
                return;
            }
            return response.json();
        })
        .then(data => {
            if (data && data.success) {
                btn.classList.remove('btn-success');
                btn.classList.add('btn-outline-success');
                btn.innerHTML = '<i class="fas fa-bookmark me-1"></i>Add to Watchlist';
                showNotification(data.message, 'success');
            } else if (data) {
                showNotification(data.error || 'Failed to remove from watchlist', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error updating watchlist', 'danger');
        });
    } else {
        // Add to watchlist
        fetch('/api/watchlist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                bill_id: billId,
                bill_title: billTitle,
                notes: ''
            })
        })
        .then(response => {
            // Check if redirected to login (302 status)
            if (response.redirected || response.status === 302) {
                showNotification('Please log in to add bills to your watchlist', 'warning');
                window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
                return;
            }
            return response.json();
        })
        .then(data => {
            if (data && data.success) {
                btn.classList.remove('btn-outline-success');
                btn.classList.add('btn-success');
                btn.innerHTML = '<i class="fas fa-bookmark me-1"></i>Remove from Watchlist';
                showNotification(data.message, 'success');
            } else if (data) {
                showNotification(data.error || 'Failed to add to watchlist', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error updating watchlist', 'danger');
        });
    }
}

