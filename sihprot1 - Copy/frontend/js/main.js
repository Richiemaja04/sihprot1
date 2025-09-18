// Main application logic
class TimetableApp {
    constructor() {
        this.currentPrograms = [];
        this.selectedDepartment = '';
        this.selectedLevel = '';
        this.selectedSemester = '';
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Department selection
        const departmentSelect = document.getElementById('department');
        if (departmentSelect) {
            departmentSelect.addEventListener('change', (e) => {
                this.selectedDepartment = e.target.value;
                this.loadLevels();
            });
        }

        // Level selection
        const levelSelect = document.getElementById('level');
        if (levelSelect) {
            levelSelect.addEventListener('change', (e) => {
                this.selectedLevel = e.target.value;
                this.loadSemesters();
            });
        }

        // Semester selection
        const semesterSelect = document.getElementById('semester');
        if (semesterSelect) {
            semesterSelect.addEventListener('change', (e) => {
                this.selectedSemester = e.target.value;
                this.updateViewTimetableButton();
            });
        }

        // View timetable button
        const viewTimetableBtn = document.getElementById('viewTimetableBtn');
        if (viewTimetableBtn) {
            viewTimetableBtn.addEventListener('click', () => {
                this.viewTimetable();
            });
        }

        // Login form
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleLogin();
            });
        }

        // Modal close handlers
        const modal = document.getElementById('loginModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    hideLoginModal();
                }
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                hideLoginModal();
            }
        });
    }

    async loadPrograms() {
        try {
            this.currentPrograms = await api.getPrograms();
            this.populateDepartmentSelect();
        } catch (error) {
            console.error('Failed to load programs:', error);
            showNotification('Failed to load programs', 'error');
        }
    }

    populateDepartmentSelect() {
        const select = document.getElementById('department');
        if (!select || !this.currentPrograms) return;

        select.innerHTML = '<option value="">Choose Department...</option>';
        
        this.currentPrograms.forEach(program => {
            const option = document.createElement('option');
            option.value = program.department;
            option.textContent = program.department;
            select.appendChild(option);
        });
    }

    loadLevels() {
        const levelSelect = document.getElementById('level');
        const semesterSelect = document.getElementById('semester');
        
        if (!levelSelect || !this.selectedDepartment) return;

        // Reset dependent selects
        levelSelect.innerHTML = '<option value="">Choose Level...</option>';
        semesterSelect.innerHTML = '<option value="">Choose Semester...</option>';
        semesterSelect.disabled = true;
        this.selectedLevel = '';
        this.selectedSemester = '';
        this.updateViewTimetableButton();

        // Find selected program
        const program = this.currentPrograms.find(p => p.department === this.selectedDepartment);
        if (!program) return;

        // Populate levels
        program.levels.forEach(level => {
            const option = document.createElement('option');
            option.value = level;
            option.textContent = level;
            levelSelect.appendChild(option);
        });

        levelSelect.disabled = false;
    }

    async loadSemesters() {
        if (!this.selectedDepartment || !this.selectedLevel) return;

        const semesterSelect = document.getElementById('semester');
        if (!semesterSelect) return;

        try {
            const semesters = await api.getSemesters(this.selectedDepartment, this.selectedLevel);
            
            semesterSelect.innerHTML = '<option value="">Choose Semester...</option>';
            
            semesters.forEach(semester => {
                const option = document.createElement('option');
                option.value = semester;
                option.textContent = `Semester ${semester}`;
                semesterSelect.appendChild(option);
            });

            semesterSelect.disabled = false;
            
        } catch (error) {
            console.error('Failed to load semesters:', error);
            showNotification('Failed to load semesters', 'error');
            semesterSelect.disabled = true;
        }
    }

    updateViewTimetableButton() {
        const button = document.getElementById('viewTimetableBtn');
        if (!button) return;

        const canView = this.selectedDepartment && this.selectedLevel && this.selectedSemester;
        button.disabled = !canView;
        
        if (canView) {
            button.classList.add('pulse');
        } else {
            button.classList.remove('pulse');
        }
    }

    async viewTimetable() {
        if (!this.selectedDepartment || !this.selectedLevel || !this.selectedSemester) {
            showNotification('Please select department, level, and semester', 'warning');
            return;
        }

        try {
            // Store selections in sessionStorage
            sessionStorage.setItem('selectedDepartment', this.selectedDepartment);
            sessionStorage.setItem('selectedLevel', this.selectedLevel);
            sessionStorage.setItem('selectedSemester', this.selectedSemester);

            // Navigate to student view
            window.location.href = 'student-view.html';
            
        } catch (error) {
            console.error('Failed to navigate to timetable:', error);
            showNotification('Failed to load timetable', 'error');
        }
    }

    async handleLogin() {
        const form = document.getElementById('loginForm');
        const formData = new FormData(form);
        
        const email = formData.get('email');
        const password = formData.get('password');
        const userType = formData.get('userType');

        if (!email || !password) {
            showNotification('Please enter email and password', 'warning');
            return;
        }

        try {
            const response = await api.login(email, password, userType);
            
            showNotification(`Welcome back, ${response.user_name}!`, 'success');
            hideLoginModal();

            // Navigate based on user type
            setTimeout(() => {
                if (response.user_type === 'admin') {
                    window.location.href = 'admin-dashboard.html';
                } else if (response.user_type === 'teacher') {
                    window.location.href = 'teacher-dashboard.html';
                }
            }, 1000);

        } catch (error) {
            showNotification(error.message || 'Login failed', 'error');
            
            // Shake the form on error
            const formElement = document.getElementById('loginForm');
            if (formElement) {
                formElement.classList.add('shake');
                setTimeout(() => formElement.classList.remove('shake'), 500);
            }
        }
    }

    async loadSystemStats() {
        try {
            const stats = await api.getSystemStats();
            this.animateStats(stats.overview);
        } catch (error) {
            console.warn('Failed to load system stats:', error);
            // Use fallback stats
            this.animateStats({
                total_batches: 25,
                total_faculty: 150,
                total_rooms: 45,
                active_classes: 1200
            });
        }
    }

    animateStats(stats) {
        const statElements = {
            totalBatches: stats.total_batches || 0,
            totalFaculty: stats.total_faculty || 0,
            totalRooms: stats.total_rooms || 0,
            totalClasses: stats.active_classes || 0
        };

        Object.keys(statElements).forEach(key => {
            const element = document.getElementById(key);
            if (element) {
                this.animateCounter(element, statElements[key]);
            }
        });
    }

    animateCounter(element, targetValue, duration = 2000) {
        const startValue = 0;
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function for smooth animation
            const easeOutQuad = progress => progress * (2 - progress);
            const currentValue = Math.floor(startValue + (targetValue - startValue) * easeOutQuad(progress));
            
            element.textContent = currentValue.toLocaleString();
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }
}

// Modal functions
function showLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.querySelector('.modal-content').classList.add('modal-enter');
        
        // Focus on email input
        setTimeout(() => {
            const emailInput = document.getElementById('email');
            if (emailInput) emailInput.focus();
        }, 100);
    }
}

function hideLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) {
        const modalContent = modal.querySelector('.modal-content');
        modalContent.classList.remove('modal-enter');
        modalContent.classList.add('modal-exit');
        
        setTimeout(() => {
            modal.style.display = 'none';
            modalContent.classList.remove('modal-exit');
            
            // Reset form
            const form = document.getElementById('loginForm');
            if (form) form.reset();
        }, 300);
    }
}

// Animation and UI functions
function initializeAnimations() {
    // Intersection Observer for scroll animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
                
                // Add stagger animation to children if present
                const children = entry.target.querySelectorAll('.feature-card, .stat-card');
                children.forEach((child, index) => {
                    child.style.animationDelay = `${index * 0.1}s`;
                    child.classList.add('slide-up');
                });
            }
        });
    }, observerOptions);

    // Observe sections for scroll animations
    document.querySelectorAll('.features-section, .stats-section').forEach(section => {
        observer.observe(section);
    });

    // Add particle effects to interactive elements
    document.querySelectorAll('.btn-primary, .feature-card, .glass-card').forEach(element => {
        element.classList.add('particle-effect');
    });

    // Add ripple effect to buttons
    document.querySelectorAll('button, .btn-primary, .btn-secondary').forEach(button => {
        button.classList.add('btn-ripple');
    });

    // Smooth scroll for navigation links
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

    // Add GPU acceleration to animated elements
    document.querySelectorAll('.floating-shapes .shape, .timetable-cell, .dashboard-card').forEach(element => {
        element.classList.add('gpu-accelerated');
    });
}

// Navigation and routing
function navigateToPage(page) {
    window.location.href = page;
}

// Utility functions
function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).format(new Date(date));
}

function formatTime(hour) {
    const time = new Date();
    time.setHours(hour + 8, 0, 0, 0); // Assuming first hour starts at 9 AM
    return time.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
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

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Global functions
async function loadPrograms() {
    if (window.timetableApp) {
        await window.timetableApp.loadPrograms();
    }
}

async function loadSystemStats() {
    if (window.timetableApp) {
        await window.timetableApp.loadSystemStats();
    }
}

// Error handling
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    showNotification('An unexpected error occurred', 'error');
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    showNotification('An unexpected error occurred', 'error');
    event.preventDefault();
});

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.timetableApp = new TimetableApp();
    
    // Add theme transition class to all elements
    document.documentElement.classList.add('theme-transition');
    
    // Initialize tooltips and other UI components
    initializeTooltips();
});

// Tooltip initialization
function initializeTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
        element.addEventListener('mousemove', moveTooltip);
    });
}

function showTooltip(event) {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = event.target.getAttribute('data-tooltip');
    tooltip.id = 'active-tooltip';
    
    document.body.appendChild(tooltip);
    
    // Position tooltip
    const rect = event.target.getBoundingClientRect();
    tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
    tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';
    
    // Animate in
    setTimeout(() => tooltip.classList.add('tooltip-visible'), 10);
}

function hideTooltip() {
    const tooltip = document.getElementById('active-tooltip');
    if (tooltip) {
        tooltip.classList.remove('tooltip-visible');
        setTimeout(() => tooltip.remove(), 200);
    }
}

function moveTooltip(event) {
    const tooltip = document.getElementById('active-tooltip');
    if (tooltip) {
        const rect = event.target.getBoundingClientRect();
        tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
        tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (event) => {
    // Ctrl/Cmd + K for quick search
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        // Open search modal (implement if needed)
        console.log('Quick search shortcut pressed');
    }
    
    // Ctrl/Cmd + L for login
    if ((event.ctrlKey || event.metaKey) && event.key === 'l') {
        event.preventDefault();
        showLoginModal();
    }
});

// Performance monitoring
if ('performance' in window) {
    window.addEventListener('load', () => {
        setTimeout(() => {
            const perfData = window.performance.timing;
            const loadTime = perfData.loadEventEnd - perfData.navigationStart;
            console.log(`Page load time: ${loadTime}ms`);
            
            // Log performance metrics (could send to analytics)
            if (loadTime > 3000) {
                console.warn('Page load time is slow');
            }
        }, 0);
    });
}