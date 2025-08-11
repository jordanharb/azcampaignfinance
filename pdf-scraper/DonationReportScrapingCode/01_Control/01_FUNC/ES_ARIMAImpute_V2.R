TEMP_FUNC <- function(
    InputData,
    DataFilter = expr(TRUE),
    Numerator,
    Denominator="DENOM_ONES",###This is one of the new params needed to make this work for "relative information" fields like $/Unit and Units/CRN
    NewFieldName, ###Another new parameter -- included to give flexibility on field naming
    IndexField,
    interval_rmv,
    interval_origin,
    interval_end,
    modelargs = list(),
    kalmanargs = list(),
    betashape=c(1,1),
    RTNMode = 1
) {
  
  
  #####
  #Condensing to just the desired fields: assumption is that the incoming data
  #has had dimension fields removed or is otherwise redundant; given the high volume
  #of data modifications posted to the encounter data for rate-setting, I don't
  #want to interpolate individual modifications, I want to interpolate the aggregated
  #total on relevant dimensions
  #####
  if(Denominator == "DENOM_ONES"){
    tbl <- InputData %>% filter(
      eval(DataFilter)
    ) %>% mutate(
      TEMP_numer = !!sym(Numerator)
    ) %>% select(
      -starts_with("MV_")
    ) %>% group_by(
      across(
        .cols = -starts_with("TEMP_")
      )
    ) %>% summarize(
      across(
        .cols = starts_with("TEMP_"),
        .fns = ~sum(.)
      )
    ) %>% ungroup() %>% mutate(
      TEMP_denom = 1
    )
  } else {
    tbl <- InputData %>% filter(
      eval(DataFilter)
    ) %>% mutate(
      TEMP_numer = !!sym(Numerator),
      TEMP_denom = !!sym(Denominator)
    ) %>% select(
      -starts_with("MV_")
    ) %>% group_by(
      across(
        .cols = -starts_with("TEMP_")
      )
    ) %>% summarize(
      across(
        .cols = starts_with("TEMP_"),
        .fns = ~sum(.)
      )
    ) %>% ungroup()
  }
  
  # tbl <- InputData %>% filter(
  #   eval(DataFilter)
  # ) %>% mutate(
  #   TEMP_numer = !!sym(Numerator),
  #   TEMP_denom = case_when(
  #     Denominator == "DENOM_ONES" ~ 1,
  #     TRUE ~ !!sym(Denominator)
  #   )
  # ) %>% select(
  #   -starts_with("MV_")
  # ) %>% group_by(
  #   across(
  #     .cols = -starts_with("TEMP_")
  #   )
  # ) %>% summarize(
  #   across(
  #     .cols = starts_with("TEMP_"),
  #     .fns = ~sum(.)
  #   )
  # ) %>% ungroup() %>% mutate(
  #   TEMP_denom = case_when(
  #     TEMP_denom == "DENOM_ONES" ~ 1,
  #     TRUE ~ TEMP_denom
  #   )
  # )
  
  ###Set the return fields
  VecFieldData <- tbl %>%
    group_by(
      across(
        .cols = IndexField
      )
    ) %>% nest() %>% ungroup() %>% unnest() %>% select(
      -c(IndexField,starts_with("TEMP_"))
    ) %>% distinct()
  
  ####
  VecFieldAugment <- tbl %>%
    group_by(
      across(
        .cols = IndexField
      )
    ) %>% nest() %>% ungroup()
  ####
  
  #Set up the vectors to interpolate between for proportional allocation
  interpvecs <- list(
    tbl %>%
      group_by(
        across(
          .cols = IndexField
        )
      ) %>% nest() %>% ungroup() %>% unnest() %>% filter(
        !!sym(IndexField) %in% seq.Date(interval_origin[1],interval_origin[2],by="month")
      ) %>% group_by(
        across(
          .cols = names(VecFieldData)
        )
      ) %>% summarize(
        n = sum(TEMP_numer),
        denom = sum(TEMP_denom)
      ) %>% ungroup() %>% mutate(
        denom = case_when(
          Denominator == "DENOM_ONES" ~ 1,
          TRUE ~ denom
        ),
        n=(n/denom)/(sum(n)/sum(denom)) #Relativity vector, instead of proportionality -- works out the same in cases where the denominator is all the same value
      ) %>% .$n
    ,
    tbl %>%
      group_by(
        across(
          .cols = IndexField
        )
      ) %>% nest() %>% ungroup() %>% unnest() %>% filter(
        !!sym(IndexField) %in% seq.Date(interval_end[1],interval_end[2],by="month")
      ) %>% group_by(
        across(
          .cols = names(VecFieldData)
        )
      ) %>% summarize(
        n = sum(TEMP_numer),
        denom = sum(TEMP_denom)
      ) %>% ungroup() %>% mutate(
        denom = case_when(
          Denominator == "DENOM_ONES" ~ 1,
          TRUE ~ denom
        ),
        n=(n/denom)/(sum(n)/sum(denom)) #Relativity vector, instead of proportionality -- works out the same in cases where the denominator is all the same value
      ) %>% .$n
  )
  
  
  #generate condensed table by index and measurements only
  datatbl <- tbl %>% group_by(
    across(
      .cols = IndexField
    )
  ) %>% summarize(
    across(
      .cols = starts_with("TEMP_"),
      .fns = ~sum(.)
    )
  ) %>% ungroup() %>% mutate(
    TEMP_denom = case_when(
      Denominator == "DENOM_ONES" ~ 1,
      TRUE ~ TEMP_denom
    ),
    !!sym(NewFieldName) := TEMP_numer/TEMP_denom
  )
  
  ##############################################################################
  #Handling Basic Time Series Layout
  ##############################################################################
  
  mintime <- datatbl %>% summarize(
    n = min(!!sym(IndexField))
  ) %>% .$n
  
  fcsttgt <- datatbl %>% arrange(
    !!sym(IndexField)
  ) %>% transmute(
    n=if_else(!!sym(IndexField) %in% seq.Date(interval_rmv[1],interval_rmv[2],by="month"),NA_real_,!!sym(NewFieldName)) #consider making this independent of the removal interval
  ) %>% .$n
  
  inputts <- ts(
    fcsttgt,start=c(year(mintime),month(mintime)),frequency=12
  )
  
  
  fit <- do.call(
    what=forecast::auto.arima, #I think we could parameterize this better. The real trouble is that the kalman method only works with ARIMA
    args=list(y=inputts) %>% append(modelargs)
  )
  
  timetbl <- datatbl %>% arrange(
    !!sym(IndexField)
  ) %>% bind_cols(
    tibble(
      !!paste0(NewFieldName,"_INTERP") := do.call(
        what = imputeTS::na_kalman,
        args = list(x=inputts,model=fit$model) %>% append(kalmanargs)
      ) %>% c()
    )
  ) %>% filter(
    !!sym(IndexField) %in% seq.Date(interval_rmv[1],interval_rmv[2],by="month")
  ) %>% mutate(
    index = row_number()
  )
  
  ############################################################################## 
  
  input_time = c(
    timetbl %>% summarize(n=min(index)) %>% .$n-1, #could set a branched path that sets the modifier to 0 if including endpoints
    timetbl %>% summarize(n=max(index)) %>% .$n+1
  )
  
  #initial return candidate
  returndat <- datatbl %>% select(
    -starts_with("TEMP_")
  ) %>% left_join(
    timetbl %>% transmute(
      !!sym(IndexField),
      !!sym(paste0(NewFieldName,"_INTERP")),
      ScalePhaseIn = scales::rescale(index,from=input_time) %>% pbeta(shape1 = betashape[1], shape2 = betashape[2]),
      PropVec = pmap(
        tibble(x=ScalePhaseIn),
        .f = ~ ..1*interpvecs[[1]]+(1-..1)*interpvecs[[2]]
      )
    )
  ) %>% mutate(
    interpIND = if_else(is.na(!!sym(paste0(NewFieldName,"_INTERP"))),"N","Y")
  ) %>% left_join(
    VecFieldAugment
  )
  
  
  ###Return Block
  
  switch(
    RTNMode,
    return(returndat),
    return(
      returndat %>% filter(
        interpIND == "Y"
      ) %>% mutate(
        data = pmap(
          tibble(x=PropVec,y=!!sym(paste0(NewFieldName,"_INTERP")),z=data),
          .f = ~bind_cols(..3,!!sym(NewFieldName):=..2,relvec=..1) %>% mutate(
            normconst = sum(relvec*TEMP_denom/sum(TEMP_denom,na.rm=TRUE),na.rm=TRUE),
            relvec_corr = relvec/normconst,
            !!sym(NewFieldName):= case_when(
              Denominator == "DENOM_ONES" ~ relvec_corr*!!sym(NewFieldName)/sum(TEMP_denom,na.rm=TRUE),
              TRUE ~ relvec_corr*!!sym(NewFieldName)
            )
          )
        )
      ) %>% select(
        -PropVec,
        -ScalePhaseIn,
        -interpIND,
        -!!sym(NewFieldName),
        -!!sym(paste0(NewFieldName,"_INTERP"))
      ) %>% unnest()
    ),
    return(
      returndat %>% select(
        c(
          IndexField,
          NewFieldName,
          paste0(NewFieldName,"_INTERP")
        )
      ) %>% pivot_longer(
        cols = c(NewFieldName,paste0(NewFieldName,"_INTERP")),
        names_to="AmtType",
        values_to="Amt"
      ) %>% filter(
        !is.na(Amt)
      ) %>% mutate(
        interpIND = if_else(str_detect(AmtType,"_INTERP$"),"Y","N"),
        AmtType = str_remove_all(AmtType,"_INTERP$")
      )
    )
    ,
    #mode 4 - return tbl
    return(tbl)
    ,
    #mode 5 - return datatbl
    return(datatbl)
  )
  
  # return(returndat)
  ###
}
###