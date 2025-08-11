#!/usr/bin/env python3
"""
Test script to verify R scraper integration works
Tests with the existing test PDF files
"""

import subprocess
import sys
from pathlib import Path

def test_r_scraper():
    """Test the R scraper with a sample PDF"""
    
    # Find a test PDF
    test_pdf_path = Path("/Users/jordanharb/Documents/az-campaign-finance/pdf-scraper/DonationReportScrapingCode/20250425-001_DonationReportDataScrape/_01-OtherSrc/Donation Filings - Consuelo Hernandez TEST/C-100940_20220101_20220331.pdf")
    
    if not test_pdf_path.exists():
        print(f"❌ Test PDF not found at: {test_pdf_path}")
        return False
    
    print(f"✅ Found test PDF: {test_pdf_path.name}")
    
    # Create simple R test script
    r_test_script = '''
# Test R Scraper
pdf_path <- commandArgs(trailingOnly = TRUE)[1]

# Load required libraries (individual tidyverse components)
suppressMessages({
    library(dplyr)
    library(tidyr)
    library(stringr)
    library(purrr)
    library(tibble)
    library(readr)
    library(lubridate)
    library(pdftools)
})

# Source the scraper function
source_path <- "/Users/jordanharb/Documents/az-campaign-finance/pdf-scraper/DonationReportScrapingCode/20250425-001_DonationReportDataScrape/_04-LocalFunctions/PDFData_DonorReports.R"

if (!file.exists(source_path)) {
    stop(paste("R scraper function not found at:", source_path))
}

source(source_path)

# Test the function
result <- TEMP_FUNC(pdf_path)

if (nrow(result) > 0) {
    cat("SUCCESS: Found", nrow(result), "donations\\n")
    print(head(result, 3))
} else {
    cat("WARNING: No donations found\\n")
}
'''
    
    # Write test script
    test_script_path = Path("test_r_scraper.R")
    with open(test_script_path, 'w') as f:
        f.write(r_test_script)
    
    # Run the test
    print("\n🔧 Testing R scraper integration...")
    try:
        result = subprocess.run(
            ['Rscript', str(test_script_path), str(test_pdf_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print("\n📋 R Output:")
        print(result.stdout)
        
        if result.stderr:
            print("\n⚠️ R Warnings/Errors:")
            print(result.stderr)
        
        # Clean up
        test_script_path.unlink()
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ R script timed out")
        test_script_path.unlink()
        return False
    except FileNotFoundError:
        print("❌ Rscript not found. Make sure R is installed and in PATH")
        test_script_path.unlink()
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        test_script_path.unlink()
        return False

def check_r_packages():
    """Check if required R packages are installed"""
    
    r_check_script = '''
    # Check individual tidyverse components instead of full tidyverse
    required_packages <- c("dplyr", "tidyr", "stringr", "purrr", "tibble", "readr", "pdftools", "lubridate")
    
    for (pkg in required_packages) {
        if (!require(pkg, character.only = TRUE, quietly = TRUE)) {
            cat("MISSING:", pkg, "\\n")
        } else {
            cat("OK:", pkg, "\\n")
        }
    }
    '''
    
    print("\n📦 Checking R packages...")
    result = subprocess.run(
        ['Rscript', '-e', r_check_script],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    if "MISSING" in result.stdout:
        print("\n⚠️ Some R packages are missing. Install them with:")
        print("  R -e 'install.packages(c(\"dplyr\", \"tidyr\", \"stringr\", \"purrr\", \"tibble\", \"readr\", \"pdftools\", \"lubridate\"))'")
        return False
    
    return True

def main():
    print("="*70)
    print("R SCRAPER INTEGRATION TEST")
    print("="*70)
    
    # Check R is installed
    try:
        result = subprocess.run(['Rscript', '--version'], capture_output=True, text=True)
        print(f"✅ R is installed: {result.stderr.strip()}")
    except FileNotFoundError:
        print("❌ R is not installed or Rscript is not in PATH")
        print("Please install R from: https://www.r-project.org/")
        sys.exit(1)
    
    # Check packages
    if not check_r_packages():
        print("\n❌ Please install missing R packages before continuing")
        sys.exit(1)
    
    # Test the scraper
    if test_r_scraper():
        print("\n✅ R scraper integration test PASSED!")
        print("\nYou can now run the full pipeline with:")
        print("  python step3_process_pdfs_v2.py --limit 5")
        print("  python step3_process_pdfs_v2.py --upload --entity 201800057")
    else:
        print("\n❌ R scraper integration test FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()