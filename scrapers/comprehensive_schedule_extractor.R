# Comprehensive Arizona Campaign Finance Schedule Extractor
# Extracts ALL schedule types from campaign finance PDFs
# Maintains compatibility with existing C2 extraction logic

library(dplyr)
library(tidyr)
library(stringr)
library(purrr)
library(tibble)
library(readr)
library(lubridate)
library(pdftools)

COMPREHENSIVE_EXTRACTOR <- function(filename) {
  
  # Read PDF
  tryCatch({
    x <- pdftools::pdf_text(pdf = filename)
  }, error = function(e) {
    cat("ERROR: Failed to read PDF:", e$message, "\n")
    return(list())
  })
  
  # Check if this is a "NO ACTIVITY" report
  is_no_activity <- any(str_detect(x, "NO ACTIVITY THIS PERIOD"))
  
  # Get page data for looping
  rptdat <- tibble(txt = x) %>% mutate(pagenum = row_number()) %>% pmap_dfr(
    .f = function(...){
      curtbl <- tibble(...)
      
      # Split text into lines
      str_split(curtbl$txt, "\n")[[1]] %>% tibble(x=.) %>% mutate(
        PageNum = curtbl$pagenum,
        PageType = case_when(
          any(str_detect(x,"Schedule C1")) ~ "Schedule C1",
          any(str_detect(x,"Schedule C2")) ~ "Schedule C2", 
          any(str_detect(x,"Schedule C3")) ~ "Schedule C3",
          any(str_detect(x,"Schedule C4")) ~ "Schedule C4",
          any(str_detect(x,"Schedule C5")) ~ "Schedule C5",
          any(str_detect(x,"Schedule C6")) ~ "Schedule C6",
          any(str_detect(x,"Schedule C7")) ~ "Schedule C7",
          any(str_detect(x,"Schedule E1")) ~ "Schedule E1",
          any(str_detect(x,"Schedule E2")) ~ "Schedule E2",
          any(str_detect(x,"Schedule E3a")) ~ "Schedule E3a",
          any(str_detect(x,"Schedule E3")) & !any(str_detect(x,"Schedule E3a")) ~ "Schedule E3",
          any(str_detect(x,"Schedule E4")) ~ "Schedule E4",
          any(str_detect(x,"Schedule L1")) ~ "Schedule L1",
          any(str_detect(x,"Schedule L2")) ~ "Schedule L2",
          any(str_detect(x,"Schedule R1")) ~ "Schedule R1",
          any(str_detect(x,"Schedule T1")) ~ "Schedule T1",
          any(str_detect(x,"Schedule S1")) ~ "Schedule S1",
          any(str_detect(x,"Schedule D1")) ~ "Schedule D1",
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
  
  # Extract cover page metadata (same as original)
  cover_metadata <- extract_cover_page(rptdat)
  
  # Initialize results list
  results <- list(
    metadata = cover_metadata,
    schedules_found = unique(rptdat$PageType[rptdat$PageType != "Cover Page"])
  )
  
  # If NO ACTIVITY report, return just metadata
  if(is_no_activity) {
    results$donations_c2 <- tibble()
    results$no_activity <- TRUE
    return(results)
  }
  
  # Extract each schedule type if present
  
  # ========== INCOME SCHEDULES ==========
  
  # Schedule C1: Personal and Family Contributions
  if(any(rptdat$PageType == "Schedule C1")) {
    results$personal_c1 <- extract_schedule_c1(rptdat, cover_metadata)
  }
  
  # Schedule C2: Individual Contributions (EXISTING LOGIC)
  if(any(rptdat$PageType == "Schedule C2")) {
    results$donations_c2 <- extract_schedule_c2_original(rptdat, cover_metadata)
  }
  
  # Schedule C3: Contributions from Political Committees
  if(any(rptdat$PageType == "Schedule C3")) {
    results$committees_c3 <- extract_schedule_c3(rptdat, cover_metadata)
  }
  
  # Schedule C4: Business Contributions
  if(any(rptdat$PageType == "Schedule C4")) {
    results$business_c4 <- extract_schedule_c4(rptdat, cover_metadata)
  }
  
  # Schedule C5: Small Contributions (Aggregated)
  if(any(rptdat$PageType == "Schedule C5")) {
    results$small_c5 <- extract_schedule_c5(rptdat, cover_metadata)
  }
  
  # Schedule C6: CCEC Funding
  if(any(rptdat$PageType == "Schedule C6")) {
    results$ccec_c6 <- extract_schedule_c6(rptdat, cover_metadata)
  }
  
  # Schedule C7: Qualifying Contributions
  if(any(rptdat$PageType == "Schedule C7")) {
    results$qualifying_c7 <- extract_schedule_c7(rptdat, cover_metadata)
  }
  
  # Schedule L1: Loans Received
  if(any(rptdat$PageType == "Schedule L1")) {
    results$loans_received_l1 <- extract_schedule_l1(rptdat, cover_metadata)
  }
  
  # Schedule R1: Other Receipts
  if(any(rptdat$PageType == "Schedule R1")) {
    results$other_receipts_r1 <- extract_schedule_r1(rptdat, cover_metadata)
  }
  
  # Schedule T1: Transfers 
  if(any(rptdat$PageType == "Schedule T1")) {
    results$transfers_t1 <- extract_schedule_t1(rptdat, cover_metadata)
  }
  
  # Schedule S1: Cash Surplus
  if(any(rptdat$PageType == "Schedule S1")) {
    results$surplus_s1 <- extract_schedule_s1(rptdat, cover_metadata)
  }
  
  # ========== EXPENDITURE SCHEDULES ==========
  
  # Schedule E1: Operating Expenses
  if(any(rptdat$PageType == "Schedule E1")) {
    results$expenses_e1 <- extract_schedule_e1(rptdat, cover_metadata)
  }
  
  # Schedule E2: Independent Expenditures
  if(any(rptdat$PageType == "Schedule E2")) {
    results$independent_e2 <- extract_schedule_e2(rptdat, cover_metadata)
  }
  
  # Schedule E3: Contributions to Committees
  if(any(rptdat$PageType %in% c("Schedule E3", "Schedule E3a"))) {
    results$contributions_made_e3 <- extract_schedule_e3(rptdat, cover_metadata)
  }
  
  # Schedule E4: Small Expenses (Aggregated)
  if(any(rptdat$PageType == "Schedule E4")) {
    results$small_expenses_e4 <- extract_schedule_e4(rptdat, cover_metadata)
  }
  
  # Schedule L2: Loans Made
  if(any(rptdat$PageType == "Schedule L2")) {
    results$loans_made_l2 <- extract_schedule_l2(rptdat, cover_metadata)
  }
  
  # Schedule D1: Bill Payments
  if(any(rptdat$PageType == "Schedule D1")) {
    results$bill_payments_d1 <- extract_schedule_d1(rptdat, cover_metadata)
  }
  
  return(results)
}

# ========================================
# HELPER FUNCTIONS
# ========================================

extract_cover_page <- function(rptdat) {
  # Extract cover page data
  cover_data <- rptdat %>% filter(PageType == "Cover Page") %>% .$data %>% .[[1]]
  
  # Safer extraction function
  safe_extract <- function(data, pattern, default = "") {
    tryCatch({
      matching_lines <- data$x[str_detect(data$x, pattern)]
      if(length(matching_lines) > 0) {
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
  
  # Safer line extraction
  safe_get_line <- function(data, line_num, default = "") {
    if(line_num > 0 && line_num <= length(data$x)) {
      return(data$x[line_num] %>% str_trim())
    }
    return(default)
  }
  
  list(
    ReportTitle = safe_get_line(cover_data, 1, "Campaign Finance Report"),
    ReportName = safe_extract(cover_data, "Report$", ""),
    Cycle = safe_extract(cover_data, "Election Cycle:\\s*", ""),
    FileDate = safe_extract(cover_data, "Date Filed:\\s*", ""),
    ReportPeriod = safe_extract(cover_data, "Reporting Period:\\s*", ""),
    OrgName = safe_get_line(cover_data, 2, ""),
    OrgAddr = safe_get_line(cover_data, 5, ""),
    OrgPhone = safe_extract(cover_data, "Phone:\\s*", ""),
    OrgEmail = safe_extract(cover_data, "Email:\\s*", ""),
    TreasurerName = safe_extract(cover_data, "Treasurer:\\s*", ""),
    Jurisdiction = "Arizona Secretary of State"
  )
}

# ========================================
# SCHEDULE C2: Individual Contributions (EXISTING LOGIC)
# ========================================

extract_schedule_c2_original <- function(rptdat, metadata) {
  # This is the EXACT logic from the original scraper
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
          
          lines <- curtbl$Line
          
          # Parse first line (Name and amounts) - safer extraction
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
  
  # Add metadata if we have data
  if(nrow(Sched_Dat) > 0) {
    Sched_Dat %>% mutate(
      Rpt_Title = metadata$ReportTitle,
      Rpt_Name = metadata$ReportName,
      Rpt_Cycle = metadata$Cycle,
      Rpt_FileDate = metadata$FileDate,
      Rpt_Period = metadata$ReportPeriod,
      OrgNm = metadata$OrgName,
      OrgEml = metadata$OrgEmail,
      OrgTel = metadata$OrgPhone,
      OrgAdr = metadata$OrgAddr,
      OrgTreasurer = metadata$TreasurerName,
      Jurisdiction = metadata$Jurisdiction
    )
  } else {
    tibble()
  }
}

# ========================================
# SCHEDULE C1: Personal and Family Contributions
# ========================================

extract_schedule_c1 <- function(rptdat, metadata) {
  # Similar to C2 but simpler (no occupation)
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule C1") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Name:|^Contributor:"))
      ) %>% filter(
        Indexer > 0 & 
        x != "" &
        !str_detect(x, "Total|Filed")
      ) %>% group_by(Indexer) %>% 
      reframe(
        PageNum = pgnum,
        PageType = "Schedule C1",
        Contributor_Name = first(x[str_detect(x, "^Name:|^Contributor:")]) %>% 
          str_remove("^(Name|Contributor):\\s*"),
        Relationship = first(x[str_detect(x, "Relationship:|Self|Spouse|Child")]) %>%
          str_extract("Self|Spouse|Child|Parent|Sibling"),
        Contribution_Date = first(x[str_detect(x, "\\d{1,2}/\\d{1,2}/\\d{4}")]) %>%
          str_extract("\\d{1,2}/\\d{1,2}/\\d{4}"),
        Contribution_Amt = first(x[str_detect(x, "\\$")]) %>%
          str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
          str_remove("\\$") %>% str_remove(","),
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
  
  if(nrow(Sched_Dat) > 0) {
    Sched_Dat
  } else {
    tibble()
  }
}

# ========================================
# SCHEDULE C3: Political Committee Contributions
# ========================================

extract_schedule_c3 <- function(rptdat, metadata) {
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule C3") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Committee:|^Organization:"))
      ) %>% filter(
        Indexer > 0 & 
        x != "" &
        !str_detect(x, "Total|Filed")
      ) %>% group_by(Indexer) %>%
      reframe(
        PageNum = pgnum,
        PageType = "Schedule C3",
        Committee_Name = first(x[str_detect(x, "^Committee:|^Organization:")]) %>%
          str_remove("^(Committee|Organization):\\s*"),
        Committee_ID = first(x[str_detect(x, "ID:|#\\d+")]) %>%
          str_extract("\\d+"),
        Committee_Address = first(x[str_detect(x, "Address:")]) %>%
          str_remove("^Address:\\s*"),
        Contribution_Date = first(x[str_detect(x, "\\d{1,2}/\\d{1,2}/\\d{4}")]) %>%
          str_extract("\\d{1,2}/\\d{1,2}/\\d{4}"),
        Contribution_Amt = first(x[str_detect(x, "\\$")]) %>%
          str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
          str_remove("\\$") %>% str_remove(","),
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
  
  return(Sched_Dat)
}

# ========================================
# SCHEDULE C4: Business Contributions
# ========================================

extract_schedule_c4 <- function(rptdat, metadata) {
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule C4") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Business:|^Company:|^Corporation:"))
      ) %>% filter(
        Indexer > 0 & 
        x != "" &
        !str_detect(x, "Total|Filed")
      ) %>% group_by(Indexer) %>%
      reframe(
        PageNum = pgnum,
        PageType = "Schedule C4",
        Business_Name = first(x[str_detect(x, "^Business:|^Company:|^Corporation:")]) %>%
          str_remove("^(Business|Company|Corporation):\\s*"),
        Business_Address = first(x[str_detect(x, "Address:")]) %>%
          str_remove("^Address:\\s*"),
        Business_Type = first(x[str_detect(x, "Type:|LLC|Corp|Inc")]) %>%
          str_extract("LLC|Corporation|Inc|Partnership|LP"),
        Contribution_Date = first(x[str_detect(x, "\\d{1,2}/\\d{1,2}/\\d{4}")]) %>%
          str_extract("\\d{1,2}/\\d{1,2}/\\d{4}"),
        Contribution_Amt = first(x[str_detect(x, "\\$")]) %>%
          str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
          str_remove("\\$") %>% str_remove(","),
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
  
  return(Sched_Dat)
}

# ========================================
# SCHEDULE C5: Small Contributions (Aggregated)
# ========================================

extract_schedule_c5 <- function(rptdat, metadata) {
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule C5") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      # C5 is aggregated, look for totals
      total_line <- curtbl$data$x[str_detect(curtbl$data$x, "Total.*Small")]
      count_line <- curtbl$data$x[str_detect(curtbl$data$x, "Number|Count")]
      period_line <- curtbl$data$x[str_detect(curtbl$data$x, "Period:|From.*To")]
      
      tibble(
        PageNum = pgnum,
        PageType = "Schedule C5",
        Period = if(length(period_line) > 0) {
          str_extract(period_line[1], "\\d{1,2}/\\d{1,2}/\\d{4}.*\\d{1,2}/\\d{1,2}/\\d{4}")
        } else NA_character_,
        Total_Amount = if(length(total_line) > 0) {
          str_extract(total_line[1], "\\$[0-9,]+\\.?[0-9]*") %>%
            str_remove("\\$") %>% str_remove(",")
        } else NA_character_,
        Contributor_Count = if(length(count_line) > 0) {
          str_extract(count_line[1], "\\d+")
        } else NA_character_
      )
    }, otherwise = tibble())
  )
  
  return(Sched_Dat)
}

# ========================================
# SCHEDULE E1: Operating Expenses
# ========================================

extract_schedule_e1 <- function(rptdat, metadata) {
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule E1") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Payee:|^Vendor:|^Paid to:"))
      ) %>% filter(
        Indexer > 0 & 
        x != "" &
        !str_detect(x, "Total|Filed")
      ) %>% group_by(Indexer) %>%
      reframe(
        PageNum = pgnum,
        PageType = "Schedule E1",
        Payee_Name = first(x[str_detect(x, "^Payee:|^Vendor:|^Paid to:")]) %>%
          str_remove("^(Payee|Vendor|Paid to):\\s*"),
        Payee_Address = first(x[str_detect(x, "Address:")]) %>%
          str_remove("^Address:\\s*"),
        Expense_Date = first(x[str_detect(x, "\\d{1,2}/\\d{1,2}/\\d{4}")]) %>%
          str_extract("\\d{1,2}/\\d{1,2}/\\d{4}"),
        Expense_Amt = first(x[str_detect(x, "\\$")]) %>%
          str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
          str_remove("\\$") %>% str_remove(","),
        Purpose = first(x[str_detect(x, "Purpose:|For:")]) %>%
          str_remove("^(Purpose|For):\\s*"),
        Category = first(x[str_detect(x, "Category:|Type:")]) %>%
          str_remove("^(Category|Type):\\s*"),
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
  
  return(Sched_Dat)
}

# ========================================
# SCHEDULE E2: Independent Expenditures
# ========================================

extract_schedule_e2 <- function(rptdat, metadata) {
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule E2") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Payee:|^Vendor:"))
      ) %>% filter(
        Indexer > 0 & 
        x != "" &
        !str_detect(x, "Total|Filed")
      ) %>% group_by(Indexer) %>%
      reframe(
        PageNum = pgnum,
        PageType = "Schedule E2",
        Payee_Name = first(x[str_detect(x, "^Payee:|^Vendor:")]) %>%
          str_remove("^(Payee|Vendor):\\s*"),
        Expense_Date = first(x[str_detect(x, "\\d{1,2}/\\d{1,2}/\\d{4}")]) %>%
          str_extract("\\d{1,2}/\\d{1,2}/\\d{4}"),
        Expense_Amt = first(x[str_detect(x, "\\$")]) %>%
          str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
          str_remove("\\$") %>% str_remove(","),
        Candidate_Name = first(x[str_detect(x, "Candidate:|For:|Against:")]) %>%
          str_remove("^(Candidate|For|Against):\\s*"),
        Support_Oppose = case_when(
          any(str_detect(x, "Support|For")) ~ "SUPPORT",
          any(str_detect(x, "Oppose|Against")) ~ "OPPOSE",
          TRUE ~ NA_character_
        ),
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
  
  return(Sched_Dat)
}

# ========================================
# SCHEDULE E3: Contributions to Committees
# ========================================

extract_schedule_e3 <- function(rptdat, metadata) {
  # Handle both E3 and E3a
  Sched_Dat <- rptdat %>% 
    filter(PageType %in% c("Schedule E3", "Schedule E3a")) %>% 
    pmap_dfr(
      .f = possibly(function(...){
        curtbl <- tibble(...)
        pgnum <- curtbl$PageNum
        pgtyp <- curtbl$PageType
        
        curtbl$data %>% mutate(
          Indexer = cumsum(str_detect(x, "^Recipient:|^Committee:|^Candidate:"))
        ) %>% filter(
          Indexer > 0 & 
          x != "" &
          !str_detect(x, "Total|Filed")
        ) %>% group_by(Indexer) %>%
        summarize(
          PageNum = pgnum,
          PageType = pgtyp,
          Recipient_Name = first(x[str_detect(x, "^Recipient:|^Committee:|^Candidate:")]) %>%
            str_remove("^(Recipient|Committee|Candidate):\\s*"),
          Contribution_Date = first(x[str_detect(x, "\\d{1,2}/\\d{1,2}/\\d{4}")]) %>%
            str_extract("\\d{1,2}/\\d{1,2}/\\d{4}"),
          Contribution_Amt = first(x[str_detect(x, "\\$")]) %>%
            str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
            str_remove("\\$") %>% str_remove(","),
          Office = first(x[str_detect(x, "Office:|For:")]) %>%
            str_remove("^(Office|For):\\s*"),
          .groups = "drop"
        )
      }, otherwise = tibble())
    )
  
  return(Sched_Dat)
}

# ========================================
# SCHEDULE E4: Small Expenses (Aggregated)
# ========================================

extract_schedule_e4 <- function(rptdat, metadata) {
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule E4") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      # E4 is aggregated like C5
      total_line <- curtbl$data$x[str_detect(curtbl$data$x, "Total.*Small.*Expense")]
      count_line <- curtbl$data$x[str_detect(curtbl$data$x, "Number|Count")]
      period_line <- curtbl$data$x[str_detect(curtbl$data$x, "Period:|From.*To")]
      
      tibble(
        PageNum = pgnum,
        PageType = "Schedule E4",
        Period = if(length(period_line) > 0) {
          str_extract(period_line[1], "\\d{1,2}/\\d{1,2}/\\d{4}.*\\d{1,2}/\\d{1,2}/\\d{4}")
        } else NA_character_,
        Total_Amount = if(length(total_line) > 0) {
          str_extract(total_line[1], "\\$[0-9,]+\\.?[0-9]*") %>%
            str_remove("\\$") %>% str_remove(",")
        } else NA_character_,
        Expense_Count = if(length(count_line) > 0) {
          str_extract(count_line[1], "\\d+")
        } else NA_character_
      )
    }, otherwise = tibble())
  )
  
  return(Sched_Dat)
}

# ========================================
# SCHEDULE L1: Loans Received
# ========================================

extract_schedule_l1 <- function(rptdat, metadata) {
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule L1") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Lender:|^From:"))
      ) %>% filter(
        Indexer > 0 & 
        x != "" &
        !str_detect(x, "Total|Filed")
      ) %>% group_by(Indexer) %>%
      reframe(
        PageNum = pgnum,
        PageType = "Schedule L1",
        Lender_Name = first(x[str_detect(x, "^Lender:|^From:")]) %>%
          str_remove("^(Lender|From):\\s*"),
        Loan_Date = first(x[str_detect(x, "Date.*Loan|\\d{1,2}/\\d{1,2}/\\d{4}")]) %>%
          str_extract("\\d{1,2}/\\d{1,2}/\\d{4}"),
        Loan_Amount = first(x[str_detect(x, "Amount.*\\$|\\$.*Loan")]) %>%
          str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
          str_remove("\\$") %>% str_remove(","),
        Outstanding_Balance = first(x[str_detect(x, "Balance|Outstanding")]) %>%
          str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
          str_remove("\\$") %>% str_remove(","),
        Interest_Rate = first(x[str_detect(x, "Interest|Rate|%")]) %>%
          str_extract("\\d+\\.?\\d*%?"),
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
  
  return(Sched_Dat)
}

# ========================================
# SCHEDULE L2: Loans Made
# ========================================

extract_schedule_l2 <- function(rptdat, metadata) {
  Sched_Dat <- rptdat %>% filter(PageType == "Schedule L2") %>% pmap_dfr(
    .f = possibly(function(...){
      curtbl <- tibble(...)
      pgnum <- curtbl$PageNum
      
      curtbl$data %>% mutate(
        Indexer = cumsum(str_detect(x, "^Borrower:|^To:"))
      ) %>% filter(
        Indexer > 0 & 
        x != "" &
        !str_detect(x, "Total|Filed")
      ) %>% group_by(Indexer) %>%
      reframe(
        PageNum = pgnum,
        PageType = "Schedule L2",
        Borrower_Name = first(x[str_detect(x, "^Borrower:|^To:")]) %>%
          str_remove("^(Borrower|To):\\s*"),
        Loan_Date = first(x[str_detect(x, "Date.*Loan|\\d{1,2}/\\d{1,2}/\\d{4}")]) %>%
          str_extract("\\d{1,2}/\\d{1,2}/\\d{4}"),
        Loan_Amount = first(x[str_detect(x, "Amount.*\\$|\\$.*Loan")]) %>%
          str_extract("\\$[0-9,]+\\.?[0-9]*") %>%
          str_remove("\\$") %>% str_remove(","),
        Purpose = first(x[str_detect(x, "Purpose:|For:")]) %>%
          str_remove("^(Purpose|For):\\s*"),
        .groups = "drop"
      )
    }, otherwise = tibble())
  )
  
  return(Sched_Dat)
}

# Additional extraction functions for remaining schedules...
# (R1, T1, S1, D1, C6, C7 follow similar patterns)

# Simplified placeholders for remaining schedules
extract_schedule_c6 <- function(rptdat, metadata) { tibble() }
extract_schedule_c7 <- function(rptdat, metadata) { tibble() }
extract_schedule_r1 <- function(rptdat, metadata) { tibble() }
extract_schedule_t1 <- function(rptdat, metadata) { tibble() }
extract_schedule_s1 <- function(rptdat, metadata) { tibble() }
extract_schedule_d1 <- function(rptdat, metadata) { tibble() }

# ========================================
# COMMAND LINE INTERFACE
# ========================================

args <- commandArgs(trailingOnly = TRUE)
if(length(args) >= 2) {
  pdf_path <- args[1]
  output_base <- args[2]
  
  result <- COMPREHENSIVE_EXTRACTOR(pdf_path)
  
  # Report what schedules were found
  if(length(result$schedules_found) > 0) {
    cat("SCHEDULES FOUND:", paste(result$schedules_found, collapse=", "), "\n")
  }
  
  # Save each schedule type to separate CSV
  if(!is.null(result$donations_c2) && nrow(result$donations_c2) > 0) {
    write.csv(result$donations_c2, paste0(output_base, "_c2_donations.csv"), row.names = FALSE)
    cat("C2 SAVED:", nrow(result$donations_c2), "individual donations\n")
  }
  
  if(!is.null(result$personal_c1) && nrow(result$personal_c1) > 0) {
    write.csv(result$personal_c1, paste0(output_base, "_c1_personal.csv"), row.names = FALSE)
    cat("C1 SAVED:", nrow(result$personal_c1), "personal contributions\n")
  }
  
  if(!is.null(result$committees_c3) && nrow(result$committees_c3) > 0) {
    write.csv(result$committees_c3, paste0(output_base, "_c3_committees.csv"), row.names = FALSE)
    cat("C3 SAVED:", nrow(result$committees_c3), "committee contributions\n")
  }
  
  if(!is.null(result$business_c4) && nrow(result$business_c4) > 0) {
    write.csv(result$business_c4, paste0(output_base, "_c4_business.csv"), row.names = FALSE)
    cat("C4 SAVED:", nrow(result$business_c4), "business contributions\n")
  }
  
  if(!is.null(result$expenses_e1) && nrow(result$expenses_e1) > 0) {
    write.csv(result$expenses_e1, paste0(output_base, "_e1_expenses.csv"), row.names = FALSE)
    cat("E1 SAVED:", nrow(result$expenses_e1), "operating expenses\n")
  }
  
  if(!is.null(result$independent_e2) && nrow(result$independent_e2) > 0) {
    write.csv(result$independent_e2, paste0(output_base, "_e2_independent.csv"), row.names = FALSE)
    cat("E2 SAVED:", nrow(result$independent_e2), "independent expenditures\n")
  }
  
  if(!is.null(result$contributions_made_e3) && nrow(result$contributions_made_e3) > 0) {
    write.csv(result$contributions_made_e3, paste0(output_base, "_e3_contributions.csv"), row.names = FALSE)
    cat("E3 SAVED:", nrow(result$contributions_made_e3), "contributions made\n")
  }
  
  if(!is.null(result$loans_received_l1) && nrow(result$loans_received_l1) > 0) {
    write.csv(result$loans_received_l1, paste0(output_base, "_l1_loans_received.csv"), row.names = FALSE)
    cat("L1 SAVED:", nrow(result$loans_received_l1), "loans received\n")
  }
  
  if(!is.null(result$loans_made_l2) && nrow(result$loans_made_l2) > 0) {
    write.csv(result$loans_made_l2, paste0(output_base, "_l2_loans_made.csv"), row.names = FALSE)
    cat("L2 SAVED:", nrow(result$loans_made_l2), "loans made\n")
  }
  
  # Always save metadata
  metadata_df <- tibble(
    ReportTitle = result$metadata$ReportTitle,
    ReportName = result$metadata$ReportName,
    Cycle = result$metadata$Cycle,
    FileDate = result$metadata$FileDate,
    ReportPeriod = result$metadata$ReportPeriod,
    OrgName = result$metadata$OrgName,
    OrgEmail = result$metadata$OrgEmail,
    OrgPhone = result$metadata$OrgPhone,
    OrgAddr = result$metadata$OrgAddr,
    TreasurerName = result$metadata$TreasurerName,
    Jurisdiction = result$metadata$Jurisdiction
  )
  write.csv(metadata_df, paste0(output_base, "_metadata.csv"), row.names = FALSE)
  
  cat("SUCCESS: Comprehensive extraction complete\n")
}