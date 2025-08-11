TEMP_FUNC <- function(FilePath,searchTab,searchRow) {
  #TEMP PARAMS
  # DatPath01 <- file.path(
  #   ProjPath,
  #   "00_FileArchive",
  #   "Global Insight 2015 Q3.xlsx"
  # )
  # 
  # searchTab <- "^tab5$"
  # 
  # searchRow <- "urban"
  # 
  #

  InclSheets <- tidyxl::xlsx_sheet_names(
    path = FilePath
  ) %>% tibble(x=.) %>% filter(
    str_detect(str_to_lower(x),searchTab) #PARAM
  ) %>% .$x
  
  TEMP_Dat <- tidyxl::xlsx_cells(
    FilePath,
    sheets = InclSheets
  )
  
  
  StartDate <- TEMP_Dat %>% filter(
    data_type == "date"
  ) %>% filter(
    col == min(col)
  ) %>% .$date %>% interval(start = ymd_hms(18991230000000),end = .) %>% {
    dateref <- .
    Year <- (dateref %/% hours(1))
    Qtr <- minute(dateref$start+dateref$.Data)
    tbl <- tibble(x=Qtr) %>% mutate(
      NDate = case_when(
        x == 1 ~ ymd(paste0(Year,"01","01")),
        x == 2 ~ ymd(paste0(Year,"04","01")),
        x == 3 ~ ymd(paste0(Year,"07","01")),
        x == 4 ~ ymd(paste0(Year,"10","01"))
      )
    )
    tbl$NDate
  }
  
  InclCols <- TEMP_Dat %>% filter(
    data_type == "date"
  ) %>% distinct(col) %>% mutate(
    QTR_Index = col - min(col),
    NDate = StartDate + months(3*QTR_Index)
  )
  
  InclRows <- TEMP_Dat %>% filter(
    str_detect(str_to_lower(character),searchRow) #PARAM - search for specific rows
  ) %>% distinct(row) %>% .$row
  
  MainDat <- TEMP_Dat %>% inner_join(
    InclCols
  ) %>% filter(
    row %in% InclRows
  ) %>% mutate(
    MV_InflIndex_QTR = numeric*100
  ) %>% transmute(
    Report_Name = basename(FilePath), #PARAM - fill out from basename of file path
    TabName = sheet,
    TabRow = row,
    QTR_Index,
    NDate,
    Year = year(NDate),
    QTR = case_when(
      month(NDate) %in% c(1,2,3) ~ 1,
      month(NDate) %in% c(4,5,6) ~ 2,
      month(NDate) %in% c(7,8,9) ~ 3,
      TRUE ~ 4
    ),
    MV_InflIndex_QTR
  )
  
  #Return Main Data after all adjustments are made
  return(MainDat)
}