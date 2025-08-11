TEMP_FUNC <- function(
    infopg,
    tbls=tibble(
      nm="",
      data=list(tibble(index=1))
    ),
    mode="open"
  ) {
  
  wb <- openxlsx::createWorkbook()
  
  openxlsx::addWorksheet(
    wb = wb,
    sheetName = "InfoAbt",
    tabColour = "#000000"
  )
  
  openxlsx::addWorksheet(
    wb = wb,
    sheetName = "DataInsert",
    tabColour = "#000000"
  )
  
  #Write InfoAbt
  openxlsx::writeDataTable(
    wb = wb,
    sheet = "InfoAbt",
    x = infopg,
    tableName = "rpreprocess_infopg"
  )
  
  #Write Various files
  tbls %>% mutate(
    index = row_number(),
    cols = pmap_int(
      .l = tibble(x = data),
      .f = function(...){
        lst <- list(...)
        lst$x %>% length()
      }
    ),
    cols_wspace = if_else(index == 1,cols + 2,cols+1),
    sumcol = cumsum(cols_wspace),
    stcol = if_else(is.na(lag(sumcol)),1,lag(sumcol))
  ) %>% pwalk(
    .f = function(...){
      curtbl <- list(...)
      openxlsx::writeDataTable(
        wb,
        sheet = "DataInsert",
        x = curtbl$data,
        startCol = curtbl$stcol,
        tableName = paste0("rpreprocess_",str_to_lower(curtbl$nm))
      )
    }
  )
  
  
  switch(
    mode,
    open = {
      openxlsx::openXL(wb)
      return(0)
    },
    return = {
      return(wb)
    },
    return(
      message("Invalid User Entry: mode should be 'open' or 'return'")
    )
  )

}