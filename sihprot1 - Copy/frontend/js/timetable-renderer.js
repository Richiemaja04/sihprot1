/**
 * Timetable Renderer - Advanced timetable visualization and interaction
 */

class TimetableRenderer {
    constructor(options = {}) {
        this.options = {
            container: options.container || '#timetableContainer',
            theme: options.theme || 'dark',
            interactive: options.interactive !== false,
            showLegend: options.showLegend !== false,
            animations: options.animations !== false,
            cellHeight: options.cellHeight || 80,
            cellWidth: options.cellWidth || 150,
            timeFormat: options.timeFormat || '12hour',
            colorScheme: options.colorScheme || 'default',
            ...options
        };
        
        this.days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
        this.timeSlots = [];
        this.timetableData = null;
        this.selectedCells = new Set();
        
        this.init();
    }

    init() {
        this.generateTimeSlots();
        this.setupEventListeners();
    }

    generateTimeSlots() {
        for (let i = 1; i <= 8; i++) {
            const startTime = 8 + i; // 9 AM start
            const endTime = startTime + 1;
            this.timeSlots.push({
                hour: i,
                label: `Period ${i}`,
                timeRange: this.formatTimeRange(startTime, endTime)
            });
        }
    }

    formatTimeRange(startHour, endHour) {
        const format = this.options.timeFormat === '12hour';
        const start = format ? this.to12Hour(startHour) : `${startHour}:00`;
        const end = format ? this.to12Hour(endHour) : `${endHour}:00`;
        return `${start} - ${end}`;
    }

    to12Hour(hour) {
        if (hour === 0) return '12:00 AM';
        if (hour < 12) return `${hour}:00 AM`;
        if (hour === 12) return '12:00 PM';
        return `${hour - 12}:00 PM`;
    }

    /**
     * Render a complete timetable from data
     * @param {Object} data - Timetable data
     * @param {string} container - Container selector
     */
    render(data, container = null) {
        this.timetableData = data;
        const targetContainer = container || this.options.container;
        const element = typeof targetContainer === 'string' 
            ? document.querySelector(targetContainer)
            : targetContainer;

        if (!element) {
            console.error('Timetable container not found');
            return;
        }

        element.innerHTML = this.generateTimetableHTML();
        
        if (this.options.animations) {
            this.animateIn();
        }
        
        if (this.options.interactive) {
            this.makeInteractive();
        }
        
        if (this.options.showLegend) {
            this.renderLegend(element);
        }
    }

    generateTimetableHTML() {
        const grid = this.timetableData.grid || {};
        
        return `
            <div class="timetable-wrapper">
                <div class="timetable-grid" style="
                    display: grid;
                    grid-template-columns: 120px repeat(${this.days.length}, 1fr);
                    gap: 1px;
                    background: var(--glass-border);
                    border-radius: var(--radius-md);
                    overflow: hidden;
                    min-width: 800px;
                ">
                    ${this.generateHeaders()}
                    ${this.generateTimeRows(grid)}
                </div>
                ${this.options.showLegend ? this.generateLegendHTML() : ''}
            </div>
        `;
    }

    generateHeaders() {
        let headers = '<div class="time-header">Time</div>';
        
        this.days.forEach(day => {
            headers += `
                <div class="day-header" data-day="${day}">
                    <span class="day-name">${day}</span>
                    <span class="day-short">${day.substring(0, 3)}</span>
                </div>
            `;
        });
        
        return headers;
    }

    generateTimeRows(grid) {
        let rows = '';
        
        this.timeSlots.forEach(timeSlot => {
            // Time cell
            rows += `
                <div class="time-cell" data-hour="${timeSlot.hour}">
                    <div class="time-label">${timeSlot.label}</div>
                    <div class="time-range">${timeSlot.timeRange}</div>
                </div>
            `;
            
            // Day cells for this time slot
            this.days.forEach(day => {
                const cellData = grid[day] && grid[day][timeSlot.hour];
                rows += this.generateCell(day, timeSlot.hour, cellData);
            });
        });
        
        return rows;
    }

    generateCell(day, hour, data) {
        if (!data) {
            return `
                <div class="timetable-cell empty" 
                     data-day="${day}" 
                     data-hour="${hour}">
                    <div class="empty-indicator">Free</div>
                </div>
            `;
        }

        const subjectType = (data.subject_type || 'theory').toLowerCase();
        const cellId = `cell-${day}-${hour}`;
        
        return `
            <div class="timetable-cell filled ${subjectType}" 
                 id="${cellId}"
                 data-day="${day}" 
                 data-hour="${hour}"
                 data-subject="${data.subject_name}"
                 data-faculty="${data.faculty_name}"
                 data-room="${data.room_name}">
                 
                <div class="subject-type-indicator type-${subjectType}"></div>
                
                <div class="cell-content">
                    <div class="subject-name" title="${data.subject_name}">
                        ${this.truncateText(data.subject_name, 20)}
                    </div>
                    <div class="faculty-name" title="${data.faculty_name}">
                        <i class="fas fa-user"></i>
                        ${this.truncateText(data.faculty_name, 15)}
                    </div>
                    <div class="room-name" title="${data.room_name}">
                        <i class="fas fa-door-open"></i>
                        ${data.room_name}
                    </div>
                </div>
                
                <div class="cell-overlay">
                    <div class="overlay-content">
                        <h4>${data.subject_name}</h4>
                        <p><strong>Faculty:</strong> ${data.faculty_name}</p>
                        <p><strong>Room:</strong> ${data.room_name}</p>
                        <p><strong>Type:</strong> ${data.subject_type}</p>
                        <p><strong>Time:</strong> ${this.timeSlots[hour-1]?.timeRange}</p>
                    </div>
                </div>
            </div>
        `;
    }

    generateLegendHTML() {
        return `
            <div class="timetable-legend">
                <div class="legend-title">
                    <i class="fas fa-info-circle"></i>
                    Legend
                </div>
                <div class="legend-items">
                    <div class="legend-item">
                        <div class="legend-dot type-theory"></div>
                        <span>Theory</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot type-lab"></div>
                        <span>Laboratory</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot type-practical"></div>
                        <span>Practical</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot empty"></div>
                        <span>Free Period</span>
                    </div>
                </div>
            </div>
        `;
    }

    makeInteractive() {
        const cells = document.querySelectorAll('.timetable-cell.filled');
        
        cells.forEach(cell => {
            // Click handler
            cell.addEventListener('click', (e) => {
                this.handleCellClick(cell, e);
            });
            
            // Hover handlers
            cell.addEventListener('mouseenter', (e) => {
                this.handleCellHover(cell, e);
            });
            
            cell.addEventListener('mouseleave', (e) => {
                this.handleCellLeave(cell, e);
            });
            
            // Touch handlers for mobile
            cell.addEventListener('touchstart', (e) => {
                this.handleCellTouch(cell, e);
            });
        });
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            this.handleKeyboard(e);
        });
    }

    handleCellClick(cell, event) {
        event.preventDefault();
        
        // Toggle selection
        const cellId = cell.id;
        if (this.selectedCells.has(cellId)) {
            this.selectedCells.delete(cellId);
            cell.classList.remove('selected');
        } else {
            this.selectedCells.add(cellId);
            cell.classList.add('selected');
        }
        
        // Show details
        this.showCellDetails(cell);
        
        // Trigger custom event
        this.triggerEvent('cellClick', {
            cell,
            day: cell.dataset.day,
            hour: cell.dataset.hour,
            subject: cell.dataset.subject,
            faculty: cell.dataset.faculty,
            room: cell.dataset.room
        });
    }

    handleCellHover(cell, event) {
        cell.classList.add('hovered');
        this.showQuickPreview(cell, event);
        
        // Highlight related cells (same subject, faculty, or room)
        this.highlightRelatedCells(cell);
    }

    handleCellLeave(cell, event) {
        cell.classList.remove('hovered');
        this.hideQuickPreview();
        this.clearHighlights();
    }

    handleCellTouch(cell, event) {
        event.preventDefault();
        this.handleCellClick(cell, event);
    }

    handleKeyboard(event) {
        if (event.ctrlKey || event.metaKey) {
            switch (event.key) {
                case 'a':
                    event.preventDefault();
                    this.selectAll();
                    break;
                case 'c':
                    if (this.selectedCells.size > 0) {
                        event.preventDefault();
                        this.copyCells();
                    }
                    break;
                case 'p':
                    event.preventDefault();
                    this.printTimetable();
                    break;
            }
        }
        
        if (event.key === 'Escape') {
            this.clearSelection();
            this.hideQuickPreview();
        }
    }

    showCellDetails(cell) {
        const data = {
            subject: cell.dataset.subject,
            faculty: cell.dataset.faculty,
            room: cell.dataset.room,
            day: cell.dataset.day,
            hour: cell.dataset.hour,
            time: this.timeSlots[parseInt(cell.dataset.hour) - 1]?.timeRange
        };
        
        // Create or update details modal
        this.updateDetailsModal(data);
    }

    showQuickPreview(cell, event) {
        const preview = this.createQuickPreview(cell);
        document.body.appendChild(preview);
        
        // Position preview
        const rect = cell.getBoundingClientRect();
        preview.style.left = `${rect.right + 10}px`;
        preview.style.top = `${rect.top}px`;
        
        // Ensure preview stays on screen
        const previewRect = preview.getBoundingClientRect();
        if (previewRect.right > window.innerWidth) {
            preview.style.left = `${rect.left - previewRect.width - 10}px`;
        }
        if (previewRect.bottom > window.innerHeight) {
            preview.style.top = `${rect.bottom - previewRect.height}px`;
        }
    }

    createQuickPreview(cell) {
        const preview = document.createElement('div');
        preview.className = 'timetable-preview';
        preview.innerHTML = `
            <div class="preview-content">
                <h4>${cell.dataset.subject}</h4>
                <p><i class="fas fa-user"></i> ${cell.dataset.faculty}</p>
                <p><i class="fas fa-door-open"></i> ${cell.dataset.room}</p>
                <p><i class="fas fa-clock"></i> ${cell.dataset.day} - ${this.timeSlots[parseInt(cell.dataset.hour) - 1]?.timeRange}</p>
            </div>
        `;
        return preview;
    }

    hideQuickPreview() {
        const preview = document.querySelector('.timetable-preview');
        if (preview) {
            preview.remove();
        }
    }

    highlightRelatedCells(cell) {
        const subject = cell.dataset.subject;
        const faculty = cell.dataset.faculty;
        const room = cell.dataset.room;
        
        document.querySelectorAll('.timetable-cell.filled').forEach(otherCell => {
            if (otherCell === cell) return;
            
            if (otherCell.dataset.subject === subject) {
                otherCell.classList.add('related-subject');
            }
            if (otherCell.dataset.faculty === faculty) {
                otherCell.classList.add('related-faculty');
            }
            if (otherCell.dataset.room === room) {
                otherCell.classList.add('related-room');
            }
        });
    }

    clearHighlights() {
        document.querySelectorAll('.timetable-cell').forEach(cell => {
            cell.classList.remove('related-subject', 'related-faculty', 'related-room');
        });
    }

    animateIn() {
        const cells = document.querySelectorAll('.timetable-cell');
        
        cells.forEach((cell, index) => {
            cell.style.opacity = '0';
            cell.style.transform = 'scale(0.8) translateY(20px)';
            
            setTimeout(() => {
                cell.style.transition = 'all 0.3s ease';
                cell.style.opacity = '1';
                cell.style.transform = 'scale(1) translateY(0)';
            }, index * 50);
        });
    }

    selectAll() {
        document.querySelectorAll('.timetable-cell.filled').forEach(cell => {
            this.selectedCells.add(cell.id);
            cell.classList.add('selected');
        });
    }

    clearSelection() {
        this.selectedCells.clear();
        document.querySelectorAll('.timetable-cell.selected').forEach(cell => {
            cell.classList.remove('selected');
        });
    }

    copyCells() {
        const selectedData = Array.from(this.selectedCells).map(cellId => {
            const cell = document.getElementById(cellId);
            return {
                day: cell.dataset.day,
                hour: cell.dataset.hour,
                subject: cell.dataset.subject,
                faculty: cell.dataset.faculty,
                room: cell.dataset.room
            };
        });
        
        const textData = selectedData.map(data => 
            `${data.day} ${data.hour}: ${data.subject} - ${data.faculty} (${data.room})`
        ).join('\n');
        
        navigator.clipboard.writeText(textData)
            .then(() => showNotification('Timetable data copied to clipboard', 'success'))
            .catch(() => showNotification('Failed to copy data', 'error'));
    }

    printTimetable() {
        const printWindow = window.open('', '_blank');
        const timetableHTML = document.querySelector('.timetable-wrapper').outerHTML;
        
        printWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Timetable</title>
                <style>
                    ${this.getPrintStyles()}
                </style>
            </head>
            <body>
                <h1>Class Timetable</h1>
                ${timetableHTML}
            </body>
            </html>
        `);
        
        printWindow.document.close();
        printWindow.print();
    }

    getPrintStyles() {
        return `
            body { font-family: Arial, sans-serif; margin: 20px; }
            .timetable-grid { 
                display: grid;
                grid-template-columns: 120px repeat(5, 1fr);
                gap: 1px;
                border: 1px solid #000;
            }
            .time-header, .day-header, .time-cell, .timetable-cell {
                padding: 8px;
                border: 1px solid #ccc;
                text-align: center;
                font-size: 12px;
            }
            .time-header, .day-header, .time-cell {
                background: #f0f0f0;
                font-weight: bold;
            }
            .timetable-cell.filled {
                background: #e6f3ff;
            }
            .subject-name { font-weight: bold; margin-bottom: 4px; }
            .faculty-name, .room-name { font-size: 10px; color: #666; }
            .timetable-legend { margin-top: 20px; }
            .legend-items { display: flex; gap: 20px; }
            .legend-item { display: flex; align-items: center; gap: 8px; }
            .legend-dot { width: 12px; height: 12px; border-radius: 50%; }
        `;
    }

    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    triggerEvent(eventName, data) {
        const event = new CustomEvent(`timetable:${eventName}`, { detail: data });
        document.dispatchEvent(event);
    }

    /**
     * Export timetable data in various formats
     */
    export(format = 'json') {
        switch (format.toLowerCase()) {
            case 'json':
                return this.exportJSON();
            case 'csv':
                return this.exportCSV();
            case 'ical':
                return this.exportICAL();
            case 'pdf':
                return this.exportPDF();
            default:
                throw new Error(`Unsupported export format: ${format}`);
        }
    }

    exportJSON() {
        return JSON.stringify(this.timetableData, null, 2);
    }

    exportCSV() {
        const headers = ['Day', 'Time', 'Subject', 'Faculty', 'Room', 'Type'];
        const rows = [headers.join(',')];
        
        Object.entries(this.timetableData.grid || {}).forEach(([day, hours]) => {
            Object.entries(hours).forEach(([hour, data]) => {
                if (data) {
                    const timeRange = this.timeSlots[parseInt(hour) - 1]?.timeRange || '';
                    const row = [
                        day,
                        timeRange,
                        data.subject_name || '',
                        data.faculty_name || '',
                        data.room_name || '',
                        data.subject_type || ''
                    ].map(field => `"${field}"`).join(',');
                    rows.push(row);
                }
            });
        });
        
        return rows.join('\n');
    }

    exportICAL() {
        let ical = 'BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//TimetableAI//Timetable//EN\n';
        
        Object.entries(this.timetableData.grid || {}).forEach(([day, hours]) => {
            Object.entries(hours).forEach(([hour, data]) => {
                if (data) {
                    const timeSlot = this.timeSlots[parseInt(hour) - 1];
                    if (timeSlot) {
                        ical += this.createICALEvent(day, timeSlot, data);
                    }
                }
            });
        });
        
        ical += 'END:VCALENDAR\n';
        return ical;
    }

    createICALEvent(day, timeSlot, data) {
        const startTime = this.getICALTime(day, timeSlot.hour);
        const endTime = this.getICALTime(day, timeSlot.hour + 1);
        
        return `BEGIN:VEVENT
UID:${day}-${timeSlot.hour}-${Date.now()}@timetableai.com
DTSTART:${startTime}
DTEND:${endTime}
SUMMARY:${data.subject_name}
DESCRIPTION:Faculty: ${data.faculty_name}\\nRoom: ${data.room_name}
LOCATION:${data.room_name}
END:VEVENT
`;
    }

    getICALTime(day, hour) {
        // This is a simplified version - in production, you'd need proper date handling
        const date = new Date();
        date.setHours(8 + hour, 0, 0, 0);
        return date.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
    }

    /**
     * Static utility methods
     */
    static createMiniTimetable(data, container, options = {}) {
        const renderer = new TimetableRenderer({
            ...options,
            cellHeight: 40,
            cellWidth: 100,
            showLegend: false,
            interactive: false
        });
        
        renderer.render(data, container);
        return renderer;
    }

    static createResponsiveTimetable(data, container, options = {}) {
        const renderer = new TimetableRenderer({
            ...options,
            responsive: true
        });
        
        renderer.render(data, container);
        
        // Add responsive behavior
        window.addEventListener('resize', () => {
            renderer.render(data, container);
        });
        
        return renderer;
    }

    static createPrintableTimetable(data, container, options = {}) {
        const renderer = new TimetableRenderer({
            ...options,
            theme: 'print',
            animations: false,
            interactive: false
        });
        
        renderer.render(data, container);
        return renderer;
    }
}

// Global utility functions
function renderTimetable(data, container, options) {
    const renderer = new TimetableRenderer(options);
    renderer.render(data, container);
    return renderer;
}

function createMiniTimetable(data, container) {
    return TimetableRenderer.createMiniTimetable(data, container);
}

function exportTimetable(renderer, format) {
    return renderer.export(format);
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TimetableRenderer;
} else {
    window.TimetableRenderer = TimetableRenderer;
}