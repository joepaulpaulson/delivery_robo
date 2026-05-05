/**
 * Live Chart Updates for Patient Vitals
 * Uses Chart.js to display real-time heart rate trends
 */

let heartRateChart = null;
const MAX_DATA_POINTS = 50;  // Show last 50 readings

// Chart configuration
const chartConfig = {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Heart Rate (BPM)',
            data: [],
            borderColor: '#00d4ff',
            backgroundColor: 'rgba(0, 212, 255, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
            pointRadius: 0,
            pointHoverRadius: 4
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: 750
        },
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                backgroundColor: 'rgba(26, 34, 50, 0.95)',
                titleColor: '#e8edf4',
                bodyColor: '#8b96a8',
                borderColor: '#2a3647',
                borderWidth: 1
            }
        },
        scales: {
            x: {
                display: true,
                grid: {
                    color: 'rgba(42, 54, 71, 0.3)',
                    drawBorder: false
                },
                ticks: {
                    color: '#5a6578',
                    maxTicksLimit: 8
                }
            },
            y: {
                display: true,
                min: 40,
                max: 140,
                grid: {
                    color: 'rgba(42, 54, 71, 0.3)',
                    drawBorder: false
                },
                ticks: {
                    color: '#5a6578',
                    stepSize: 20
                }
            }
        },
        interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false
        }
    }
};

// Initialize chart
function initChart() {
    const ctx = document.getElementById('heartRateChart');
    if (!ctx) return;
    
    heartRateChart = new Chart(ctx, chartConfig);
    console.log('✓ Heart Rate Chart initialized');
}

// Fetch and update chart data
async function updateChart() {
    try {
        const response = await fetch('/api/vitals/history?limit=50');
        const history = await response.json();
        
        if (!history || history.length === 0) return;
        
        // Extract data
        const labels = history.map(entry => {
            const date = new Date(entry.timestamp);
            return date.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        });
        
        const heartRates = history.map(entry => entry.heart_rate);
        
        // Update chart
        if (heartRateChart) {
            heartRateChart.data.labels = labels;
            heartRateChart.data.datasets[0].data = heartRates;
            
            // Change color if there's an alert
            const hasAlert = heartRates.some(hr => hr < 50 || hr > 120);
            heartRateChart.data.datasets[0].borderColor = hasAlert ? '#ff3b3b' : '#00d4ff';
            heartRateChart.data.datasets[0].backgroundColor = hasAlert ? 
                'rgba(255, 59, 59, 0.1)' : 'rgba(0, 212, 255, 0.1)';
            
            heartRateChart.update('none');  // Update without animation for smoothness
        }
    } catch (error) {
        console.error('Chart update error:', error);
    }
}

// Add single data point (alternative to full refresh)
function addChartDataPoint(timestamp, heartRate) {
    if (!heartRateChart) return;
    
    const time = new Date(timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    heartRateChart.data.labels.push(time);
    heartRateChart.data.datasets[0].data.push(heartRate);
    
    // Keep only last MAX_DATA_POINTS
    if (heartRateChart.data.labels.length > MAX_DATA_POINTS) {
        heartRateChart.data.labels.shift();
        heartRateChart.data.datasets[0].data.shift();
    }
    
    heartRateChart.update('none');
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initChart();
        updateChart();
        // Update chart every 5 seconds
        setInterval(updateChart, 5000);
    });
} else {
    initChart();
    updateChart();
    setInterval(updateChart, 5000);
}