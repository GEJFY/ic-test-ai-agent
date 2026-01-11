$resourceGroup = "rg-ic-test-evaluation"
$location = "japaneast"
$storageAccount = "stictestevaluation"
$functionApp = "func-ic-test-evaluation"

az storage account create --name $storageAccount --location $location --resource-group $resourceGroup --sku Standard_LRS