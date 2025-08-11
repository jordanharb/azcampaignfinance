TEMP_FUNC <- function(xlsxFile,sheet,rows,cols,.skipNARows=TRUE,HeaderRow=FALSE,.skipNACols=TRUE) {
  
  
  selvec <- paste0("X",1:length(cols))
  lencols <- length(cols)
  
  x <- openxlsx::readWorkbook(
    xlsxFile = xlsxFile,
    sheet = sheet,
    rows = rows,
    cols = cols,
    skipEmptyCols = FALSE,
    skipEmptyRows = .skipNARows,
    colNames = FALSE
  )
  
  if(min(cols)>1){
    x <- x %>% select(
      any_of(paste0("X",cols))
    )
  }
  
  names(x) <- paste0("X",1:length(x))
  
  origxlen <- length(x)
  
  if(length(x)==0){
    x <- tibble(X1 = NA_character_,Index=1:length(rows))
  }
  
  if(length(x)<length(cols)){
    addcols <- tibble(
      x = paste0("X",(origxlen+1):length(cols)),
      y=NA_real_
    ) %>% pivot_wider(
      names_from = x,values_from = y
    )
  } else {
    addcols <- tibble(f_RMV = NA_real_)
  }
  
  x <- x %>% bind_cols(
    addcols
  ) %>% select(
    selvec
  ) %>% 
  #####
  #The following section alters field names to directly point out columns with
  #only null values
  #####
  rename_with(
    .cols = where(~all(is.na(.x))),
    .fn = ~paste0(.,"_OPTRMV")
  ) %>%
  #####
  #The point of this is to produce output that comports with
  #expectations if the skipNArows condition is set to false.
  #Under the current readWorkbook function from Openxlsx (10/28/21),
  #the condition doesn't respond and returns a condensed table, effectively
  #skipping NA rows regardless of the condition value.
  #####
  bind_rows(
    if(.skipNARows == FALSE & (nrow(x)<length(rows))) {
      tibble(index = 1:(length(rows)-nrow(x)))
    } else {
      tibble()
    }
  ) %>%
  #####
  #The previous step, if executed, adds an "index" column that isn't needed in the
  #final output. The following step removes the "index" column if it exists
  #####
  select(
    -any_of("index")
  ) %>%
  identity()
  
  #####
  #The step below checks the first row for column names, filters out columns
  #previously identified to be completely null, and replaces generic column
  #names with the result while removing the first row.
  #This reproduces the "Column Names = TRUE" condition in the original function
  #####
  if(HeaderRow == TRUE) {
    newnames <- (select(x,!contains("_OPTRMV")) %>% .[1,] %>% unlist() %>% unname())
    x <- x %>% rename_with(
      .cols = !contains("_OPTRMV"),
      .fn = ~newnames
    )
    x <- x[-1,]
  }
  
  if(.skipNACols == TRUE){
    x <- x %>% select(
      -contains("_OPTRMV")
    )
  }
  
  
  
  return(x)
}
  