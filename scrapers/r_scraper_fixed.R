# Fixed R Scraper for Arizona Campaign Finance PDFs
# Handles both "NO ACTIVITY" reports and regular donation reports

TEMP_FUNC <- function(filename) {
  
  # Load required libraries
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
  
  # Read PDF
  tryCatch({
    x <- pdftools::pdf_text(pdf = filename)
  }, error = function(e) {
    cat("ERROR: Failed to read PDF:", e$message, "\n")
    return(tibble())
  })
  
  # Check if this is a "NO ACTIVITY" report
  is_no_activity <- any(str_detect(x, "NO ACTIVITY THIS PERIOD"))
  
  # Get page data for looping
  rptdat <- tibble(txt = x) %>% mutate(pagenum = row_number()) %>% pmap_dfr(
    .f = function(...){
      curtbl <- tibble(...)
      
      # curtbl$txt already contains the text, split it into lines
      str_split(curtbl$txt, "\n")[[1]] %>% tibble(x=.) %>% mutate(
        PageNum = curtbl$pagenum,
        PageType = case_when(
          any(str_detect(x,"Schedule C2")) ~ "Schedule C2",
          any(str_detect(x,"Campaign Finance Report")) ~ "Cover Page",
          TRUE ~ "NONE"
        )
      ) %>% group_by(
        PageNum,
        PageType
      ) %>% nest() %>% ungroup() %>% filter(
        PageType != "NONE"
      )
    }
  )
  
  # If no valid pages found
  if(nrow(rptdat) == 0) {
    return(tibble())
  }
  
  # Safer function to extract cover page data
  safe_extract <- function(data, pattern, default = "") {
    tryCatch({
      # Try to find line containing the pattern
      matching_lines <- data$x[str_detect(data$x, pattern)]
      if(length(matching_lines) > 0) {
        # Clean up the extracted value
        value <- matching_lines[1] %>% 
          str_remove(pattern) %>% 
          str_trim()
        return(value)
      }
      return(default)
    }, error = function(e) {
      return(default)
    })
  }
  
  # Extract cover page data with flexible pattern matching
  cover_data <- rptdat %>% filter(PageType == "Cover Page") %>% .$data %>% .[[1]]
  
  # For "NO ACTIVITY" reports, extract data differently
  if(is_no_activity) {
    # Extract from the structured text (first page shows the data nicely)
    all_text <- paste(cover_data$x, collapse = "\n")
    
    # Extract report title (always "Campaign Finance Report")
    ReportTitle <- "Campaign Finance Report"
    
    # Extract report name (e.g., "2020 Q2 Report" or "Amended 2019 Interim Report")
    report_lines <- cover_data$x[str_detect(cover_data$x, "Report$")]
    ReportName <- if(length(report_lines) > 1) {
      # Skip "Campaign Finance Report" and get the actual report name
      report_lines[!str_detect(report_lines, "Campaign Finance Report")][1] %>% str_trim()
    } else {
      safe_extract(cover_data, "Report ID:.*", "")
    }
    
    # Extract other fields using safer patterns
    Cycle <- safe_extract(cover_data, "Election Cycle:\\s*", "")
    FileDate <- safe_extract(cover_data, "Date Filed:\\s*", "")
    ReportPeriod <- safe_extract(cover_data, "Reporting Period:\\s*", "")
    
    # Committee/Organization info is in the header section
    # Look for committee name (second line usually)
    committee_lines <- cover_data$x[2:10]
    OrgName <- committee_lines[!str_detect(committee_lines, "^(Committee|Treasurer|Phone|Email|Candidate|Office)")][1] %>% 
      str_trim() %>% 
      na_if("") %>% 
      replace_na("")
    
    # Extract contact info
    OrgPhone <- safe_extract(cover_data, "Phone:\\s*", "")
    OrgEmail <- safe_extract(cover_data, "Email:\\s*", "")
    
    # Address is usually the line after treasurer name
    treasurer_line_idx <- which(str_detect(cover_data$x, "^Treasurer:"))
    OrgAddr <- if(length(treasurer_line_idx) > 0 && treasurer_line_idx < length(cover_data$x)) {
      cover_data$x[treasurer_line_idx + 1] %>% str_trim()
    } else {
      ""
    }
    
    # Treasurer name
    TreasurerName <- safe_extract(cover_data, "Treasurer:\\s*", "")
    
    # Return empty donations table but with metadata
    return(
      tibble(
        Rpt_Title = ReportTitle,
        Rpt_Name = ReportName,
        Rpt_Cycle = Cycle,
        Rpt_FileDate = FileDate,
        Rpt_Period = ReportPeriod,
        OrgNm = OrgName,
        OrgEml = OrgEmail,
        OrgTel = OrgPhone,
        OrgAdr = OrgAddr,
        OrgTreasurer = TreasurerName,
        Jurisdiction = "Arizona Secretary of State"
      )
    )
  }
  
  # For regular reports with donations, use safer extraction
  # Find offset for data extraction (empty line position)
  covpg_offset <- tryCatch({
    empty_line_positions <- which(cover_data$x == "")
    if(length(empty_line_positions) > 0) {
      min(empty_line_positions)
    } else {
      7  # Default offset
    }
  }, error = function(e) { 7 })
  
  # Safer line extraction with bounds checking
  safe_get_line <- function(data, line_num, default = "") {
    if(line_num > 0 && line_num <= length(data$x)) {
      return(data$x[line_num] %>% str_trim())
    }
    return(default)
  }
  
  # Extract report metadata using flexible indexing
  ReportTitle <- safe_get_line(cover_data, 1, "Campaign Finance Report")
  
  # Try to find report name near the offset
  ReportName <- safe_get_line(cover_data, covpg_offset + 4, "")
  if(ReportName == "" || str_detect(ReportName, "^(Phone|Email|Treasurer)")) {
    # Try alternative positions
    for(i in (covpg_offset+2):(covpg_offset+6)) {
      test_line <- safe_get_line(cover_data, i, "")
      if(str_detect(test_line, "Report$") && !str_detect(test_line, "Campaign Finance Report")) {
        ReportName <- test_line
        break
      }
    }
  }
  
  # Extract other fields with flexible positioning
  Cycle <- ""
  FileDate <- ""
  ReportPeriod <- ""
  
  # Search for these fields in a range around the expected position
  for(i in max(1, covpg_offset):min(length(cover_data$x), covpg_offset+10)) {
    line <- cover_data$x[i]
    if(str_detect(line, "Election Cycle:")) {
      Cycle <- str_remove(line, "Election Cycle:\\s*") %>% str_trim()
    } else if(str_detect(line, "Date Filed:")) {
      FileDate <- str_remove(line, "Date Filed:\\s*") %>% str_trim()
    } else if(str_detect(line, "Reporting Period:")) {
      ReportPeriod <- str_remove(line, "Reporting Period:\\s*") %>% str_trim()
    }
  }
  
  # Organization info from top of page
  OrgName <- safe_get_line(cover_data, 2, "")
  OrgAddr <- safe_get_line(cover_data, 5, "")
  OrgPhone <- safe_get_line(cover_data, 6, "") %>% str_remove("Phone:\\s*")
  OrgEmail <- safe_get_line(cover_data, 7, "") %>% str_remove("Email:\\s*")
  TreasurerName <- safe_get_line(cover_data, 4, "") %>% str_remove("Treasurer:\\s*")
  
  # Process Schedule C2 (Donations) with safer indexing
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule C2") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      
      pgnum <- curtbl %>% distinct(PageNum) %>% .$PageNum
      pgtyp <- curtbl %>% distinct(PageType) %>% .$PageType
      
      curtbl$data %>% mutate(
        Indexer = case_when(
          str_detect(x, pattern = "^Name:") ~ 1,
          TRUE ~ 0
        ),
        Indexer = cumsum(Indexer)
      ) %>% filter(
        Indexer != 0 &
          x != "" &
          !str_detect(x,"Filed") &
          !str_detect(x,"Total of Individual Contributions") &
          !str_detect(x,"Total of Refunds Given") &
          !str_detect(x,"Net Total of Individual Contributions") &
          !str_detect(x,"Trans. Type:") &
          !str_detect(x,"Original Date:") &
          !str_detect(x,"Original Amount:") &
          !str_detect(x,"Memo:")
      ) %>% transmute(
        Indexer,
        Line = x
      ) %>% group_by(Indexer) %>% nest() %>% ungroup() %>% pmap_dfr(
        .l = .,
        .f = possibly(function(...){
          curtbl <- tibble(...) %>% unnest(cols = c(data))
          
          # Ensure we have enough lines
          if(nrow(curtbl) < 2) {
            return(tibble())
          }
          
          # Safer extraction with bounds checking
          lines <- curtbl$Line
          
          # Parse first line (Name and amounts)
          name_parts <- str_split(lines[1], "\\s{2,}")[[1]]
          name_parts <- name_parts[name_parts != ""]
          
          donor_name <- if(length(name_parts) >= 2) {
            str_remove(name_parts[2], "^Name:\\s*")
          } else ""
          
          donation_date <- if(length(name_parts) >= 3) name_parts[3] else ""
          donation_amt <- if(length(name_parts) >= 4) name_parts[4] else ""
          cycle_amt <- if(length(name_parts) >= 5) name_parts[5] else ""
          
          # Parse second line (Address and type)
          if(length(lines) >= 2) {
            addr_parts <- str_split(lines[2], "\\s{2,}")[[1]]
            addr_parts <- addr_parts[addr_parts != ""]
            
            donor_addr <- if(length(addr_parts) >= 2) {
              str_remove(addr_parts[2], "^Address:\\s*")
            } else ""
            
            # Donation type is usually the last element
            donation_type <- if(length(addr_parts) >= 3) {
              addr_parts[length(addr_parts)]
            } else ""
          } else {
            donor_addr <- ""
            donation_type <- ""
          }
          
          # Parse third line (Occupation)
          donor_occupation <- if(length(lines) >= 3) {
            occ_parts <- str_split(lines[3], "\\s{2,}")[[1]]
            occ_parts <- occ_parts[occ_parts != ""]
            if(length(occ_parts) >= 2) {
              str_remove(occ_parts[2], "^Occupation:\\s*")
            } else "NO INFO"
          } else "NO INFO"
          
          tibble(
            PageNum = pgnum,
            PageType = pgtyp,
            Donor_Name = donor_name,
            Donor_Addr = donor_addr,
            Donor_Occupation = donor_occupation,
            Donation_Date = donation_date,
            Donation_Amt = donation_amt,
            Donation_Type = donation_type,
            CycleToDate_Amt = cycle_amt
          )
        }, otherwise = tibble())
      )
    }, otherwise = tibble())
  )
  
  # Return results with metadata
  if(nrow(Sched_Dat) == 0) {
    # Return metadata even when no donations
    return(
      tibble(
        Rpt_Title = ReportTitle,
        Rpt_Name = ReportName,
        Rpt_Cycle = Cycle,
        Rpt_FileDate = FileDate,
        Rpt_Period = ReportPeriod,
        OrgNm = OrgName,
        OrgEml = OrgEmail,
        OrgTel = OrgPhone,
        OrgAdr = OrgAddr,
        OrgTreasurer = TreasurerName,
        Jurisdiction = "Arizona Secretary of State"
      )
    )
  } else {
    # Add metadata to donations
    return(
      Sched_Dat %>% transmute(
        Rpt_Title = ReportTitle,
        Rpt_Name = ReportName,
        Rpt_Cycle = Cycle,
        Rpt_FileDate = FileDate,
        Rpt_Period = ReportPeriod,
        OrgNm = OrgName,
        OrgEml = OrgEmail,
        OrgTel = OrgPhone,
        OrgAdr = OrgAddr,
        OrgTreasurer = TreasurerName,
        Jurisdiction = "Arizona Secretary of State",
        PageNum,
        PageType,
        Donor_Name,
        Donor_Addr,
        Donor_Occupation,
        Donation_Date,
        Donation_Amt,
        Donation_Type,
        CycleToDate_Amt
      )
    )
  }
}

# Test if called from command line
args <- commandArgs(trailingOnly = TRUE)
if(length(args) >= 2) {
  pdf_path <- args[1]
  output_path <- args[2]
  
  result <- TEMP_FUNC(pdf_path)
  
  if(nrow(result) > 0) {
    # Add metadata columns expected by Python
    result$META_SegmentName <- basename(dirname(pdf_path))
    result$META_FileName <- basename(pdf_path)
    
    # Write CSV
    write.csv(result, output_path, row.names = FALSE)
    
    # Check if donations exist
    if("Donor_Name" %in% names(result) && any(!is.na(result$Donor_Name) & result$Donor_Name != "")) {
      cat("SUCCESS: Processed", sum(!is.na(result$Donor_Name) & result$Donor_Name != ""), "donations\n")
    } else {
      cat("SUCCESS: No donations - Report metadata extracted\n")
    }
  } else {
    # Write empty CSV with headers
    empty_result <- tibble(
      Rpt_Title = character(),
      Rpt_Name = character(),
      Rpt_Cycle = character(),
      Rpt_FileDate = character(),
      Rpt_Period = character(),
      OrgNm = character(),
      OrgEml = character(),
      OrgTel = character(),
      OrgAdr = character(),
      OrgTreasurer = character(),
      Jurisdiction = character(),
      PageNum = numeric(),
      PageType = character(),
      Donor_Name = character(),
      Donor_Addr = character(),
      Donor_Occupation = character(),
      Donation_Date = character(),
      Donation_Amt = character(),
      Donation_Type = character(),
      CycleToDate_Amt = character(),
      META_SegmentName = character(),
      META_FileName = character()
    )
    write.csv(empty_result, output_path, row.names = FALSE)
    cat("WARNING: No data extracted from PDF\n")
  }
}