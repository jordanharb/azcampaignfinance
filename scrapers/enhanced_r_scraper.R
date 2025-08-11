# Enhanced R Scraper for both Donations and Expenses
# Based on the original PDFData_DonorReports.R but extended to handle all schedules

PROCESS_PDF_COMPLETE <- function(filename) {
  
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
    return(list(donations = tibble(), expenses = tibble()))
  })
  
  # Get page data for looping
  rptdat <- tibble(txt = x) %>% mutate(pagenum = row_number()) %>% pmap_dfr(
    .f = function(...){
      curtbl <- tibble(...)
      
      read_lines(curtbl$txt) %>% tibble(x=.) %>% mutate(
        PageNum = curtbl$pagenum,
        PageType = case_when(
          any(str_detect(x,"Schedule C2")) ~ "Schedule C2",
          any(str_detect(x,"Schedule E1")) ~ "Schedule E1", 
          any(str_detect(x,"Schedule E3a")) ~ "Schedule E3a",
          any(str_detect(x,"Schedule E3")) & !any(str_detect(x,"Schedule E3a")) ~ "Schedule E3",
          any(str_detect(x,"Schedule E4")) ~ "Schedule E4",
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
    return(list(donations = tibble(), expenses = tibble()))
  }
  
  # Extract cover page info (same as original)
  covpg_offset <- tryCatch({
    rptdat$data[[1]] %>% mutate(n=row_number()) %>% 
      filter(x == "") %>% summarize(val = min(n)) %>% 
      unlist() %>% unname()
  }, error = function(e) { 7 })  # Default offset if error
  
  # Safely extract cover page fields
  safe_extract <- function(data, slice_num, pattern = NULL) {
    tryCatch({
      val <- data %>% slice(slice_num) %>% unlist() %>% unname() %>% str_trim()
      if(!is.null(pattern)) val <- str_remove(val, pattern)
      return(val)
    }, error = function(e) { return("") })
  }
  
  cover_data <- rptdat %>% filter(PageType == "Cover Page") %>% .$data %>% bind_rows()
  
  ReportTitle <- safe_extract(cover_data, 1)
  ReportName <- safe_extract(cover_data, covpg_offset+4)
  Cycle <- safe_extract(cover_data, covpg_offset+5, "Election Cycle: ")
  FileDate <- safe_extract(cover_data, covpg_offset+6, "Date Filed: ")
  ReportPeriod <- safe_extract(cover_data, covpg_offset+7, "Reporting Period: ")
  OrgName <- safe_extract(cover_data, 2)
  OrgAddr <- safe_extract(cover_data, 5)
  OrgPhone <- safe_extract(cover_data, 6, "Phone: ")
  OrgEmail <- safe_extract(cover_data, 7, "Email: ")
  TreasurerName <- safe_extract(cover_data, 4, "Treasurer: ")
  
  # Process Schedule C2 (Donations) - Using safer indexing
  donations_data <- tryCatch({
    process_schedule_c2_safe(rptdat, ReportTitle, ReportName, Cycle, FileDate, 
                             ReportPeriod, OrgName, OrgEmail, OrgPhone, 
                             OrgAddr, TreasurerName)
  }, error = function(e) {
    cat("WARNING: Error processing donations:", e$message, "\n")
    tibble()
  })
  
  # Process Schedule E1 (Operating Expenses)
  expenses_e1 <- tryCatch({
    process_schedule_e1(rptdat)
  }, error = function(e) {
    cat("WARNING: Error processing E1 expenses:", e$message, "\n")
    tibble()
  })
  
  # Process Schedule E3 (Contributions to Organizations)
  expenses_e3 <- tryCatch({
    process_schedule_e3(rptdat)
  }, error = function(e) {
    cat("WARNING: Error processing E3 expenses:", e$message, "\n")
    tibble()
  })
  
  # Process Schedule E3a (Contributions to Candidates)
  expenses_e3a <- tryCatch({
    process_schedule_e3a(rptdat)
  }, error = function(e) {
    cat("WARNING: Error processing E3a expenses:", e$message, "\n")
    tibble()
  })
  
  # Combine all expenses
  expenses_data <- bind_rows(
    expenses_e1,
    expenses_e3,
    expenses_e3a
  )
  
  # Add report metadata to expenses
  if(nrow(expenses_data) > 0) {
    expenses_data <- expenses_data %>% mutate(
      Rpt_Title = ReportTitle,
      Rpt_Name = ReportName,
      Rpt_Cycle = Cycle,
      Rpt_FileDate = FileDate,
      Rpt_Period = ReportPeriod,
      OrgNm = OrgName,
      OrgEml = OrgEmail,
      OrgTel = OrgPhone,
      OrgAdr = OrgAddr,
      OrgTreasurer = TreasurerName
    )
  }
  
  return(list(
    donations = donations_data,
    expenses = expenses_data,
    report_info = tibble(
      Rpt_Title = ReportTitle,
      Rpt_Name = ReportName,
      Rpt_Cycle = Cycle,
      Rpt_FileDate = FileDate,
      Rpt_Period = ReportPeriod,
      OrgNm = OrgName
    )
  ))
}

# Safer version of Schedule C2 processing with better error handling
process_schedule_c2_safe <- function(rptdat, ReportTitle, ReportName, Cycle, FileDate, 
                                     ReportPeriod, OrgName, OrgEmail, OrgPhone, 
                                     OrgAddr, TreasurerName) {
  
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
          !str_detect(x,"Net Total of Individual Contributions")
      ) %>% transmute(
        Indexer,
        Line = x
      ) %>% group_by(Indexer) %>% nest() %>% ungroup() %>% pmap_dfr(
        .l = .,
        .f = possibly(function(...){
          curtbl <- tibble(...) %>% unnest(cols = c(data))
          
          # Safer extraction with bounds checking
          lines <- curtbl$Line
          if(length(lines) < 2) return(tibble())
          
          # Parse name row safely
          name_parts <- str_split(lines[1], "  ")[[1]] %>% .[. != ""]
          donor_name <- if(length(name_parts) >= 2) name_parts[2] else ""
          donation_date <- if(length(name_parts) >= 3) name_parts[3] else ""
          donation_amt <- if(length(name_parts) >= 4) name_parts[4] else ""
          cycle_amt <- if(length(name_parts) >= 5) name_parts[5] else ""
          
          # Parse address row safely
          addr_parts <- if(length(lines) >= 2) {
            str_split(lines[2], "  ")[[1]] %>% .[. != ""]
          } else { c() }
          
          donor_addr <- if(length(addr_parts) >= 2) addr_parts[2] else ""
          donation_type <- if(length(addr_parts) >= 3) addr_parts[length(addr_parts)] else ""
          
          # Parse occupation safely
          donor_occupation <- if(length(lines) >= 3) {
            occ_parts <- str_split(lines[3], "  ")[[1]] %>% .[. != ""]
            if(length(occ_parts) >= 2) occ_parts[2] else "NO INFO"
          } else { "NO INFO" }
          
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
  
  if(nrow(Sched_Dat) == 0) {
    return(tibble())
  }
  
  # Add report metadata
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
}

# Process Schedule E1 - Operating Expenses
process_schedule_e1 <- function(rptdat) {
  rptdat %>% filter(PageType == "Schedule E1") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      # Extract expense entries (simplified for now)
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Payee:"))
      ) %>% filter(Indexer > 0) %>% 
      group_by(Indexer) %>% 
      summarize(
        PageNum = pgnum,
        PageType = "Schedule E1",
        ScheduleType = "E1",
        ExpenseType = "Operating",
        PayeeName = first(x[str_detect(x, "^Payee:")]) %>% str_remove("^Payee: "),
        ExpenseDate = first(x[str_detect(x, "Date:")]) %>% str_remove(".*Date: "),
        ExpenseAmt = first(x[str_detect(x, "Amount:")]) %>% str_remove(".*Amount: "),
        ExpensePurpose = first(x[str_detect(x, "Purpose:")]) %>% str_remove(".*Purpose: "),
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
}

# Process Schedule E3 - Contributions to Organizations
process_schedule_e3 <- function(rptdat) {
  rptdat %>% filter(PageType == "Schedule E3") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Organization:"))
      ) %>% filter(Indexer > 0) %>%
      group_by(Indexer) %>%
      summarize(
        PageNum = pgnum,
        PageType = "Schedule E3",
        ScheduleType = "E3",
        ExpenseType = "Contribution to Org",
        PayeeName = first(x[str_detect(x, "^Organization:")]) %>% str_remove("^Organization: "),
        ExpenseDate = first(x[str_detect(x, "Date:")]) %>% str_remove(".*Date: "),
        ExpenseAmt = first(x[str_detect(x, "Amount:")]) %>% str_remove(".*Amount: "),
        BeneficiaryCommittee = PayeeName,
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
}

# Process Schedule E3a - Contributions to Candidates
process_schedule_e3a <- function(rptdat) {
  rptdat %>% filter(PageType == "Schedule E3a") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Candidate:"))
      ) %>% filter(Indexer > 0) %>%
      group_by(Indexer) %>%
      summarize(
        PageNum = pgnum,
        PageType = "Schedule E3a", 
        ScheduleType = "E3a",
        ExpenseType = "Contribution to Candidate",
        PayeeName = first(x[str_detect(x, "^Candidate:")]) %>% str_remove("^Candidate: "),
        ExpenseDate = first(x[str_detect(x, "Date:")]) %>% str_remove(".*Date: "),
        ExpenseAmt = first(x[str_detect(x, "Amount:")]) %>% str_remove(".*Amount: "),
        BeneficiaryCandidate = PayeeName,
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
}

# Command line interface
args <- commandArgs(trailingOnly = TRUE)
if(length(args) >= 2) {
  pdf_path <- args[1]
  output_base <- args[2]
  
  result <- PROCESS_PDF_COMPLETE(pdf_path)
  
  # Write donations CSV
  if(nrow(result$donations) > 0) {
    write.csv(result$donations, paste0(output_base, "_donations.csv"), row.names = FALSE)
    cat("SUCCESS: Processed", nrow(result$donations), "donations\n")
  } else {
    # Write empty CSV with headers
    write.csv(result$donations, paste0(output_base, "_donations.csv"), row.names = FALSE)
    cat("WARNING: No donations found in PDF\n")
  }
  
  # Write expenses CSV
  if(nrow(result$expenses) > 0) {
    write.csv(result$expenses, paste0(output_base, "_expenses.csv"), row.names = FALSE)
    cat("SUCCESS: Processed", nrow(result$expenses), "expenses\n")
  }
}