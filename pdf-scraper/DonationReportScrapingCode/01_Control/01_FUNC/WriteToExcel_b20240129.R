TEMP_FUNC <- function(infopg,tbls = c(),mode="open") {
  
  lst <- tibble(Data = tbls)
  
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
  lst %>% mutate(
    index = row_number(),
    cols = pmap_int(
      .l = tibble(x = Data),
      .f = ~eval(sym(..1)) %>% length()
    ),
    cols_wspace = if_else(index == 1,cols + 2,cols+1),
    sumcol = cumsum(cols_wspace),
    stcol = if_else(is.na(lag(sumcol)),1,lag(sumcol))
  ) %>% pwalk(
    .f = function(...){
      curtbl <- tibble(...)
      openxlsx::writeDataTable(
        wb,
        sheet = "DataInsert",
        x = eval(sym(curtbl$Data)),
        startCol = curtbl$stcol,
        tableName = paste0("rpreprocess_",str_to_lower(curtbl$Data))
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