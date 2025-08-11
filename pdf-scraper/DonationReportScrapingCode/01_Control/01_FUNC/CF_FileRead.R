TEMP_FUNC <- function(filename,.rows,.cols,.vers) {
  ######
  #TEMP PARAMS
  ######
  # filename <- "Test01.xlsx"
  # .rows <- 2:8911
  # .cols <- c(1,6:11)
  
  #Establish path to file
  DatPath <- filename
  
  sheetlist <- tidyxl::xlsx_sheet_names(
    path = DatPath
  ) %>% tibble(x=.) %>% filter(
    str_detect(x,"^M_")
  ) %>% .$x
  ##############################################################################
  #Reading Data from File
  ##############################################################################
  readfile <- tidyxl::xlsx_cells(
    path = DatPath,
    sheets = sheetlist
  )
  
  MainDat <- readfile %>% filter(
    row %in% .rows & col %in% .cols
  ) %>% mutate(
    TEMP_ColHDR = case_when(
      col == 4 ~ "CFValid_IND",
      col == 9 ~ "LagDuration",
      col == 11 ~ "MV_LR",
      col == 12 ~ "LR_RunProd",
      col == 13 ~ "CompFact",
      col == 10 ~ "SVC_NDate"
    ),
    TEMP_Val = case_when(
      data_type == "character" ~ character,
      data_type == "numeric" ~ as.character(numeric),
      data_type == "date" ~ as.character(date),
      TRUE ~ "UNKNOWN"
    )
  ) %>% select(
    sheet,row, TEMP_ColHDR, TEMP_Val
  ) %>% pivot_wider(
    names_from = TEMP_ColHDR,
    values_from = TEMP_Val
  ) %>% select(
    -row
  ) %>% mutate(
    LagDuration = as.numeric(LagDuration),
    MV_LR = as.numeric(MV_LR),
    LR_RunProd = as.numeric(LR_RunProd),
    CompFact = as.numeric(CompFact),
    SVC_NDate = ymd(SVC_NDate),
    CFGroup = str_remove_all(sheet,"^M_")
  ) %>% arrange(
    CFGroup,
    desc(LagDuration)
  ) %>% group_by(
    CFGroup
  ) %>% mutate(
    MV_AggLR = cumprod(MV_LR)
  ) %>% ungroup() %>% mutate(
    MV_CompFact = 1/MV_AggLR
  ) %>% transmute(
    CFGroup,
    LagDuration,
    CFValid_IND,
    MV_LR,
    MV_AggLR,
    MV_CompFact,
    SVC_NDate,
    Version = .vers
  )
  
  
  #Return Main Data after all adjustments are made
  return(MainDat)
}


