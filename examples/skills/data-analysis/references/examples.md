# Data Analysis Skill - Usage Examples

## Basic Usage

### Loading and Inspecting Data

```python
from scripts.analyze import load_dataset, basic_statistics

# Load dataset
df = load_dataset('/path/to/data.csv')

# Get basic statistics
stats = basic_statistics(df)
print(f"Dataset shape: {stats['shape']}")
print(f"Columns: {stats['columns']}")
print(f"Missing values: {stats['missing_values']}")
```

### Statistical Analysis

```python
from scripts.analyze import correlation_analysis, detect_outliers

# Correlation analysis
corr_matrix = correlation_analysis(df, method='pearson')
print("Correlation Matrix:")
print(corr_matrix)

# Outlier detection
outliers = detect_outliers(df, 'price', method='iqr')
print(f"Found {outliers['num_outliers']} outliers")
```

### Visualization

```python
from scripts.visualize import plot_distribution, plot_correlation_matrix, save_plot

# Distribution plot
fig1 = plot_distribution(df, 'price', bins=50)
save_plot(fig1, 'price_distribution.png')

# Correlation heatmap
fig2 = plot_correlation_matrix(df)
save_plot(fig2, 'correlations.png')
```

## Common Analysis Patterns

### 1. Sales Data Analysis

```python
# Load sales data
df = load_dataset('sales_data.csv')

# Group by month
from scripts.analyze import group_analysis
monthly_sales = group_analysis(df, 'month', 'sales', agg_func='sum')

# Visualize trends
from scripts.visualize import plot_bar_chart
fig = plot_bar_chart(monthly_sales, 'month', 'sales',
                     title='Monthly Sales Trends')
save_plot(fig, 'monthly_sales.png')
```

### 2. Customer Behavior Analysis

```python
# Load customer data
df = load_dataset('customers.csv')

# Statistical overview
stats = basic_statistics(df)

# Distribution of customer ages
fig1 = plot_distribution(df, 'age', title='Customer Age Distribution')

# Purchase patterns by segment
from scripts.analyze import group_analysis
segment_analysis = group_analysis(df, 'segment', 'purchase_amount',
                                  agg_func='mean')
```

### 3. Time Series Analysis

```python
# Load time series data
df = load_dataset('stock_prices.csv')

# Analyze trends
from scripts.analyze import time_series_analysis
ts_stats = time_series_analysis(df, 'date', 'price', freq='D')
print(f"Trend slope: {ts_stats['trend_slope']}")
print(f"R-squared: {ts_stats['trend_r_squared']}")

# Visualize with moving average
from scripts.visualize import plot_time_series
fig = plot_time_series(df, 'date', 'price', rolling_window=30)
save_plot(fig, 'price_trends.png')
```

### 4. Comparative Analysis

```python
# Compare multiple groups
df = load_dataset('experiment_results.csv')

# Box plot comparison
from scripts.visualize import plot_box_plot
fig = plot_box_plot(df, ['control_group', 'test_group_a', 'test_group_b'])
save_plot(fig, 'group_comparison.png')

# Statistical testing
from scripts.analyze import group_analysis
group_stats = group_analysis(df, 'group', 'metric', agg_func='mean')
```

## Complete Analysis Workflow

```python
# 1. Load data
df = load_dataset('data.csv')

# 2. Inspect and clean
stats = basic_statistics(df)
print(f"Shape: {stats['shape']}")
print(f"Missing: {stats['missing_values']}")

# Handle missing values
df = df.dropna()

# 3. Explore distributions
for col in df.select_dtypes(include=['float64', 'int64']).columns:
    fig = plot_distribution(df, col)
    save_plot(fig, f'{col}_distribution.png')

# 4. Find correlations
corr = correlation_analysis(df)
fig = plot_correlation_matrix(df)
save_plot(fig, 'correlations.png')

# 5. Detect outliers
for col in ['price', 'quantity', 'revenue']:
    outliers = detect_outliers(df, col, method='iqr')
    if outliers['num_outliers'] > 0:
        print(f"Warning: {outliers['num_outliers']} outliers in {col}")

# 6. Create dashboard
from scripts.visualize import create_dashboard
fig = create_dashboard(df, output_file='dashboard.png')

# 7. Generate report
print("\nAnalysis Complete!")
print(f"Total rows: {len(df)}")
print(f"Total columns: {len(df.columns)}")
print(f"Files generated: distribution plots, correlations, dashboard")
```

## Tips for Effective Analysis

1. **Always inspect your data first**
   - Check shape, data types, missing values
   - Look for obvious errors or inconsistencies

2. **Choose appropriate visualizations**
   - Distributions: histograms, box plots
   - Relationships: scatter plots, correlation matrices
   - Trends: line plots, time series
   - Comparisons: bar charts, box plots

3. **Handle missing data carefully**
   - Understand why data is missing
   - Choose appropriate strategy (drop, fill, interpolate)

4. **Watch for outliers**
   - Identify using IQR or Z-score methods
   - Decide whether to keep or remove them

5. **Document your findings**
   - Save all plots and statistics
   - Write clear explanations
   - Note any assumptions or limitations
