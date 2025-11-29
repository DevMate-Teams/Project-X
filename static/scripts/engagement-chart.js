/**
 * Engagement Analytics Chart
 * Handles fetching data and rendering interactive engagement charts
 */

(function() {
    'use strict';

    // Chart instance
    let engagementChart = null;
    
    // Current state
    let currentState = {
        username: '',
        startDate: null,
        endDate: null,
        granularity: 'day',
        chartType: 'line',
        data: null
    };

    // Chart colors
    const COLORS = {
        logs: {
            border: 'rgb(59, 130, 246)',
            background: 'rgba(59, 130, 246, 0.2)'
        },
        reactions: {
            border: 'rgb(236, 72, 153)',
            background: 'rgba(236, 72, 153, 0.2)'
        },
        comments: {
            border: 'rgb(6, 182, 212)',
            background: 'rgba(6, 182, 212, 0.2)'
        },
        totalEngagement: {
            border: 'rgb(34, 197, 94)',
            background: 'rgba(34, 197, 94, 0.2)'
        }
    };

    /**
     * Initialize the engagement chart on page load
     */
    function init() {
        const section = document.getElementById('engagement-analytics-section');
        if (!section) return;

        currentState.username = section.dataset.username;
        
        // Set default date range (last 7 days)
        const today = new Date();
        const sevenDaysAgo = new Date(today);
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
        
        currentState.endDate = formatDate(today);
        currentState.startDate = formatDate(sevenDaysAgo);
        
        // Set input values
        document.getElementById('engagement-end-date').value = currentState.endDate;
        document.getElementById('engagement-start-date').value = currentState.startDate;
        
        // Bind event listeners
        bindEvents();
        
        // Load initial data
        fetchAndRenderChart();
    }

    /**
     * Bind all event listeners
     */
    function bindEvents() {
        // Date range preset buttons
        document.querySelectorAll('.date-range-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const days = parseInt(this.dataset.range);
                setDateRange(days);
                updateActiveRangeButton(this);
            });
        });

        // Apply custom date range
        document.getElementById('apply-custom-range').addEventListener('click', function() {
            const startDate = document.getElementById('engagement-start-date').value;
            const endDate = document.getElementById('engagement-end-date').value;
            
            if (startDate && endDate) {
                currentState.startDate = startDate;
                currentState.endDate = endDate;
                clearActiveRangeButtons();
                fetchAndRenderChart();
            }
        });

        // Granularity selector
        document.getElementById('engagement-granularity').addEventListener('change', function() {
            currentState.granularity = this.value;
            fetchAndRenderChart();
        });

        // Chart type buttons
        document.querySelectorAll('.chart-type-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                currentState.chartType = this.dataset.type;
                updateActiveChartTypeButton(this);
                renderChart();
            });
        });
    }

    /**
     * Set date range based on days preset
     */
    function setDateRange(days) {
        const today = new Date();
        const startDate = new Date(today);
        startDate.setDate(startDate.getDate() - days);
        
        currentState.endDate = formatDate(today);
        currentState.startDate = formatDate(startDate);
        
        // Update auto granularity based on range
        if (days <= 14) {
            currentState.granularity = 'day';
        } else if (days <= 90) {
            currentState.granularity = 'day';
        } else {
            currentState.granularity = 'week';
        }
        document.getElementById('engagement-granularity').value = currentState.granularity;
        
        // Update date inputs
        document.getElementById('engagement-end-date').value = currentState.endDate;
        document.getElementById('engagement-start-date').value = currentState.startDate;
        
        fetchAndRenderChart();
    }

    /**
     * Update active state for range buttons
     */
    function updateActiveRangeButton(activeBtn) {
        document.querySelectorAll('.date-range-btn').forEach(btn => {
            btn.classList.remove('bg-[#238636]', 'text-white');
            btn.classList.add('text-gray-400', 'hover:bg-[#21262d]');
        });
        activeBtn.classList.remove('text-gray-400', 'hover:bg-[#21262d]');
        activeBtn.classList.add('bg-[#238636]', 'text-white');
    }

    /**
     * Clear active state from all range buttons
     */
    function clearActiveRangeButtons() {
        document.querySelectorAll('.date-range-btn').forEach(btn => {
            btn.classList.remove('bg-[#238636]', 'text-white');
            btn.classList.add('text-gray-400', 'hover:bg-[#21262d]');
        });
    }

    /**
     * Update active state for chart type buttons
     */
    function updateActiveChartTypeButton(activeBtn) {
        document.querySelectorAll('.chart-type-btn').forEach(btn => {
            btn.classList.remove('bg-[#238636]', 'text-white');
            btn.classList.add('bg-[#161b22]', 'text-gray-400', 'border', 'border-[#30363d]');
        });
        activeBtn.classList.remove('bg-[#161b22]', 'text-gray-400', 'border', 'border-[#30363d]');
        activeBtn.classList.add('bg-[#238636]', 'text-white');
    }

    /**
     * Fetch engagement data from API
     */
    async function fetchAndRenderChart() {
        showLoading(true);
        
        try {
            const params = new URLSearchParams({
                start_date: currentState.startDate,
                end_date: currentState.endDate,
                granularity: currentState.granularity,
                include_breakdown: 'false',
                include_comparison: 'false'
            });
            
            const response = await fetch(`/logs/analytics/${currentState.username}/engagement/?${params}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch engagement data');
            }
            
            const result = await response.json();
            
            if (result.success) {
                currentState.data = result.data;
                updateSummaryStats(result.data.summary);
                renderChart();
                showEmptyState(false);
            } else {
                showEmptyState(true);
            }
        } catch (error) {
            console.error('Error fetching engagement data:', error);
            showEmptyState(true);
        } finally {
            showLoading(false);
        }
    }

    /**
     * Update summary statistics display
     */
    function updateSummaryStats(summary) {
        document.getElementById('stat-total-logs').textContent = summary.total_logs;
        document.getElementById('stat-total-reactions').textContent = summary.total_reactions;
        document.getElementById('stat-total-comments').textContent = summary.total_comments;
        document.getElementById('stat-avg-engagement').textContent = summary.avg_engagement_per_log.toFixed(1);
    }

    /**
     * Render the chart with current data and settings
     */
    function renderChart() {
        if (!currentState.data) return;
        
        const ctx = document.getElementById('engagement-chart').getContext('2d');
        
        // Destroy existing chart
        if (engagementChart) {
            engagementChart.destroy();
        }
        
        // Format labels for display
        const labels = currentState.data.labels.map(label => {
            const date = new Date(label);
            if (currentState.granularity === 'day') {
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            } else if (currentState.granularity === 'week') {
                return 'Week of ' + date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            } else {
                return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
            }
        });

        // Configure datasets based on chart type
        const datasets = getDatasets();
        
        // Chart configuration
        const config = {
            type: currentState.chartType === 'bar' || currentState.chartType === 'stacked' ? 'bar' : 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: getChartOptions()
        };
        
        engagementChart = new Chart(ctx, config);
    }

    /**
     * Get datasets based on chart type
     */
    function getDatasets() {
        const baseDatasets = [
            {
                label: 'Logs',
                data: currentState.data.logs,
                borderColor: COLORS.logs.border,
                backgroundColor: COLORS.logs.background,
                borderWidth: 2,
                tension: 0.3,
                fill: currentState.chartType === 'stacked'
            },
            {
                label: 'Reactions',
                data: currentState.data.reactions,
                borderColor: COLORS.reactions.border,
                backgroundColor: COLORS.reactions.background,
                borderWidth: 2,
                tension: 0.3,
                fill: currentState.chartType === 'stacked'
            },
            {
                label: 'Comments',
                data: currentState.data.comments,
                borderColor: COLORS.comments.border,
                backgroundColor: COLORS.comments.background,
                borderWidth: 2,
                tension: 0.3,
                fill: currentState.chartType === 'stacked'
            }
        ];

        // Add total engagement line for non-stacked charts
        if (currentState.chartType !== 'stacked') {
            baseDatasets.push({
                label: 'Total Engagement',
                data: currentState.data.total_engagement,
                borderColor: COLORS.totalEngagement.border,
                backgroundColor: COLORS.totalEngagement.background,
                borderWidth: 2,
                tension: 0.3,
                borderDash: [5, 5],
                fill: false
            });
        }

        return baseDatasets;
    }

    /**
     * Get chart options based on type
     */
    function getChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(22, 27, 34, 0.95)',
                    titleColor: '#fff',
                    bodyColor: '#a8b3cf',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    titleFont: {
                        size: 13,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 12
                    },
                    callbacks: {
                        title: function(tooltipItems) {
                            return tooltipItems[0].label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(48, 54, 61, 0.3)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#8b949e',
                        font: {
                            size: 10
                        },
                        maxRotation: 45,
                        minRotation: 0,
                        maxTicksLimit: 12
                    }
                },
                y: {
                    beginAtZero: true,
                    stacked: currentState.chartType === 'stacked',
                    grid: {
                        color: 'rgba(48, 54, 61, 0.3)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#8b949e',
                        font: {
                            size: 11
                        },
                        stepSize: 1,
                        precision: 0
                    }
                }
            }
        };
    }

    /**
     * Show/hide loading state
     */
    function showLoading(show) {
        const loader = document.getElementById('chart-loading');
        if (loader) {
            loader.classList.toggle('hidden', !show);
        }
    }

    /**
     * Show/hide empty state
     */
    function showEmptyState(show) {
        const emptyState = document.getElementById('chart-empty-state');
        const chartCanvas = document.getElementById('engagement-chart');
        
        if (emptyState) {
            emptyState.classList.toggle('hidden', !show);
        }
        if (chartCanvas) {
            chartCanvas.parentElement.classList.toggle('hidden', show);
        }
    }

    /**
     * Format date to YYYY-MM-DD
     */
    function formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
