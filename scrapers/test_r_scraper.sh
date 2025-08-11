#!/bin/bash

# Test the fixed R scraper on problematic PDFs

echo "Testing Fixed R Scraper"
echo "======================"

# Test PDF 634 (2020 Q2 Report - NO ACTIVITY)
echo ""
echo "Test 1: PDF 634 (2020 Q2 Report with NO ACTIVITY)"
echo "--------------------------------------------------"
Rscript r_scraper_fixed.R "/Users/jordanharb/Downloads/A7C72804-5062-47E3-BA9B-AF0F40944BD4.pdf" "/tmp/test_634.csv"

if [ -f "/tmp/test_634.csv" ]; then
    echo "Output saved to /tmp/test_634.csv"
    echo "First few lines:"
    head -5 /tmp/test_634.csv
fi

# Test PDF 638 (2019 Interim Report - NO ACTIVITY)
echo ""
echo "Test 2: PDF 638 (2019 Interim Report with NO ACTIVITY)"
echo "-------------------------------------------------------"
Rscript r_scraper_fixed.R "/Users/jordanharb/Downloads/91DF18B7-8C66-473A-B0CC-BE2BE7DDF4B4.pdf" "/tmp/test_638.csv"

if [ -f "/tmp/test_638.csv" ]; then
    echo "Output saved to /tmp/test_638.csv"
    echo "First few lines:"
    head -5 /tmp/test_638.csv
fi

echo ""
echo "Tests complete!"