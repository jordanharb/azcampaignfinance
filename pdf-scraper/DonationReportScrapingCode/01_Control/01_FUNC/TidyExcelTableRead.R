TEMP_FUNC <- function(.tidyxldf,.sheet,.stcell=c(1,1),.endcell=c(Inf,Inf)) {
  #####
  #We'll want to vectorize future versions over all sheets and start cells
  #and enforce some rules about the length of the start cell list
  #We may even want to change this into a "select a rectangle" function and 
  #just turn each defined rectangle into a table
  #
  #Basic upgrade plan:
  #1) Add .endcell argument with default of c(Inf,Inf)
  #2) Add ".header" argument to identify if there's a header row that needs to be excluded
  #####
  
  #Establish connection and read data
  # Will need to substantially revise once actual file is available,
  # will depend on DDDs response format
  
  TEMP_Dat <- .tidyxldf %>% 
  filter(
    sheet %in% .sheet
  ) %>% 
    ##Adding because there is some weird behavior when reading a Cognos file:
    #lines past a certain point get auto-formatted in such a way that the character
    #format returns "NULL", causing "is_blank" to return TRUE, even though the
    #character field is filled in with relevant data
  mutate(
    es_is_blank = if_all(
      .cols = c("error","logical","numeric","date","character"),
      .fns = ~is.na(.)
    )
  )
  
  returndat <- TEMP_Dat %>% left_join(
    TEMP_Dat %>% filter(
      row == .stcell[1]
    ) %>% transmute(
      sheet,
      col,
      colname = character
    ) %>% distinct()
  ) %>% filter(
    row != .stcell[1] & between(row,.stcell[1],.endcell[1])
    & between(col,.stcell[2],.endcell[2])
    & !es_is_blank #Original is_blank doesn't handle the auto-formatting decisions of Cognos very well
  ) %>% transmute(
    sheet,
    row,
    colname,
    colval = case_when(
      data_type == "character" ~ character,
      data_type == "numeric" ~ as.character(numeric),
      data_type == "date" ~ as.character(date),
      data_type == "logical" ~ as.character(as.numeric(logical)),
      data_type == "error" ~ "ERROR",
      TRUE ~ "BLANK"
    )
  ) %>% pivot_wider(
    names_from = colname,
    values_from = colval
  )
  
  
  #Return Main Data after all adjustments are made
  return(returndat)
}