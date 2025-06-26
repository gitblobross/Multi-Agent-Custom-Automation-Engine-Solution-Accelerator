
@description('Required. The name of Cognitive Services account.')
param name string

@description('Required. Kind of the Cognitive Services account. Use \'Get-AzCognitiveServicesAccountSku\' to determine a valid combinations of \'kind\' and \'SKU\' for your Azure region.')
@allowed([
  'AIServices'
  'AnomalyDetector'
  'CognitiveServices'
  'ComputerVision'
  'ContentModerator'
  'ContentSafety'
  'ConversationalLanguageUnderstanding'
  'CustomVision.Prediction'
  'CustomVision.Training'
  'Face'
  'FormRecognizer'
  'HealthInsights'
  'ImmersiveReader'
  'Internal.AllInOne'
  'LUIS'
  'LUIS.Authoring'
  'LanguageAuthoring'
  'MetricsAdvisor'
  'OpenAI'
  'Personalizer'
  'QnAMaker.v2'
  'SpeechServices'
  'TextAnalytics'
  'TextTranslation'
])
param kind string

@description('Optional. The resource ID of an existing Cognitive Services account to reuse.')
param existingCognitiveServicesAccountResourceId string

@description('Optional. SKU of the Cognitive Services account. Use \'Get-AzCognitiveServicesAccountSku\' to determine a valid combinations of \'kind\' and \'SKU\' for your Azure region.')
@allowed([
  'C2'
  'C3'
  'C4'
  'F0'
  'F1'
  'S'
  'S0'
  'S1'
  'S10'
  'S2'
  'S3'
  'S4'
  'S5'
  'S6'
  'S7'
  'S8'
  'S9'
])
param sku string = 'S0'

@description('Optional. Location for all Resources.')
param location string = resourceGroup().location


@description('Optional. Whether or not public network access is allowed for this resource. For security reasons it should be disabled. If not specified, it will be disabled by default if private endpoints are set and networkAcls are not set.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string?

@description('Conditional. Subdomain name used for token-based authentication. Required if \'networkAcls\' or \'privateEndpoints\' are set.')
param customSubDomainName string?

@description('Optional. A collection of rules governing the accessibility from specific network locations.')
param networkAcls object?

@description('Optional. List of allowed FQDN.')
param allowedFqdnList array?

@description('Optional. The API properties for special APIs.')
param apiProperties object?

@description('Optional. Allow only Azure AD authentication. Should be enabled for security reasons.')
param disableLocalAuth bool = true

import { customerManagedKeyType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The customer managed key definition.')
param customerManagedKey customerManagedKeyType?

@description('Optional. The flag to enable dynamic throttling.')
param dynamicThrottlingEnabled bool = false

@secure()
@description('Optional. Resource migration token.')
param migrationToken string?

@description('Optional. Restore a soft-deleted cognitive service at deployment time. Will fail if no such soft-deleted resource exists.')
param restore bool = false

@description('Optional. Restrict outbound network access.')
param restrictOutboundNetworkAccess bool = true

@description('Optional. The storage accounts for this resource.')
param userOwnedStorage array?

import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The managed identity definition for this resource.')
param managedIdentities managedIdentityAllType?

@description('Optional. Enable/Disable project management feature for AI Foundry.')
param allowProjectManagement bool?

param cMKKeyVault object


var formattedUserAssignedIdentities = reduce(
  map((managedIdentities.?userAssignedResourceIds ?? []), (id) => { '${id}': {} }),
  {},
  (cur, next) => union(cur, next)
) // Converts the flat array to an object like { '${id1}': {}, '${id2}': {} }
var identity = !empty(managedIdentities)
  ? {
      type: (managedIdentities.?systemAssigned ?? false)
        ? (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'SystemAssigned, UserAssigned' : 'SystemAssigned')
        : (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'UserAssigned' : null)
      userAssignedIdentities: !empty(formattedUserAssignedIdentities) ? formattedUserAssignedIdentities : null
    }
  : null


@description('Optional. The prefix to add in the default names given to all deployed Azure resources.')
@maxLength(19)
param solutionPrefix string = 'macae${uniqueString(deployer().objectId, deployer().tenantId, subscription().subscriptionId, resourceGroup().id)}'

param cMKUserAssignedIdentity object

//param cMKKey object

@description('Required. Location for all Resources except AI Foundry.')
param solutionLocation string = resourceGroup().location

// @description('Set this if you want to deploy to a different region than the resource group. Otherwise, it will use the resource group location by default.')
// param AZURE_LOCATION string=''
// param solutionLocation string = empty(AZURE_LOCATION) ? resourceGroup().location

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags object = {
  app: solutionPrefix
  location: solutionLocation
}

var useExisting = !empty(existingCognitiveServicesAccountResourceId)

// Extract values from existing resource ID
var existingSubId = split(existingCognitiveServicesAccountResourceId, '/')[2]
var existingRg = split(existingCognitiveServicesAccountResourceId, '/')[4]
var existingName = last(split(existingCognitiveServicesAccountResourceId, '/'))
var properties = cMKKeyVault.cMKKey.properties

// Reuse existing account
resource existingCognitiveService 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = if (useExisting) {
  name: existingName
  scope: resourceGroup(existingSubId, existingRg)
}

resource cognitiveService 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = if (!useExisting) {
  name: name
  kind: kind
  identity: identity
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    allowProjectManagement: allowProjectManagement // allows project management for Cognitive Services accounts in AI Foundry - FDP updates
    customSubDomainName: customSubDomainName
    networkAcls: !empty(networkAcls ?? {})
      ? {
          defaultAction: networkAcls.?defaultAction
          virtualNetworkRules: networkAcls.?virtualNetworkRules ?? []
          ipRules: networkAcls.?ipRules ?? []
        }
      : null
    publicNetworkAccess: publicNetworkAccess != null
      ? publicNetworkAccess
      : (!empty(networkAcls) ? 'Enabled' : 'Disabled')
    allowedFqdnList: allowedFqdnList
    apiProperties: apiProperties
    disableLocalAuth: disableLocalAuth
    encryption: !empty(customerManagedKey)
      ? {
          keySource: 'Microsoft.KeyVault'
          keyVaultProperties: {
            identityClientId: !empty(customerManagedKey.?userAssignedIdentityResourceId ?? '')
              ? cMKUserAssignedIdentity.properties.clientId
              : null
            keyVaultUri: cMKKeyVault.properties.vaultUri
            keyName: customerManagedKey!.keyName
            keyVersion: !empty(customerManagedKey.?keyVersion ?? '')
              ? customerManagedKey!.?keyVersion
              : last(split(properties.keyUriWithVersion, '/'))
          }
        }
      : null
    migrationToken: migrationToken
    restore: restore
    restrictOutboundNetworkAccess: restrictOutboundNetworkAccess
    userOwnedStorage: userOwnedStorage
    dynamicThrottlingEnabled: dynamicThrottlingEnabled
  }
}

var finalResourceId = useExisting
  ? existingCognitiveServicesAccountResourceId
  : cognitiveService.id

var finalEndpoint = useExisting
  ? reference(existingCognitiveServicesAccountResourceId, '2025-04-01-preview').properties.endpoint
  : cognitiveService.properties.endpoint

output resourceId string = finalResourceId
output endpoint string = finalEndpoint

@description('The name of the cognitive services account.')
output name string = useExisting
  ? existingCognitiveService.name  : cognitiveService.name

@description('The resource group the cognitive services account was deployed into.')
output resourceGroupName string = resourceGroup().name


@description('All endpoints available for the cognitive services account, types depends on the cognitive service kind.')
output endpoints object = useExisting
  ? existingCognitiveService.properties.endpoints  : cognitiveService.properties.endpoints//cognitiveService.properties.endpoints

@description('The principal ID of the system assigned identity.')
output systemAssignedMIPrincipalId string? = useExisting
  ? existingCognitiveService.?identity.?principalId  : cognitiveService.?identity.?principalId//cognitiveService.?identity.?principalId

@description('The location the resource was deployed into.')
output location string = useExisting
  ? existingCognitiveService.location  : cognitiveService.location

output cognitiveService resource 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = useExisting 
? existingCognitiveService : cognitiveService

output subId string = useExisting
  ? existingSubId  :  subscription().subscriptionId


 
