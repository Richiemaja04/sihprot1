/**
 * Charts and Analytics Module
 * Handles all chart rendering and data visualization
 */

class ChartManager {
    constructor() {
        this.charts = new Map();
        this.colorSchemes = {
            primary: ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe'],
            secondary: ['#667eea', '#a8edea', '#fed6e3', '#d299c2', '#fef9d7', '#89f7fe'],
            success: ['#10b981', '#34d399', '#6ee7b7', '#9deccc', '#c6f6d5'],
            warning: ['#f59e0b', '#fbbf24', '#fcd34d', '#fde68a', '#fef3c7'],
            error: ['#ef4444', '#f87171', '#fca5a5', '#fecaca', '#fee2e2']
        };
        this.defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                        color: '#b3b3cc'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 15, 35, 0.9)',
                    titleColor: '#ffffff',
                    bodyColor: '#b3b3cc',
                    borderColor: 'rgba(102, 126, 234, 0.2)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                        borderColor: 'rgba(255, 255, 255, 0.2)'
                    },
                    ticks: {
                        color: '#b3b3cc'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                        borderColor: 'rgba(255, 255, 255, 0.2)'
                    },
                    ticks: {
                        color: '#b3b3cc'
                    }
                }
            }
        };
    }

    /**
     * Create a faculty workload distribution chart
     */
    createFacultyWorkloadChart(containerId, data) {
        const ctx = this.getCanvasContext(containerId);
        if (!ctx) return null;

        const chartData = {
            labels: data.map(item => item.name.split(' ')[0]), // First name only
            datasets: [{
                label: 'Current Hours',
                data: data.map(item => item.current_hours),
                backgroundColor: this.addAlpha(this.colorSchemes.primary[0], 0.8),
                borderColor: this.colorSchemes.primary[0],
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false
            }, {
                label: 'Max Hours',
                data: data.map(item => item.max_hours),
                backgroundColor: this.addAlpha(this.colorSchemes.primary[1], 0.3),
                borderColor: this.colorSchemes.primary[1],
                borderWidth: 1,
                borderRadius: 8,
                borderSkipped: false
            }]
        };

        const options = {
            ...this.defaultOptions,
            plugins: {
                ...this.defaultOptions.plugins,
                title: {
                    display: true,
                    text: 'Faculty Workload Distribution',
                    color: '#ffffff',
                    font: { size: 16, weight: 'bold' }
                }
            },
            scales: {
                ...this.defaultOptions.scales,
                y: {
                    ...this.defaultOptions.scales.y,
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Hours per Week',
                        color: '#b3b3cc'
                    }
                }
            }
        };

        const chart = new Chart(ctx, {
            type: 'bar',
            data: chartData,
            options: options
        });

        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * Create a room utilization pie chart
     */
    createRoomUtilizationChart(containerId, data) {
        const ctx = this.getCanvasContext(containerId);
        if (!ctx) return null;

        const chartData = {
            labels: data.map(item => item.room_type),
            datasets: [{
                data: data.map(item => item.utilization),
                backgroundColor: this.colorSchemes.primary,
                borderColor: '#1a1a2e',
                borderWidth: 2,
                hoverOffset: 10
            }]
        };

        const options = {
            ...this.defaultOptions,
            plugins: {
                ...this.defaultOptions.plugins,
                title: {
                    display: true,
                    text: 'Room Utilization by Type',
                    color: '#ffffff',
                    font: { size: 16, weight: 'bold' }
                },
                tooltip: {
                    ...this.defaultOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.parsed}%`;
                        }
                    }
                }
            }
        };

        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: chartData,
            options: options
        });

        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * Create a schedule distribution heatmap
     */
    createScheduleHeatmap(containerId, data) {
        const canvas = this.getCanvas(containerId);
        if (!canvas) return null;

        // Create custom heatmap using canvas
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // Clear canvas
        ctx.clearRect(0, 0, width, height);

        const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
        const hours = Array.from({length: 8}, (_, i) => i + 1);
        
        const cellWidth = width / days.length;
        const cellHeight = height / hours.length;
        
        // Find max value for scaling
        const maxValue = Math.max(...data.map(d => d.count));
        
        // Draw heatmap
        data.forEach(item => {
            const dayIndex = days.indexOf(item.day.substring(0, 3));
            const hourIndex = item.hour - 1;
            
            if (dayIndex >= 0 && hourIndex >= 0) {
                const intensity = item.count / maxValue;
                const color = this.getHeatmapColor(intensity);
                
                ctx.fillStyle = color;
                ctx.fillRect(
                    dayIndex * cellWidth, 
                    hourIndex * cellHeight, 
                    cellWidth - 1, 
                    cellHeight - 1
                );
                
                // Add text
                ctx.fillStyle = intensity > 0.5 ? '#ffffff' : '#333333';
                ctx.font = '12px Inter';
                ctx.textAlign = 'center';
                ctx.fillText(
                    item.count.toString(),
                    dayIndex * cellWidth + cellWidth / 2,
                    hourIndex * cellHeight + cellHeight / 2 + 4
                );
            }
        });

        // Draw grid lines
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        ctx.lineWidth = 1;
        
        // Vertical lines
        for (let i = 0; i <= days.length; i++) {
            ctx.beginPath();
            ctx.moveTo(i * cellWidth, 0);
            ctx.lineTo(i * cellWidth, height);
            ctx.stroke();
        }
        
        // Horizontal lines
        for (let i = 0; i <= hours.length; i++) {
            ctx.beginPath();
            ctx.moveTo(0, i * cellHeight);
            ctx.lineTo(width, i * cellHeight);
            ctx.stroke();
        }

        // Add labels
        ctx.fillStyle = '#b3b3cc';
        ctx.font = 'bold 14px Inter';
        ctx.textAlign = 'center';
        
        // Day labels
        days.forEach((day, index) => {
            ctx.fillText(
                day,
                index * cellWidth + cellWidth / 2,
                height + 20
            );
        });
        
        // Hour labels
        ctx.textAlign = 'right';
        hours.forEach((hour, index) => {
            ctx.fillText(
                `H${hour}`,
                -10,
                index * cellHeight + cellHeight / 2 + 4
            );
        });

        return { canvas, data };
    }

    /**
     * Create subject type distribution chart
     */
    createSubjectTypeChart(containerId, data) {
        const ctx = this.getCanvasContext(containerId);
        if (!ctx) return null;

        const chartData = {
            labels: data.map(item => item.type),
            datasets: [{
                data: data.map(item => item.count),
                backgroundColor: [
                    this.colorSchemes.success[0], // Theory
                    this.colorSchemes.warning[0], // Lab
                    this.colorSchemes.error[0],   // Practical
                    this.colorSchemes.primary[3], // Others
                ],
                borderColor: '#1a1a2e',
                borderWidth: 2,
                hoverOffset: 8
            }]
        };

        const options = {
            ...this.defaultOptions,
            plugins: {
                ...this.defaultOptions.plugins,
                title: {
                    display: true,
                    text: 'Subject Type Distribution',
                    color: '#ffffff',
                    font: { size: 16, weight: 'bold' }
                },
                tooltip: {
                    ...this.defaultOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            return `${context.label}: ${context.parsed} (${percentage}%)`;
                        }
                    }
                }
            }
        };

        const chart = new Chart(ctx, {
            type: 'pie',
            data: chartData,
            options: options
        });

        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * Create workload balance line chart
     */
    createWorkloadTrendChart(containerId, data) {
        const ctx = this.getCanvasContext(containerId);
        if (!ctx) return null;

        const chartData = {
            labels: data.labels,
            datasets: [{
                label: 'Average Workload',
                data: data.average,
                borderColor: this.colorSchemes.primary[0],
                backgroundColor: this.addAlpha(this.colorSchemes.primary[0], 0.1),
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: this.colorSchemes.primary[0],
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8
            }, {
                label: 'Peak Workload',
                data: data.peak,
                borderColor: this.colorSchemes.error[0],
                backgroundColor: this.addAlpha(this.colorSchemes.error[0], 0.1),
                borderWidth: 2,
                borderDash: [5, 5],
                fill: false,
                tension: 0.4,
                pointBackgroundColor: this.colorSchemes.error[0],
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        };

        const options = {
            ...this.defaultOptions,
            plugins: {
                ...this.defaultOptions.plugins,
                title: {
                    display: true,
                    text: 'Workload Trends',
                    color: '#ffffff',
                    font: { size: 16, weight: 'bold' }
                }
            },
            scales: {
                ...this.defaultOptions.scales,
                y: {
                    ...this.defaultOptions.scales.y,
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Hours',
                        color: '#b3b3cc'
                    }
                }
            }
        };

        const chart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: options
        });

        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * Create analytics dashboard with multiple charts
     */
    createAnalyticsDashboard(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        container.innerHTML = `
            <div class="analytics-dashboard">
                <div class="chart-row">
                    <div class="chart-container">
                        <canvas id="${containerId}-workload"></canvas>
                    </div>
                    <div class="chart-container">
                        <canvas id="${containerId}-rooms"></canvas>
                    </div>
                </div>
                <div class="chart-row">
                    <div class="chart-container">
                        <canvas id="${containerId}-subjects"></canvas>
                    </div>
                    <div class="chart-container">
                        <canvas id="${containerId}-heatmap"></canvas>
                    </div>
                </div>
            </div>
        `;

        // Create individual charts
        const charts = {};
        
        if (data.faculty) {
            charts.workload = this.createFacultyWorkloadChart(`${containerId}-workload`, data.faculty);
        }
        
        if (data.rooms) {
            charts.rooms = this.createRoomUtilizationChart(`${containerId}-rooms`, data.rooms);
        }
        
        if (data.subjects) {
            charts.subjects = this.createSubjectTypeChart(`${containerId}-subjects`, data.subjects);
        }
        
        if (data.schedule) {
            charts.heatmap = this.createScheduleHeatmap(`${containerId}-heatmap`, data.schedule);
        }

        return charts;
    }

    /**
     * Create real-time updating chart
     */
    createRealtimeChart(containerId, initialData, updateInterval = 5000) {
        const chart = this.createWorkloadTrendChart(containerId, initialData);
        
        const updateChart = async () => {
            try {
                // Fetch new data (this would be replaced with actual API call)
                const newData = await this.fetchRealtimeData();
                
                // Update chart data
                chart.data.labels = newData.labels;
                chart.data.datasets[0].data = newData.average;
                chart.data.datasets[1].data = newData.peak;
                
                // Animate update
                chart.update('active');
                
            } catch (error) {
                console.error('Failed to update realtime chart:', error);
            }
        };

        // Set up periodic updates
        const intervalId = setInterval(updateChart, updateInterval);
        
        // Store interval ID for cleanup
        if (!this.intervals) this.intervals = new Map();
        this.intervals.set(containerId, intervalId);
        
        return chart;
    }

    /**
     * Utility methods
     */
    getCanvasContext(containerId) {
        const canvas = this.getCanvas(containerId);
        return canvas ? canvas.getContext('2d') : null;
    }

    getCanvas(containerId) {
        let canvas = document.getElementById(containerId);
        
        if (!canvas) {
            // Create canvas if it doesn't exist
            const container = document.querySelector(`#${containerId}, .${containerId}`);
            if (container) {
                canvas = document.createElement('canvas');
                canvas.id = containerId;
                container.appendChild(canvas);
            }
        }
        
        if (canvas) {
            // Set responsive dimensions
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width = rect.width;
            canvas.height = rect.height || 300;
        }
        
        return canvas;
    }

    addAlpha(color, alpha) {
        // Convert hex to rgba
        const hex = color.replace('#', '');
        const r = parseInt(hex.substr(0, 2), 16);
        const g = parseInt(hex.substr(2, 2), 16);
        const b = parseInt(hex.substr(4, 2), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    getHeatmapColor(intensity) {
        // Create gradient from blue to red
        const r = Math.floor(255 * intensity);
        const g = Math.floor(100 * (1 - intensity));
        const b = Math.floor(255 * (1 - intensity));
        return `rgba(${r}, ${g}, ${b}, 0.8)`;
    }

    async fetchRealtimeData() {
        // Mock data - replace with actual API call
        return {
            labels: ['9AM', '10AM', '11AM', '12PM', '1PM', '2PM', '3PM', '4PM'],
            average: Array.from({length: 8}, () => Math.floor(Math.random() * 20) + 10),
            peak: Array.from({length: 8}, () => Math.floor(Math.random() * 15) + 25)
        };
    }

    /**
     * Chart management methods
     */
    updateChart(containerId, newData) {
        const chart = this.charts.get(containerId);
        if (!chart) return false;

        chart.data = newData;
        chart.update('active');
        return true;
    }

    destroyChart(containerId) {
        const chart = this.charts.get(containerId);
        if (chart) {
            chart.destroy();
            this.charts.delete(containerId);
        }

        // Clear interval if exists
        if (this.intervals && this.intervals.has(containerId)) {
            clearInterval(this.intervals.get(containerId));
            this.intervals.delete(containerId);
        }
    }

    destroyAllCharts() {
        this.charts.forEach((chart, containerId) => {
            this.destroyChart(containerId);
        });
    }

    resizeChart(containerId) {
        const chart = this.charts.get(containerId);
        if (chart) {
            chart.resize();
        }
    }

    resizeAllCharts() {
        this.charts.forEach((chart) => {
            chart.resize();
        });
    }

    /**
     * Export chart as image
     */
    exportChart(containerId, format = 'png') {
        const chart = this.charts.get(containerId);
        if (!chart) return null;

        return chart.toBase64Image(format, 1);
    }

    /**
     * Save chart configuration
     */
    saveChartConfig(containerId) {
        const chart = this.charts.get(containerId);
        if (!chart) return null;

        return {
            type: chart.config.type,
            data: chart.data,
            options: chart.options
        };
    }

    /**
     * Create chart from saved configuration
     */
    createFromConfig(containerId, config) {
        const ctx = this.getCanvasContext(containerId);
        if (!ctx) return null;

        const chart = new Chart(ctx, config);
        this.charts.set(containerId, chart);
        return chart;
    }
}

// Animation utilities
class ChartAnimations {
    static fadeIn(chart, duration = 1000) {
        chart.options.animation = {
            duration: duration,
            easing: 'easeInOutQuart'
        };
        chart.update();
    }

    static slideInFromLeft(chart, duration = 800) {
        chart.options.animation = {
            duration: duration,
            easing: 'easeOutQuart',
            animateRotate: false,
            animateScale: true
        };
        chart.update();
    }

    static bounceIn(chart, duration = 1200) {
        chart.options.animation = {
            duration: duration,
            easing: 'easeOutBounce'
        };
        chart.update();
    }
}

// Global chart manager instance
const chartManager = new ChartManager();

// Utility functions for easy access
function createChart(type, containerId, data, options = {}) {
    switch (type) {
        case 'workload':
            return chartManager.createFacultyWorkloadChart(containerId, data);
        case 'rooms':
            return chartManager.createRoomUtilizationChart(containerId, data);
        case 'subjects':
            return chartManager.createSubjectTypeChart(containerId, data);
        case 'heatmap':
            return chartManager.createScheduleHeatmap(containerId, data);
        case 'trend':
            return chartManager.createWorkloadTrendChart(containerId, data);
        default:
            console.warn(`Unknown chart type: ${type}`);
            return null;
    }
}

function updateChart(containerId, data) {
    return chartManager.updateChart(containerId, data);
}

function destroyChart(containerId) {
    return chartManager.destroyChart(containerId);
}

function exportChart(containerId, format = 'png') {
    return chartManager.exportChart(containerId, format);
}

// Handle window resize
window.addEventListener('resize', () => {
    chartManager.resizeAllCharts();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    chartManager.destroyAllCharts();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChartManager, ChartAnimations };
} else {
    window.ChartManager = ChartManager;
    window.ChartAnimations = ChartAnimations;
    window.chartManager = chartManager;
}