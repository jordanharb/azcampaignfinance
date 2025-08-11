library(AzureStor)
library(tidyverse)
library(Microsoft365R)

#Automatic AAD V2 Token creation -- seems to work well, but doesn't provide appropriate resource token for a storage account
#default gives the .az_cli_app_id the Azure Cross-platform CLI app...not sure what this is...
#AzureRMR::create_azure_login()

###Getting a valid token
token <- AzureAuth::get_azure_token(
  resource = "https://storage.azure.com",
  tenant = "AHCCCS",
  app = "04b07795-8ddb-461a-bbee-02f9e1bf7b46" ##This is the .az_cli_app_id
)

#MS365 Token
MS365Token <- AzureAuth::get_azure_token(
  resource = c(
    # "https://graph.microsoft.com/"
    # "https://ahcccs.sharepoint.com/sites/Actuarial"
    # ,
    "https://graph.microsoft.com/Files.ReadWrite.All"
    # ,
    # "https://graph.microsoft.com/User.Read",
    # "openid", "offline_access"
  ),
  tenant = "AHCCCS",
  app = "31359c7f-bd7e-475c-86db-fdb8c937548e", ##token identified on this web-page: https://cran.r-project.org/web/packages/Microsoft365R/vignettes/auth.html
  version = 2
)

#### You will occasionally need to refresh the token by deleting and recreating
AzureAuth::delete_azure_token(
  resource = "https://storage.azure.com",
  tenant = "AHCCCS",
  app = "04b07795-8ddb-461a-bbee-02f9e1bf7b46" ##This is the .az_cli_app_id
)

#OR:
AzureAuth::clean_token_directory()

###Storage Endpoint -- 
fsendpoint <- AzureStor::storage_endpoint(
  endpoint = "https://saprdsmb3.file.core.windows.net",
  token = token
)

###Get Storage Endpoint
endpoint <- AzureStor::storage_endpoint(
  endpoint = "https://adlsprdactuarial01.dfs.core.windows.net",
  token = token
)


###Get Container
fscont <- AzureStor::storage_container(
  endpoint = fsendpoint,
  "actuarial-bigdata"
)

cont <- AzureStor::storage_container(
  endpoint = endpoint,
  "actuarialdata"
)

list_storage_files(
  container = cont,
  "ACC_RBHA"
)

list_storage_files(
  container = fscont,
  "Access Testing"
)

###T-drive/Azure Files functionality not working

###What about OneDrive/Sharepoint?
site <- Microsoft365R::get_sharepoint_site(
  "https://ahcccs.sharepoint.com/sites/Actuarial",app="04b07795-8ddb-461a-bbee-02f9e1bf7b46"
  )
#get_sharepoint_site("My site", app="04b07795-8ddb-461a-bbee-02f9e1bf7b46") #allegedly this is the first-party default access app and can be used to 
#work with sharepoint sites...this may cause issues with ISD if I use it without permissions. Let's bring this up and discuss at the
#OneDrive Sync meeting.

#Still doesn't work. Probably denied entry for default scopes, which brings us back to the obvious solution of needing to get ISD to agree
#to the Microsoft365R app...they might approve it with all of the documentation I can point to, but this will never be the solution
#I want it to be. It also bears mentioning that if ISD's position is going to be that we lose all data protection privileges, the 
#cost would be too high for any of these pathways.

#It may be a better idea to try to spend some time coming up with automated actions I can take from the Windows desktop using my
#user profile permissions...something like a desktop macro...