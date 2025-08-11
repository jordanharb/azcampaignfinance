
# Test PDF field extraction
library(pdftools)
library(dplyr)

# Read PDF and extract text
pdf_file <- commandArgs(trailingOnly = TRUE)[1]
text <- pdf_text(pdf_file)

# Print first page structure
cat("\n=== FIRST PAGE TEXT ===\n")
cat(text[1])

# Look for field markers
cat("\n=== FIELD DETECTION ===\n")
lines <- strsplit(text[1], "\n")[[1]]

# Find organization info
for (i in 1:min(30, length(lines))) {
    line <- lines[i]
    if (grepl("Committee Name|Organization", line, ignore.case = TRUE)) {
        cat("Found org name line:", i, "-", line, "\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\n")
    }
    if (grepl("Email", line, ignore.case = TRUE)) {
        cat("Found email line:", i, "-", line, "\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\n")
    }
    if (grepl("Phone", line, ignore.case = TRUE)) {
        cat("Found phone line:", i, "-", line, "\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\n")
    }
    if (grepl("Address", line, ignore.case = TRUE)) {
        cat("Found address line:", i, "-", line, "\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\n")
    }
    if (grepl("Treasurer", line, ignore.case = TRUE)) {
        cat("Found treasurer line:", i, "-", line, "\n")
        if (i < length(lines)) cat("  Next line:", lines[i+1], "\n")
    }
}
