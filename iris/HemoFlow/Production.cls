Class HemoFlow.Production Extends Ens.Production
{
XData ProductionDefinition
{
<Production Name="HemoFlow.Production" LogGeneralTraceEvents="true">
<Description>HemoFlow synthetic federated blood coordination</Description>
<ActorPoolSize>4</ActorPoolSize>
<Item Name="InventoryEventService" ClassName="HemoFlow.InventoryEventService" PoolSize="0" Enabled="true"/>
<Item Name="ExpirationService" ClassName="HemoFlow.ExpirationService" PoolSize="1" Enabled="true"><Setting Target="Adapter" Name="CallInterval">15</Setting></Item>
<Item Name="DecisionBPL" ClassName="HemoFlow.DecisionBPL" PoolSize="2" Enabled="true"/>
<Item Name="TransferBPL" ClassName="HemoFlow.TransferBPL" PoolSize="2" Enabled="true"/>
<Item Name="CampaignBPL" ClassName="HemoFlow.CampaignBPL" PoolSize="2" Enabled="true"/>
<Item Name="ApprovalBPL" ClassName="HemoFlow.ApprovalBPL" PoolSize="2" Enabled="true"/>
<Item Name="DomainOperation" ClassName="HemoFlow.DomainOperation" PoolSize="2" Enabled="true"/>
<Item Name="AIHubDecisionOperation" ClassName="HemoFlow.AIHubDecisionOperation" PoolSize="1" Enabled="true"/>
<Item Name="AIReadOperation" ClassName="HemoFlow.AIReadOperation" PoolSize="2" Enabled="true"/>
<Item Name="AnalyticsOperation" ClassName="HemoFlow.AnalyticsOperation" PoolSize="2" Enabled="true"/>
<Item Name="FHIRTransferOperation" ClassName="HemoFlow.FHIRTransferOperation" PoolSize="2" Enabled="true"/>
<Item Name="Approvals" ClassName="EnsLib.Workflow.Operation" PoolSize="1" Enabled="true"><Setting Target="Host" Name="AutoCreateRole">1</Setting></Item>
<Item Name="FederatedInventoryOperation" ClassName="HemoFlow.FederatedInventoryOperation" PoolSize="2" Enabled="true">
<Setting Target="Host" Name="%gatewayName">%Java Server</Setting>
<Setting Target="Host" Name="%gatewayExtraClasspaths">/usr/irissys/dev/java/lib/1.8/intersystems-pex-1.0.0-shaded.jar:/opt/hemoflow/java/pex/target/hemoflow-pex.jar</Setting>
<Setting Target="Host" Name="%remoteClassname">com.hemoflow.pex.FederatedInventoryOperation</Setting>
<Setting Target="Adapter" Name="%remoteClassname">com.hemoflow.pex.FederatedInventoryAdapter</Setting>
<Setting Target="Adapter" Name="%gatewayName">%Java Server</Setting>
<Setting Target="Adapter" Name="%gatewayExtraClasspaths">/usr/irissys/dev/java/lib/1.8/intersystems-pex-1.0.0-shaded.jar:/opt/hemoflow/java/pex/target/hemoflow-pex.jar</Setting>
</Item>
<Item Name="CampaignCreationOperation" ClassName="EnsLib.PEX.BusinessOperation" PoolSize="1" Enabled="true">
<Setting Target="Host" Name="%gatewayName">%Java Server</Setting>
<Setting Target="Host" Name="%gatewayExtraClasspaths">/usr/irissys/dev/java/lib/1.8/intersystems-pex-1.0.0-shaded.jar:/opt/hemoflow/java/pex/target/hemoflow-pex.jar</Setting>
<Setting Target="Host" Name="%remoteClassname">com.hemoflow.pex.CampaignCreationOperation</Setting>
</Item>
</Production>
}
}
