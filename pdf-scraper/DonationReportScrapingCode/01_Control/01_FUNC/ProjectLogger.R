###Used to log actions that alter the current state of data nodes in the project
TEMP_FUNC <- function (
    inputFiles,
    outputFile
) {
  
  MainLog <- readRDS(
    file = file.path(
      ProjPath,
      CurrMod_Ext,
      "02_Output",
      "00_DCM",
      "_ProjectLog.RDS"
    )
  )
  
  LogData <- tibble(
    ActTime = Sys.time(),
    ActAgent = Sys.info()["user"] %>% as.character(),
    controller = rstudioapi::getSourceEditorContext()$path,
    input = paste0(inputFiles,collapse="|"),
    output = outputFile
  )
  
  saveRDS(
    object = bind_rows(
      MainLog,
      LogData
    ),
    file = file.path(
      ProjPath,
      CurrMod_Ext,
      "02_Output",
      "00_DCM",
      "_ProjectLog.RDS"
    )
  )
  
  return(message("Activity has been logged"))
}


