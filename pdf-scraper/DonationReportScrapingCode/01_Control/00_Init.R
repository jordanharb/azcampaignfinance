########

### Static Objects - Restore State Function

PROJ_Orig <- c(
  "PROJ_DATA",
  "PROJ_FUNC",
  "LOCAL_FUNC",
  "PROJ_SCPT",
  "ProjPath",
  "CurrMod_Ext",
  "CurrMod_Name",
  "Pathfinder",
  "PROJ_Orig"
)

### Local Project Functions
LOCAL_FUNC <- tribble(
  ~FUNC_NAME,~FUNC,
  # "ZZZ_DeleteMe",function(){
  #   return("This is a placeholder for an actual function")
  # }
) %>% mutate(
  FUNC = set_names(FUNC,FUNC_NAME)
)

PROJ_FUNC <- tribble(
  ~FUNC_NAME,~FUNC,
  "CORE_softReset",function(){
    rm(list=ls(envir=.GlobalEnv)[!ls(envir=.GlobalEnv) %in% PROJ_Orig],envir = .GlobalEnv)
  },
  "CORE_addFunc",function(filepath){
    source(filepath,local = TRUE)
    envVars <- ls()
    funcname <- tibble(
      x=envVars
    ) %>% mutate(
      y=map_chr(
        x,
        .f=~first(class(eval(sym(.))))
      )
    ) %>% filter(
      y=="function"
    ) %>% .$x
    func <- eval(sym(funcname))
    
    if(funcname=="TEMP_FUNC"){
      funcname <- str_replace(basename(filepath),"\\.(r|R)","")
    }
    assign(
      "PROJ_FUNC",
      bind_rows(
        PROJ_FUNC,
        tribble(
          ~FUNC_NAME,~FUNC,
          funcname,func
        )
      ) %>% mutate(
        FUNC = set_names(FUNC,FUNC_NAME)
      )
      ,
      envir=.GlobalEnv
    )
  },
  "CORE_addLocalFunc",function(filepath){
    source(filepath,local = TRUE)
    envVars <- ls()
    funcname <- tibble(
      x=envVars
    ) %>% mutate(
      y=map_chr(
        x,
        .f=~first(class(eval(sym(.))))
      )
    ) %>% filter(
      y=="function"
    ) %>% .$x
    func <- eval(sym(funcname))
    
    if(funcname=="TEMP_FUNC"){
      funcname <- str_replace(basename(filepath),"\\.(r|R)","")
    }
    assign(
      "LOCAL_FUNC",
      bind_rows(
        LOCAL_FUNC,
        tribble(
          ~FUNC_NAME,~FUNC,
          funcname,func
        )
      ) %>% mutate(
        FUNC = set_names(FUNC,FUNC_NAME)
      )
      ,
      envir=.GlobalEnv
    )
  },
  "CORE_listInfo",function(InputPath=file.path(ProjPath,CurrMod_Ext,"01_Control"),filterRegex=".*"){
    return(
      tibble(
        files_fullpath = dir(
          path = InputPath,
          pattern = filterRegex,
          full.names = TRUE
        )
      ) %>% mutate(
        files = basename(files_fullpath),
        isDir = map_lgl(.x=files_fullpath,.f=~file.info(.)$isdir),
        fileExt = if_else(
          isDir==TRUE,
          "folder",
          str_replace(files,".*\\.","")%>%str_to_lower()
        )
      )
    )
  },
  "CORE_hardReset",function(){
    rm(list=ls(envir=.GlobalEnv)[!ls(envir=.GlobalEnv) %in% PROJ_Orig],envir = .GlobalEnv)
    assign(
      "PROJ_FUNC",
      PROJ_FUNC %>% filter(
        #Provide list of core initialization functions to preserve
        FUNC_NAME %in% c(
          "CORE_softReset",
          "CORE_listInfo",
          "CORE_addFunc",
          "CORE_addLocalFunc"
          ,
          "CORE_hardReset"
        )
      ),
      envir=.GlobalEnv
    )
    assign(
      "LOCAL_FUNC",
      LOCAL_FUNC %>% filter(
        #Provide list of core initialization functions to preserve
        1==2
      ),
      envir=.GlobalEnv
    )
  }
) %>% mutate(
  FUNC = set_names(FUNC,FUNC_NAME)
)


########