# Data

This directory contains the source and processed datasets used in the project.

## Raw Data

The raw datasets are sourced from Statistics Canada.
The original CSV files are not included in the repository because of their size.
Source: Statistics Canada 

### `14100022.csv`

Table: Labour force characteristics by industry, monthly, unadjusted for seasonality  
Table number: 14-10-0022-01  
Source URL: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201  
Frequency: Monthly  

### `14100063.csv`

Table: Employee wages by industry, monthly, unadjusted for seasonality  
Table number: 14-10-0063-01  
Source URL: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301  
Frequency: Monthly  

### `14100372.csv`

Table: Job vacancies, payroll employees, and job vacancy rate by industry sector, monthly, unadjusted for seasonality  
Table number: 14-10-0372-01  
Source URL: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410037201  
Frequency: Monthly  

## Processed Data

The `processed/` directory contains datasets generated from the raw data for analysis.

## Directory Structure

data/  
├── README.md  
├── raw/ # Original source files; not included in Git  
└── processed/ # Analysis-ready datasets  
